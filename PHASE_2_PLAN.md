# PHASE_2_PLAN

## Goal

Implement a deterministic Search Router with BM25 + Fuzzy Search over Metadata Text for the existing single-offense Event Metadata Records.

Phase 2 should let analysts submit one query and deterministically route it through exact field search first, BM25 metadata text search second, and fuzzy metadata text search as a fallback.

## Why This Is Phase 2

The documented search architecture is:

```text
Metadata -> Exact Match
Metadata Text -> BM25 + Fuzzy
Offense Profile -> Embedding -> Vector Search
```

Phase 1 completed the first layer:

```text
Metadata -> Exact Match
```

Therefore, the real next phase is the second layer:

```text
Analyst Query
  -> Search Router
      -> Metadata -> Exact Match
      -> Metadata Text -> BM25
      -> Metadata Text -> Fuzzy Fallback
```

Embeddings, vector databases, RAG, and LLM integration belong to later phases only.

## Scope

- Single offense only.
- Event-level search only.
- Deterministic search only.
- Use existing `data/event_metadata_records_82303.json`.
- Build searchable metadata text from existing event metadata fields.
- Implement BM25 scoring over metadata text.
- Implement fuzzy matching for typos, partial terms, and near matches.
- Implement deterministic routing above the search methods.
- Return ranked matching events with event indexes.
- Keep exact field resolution from Phase 1 available.
- Update the Streamlit app to expose routed search results and selected search method.

## Out Of Scope

Do not implement:

- Embeddings
- Vector search
- Qdrant
- RAG
- OpenAI API calls
- LLM calls
- Semantic search
- Offense Profile embedding pipeline
- Multi-offense search
- New offense datasets

## Files To Create Or Change

Create:

- `app/search_router.py`
  - Tries exact field search first.
  - Routes to BM25 metadata text search when exact field search is not confident or useful.
  - Routes to fuzzy metadata text search when BM25 results are weak or empty.
  - Returns the selected method: `exact_field`, `bm25_metadata_text`, or `fuzzy_metadata_text`.

- `app/search_metadata_text.py`
  - Builds metadata text from each Event Metadata Record.
  - Performs deterministic BM25-only ranking.
  - Performs deterministic fuzzy-only fallback matching.
  - Returns ranked event-level search results.

- `scripts/validate_metadata_text_search.py`
  - Runs deterministic validation queries for BM25 + fuzzy behavior.
  - Verifies ranked results, event indexes, and stable output shape.

Change:

- `app/app.py`
  - Use `app/search_router.py` for analyst queries.
  - Display the selected method, route decisions, ranked matching events, scores, matched terms, and event indexes.

- `README.md`
  - Document Phase 2 architecture, commands, constraints, and validation.

- `AGENTS.md`
  - Document deterministic search routing rules and identifier-aware matching rules.

- `PHASE_2_PLAN.md`
  - Document deterministic search routing rules and identifier-aware matching rules.

Do not create duplicate datasets. Reuse `data/event_metadata_records_82303.json`.

## Search Router Behavior

Required flow:

```text
Analyst Query
  -> Search Router
      -> Try Phase 1 Exact Field Search
          -> If confident/useful result: return exact_field result
          -> Else route to Phase 2 Metadata Text Search
              -> Run deterministic BM25 search
              -> If BM25 has useful results: return bm25_metadata_text result
              -> Else run deterministic fuzzy fallback
                  -> return fuzzy_metadata_text result
```

Exact field success:

- A resolver candidate exists.
- The top resolver score is at least `0.75`.
- The top resolver reason is deterministic and strong: `exact_question_match`, `alias_phrase_in_question`, or `question_phrase_in_alias`.
- If the top reason is `question_phrase_in_alias`, the score gap from the second candidate must be at least `0.10`.
- The exact field answer must return non-empty values and `event_count > 0`.

BM25 useful result:

- BM25-only metadata text search returns at least one result.
- The top result has a positive score.
- The top result has at least one exact matched term.
- Non-identifier queries require top score of at least `0.10`.
- Identifier-like queries require exact normalized identifier matches and must not be accepted from weak partial fragments alone.

Fuzzy fallback trigger:

- Exact field search is not confident/useful.
- BM25 metadata text search is empty or weak.
- Fuzzy metadata text search is run as the final deterministic fallback.

## Metadata Text Search Behavior

Metadata text construction:

- Build one searchable text document per event.
- Include field names and normalized field values.
- Flatten arrays into text.
- Skip null and empty values.
- Preserve event identity separately from searchable text.

BM25 behavior:

- Tokenize analyst query deterministically.
- Tokenize each event metadata text deterministically.
- Score event documents using BM25.
- Return ranked matches in descending score order.
- Include `event_index`, `event_id`, score, and selected fields for display.
- Do not combine fuzzy scores into BM25 results.

Fuzzy behavior:

- Apply fuzzy matching to query tokens against metadata text tokens.
- Support typo-tolerant matches such as misspelled detections, hostnames, file names, registry terms, and process names.
- Keep fuzzy scoring deterministic.
- Do not use embeddings or semantic similarity.
- Run only after exact field search and BM25 metadata text search fail to produce a useful result.

## Query Classification

The search system must classify queries deterministically before applying partial or fuzzy behavior.

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

Metadata text and routed results should expose `query_type` as `identifier_like` or `free_text` when metadata text search is used.

## Identifier Search Rules

The following values must be treated as identifiers rather than generic text:

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

The Streamlit UI must expose these search modes:

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

Do not expose Fuzzy Search as a separate primary UI mode for now.

The UI must clearly display:

- Selected search mode.
- Method actually used.
- Query type when metadata text search is used.
- Result count.
- Event indexes.
- Scores where relevant.
- Matched terms where relevant.

Result shape:

```python
{
    "query": query,
    "method": "exact_field | bm25_metadata_text | fuzzy_metadata_text",
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

## Validation Checklist

- Verify BM25 search returns ranked events for detection names.
- Verify BM25 search returns ranked events for process names.
- Verify BM25 search returns ranked events for registry terms.
- Verify fuzzy search handles at least one typo in a detection or process query.
- Verify routed exact field queries return `method == "exact_field"`.
- Verify routed metadata text queries return `method == "bm25_metadata_text"` when BM25 is useful.
- Verify routed typo queries return `method == "fuzzy_metadata_text"` when BM25 is weak or empty.
- Verify missing identifier queries do not return strong BM25 matches from weak partial fragments.
- Verify hostname-like queries such as `WK-MOKEDM-5342` return only matching hostnames, not nearby hosts with shared fragments.
- Verify bounded hostname fuzzy queries such as `WK-MOKDP-5534` preserve the exact numeric station segment.
- Verify free-text queries such as `setup` may fuzzy/partial-match `setupplatform`.
- Verify weak free-text fuzzy queries such as `typo` do not return broad false positives.
- Verify every returned result includes `event_index`.
- Verify no duplicate datasets are created.
- Verify exact Phase 1 questions still work.
- Verify Streamlit starts successfully.
- Verify the app displays ranked metadata text search results.

## Clear Constraints

- Deterministic only.
- No RAG.
- No embeddings.
- No semantic search.
- No vector search.
- No Qdrant.
- No OpenAI API.
- No LLM calls.
- No Offense Profile embedding pipeline.
- No multi-offense search.
- Reuse existing data and mappings whenever possible.
