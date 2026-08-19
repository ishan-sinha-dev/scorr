from unittest.mock import ANY, MagicMock, patch

from app.core.config import settings
from app.schemas.control_mappings import ControlMappingCandidate, ControlMappingResult
from app.services.control_mapping import run_mapping_for_audit_period

_ORG_ID = "22222222-2222-2222-2222-222222222222"
_PERIOD_ID = "33333333-3333-3333-3333-333333333333"
_IC_ID = "ic-1"


def _run() -> None:
    run_mapping_for_audit_period(
        MagicMock(), organization_id=_ORG_ID, audit_period_id=_PERIOD_ID
    )


def test_backfill_only_embeds_rows_missing_an_embedding() -> None:
    with (
        patch("app.services.control_mapping.control_mappings_repo") as fake_repo,
        patch("app.services.control_mapping.internal_controls_repo") as fake_ic_repo,
        patch("app.services.control_mapping.get_embedding") as fake_get_embedding,
        patch("app.services.control_mapping.ai_client"),
    ):

        def missing_for_table(
            _client: object, *, table: str, **_kwargs: object
        ) -> list[dict[str, object]]:
            if table == "soc_controls":
                return [{"id": "sc-1", "description": "Encrypts data at rest"}]
            return []

        fake_repo.list_rows_missing_embedding.side_effect = missing_for_table
        fake_get_embedding.return_value = [0.5, 0.5]
        fake_ic_repo.list_internal_controls.return_value = []

        _run()

        fake_get_embedding.assert_called_once_with("Encrypts data at rest")
        fake_repo.set_embedding.assert_called_once_with(
            ANY, table="soc_controls", row_id="sc-1", embedding=[0.5, 0.5]
        )


def test_backfill_skips_rows_with_blank_description() -> None:
    with (
        patch("app.services.control_mapping.control_mappings_repo") as fake_repo,
        patch("app.services.control_mapping.internal_controls_repo") as fake_ic_repo,
        patch("app.services.control_mapping.get_embedding") as fake_get_embedding,
        patch("app.services.control_mapping.ai_client"),
    ):

        def missing_for_table(
            _client: object, *, table: str, **_kwargs: object
        ) -> list[dict[str, object]]:
            if table == "internal_controls":
                return [{"id": "ic-blank", "description": "   "}]
            return []

        fake_repo.list_rows_missing_embedding.side_effect = missing_for_table
        fake_ic_repo.list_internal_controls.return_value = []

        _run()

        fake_get_embedding.assert_not_called()
        fake_repo.set_embedding.assert_not_called()


def test_no_soc_candidates_marks_attempted_without_calling_ai() -> None:
    with (
        patch("app.services.control_mapping.control_mappings_repo") as fake_repo,
        patch("app.services.control_mapping.internal_controls_repo") as fake_ic_repo,
        patch("app.services.control_mapping.ai_client") as fake_ai_client,
    ):
        fake_repo.list_rows_missing_embedding.return_value = []
        fake_ic_repo.list_internal_controls.return_value = [
            {"id": _IC_ID, "description": "Reviews access quarterly", "embedding": [0.1, 0.2]}
        ]
        fake_repo.match_soc_controls.return_value = []

        _run()

        fake_ai_client.call_structured.assert_not_called()
        fake_repo.insert_control_mapping.assert_not_called()
        fake_repo.mark_mapping_attempted.assert_called_once_with(
            ANY, internal_control_id=_IC_ID
        )


def test_candidates_below_similarity_threshold_are_filtered_out() -> None:
    with (
        patch("app.services.control_mapping.control_mappings_repo") as fake_repo,
        patch("app.services.control_mapping.internal_controls_repo") as fake_ic_repo,
        patch("app.services.control_mapping.ai_client") as fake_ai_client,
    ):
        fake_repo.list_rows_missing_embedding.return_value = []
        fake_ic_repo.list_internal_controls.return_value = [
            {"id": _IC_ID, "description": "Reviews access quarterly", "embedding": [0.1, 0.2]}
        ]
        fake_repo.match_soc_controls.return_value = [
            {
                "id": "sc-high",
                "description": "Access review control",
                "excerpt": "...",
                "similarity": 0.9,
            },
            {
                "id": "sc-low",
                "description": "Unrelated control",
                "excerpt": "...",
                "similarity": 0.1,
            },
        ]
        fake_repo.match_cuecs.return_value = []
        fake_repo.match_exceptions.return_value = []
        fake_ai_client.call_structured.return_value = ControlMappingResult(mappings=[])

        _run()

        assert settings.mapping_similarity_threshold > 0.1
        messages = fake_ai_client.call_structured.call_args[0][2]
        user_message = messages[1]["content"]
        assert "sc-high" in user_message
        assert "sc-low" not in user_message


def test_llm_failure_persists_requires_review_rows() -> None:
    with (
        patch("app.services.control_mapping.control_mappings_repo") as fake_repo,
        patch("app.services.control_mapping.internal_controls_repo") as fake_ic_repo,
        patch("app.services.control_mapping.ai_client") as fake_ai_client,
    ):
        fake_repo.list_rows_missing_embedding.return_value = []
        fake_ic_repo.list_internal_controls.return_value = [
            {"id": _IC_ID, "description": "Reviews access quarterly", "embedding": [0.1, 0.2]}
        ]
        fake_repo.match_soc_controls.return_value = [
            {
                "id": "sc-high",
                "description": "Access review control",
                "excerpt": "...",
                "similarity": 0.9,
            }
        ]
        fake_repo.match_cuecs.return_value = []
        fake_repo.match_exceptions.return_value = []
        fake_ai_client.call_structured.return_value = None  # malformed/refused

        _run()

        fake_repo.insert_control_mapping.assert_called_once()
        kwargs = fake_repo.insert_control_mapping.call_args.kwargs
        assert kwargs["soc_control_id"] == "sc-high"
        assert kwargs["requires_review"] is True
        fake_repo.mark_mapping_attempted.assert_called_once()


def test_rerun_clears_existing_mappings_before_recomputing() -> None:
    # A second "Map controls" click must not hit control_mappings' unique
    # (internal_control_id, soc_control_id) constraint on re-insert — this
    # is what makes re-running idempotent instead of aborting the task.
    with (
        patch("app.services.control_mapping.control_mappings_repo") as fake_repo,
        patch("app.services.control_mapping.internal_controls_repo") as fake_ic_repo,
        patch("app.services.control_mapping.ai_client") as fake_ai_client,
    ):
        fake_repo.list_rows_missing_embedding.return_value = []
        fake_ic_repo.list_internal_controls.return_value = [
            {"id": _IC_ID, "description": "Reviews access quarterly", "embedding": [0.1, 0.2]}
        ]
        fake_repo.match_soc_controls.return_value = []
        fake_ai_client.call_structured.return_value = ControlMappingResult(mappings=[])

        _run()

        fake_repo.delete_control_mappings_for_internal_control.assert_called_once_with(
            ANY, internal_control_id=_IC_ID
        )


def test_llm_confirmation_persists_mapping_and_drops_hallucinated_ids() -> None:
    with (
        patch("app.services.control_mapping.control_mappings_repo") as fake_repo,
        patch("app.services.control_mapping.internal_controls_repo") as fake_ic_repo,
        patch("app.services.control_mapping.ai_client") as fake_ai_client,
    ):
        fake_repo.list_rows_missing_embedding.return_value = []
        fake_ic_repo.list_internal_controls.return_value = [
            {"id": _IC_ID, "description": "Reviews access quarterly", "embedding": [0.1, 0.2]}
        ]
        fake_repo.match_soc_controls.return_value = [
            {
                "id": "sc-high",
                "description": "Access review control",
                "excerpt": "...",
                "similarity": 0.9,
            }
        ]
        fake_repo.match_cuecs.return_value = [
            {
                "id": "cuec-1",
                "description": "Reviewer signs off",
                "excerpt": "...",
                "similarity": 0.8,
            }
        ]
        fake_repo.match_exceptions.return_value = []
        fake_repo.insert_control_mapping.return_value = "mapping-1"
        fake_ai_client.call_structured.return_value = ControlMappingResult(
            mappings=[
                ControlMappingCandidate(
                    soc_control_id="sc-high",
                    confidence=0.95,
                    relevance_summary="Directly implements the same access review requirement.",
                    relevant_cuec_ids=["cuec-1", "cuec-nonexistent"],
                ),
                ControlMappingCandidate(
                    soc_control_id="sc-hallucinated",
                    confidence=0.5,
                    relevance_summary="Invented id outside the candidate pool.",
                ),
            ]
        )

        _run()

        fake_repo.insert_control_mapping.assert_called_once()
        kwargs = fake_repo.insert_control_mapping.call_args.kwargs
        assert kwargs["soc_control_id"] == "sc-high"
        assert kwargs["requires_review"] is False
        fake_repo.insert_mapping_cuecs.assert_called_once_with(
            ANY, organization_id=_ORG_ID, control_mapping_id="mapping-1", cuec_ids=["cuec-1"]
        )
        fake_repo.mark_mapping_attempted.assert_called_once()
