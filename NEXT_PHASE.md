# NEXT_PHASE

Phase 3 upload intake UI is complete.

The recommended next phase is deterministic Offense Profile generation.

Do not implement the next phase until explicitly approved.

## Recommended Next Goal

Generate a deterministic Offense Profile from discovered Event Metadata Records.

## Suggested Phase 3 Flow

```text
data/event_metadata_records_<offense_id>.json
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

- Selected offense first; all-discovered-offense profile support only if explicitly approved.
- Deterministic only.
- Event Metadata Records only.
- No new offense datasets unless explicitly approved.
- No dataset regeneration unless explicitly approved.
- Generate structured offense-level summaries from existing event fields.

## Recommended Deliverables

Potential Phase 3 deliverables:

- `app/offense_profile.py`
  - Build a deterministic offense profile from discovered Event Metadata Records.
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
- New search semantics
- New offense datasets

## References

Phase 2 completion is documented in `PHASE_2_COMPLETED.md`.
Phase 3 completion is documented in `PHASE_3_COMPLETED.md`.
