# SOC_RAG

## Current Phase

Event Metadata Search MVP.

Current scope is deterministic, single-offense, event-level search over Event Metadata Records only.

Do not implement in this phase:

- RAG
- Embeddings
- Vector search
- Semantic search
- LLM calls
- Multi-offense search

## Repository Layout

```text
SOC_RAG/
  AGENTS.md
  NEXT_PHASE.md
  README.md
  app/
  archive/
  data/
  docs/
  mappings/
  scripts/
```

## Active Architecture

```text
data/offense_82303_events_964_fixed.json
  -> scripts/extract_event_metadata.py
  -> data/event_metadata_records_82303.json
  -> mappings/event_field_aliases_v1.json
  -> scripts/resolve_query_field.py
  -> app/answer_event_question.py
  -> app/app.py
```

## Active Files

- `data/offense_82303_events_964_fixed.json`: canonical raw offense event dataset for offense 82303.
- `data/event_metadata_records_82303.json`: generated Event Metadata Records for offense 82303.
- `mappings/event_field_aliases_v1.json`: natural-language aliases for metadata fields.
- `mappings/event_metadata_mapping_v2_reviewed_fixed.json`: reviewed extraction mapping.
- `mappings/event_metadata_fields_v1.json`: metadata field descriptions.
- `scripts/extract_event_metadata.py`: deterministic extractor from raw offense events to Event Metadata Records.
- `scripts/resolve_query_field.py`: deterministic natural-language field resolver.
- `app/answer_event_question.py`: deterministic answer layer over Event Metadata Records.
- `app/app.py`: Streamlit analyst interface.

## Usage

Resolve a field from an analyst question:

```bash
python scripts/resolve_query_field.py --question "What is the source ip?"
```

Resolve a field with an explicit aliases path:

```bash
python scripts/resolve_query_field.py --aliases mappings/event_field_aliases_v1.json --question "What registry key was modified?"
```

Regenerate Event Metadata Records:

```bash
python scripts/extract_event_metadata.py --events data/offense_82303_events_964_fixed.json --mapping mappings/event_metadata_mapping_v2_reviewed_fixed.json --offense-id 82303 --output data/event_metadata_records_82303.json
```

Answer an event metadata question:

```bash
python app/answer_event_question.py --question "What is the source ip?"
```

Run the analyst interface:

```bash
streamlit run app/app.py
```

## Migration Summary

The repository was reorganized into maintainable folders without deleting files.

- `AGENTS.md` and `NEXT_PHASE.md` remain at the repository root.
- Active datasets moved to `data/`.
- Active mappings moved to `mappings/`.
- Existing utility scripts moved to `scripts/`.
- Current project documentation moved to `docs/`.
- `app/` contains the current deterministic analyst search application.
- Historical, future-phase, legacy, and duplicate materials moved to `archive/`.
- The duplicate raw offense JSON was archived, not deleted. It matched the canonical active raw offense JSON by SHA-256 hash before migration.
- `scripts/resolve_query_field.py` now resolves its default aliases file from the repository layout, so it can run from the repository root after reorganization.
- `app/answer_event_question.py` and `app/app.py` implement the current phase described in `NEXT_PHASE.md` without RAG, embeddings, vector search, semantic search, LLM calls, or multi-offense search.

## Validation Notes

Current deterministic validations:

- Validate `scripts/resolve_query_field.py` with its default aliases path.
- Validate `scripts/resolve_query_field.py` with an explicit aliases path.
- Validate `scripts/extract_event_metadata.py` by writing to a temporary output path.
- Validate `app/answer_event_question.py` with supported example questions.
- Validate that `streamlit run app/app.py` starts successfully.
