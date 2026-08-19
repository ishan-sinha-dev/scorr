"use client";

import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";

type AnalysisStatus = {
  status: "not_started" | "processing" | "complete" | "requires_review" | "failed";
  processed_chunks: number;
};
type MappingStatus = {
  status: "not_started" | "processing" | "complete";
  mapped: number;
  total: number;
};

const ANALYSIS_TERMINAL = new Set(["complete", "requires_review", "failed"]);
// ponytail: bounded polling so a stuck backend task can't spin this button
// forever — the page's own badges/tables are still correct on a manual
// refresh either way. 90 * 2s = 3 minutes.
const MAX_POLLS = 90;
const POLL_INTERVAL_MS = 2000;

/**
 * Button for a form action that enqueues a Celery task, polling a status
 * endpoint until the task itself (not just the enqueue request) finishes.
 * "kind" picks how to read the polled JSON — kept as a switch rather than
 * a passed-in parser function, since a plain callback can't cross the
 * Server Component -> Client Component boundary this is rendered across.
 */
export function PollingActionButton({
  kind,
  action,
  statusUrl,
  pendingLabel,
  className,
  children,
}: {
  kind: "analyze" | "map-controls";
  action: () => Promise<void>;
  statusUrl: string;
  pendingLabel: string;
  className?: string;
  children: ReactNode;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [label, setLabel] = useState(pendingLabel);
  const pollCount = useRef(0);

  useEffect(() => {
    if (!busy) return;
    pollCount.current = 0;
    const id = setInterval(async () => {
      pollCount.current += 1;
      if (pollCount.current > MAX_POLLS) {
        setBusy(false);
        return;
      }
      const response = await fetch(statusUrl, { cache: "no-store" });
      if (!response.ok) return;
      const data = await response.json();

      let done: boolean;
      if (kind === "analyze") {
        const s = data as AnalysisStatus;
        const chunkWord = s.processed_chunks === 1 ? "chunk" : "chunks";
        setLabel(`${pendingLabel} (${s.processed_chunks} ${chunkWord})`);
        done = ANALYSIS_TERMINAL.has(s.status);
      } else {
        // Re-running mapping on an already-fully-mapped period will read
        // as "complete" from the first poll (mapping_attempted_at is
        // already set from the prior run) until this run's own updates
        // land — a known, accepted gap for the re-run case, not the
        // common first-time-mapping case this is built for.
        const s = data as MappingStatus;
        setLabel(s.total > 0 ? `${pendingLabel} ${s.mapped}/${s.total}` : pendingLabel);
        done = s.status === "complete";
      }

      if (done) {
        setBusy(false);
        router.refresh();
      }
    }, POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [busy, kind, pendingLabel, statusUrl, router]);

  return (
    <button
      type="button"
      disabled={busy}
      className={className}
      onClick={async () => {
        setLabel(pendingLabel);
        setBusy(true);
        await action();
      }}
    >
      {busy ? (
        <span className="inline-flex items-center gap-1.5">
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          {label}
        </span>
      ) : (
        children
      )}
    </button>
  );
}
