import logging

from supabase import Client

from app.core.config import settings
from app.repositories import control_mappings as control_mappings_repo
from app.repositories import internal_controls as internal_controls_repo
from app.schemas.control_mappings import ControlMappingResult
from app.services import ai_client
from app.services.embeddings import get_embedding

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are validating candidate matches between a customer's internal "
    "control and items extracted from a SOC report. Each candidate below "
    "has an id — only ever reference ids that appear in this prompt, "
    "never invent one. For every candidate SOC control that is genuinely "
    "related to the internal control (implements, tests, or otherwise "
    "relates to the same requirement), return it with a confidence score "
    "and a one-sentence relevance_summary explaining why. Omit SOC "
    "controls that are not actually related — do not include a "
    "not-relevant entry for them. For each SOC control you confirm, also "
    "list the ids of any candidate CUECs or exceptions that relate to "
    "that same control, if any."
)

# Embedding backfill is the same shape across all four embedded tables —
# (table name, text column embedded, id column on internal_controls that
# points at it isn't needed here since each is keyed by its own id).
_EMBEDDED_TABLES = (
    ("internal_controls", "description"),
    ("soc_controls", "description"),
    ("cuecs", "description"),
    ("exceptions", "description"),
)


def _backfill_embeddings(client: Client, *, audit_period_id: str) -> None:
    """Idempotent: only rows with embedding IS NULL are touched, so
    re-running mapping for a period that's partially embedded doesn't
    re-embed (and re-bill) rows that already have one.
    """
    for table, text_column in _EMBEDDED_TABLES:
        rows = control_mappings_repo.list_rows_missing_embedding(
            client, table=table, audit_period_id=audit_period_id, text_column=text_column
        )
        for row in rows:
            text = str(row[text_column]).strip()
            if not text:
                continue
            embedding = get_embedding(text)
            control_mappings_repo.set_embedding(
                client, table=table, row_id=row["id"], embedding=embedding
            )


def _format_candidates(candidates: list[dict[str, object]], *, label: str) -> str:
    if not candidates:
        return f"No candidate {label} found."
    lines = [f"Candidate {label}:"]
    for candidate in candidates:
        description = candidate.get("description") or candidate.get("control_code") or ""
        excerpt = candidate.get("excerpt", "")
        lines.append(f"- id={candidate['id']}: {description}\n  excerpt: {excerpt}")
    return "\n".join(lines)


def _build_messages(
    *,
    description: str,
    soc_candidates: list[dict[str, object]],
    cuec_candidates: list[dict[str, object]],
    exception_candidates: list[dict[str, object]],
) -> list[dict[str, str]]:
    user_content = "\n\n".join(
        [
            f"Internal control:\n{description}",
            _format_candidates(soc_candidates, label="SOC controls"),
            _format_candidates(cuec_candidates, label="CUECs"),
            _format_candidates(exception_candidates, label="exceptions"),
        ]
    )
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def _persist_confirmed(
    client: Client,
    *,
    organization_id: str,
    audit_period_id: str,
    internal_control_id: str,
    soc_candidates: list[dict[str, object]],
    cuec_candidates: list[dict[str, object]],
    exception_candidates: list[dict[str, object]],
    result: ControlMappingResult,
) -> None:
    soc_by_id = {str(c["id"]): c for c in soc_candidates}
    cuec_ids = {str(c["id"]) for c in cuec_candidates}
    exception_ids = {str(c["id"]) for c in exception_candidates}

    for mapping in result.mappings:
        candidate = soc_by_id.get(mapping.soc_control_id)
        if candidate is None:
            # The model referenced an id outside the candidate pool it was
            # given — dropped, never persisted (never trust an AI-invented id).
            continue
        mapping_id = control_mappings_repo.insert_control_mapping(
            client,
            organization_id=organization_id,
            audit_period_id=audit_period_id,
            internal_control_id=internal_control_id,
            soc_control_id=str(candidate["id"]),
            similarity_score=float(candidate["similarity"]),  # type: ignore[arg-type]
            confidence=mapping.confidence,
            relevance_summary=mapping.relevance_summary,
            requires_review=False,
        )
        control_mappings_repo.insert_mapping_cuecs(
            client,
            organization_id=organization_id,
            control_mapping_id=mapping_id,
            cuec_ids=[cid for cid in mapping.relevant_cuec_ids if cid in cuec_ids],
        )
        control_mappings_repo.insert_mapping_exceptions(
            client,
            organization_id=organization_id,
            control_mapping_id=mapping_id,
            exception_ids=[eid for eid in mapping.relevant_exception_ids if eid in exception_ids],
        )


def _persist_requires_review(
    client: Client,
    *,
    organization_id: str,
    audit_period_id: str,
    internal_control_id: str,
    soc_candidates: list[dict[str, object]],
) -> None:
    """The LLM confirmation call failed entirely (malformed/refused after
    retries) — the only signal left is raw vector similarity, which is not
    enough to call a candidate confirmed. Persisted as requires_review
    rather than silently dropped, so Phase 8 can distinguish this from
    NOT_COVERED (zero candidates found at all).
    """
    for candidate in soc_candidates:
        similarity = float(candidate["similarity"])  # type: ignore[arg-type]
        control_mappings_repo.insert_control_mapping(
            client,
            organization_id=organization_id,
            audit_period_id=audit_period_id,
            internal_control_id=internal_control_id,
            soc_control_id=str(candidate["id"]),
            similarity_score=similarity,
            confidence=max(0.0, min(similarity, 1.0)),
            relevance_summary=(
                "AI relevance confirmation failed after retries; candidate "
                "identified by embedding similarity search only."
            ),
            requires_review=True,
        )


def run_mapping_for_audit_period(
    client: Client, *, organization_id: str, audit_period_id: str
) -> None:
    """Backfills missing embeddings, then for each internal control in the
    period: vector-searches candidate soc_controls/cuecs/exceptions, has
    one LLM call confirm which are genuinely relevant, and persists only
    confirmed (or, on total LLM failure, requires_review) mappings.
    mapping_attempted_at is set regardless of outcome — including "found
    nothing" — so Phase 8 can tell "mapped, no matches" apart from "never
    mapped".
    """
    _backfill_embeddings(client, audit_period_id=audit_period_id)

    controls = internal_controls_repo.list_internal_controls(
        client, audit_period_id=audit_period_id
    )
    for control in controls:
        embedding = control.get("embedding")
        if embedding is None:
            # Empty description — nothing was embedded during backfill.
            continue

        # Clear this control's existing mappings before recomputing, so a
        # second "Map controls" click replaces last run's result instead of
        # hitting control_mappings' unique constraint on re-insert.
        control_mappings_repo.delete_control_mappings_for_internal_control(
            client, internal_control_id=control["id"]
        )

        raw_soc_matches = control_mappings_repo.match_soc_controls(
            client,
            embedding=embedding,
            audit_period_id=audit_period_id,
            match_count=settings.mapping_top_k,
        )
        # Targeted evidence-gathering log: the raw similarity scores this
        # threshold is filtering, not just the post-filter outcome — needed
        # to tell "genuinely no related SOC control" apart from "threshold
        # cut off a real match" without guessing.
        logger.info(
            "control mapping: internal_control_id=%s threshold=%.2f candidates=%s",
            control["id"],
            settings.mapping_similarity_threshold,
            [(c["id"], round(float(c["similarity"]), 4)) for c in raw_soc_matches],
        )
        soc_candidates = [
            c for c in raw_soc_matches if c["similarity"] >= settings.mapping_similarity_threshold
        ]
        if not soc_candidates:
            control_mappings_repo.mark_mapping_attempted(client, internal_control_id=control["id"])
            continue

        cuec_candidates = [
            c
            for c in control_mappings_repo.match_cuecs(
                client,
                embedding=embedding,
                audit_period_id=audit_period_id,
                match_count=settings.mapping_top_k,
            )
            if c["similarity"] >= settings.mapping_similarity_threshold
        ]
        exception_candidates = [
            c
            for c in control_mappings_repo.match_exceptions(
                client,
                embedding=embedding,
                audit_period_id=audit_period_id,
                match_count=settings.mapping_top_k,
            )
            if c["similarity"] >= settings.mapping_similarity_threshold
        ]

        result = ai_client.call_structured(
            settings.openai_extraction_model,
            ControlMappingResult,
            _build_messages(
                description=control["description"],
                soc_candidates=soc_candidates,
                cuec_candidates=cuec_candidates,
                exception_candidates=exception_candidates,
            ),
        )
        if result is None:
            _persist_requires_review(
                client,
                organization_id=organization_id,
                audit_period_id=audit_period_id,
                internal_control_id=control["id"],
                soc_candidates=soc_candidates,
            )
        else:
            _persist_confirmed(
                client,
                organization_id=organization_id,
                audit_period_id=audit_period_id,
                internal_control_id=control["id"],
                soc_candidates=soc_candidates,
                cuec_candidates=cuec_candidates,
                exception_candidates=exception_candidates,
                result=result,
            )

        control_mappings_repo.mark_mapping_attempted(client, internal_control_id=control["id"])
