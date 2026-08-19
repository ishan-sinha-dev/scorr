"use client";

// The only Client Component in the app so far — needed for a confirm()
// prompt before a cascading delete (removes every document, control,
// mapping, and finding under the audit period). Every other action here
// is a plain Server Action form; this one wraps the same pattern with a
// client-side guard on submit.
export function DeleteAuditPeriodButton({ periodName }: { periodName: string }) {
  return (
    <button
      type="submit"
      onClick={(event) => {
        const confirmed = confirm(
          `Delete "${periodName}"? This also deletes every document, internal control, mapping, and finding under it. This cannot be undone.`,
        );
        if (!confirmed) {
          event.preventDefault();
        }
      }}
      className="text-sm text-destructive hover:underline"
    >
      Delete
    </button>
  );
}
