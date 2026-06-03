# SOC_RAG

## Current Project Phase

Phase 3 upload intake UI is complete.

The active project status is deterministic, event-level analyst search over generated Event Metadata Records with Streamlit upload intake. The current search contract remains the Phase 2 deterministic router:

```text
Analyst Query
  -> Search Router
      -> Exact Field Search
      -> BM25 Metadata Text Search
      -> Fuzzy Metadata Text Search Fallback
```

Repository history after the Phase 2 tag also added deterministic metadata-file discovery, selected-offense search, all-discovered-offense metadata search controls, offense intake support, a Streamlit upload intake UI, and an offenses inventory view. These are operational extensions around the same deterministic Event Metadata Records search surface; they do not change the current no-RAG/no-embedding architecture.

Do not implement in this phase without explicit approval:

- RAG
- Embeddings
- Vector search
- Semantic search
- Qdrant
- OpenAI API calls
- LLM calls
- Offense Profile embedding pipeline
- New semantic or vector-backed search behavior

## Completed Phases

| Phase | Status | Objective | Main outcomes |
| --- | --- | --- | --- |
| Phase 1: Event Metadata Search MVP | Completed at `phase1-mvp` / `dfb3328` | Build deterministic exact-field analyst search for one offense using Event Metadata Records. | Repository reorganization, offense `82303` raw events and metadata records, deterministic metadata extraction, field alias resolution, exact-field answer layer, and initial Streamlit UI. |
| Phase 2: Deterministic Metadata Text Search | Completed at `phase2-complete` / `ed3ce30` | Add routed deterministic search over metadata text while preserving exact-field search. | Search router, BM25 metadata text search, fuzzy metadata text fallback, deterministic query classification, identifier-aware safety rules, UI search modes, and validation coverage. |
| Phase 2.1: Dynamic Metadata-File Search and Offense Intake | Completed at `phase2-multi-offense-search` / `69c4108`; extended by `042cfd1` | Reuse the Phase 2 router across discovered metadata record files and improve analyst workflow around additional offenses. | Dynamic `event_metadata_records_<offense_id>.json` discovery, selected-offense and all-discovered-offense search controls, additional offense metadata files, mapping fallback paths, deterministic offense intake support, and offenses inventory documentation. |
| Phase 3: Streamlit Upload Intake UI | Completed; ready for commit checkpoint | Run deterministic offense intake from the Streamlit UI. | Upload offense JSON through the UI, save raw offense files under `data/`, generate `event_metadata_records_<offense_id>.json`, refresh discovery, run intake checks and smoke searches, display an intake report, and enforce overwrite protection. |

## Phase Objectives

- Phase 1 objective: turn raw QRadar/Cisco event payloads into normalized Event Metadata Records and answer field-oriented analyst questions deterministically.
- Phase 2 objective: route analyst queries through exact field search, BM25 metadata text search, and fuzzy metadata text fallback with deterministic method selection and result metadata.
- Phase 2.1 objective: make the deterministic search workflow operate over discovered metadata files without introducing semantic search, vector databases, embeddings, RAG, or LLM calls.
- Phase 3 objective: expose deterministic offense intake through Streamlit upload controls while preserving existing search behavior.
- Planned next phase objective: generate a deterministic offense-level profile from Event Metadata Records.

## Current Capabilities

- Deterministic extraction from raw offense JSON into `data/event_metadata_records_<offense_id>.json`.
- Deterministic field alias resolution and exact-field event metadata answers.
- Routed analyst search with method reporting: `exact_field`, `bm25_metadata_text`, or `fuzzy_metadata_text`.
- Deterministic query classification for metadata text search: `identifier_like` or `free_text`.
- Identifier-aware matching for IP addresses, hostnames, hashes, process names, file names, and registry paths.
- BM25 metadata text ranking and conservative fuzzy fallback over event-level metadata text.
- Dynamic discovery of available metadata record files by offense ID.
- Streamlit controls for Auto / Routed Search, Exact Field Search, and Metadata Text Search.
- Streamlit offense intake support for uploaded offense JSON files, deterministic extraction, validation checks, smoke-search checks, and overwrite protection.
- Streamlit offenses inventory view over discovered metadata records.
- Deterministic validation through `scripts/validate_metadata_text_search.py`.

## Next Planned Phase

The next planned phase is deterministic Offense Profile generation, as documented in `NEXT_PHASE.md`.

The intended output is an offense-level profile derived from existing Event Metadata Records, including hosts, users, IPs, detections, processes, registry keys, event counts, and notable artifacts. The next phase should remain deterministic and should not add embeddings, vector search, RAG, semantic search, OpenAI API calls, or LLM calls unless explicitly approved.

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
Streamlit upload of data/offense_<offense_id>*.json
  -> app/offense_intake.py
      -> scripts/extract_event_metadata.py
      -> data/event_metadata_records_<offense_id>.json
      -> app/metadata_records.py discovery refresh
      -> app/search_router.py smoke checks

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
- `app/offense_intake.py`: deterministic Streamlit upload intake wrapper around the existing extractor, validation, discovery, and smoke checks.
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

The main Streamlit app includes an Offense Intake panel before metadata discovery can stop the page. The panel accepts an uploaded `offense_<offense_id>*.json` file, validates the JSON shape, saves the raw offense JSON under `data/`, runs the existing deterministic extractor, writes `data/event_metadata_records_<offense_id>.json`, refreshes metadata discovery, and reports validation plus smoke-search checks in the UI. Existing raw files or metadata outputs are not overwritten unless the analyst enables the explicit overwrite checkbox.

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
