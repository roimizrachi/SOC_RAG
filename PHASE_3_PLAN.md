# PHASE_3_PLAN

## Goal

Build a deterministic Streamlit upload intake UI for QRadar offense JSON files.

Phase 3 should let an analyst upload an offense JSON file through Streamlit and run the existing deterministic offense intake pipeline outside Codex.

## Why This Is Phase 3

Phase 1 established deterministic exact-field search over Event Metadata Records.
Phase 2 added deterministic routed metadata search with BM25 and fuzzy fallback.
Phase 2.1 added dynamic metadata-file discovery and additional offense intake support.

The next operational gap was making offense intake available through the analyst UI without manually copying files or running extractor commands.

## Scope

- Deterministic Streamlit upload flow only.
- Upload raw offense JSON through `st.file_uploader`.
- Save valid uploaded offense JSON under `data/offense_<offense_id>*.json`.
- Extract metadata by wrapping the existing `scripts/extract_event_metadata.py` logic.
- Write `data/event_metadata_records_<offense_id>.json`.
- Refresh metadata discovery after intake.
- Run deterministic intake validation checks.
- Run deterministic exact-field and metadata-text smoke searches.
- Display a clear intake report in the UI.
- Protect existing raw files and metadata outputs from overwrite unless an explicit checkbox is enabled.

## Out Of Scope

Do not implement:

- RAG
- Embeddings
- Vector search
- Semantic search
- Qdrant
- OpenAI API calls
- LLM calls
- New search semantics
- New extractor mapping behavior unless required by uploaded offense compatibility
- Manual file-copy workflow as the primary intake path

## Files To Create Or Change

Create:

- `app/offense_intake.py`
  - Parses and validates uploaded offense JSON.
  - Infers offense ID from `offense_<offense_id>*.json`.
  - Applies overwrite protection.
  - Calls the existing deterministic extractor.
  - Writes raw and metadata files.
  - Runs intake validation and smoke checks.
  - Returns a structured report for Streamlit display.

Change:

- `app/app.py`
  - Render an Offense Intake panel before metadata discovery can stop the page.
  - Add upload, overwrite checkbox, and `Run intake` button.
  - Display intake report metrics, paths, validation checks, and smoke-search results.

- `README.md`
  - Document Phase 3 status, architecture, constraints, and next planned phase.

- `AGENTS.md`
  - Align repository instructions with current deterministic metadata-file discovery and upload-intake behavior.

Create or update:

- `PHASE_3_PLAN.md`
- `PHASE_3_COMPLETED.md`

## Intake Flow

```text
Uploaded offense_<offense_id>*.json
  -> Streamlit Offense Intake panel
      -> validate filename, offense ID, JSON, events list
      -> check overwrite protection
      -> save raw offense JSON under data/
      -> existing deterministic extractor
      -> data/event_metadata_records_<offense_id>.json
      -> load generated metadata records
      -> validate identity, event count, indexes, event IDs, mapped-field density
      -> refresh discovery
      -> exact-field smoke search
      -> metadata-text smoke search
      -> intake report
```

## Validation Checklist

- Verify invalid JSON reports a UI error.
- Verify missing offense ID reports a UI error.
- Verify missing or non-list `events` reports a UI error.
- Verify missing `utf8_payload.id` reports a warning.
- Verify sparse mapped fields report a warning.
- Verify existing raw files and metadata outputs are not overwritten by default.
- Verify overwrite requires the explicit checkbox.
- Verify successful upload saves the raw file under `data/`.
- Verify successful upload writes `data/event_metadata_records_<offense_id>.json`.
- Verify generated metadata is non-empty and has matching offense identity.
- Verify discovery includes the uploaded offense ID.
- Verify exact-field and metadata-text smoke checks run from the UI flow.
- Verify existing deterministic search validation still passes.
- Verify no forbidden technologies or dependencies are added.

## Clear Constraints

- Deterministic only.
- No RAG.
- No embeddings.
- No semantic search.
- No vector search.
- No Qdrant.
- No OpenAI API.
- No LLM calls.
- Do not change search semantics.
- Do not create `CURRENT_PHASE.md`.
