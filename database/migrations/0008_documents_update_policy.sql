-- Phase 4 follow-up fix. `documents` (0002) shipped with select/insert/delete
-- RLS policies only — no update. Phase 4 (0003) then added the
-- extraction_status/extraction_error columns and a code path that updates
-- them (app/repositories/document_pages.py::set_extraction_status, called
-- both synchronously on upload and by the Celery extraction task). Without
-- an update policy, Postgrest's UPDATE silently matches zero rows under RLS
-- — no exception, no error surfaced anywhere — so extraction_status stayed
-- NULL forever no matter what the worker did. Confirmed live: a document
-- row showed no extraction badge at all after upload, meaning the
-- synchronous 'pending' write (which runs before the row is even returned
-- to the caller, independent of whether a worker is running) never took.
--
-- 0002 is already applied to the live project, so this ships as its own
-- migration rather than editing 0002 in place.

create policy "members can update documents"
  on documents for update
  using (is_organization_member(organization_id));
