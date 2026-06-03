# NEXT_PHASE

Phase 2 is complete.

The recommended next phase is Phase 3: Deterministic Offense Profile generation.

Do not implement Phase 3 until explicitly approved.

## Recommended Phase 3 Goal

Generate a deterministic Offense Profile from the existing single-offense Event Metadata Records.

## Suggested Phase 3 Flow

```text
data/event_metadata_records_82303.json
  -> Deterministic Offense Profile
      -> Hosts
      -> Users
      -> IPs
      -> Detections
      -> Processes
      -> Registry keys
      -> Event counts
      -> Notable artifacts
```

## Recommended Scope

- Single offense only.
- Deterministic only.
- Event Metadata Records only.
- No new offense datasets.
- No dataset regeneration unless explicitly approved.
- Generate structured offense-level summaries from existing event fields.

## Recommended Deliverables

Potential Phase 3 deliverables:

- `app/offense_profile.py`
  - Build a deterministic offense profile from `data/event_metadata_records_82303.json`.
  - Aggregate hosts, users, IPs, detections, processes, registry keys, counts, and artifacts.

- `scripts/validate_offense_profile.py`
  - Validate deterministic output shape and expected counts.

- `app/app.py`
  - Optionally add an Offense Profile view after approval.

- `README.md`
  - Document the Phase 3 profile architecture and validation commands.

## Continue To Avoid Unless Explicitly Approved

- RAG
- Embeddings
- Vector search
- Semantic search
- LLM calls
- OpenAI API calls
- Qdrant
- Multi-offense search
- New offense datasets

## Phase 2 Reference

Phase 2 completion is documented in `PHASE_2_COMPLETED.md`.

