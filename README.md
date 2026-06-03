# SOC_RAG

## Current Phase

Event Metadata Search MVP, Phase 2.

Current scope is deterministic, single-offense, event-level search over Event Metadata Records only.

Phase 1 exact field search remains active. Phase 2 adds a deterministic Search Router that tries exact field search first, BM25 metadata text search second, and fuzzy metadata text search as the fallback.

Do not implement in this phase:

- RAG
- Embeddings
- Vector search
- Semantic search
- Qdrant
- OpenAI API calls
- LLM calls
- Offense Profile embedding pipeline
- Multi-offense search
- New offense datasets

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

## Active Files

- `data/offense_82303_events_964_fixed.json`: canonical raw offense event dataset for offense 82303.
- `data/event_metadata_records_82303.json`: generated Event Metadata Records for offense 82303.
- `mappings/event_field_aliases_v1.json`: natural-language aliases for metadata fields.
- `mappings/event_metadata_mapping_v2_reviewed_fixed.json`: reviewed extraction mapping.
- `mappings/event_metadata_fields_v1.json`: metadata field descriptions.
- `scripts/extract_event_metadata.py`: deterministic extractor from raw offense events to Event Metadata Records.
- `scripts/resolve_query_field.py`: deterministic natural-language field resolver.
- `app/answer_event_question.py`: deterministic answer layer over Event Metadata Records.
- `app/search_metadata_text.py`: deterministic BM25-only and fuzzy-only metadata text search over Event Metadata Records.
- `app/search_router.py`: deterministic router over exact field search, BM25 metadata text search, and fuzzy metadata text search fallback.
- `app/app.py`: Streamlit analyst interface with routed search and exact field search.
- `scripts/validate_metadata_text_search.py`: deterministic Phase 2 validation checks.

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

Search event metadata text with deterministic BM25 + fuzzy matching:

```bash
python app/search_metadata_text.py --query "setupplatform.exe winlogon" --mode bm25
```

Route an analyst query deterministically:

```bash
python app/search_router.py --query "Does setupplatform.exe appear in the offense?"
```

Run Phase 2 validation:

```bash
python scripts/validate_metadata_text_search.py
```

Run the analyst interface:

```bash
streamlit run app/app.py
```

## Phase 2 Search Router Behavior

`app/search_router.py`:

1. Receives one analyst query.
2. Tries Phase 1 exact field search first.
3. Returns `method == "exact_field"` when exact search is confident and useful.
4. Otherwise runs BM25 metadata text search.
5. Returns `method == "bm25_metadata_text"` when BM25 results are useful.
6. Otherwise runs fuzzy metadata text search as the deterministic fallback.
7. Returns `method == "fuzzy_metadata_text"` for the fallback result, including empty results when no strong match exists.

Deterministic thresholds and fallback rules:

- Exact field success requires top resolver score at least `0.75`, a strong resolver reason, and non-empty exact values.
- `question_phrase_in_alias` exact matches require a score gap of at least `0.10` from the second resolver candidate.
- BM25 useful results require positive score and at least one exact matched term.
- Non-identifier BM25 queries require top score at least `0.10`.
- Identifier-like BM25 queries require exact normalized identifier matches.
- Fuzzy search runs only when exact field search is not useful and BM25 is weak or empty.

## Query Classification

The search system classifies queries deterministically before applying partial or fuzzy behavior.

1. Identifier-like queries
   - Examples: IP addresses, hostnames, hashes, process names, file names, and registry paths.
   - Prefer exact normalized matching.
   - Allow controlled prefix matching only when meaningful.
   - Do not treat weak shared fragments as meaningful matches.
   - Do not return unrelated identifiers just because they share fragments.
   - Hostname textual segments may fuzzy-match only in fuzzy fallback.
   - Hostname numeric asset/station segments must match exactly.
   - Example:
     - Query: `WK-MOKEDM-5342`
     - Valid match: `WK-MOKEDM-5342.OPENU.LAN`
     - Invalid matches: `WK-MOKEDM-5341.OPENU.LAN`, `WK-MOKEDM-5414.OPENU.LAN`, `WK-MOKEDM-5345.OPENU.LAN`

2. Free-text queries
   - Examples: `setup`, `registry`, `winlogon`, `userinit`, `modification`.
   - BM25 ranking is allowed.
   - Fuzzy matching is allowed.
   - Partial token matches are allowed when useful.
   - Weak short-token fuzzy substitutions that would return broad false positives are not useful.
   - Example:
     - Query: `setup`
     - Valid fuzzy/partial match: `setup -> setupplatform`

Strict partial-match restrictions apply only to identifier-like queries. They must not block useful free-text fuzzy behavior.

Metadata text and routed results expose `query_type` as `identifier_like` or `free_text` when metadata text search is used.

## Identifier Search Rules

The following values are treated as identifiers rather than generic text:

- IP addresses
- Hashes (MD5/SHA1/SHA256)
- Hostnames
- Process names
- File names
- Registry paths

For identifier-like queries:

- Prefer exact normalized token matching.
- Do not consider weak partial fragment matches as strong results.
- BM25 should not produce a positive search result solely because fragments of an identifier matched.
- For hostname-like identifiers, partial/prefix matching is allowed only when the full normalized query identifier is a prefix or exact normalized substring of the candidate hostname.
- Shared hostname fragments such as `WK` or `MOKEDM` are not meaningful identifier matches by themselves.
- Bounded hostname fuzzy fallback may match textual hostname segments, but numeric asset/station segments must match exactly.
- Example:
  - Query: `10.147.63.36`
  - Record: `10.147.88.10`
  - This is not considered a meaningful match.
- Example:
  - Query: `WK-MOKEDM-5342`
  - Valid record match: `WK-MOKEDM-5342.OPENU.LAN`
  - Invalid record match: `WK-MOKEDM-5341.OPENU.LAN`
- Example:
  - Query: `WK-MOKDP-5534`
  - Valid fuzzy fallback match: `WK-MOKEDP-5534.OPENU.LAN`
  - Invalid fuzzy fallback match: any hostname with a station number other than `5534`

These rules exist to reduce false positives during SOC investigations.

## Streamlit UI Search Modes

The Streamlit UI exposes these search modes:

1. Auto / Routed Search
   - Default mode.
   - Uses deterministic routing: `exact_field -> bm25_metadata_text -> fuzzy_metadata_text`.

2. Exact Field Search
   - Runs only the Phase 1 exact field search.
   - Used for validation/debugging.

3. Metadata Text Search
   - Runs Phase 2 metadata text search.
   - Uses BM25 first.
   - Uses fuzzy fallback only if BM25 is weak or empty.

Fuzzy Search is not exposed as a separate primary UI mode.

The UI displays:

- Selected search mode.
- Method actually used.
- Query type when metadata text search is used.
- Result count.
- Event indexes.
- Scores where relevant.
- Matched terms where relevant.

Pressing Enter in the analyst query input triggers the same search action as clicking the Search button for all search modes.

## Metadata Text Search Behavior

`app/search_metadata_text.py`:

1. Loads `data/event_metadata_records_82303.json`.
2. Builds one metadata text document per event from existing field names and non-empty field values.
3. Flattens arrays and nested values into deterministic text.
4. Tokenizes query and event metadata text deterministically.
5. Supports BM25-only event scoring.
6. Supports fuzzy-only fallback scoring.
7. Returns ranked event-level results:

```python
{
    "query": query,
    "method": "bm25_metadata_text | fuzzy_metadata_text",
    "query_type": "identifier_like | free_text",
    "results": [
        {
            "event_index": event_index,
            "event_id": event_id,
            "score": score,
            "matched_terms": matched_terms,
            "fields": fields
        }
    ]
}
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
- `app/search_metadata_text.py` adds Phase 2 deterministic BM25-only and fuzzy-only metadata text search using the existing `data/event_metadata_records_82303.json` file only.
- `app/search_router.py` adds the deterministic fallback strategy over exact field search, BM25 metadata text search, and fuzzy metadata text search.

## Validation Notes

Current deterministic validations:

- Validate `scripts/resolve_query_field.py` with its default aliases path.
- Validate `scripts/resolve_query_field.py` with an explicit aliases path.
- Validate `scripts/extract_event_metadata.py` by writing to a temporary output path.
- Validate `app/answer_event_question.py` with supported example questions.
- Validate `app/search_metadata_text.py` with detection, process, registry, fuzzy typo, free-text partial, bounded hostname fuzzy, weak fuzzy suppression, and identifier-aware queries.
- Validate `app/search_router.py` routes exact, BM25, fuzzy, and missing identifier queries deterministically.
- Validate `scripts/validate_metadata_text_search.py`.
- Validate that `streamlit run app/app.py` starts successfully.
