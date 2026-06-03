# SOC_RAG

## Current Phase

Event Metadata Search MVP, deterministic multi-offense metadata-file search.

Current scope is deterministic, event-level search over generated Event Metadata Records. The active search router still follows the Phase 2 route:

```text
Analyst Query
  -> Search Router
      -> Exact Field Search
      -> BM25 Metadata Text Search
      -> Fuzzy Metadata Text Search Fallback
```

Do not implement in this phase:

- RAG
- Embeddings
- Vector search
- Semantic search
- Qdrant
- OpenAI API calls
- LLM calls
- Offense Profile embedding pipeline

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
data/offense_<offense_id>_events_<logsource_id>_*.json
  -> scripts/extract_event_metadata.py
  -> data/event_metadata_records_<offense_id>.json
      -> app/metadata_records.py
          -> discover available metadata files dynamically
          -> load one selected offense or all discovered offenses
      -> Analyst Query
         -> app/search_router.py
             -> Exact Field Search:
                mappings/event_field_aliases_v1.json
                -> scripts/resolve_query_field.py
                -> app/answer_event_question.py
             -> BM25 Metadata Text Search:
                app/search_metadata_text.py
             -> Fuzzy Metadata Text Search Fallback:
                app/search_metadata_text.py
             -> app/app.py
             -> scripts/validate_metadata_text_search.py
```

The extractor mapping supports either a single deterministic source path or an ordered list of fallback paths for a normalized field. Fallback paths let the same metadata field cover compatible Cisco Secure Endpoint payload variants, such as registry-set activity and Cloud IOC command-line alerts, while preserving the original path for existing offenses.

## Active Files

- `data/event_metadata_records_<offense_id>.json`: generated Event Metadata Records discovered by filename.
- `mappings/event_field_aliases_v1.json`: natural-language aliases for metadata fields.
- `mappings/event_metadata_mapping_v2_reviewed_fixed.json`: reviewed extraction mapping.
- `mappings/event_metadata_fields_v1.json`: metadata field descriptions.
- `scripts/extract_event_metadata.py`: deterministic extractor from raw offense events to Event Metadata Records.
- `scripts/resolve_query_field.py`: deterministic natural-language field resolver.
- `app/metadata_records.py`: dynamic metadata-file discovery and loading.
- `app/answer_event_question.py`: deterministic exact-field answer layer.
- `app/search_metadata_text.py`: deterministic BM25-only and fuzzy-only metadata text search.
- `app/search_router.py`: deterministic router over exact field search, BM25 metadata text search, and fuzzy metadata text fallback.
- `app/app.py`: Streamlit analyst interface.
- `app/offense_inventory.py`: deterministic offense inventory builder over discovered metadata records.
- `app/pages/1_Offenses_Inventory.py`: Streamlit Offenses Inventory page.
- `scripts/validate_metadata_text_search.py`: deterministic validation checks.

## Usage

Resolve a field from an analyst question:

```bash
python scripts/resolve_query_field.py --question "What is the source ip?"
```

Generate Event Metadata Records:

```bash
python scripts/extract_event_metadata.py --events <raw_offense_events.json> --mapping mappings/event_metadata_mapping_v2_reviewed_fixed.json --offense-id <offense_id> --output data/event_metadata_records_<offense_id>.json
```

Answer an exact-field metadata question for one discovered offense:

```bash
python app/answer_event_question.py --offense-id <offense_id> --question "What is the source ip?"
```

Search event metadata text for one discovered offense:

```bash
python app/search_metadata_text.py --offense-id <offense_id> --query "setupplatform.exe winlogon" --mode bm25
```

Route an analyst query across all discovered offenses:

```bash
python app/search_router.py --all-offenses --query "Does setupplatform.exe appear in the offense?"
```

Run deterministic validation:

```bash
python scripts/validate_metadata_text_search.py
```

Run the analyst interface:

```bash
streamlit run app/app.py
```

## Search Behavior

`app/search_router.py`:

1. Receives one analyst query.
2. Skips exact-field routing for identifier-like queries so literal IPs, hostnames, hashes, process names, file names, and registry paths are searched as metadata values.
3. Tries Phase 1 exact field search first for field-oriented questions.
4. Returns `method == "exact_field"` when exact search is confident and useful.
5. Otherwise runs BM25 metadata text search.
6. Returns `method == "bm25_metadata_text"` when BM25 results are useful.
7. Otherwise runs fuzzy metadata text search as the deterministic fallback.
8. Returns `method == "fuzzy_metadata_text"` for the fallback result, including empty results when no strong match exists.

Metadata text results expose:

- `method`
- `query_type`
- `offense_id`
- `event_index`
- `event_id`
- `score`
- `matched_terms`
- `matched_identifiers`

## Streamlit UI

The UI dynamically discovers available offenses from:

```text
data/event_metadata_records_<offense_id>.json
```

The Streamlit app also includes an Offenses Inventory page that dynamically lists every discovered metadata file with its offense ID, event count, first and last event time, primary QRadar log source ID, metadata file path, and deterministically inferred raw offense file path.

At the top of the UI, before the analyst query, the analyst chooses:

1. Search inside a specific offense
2. Search across all offenses

Specific-offense mode uses a dropdown generated from discovered metadata files. Cross-offense mode searches all discovered metadata files and displays `offense_id` with each ranked result.

The UI search modes remain:

1. Auto / Routed Search
2. Exact Field Search
3. Metadata Text Search

Fuzzy Search is not exposed as a separate primary UI mode.
