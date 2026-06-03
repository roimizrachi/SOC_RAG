# SOC_RAG AGENTS

## Current Phase

Event Metadata Search MVP

## Scope

- Single offense only
- Event-level search only
- Deterministic search only

## Do Not Implement

- RAG
- Embeddings
- Vector Search
- Semantic Search
- LLM Calls
- Multi-Offense Search

## Current Goal

Build a deterministic analyst search router over Event Metadata Records.

## Search Routing Rules

Analyst queries must use the deterministic router:

```text
Analyst Query
  -> Search Router
      -> Exact Field Search
      -> BM25 Metadata Text Search
      -> Fuzzy Metadata Text Search Fallback
```

- Exact field search is always tried first.
- BM25 metadata text search is tried only when exact field search is not confident or useful.
- Fuzzy metadata text search is the fallback when BM25 results are weak or empty.
- Results must expose the selected method: `exact_field`, `bm25_metadata_text`, or `fuzzy_metadata_text`.

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

- Selected search mode
- Method actually used
- Query type when metadata text search is used
- Result count
- Event indexes
- Scores where relevant
- Matched terms where relevant

## Important Files

- offense_82303_events_964_fixed.json
- event_metadata_records_82303.json
- event_field_aliases_v1.json
- resolve_query_field.py
- search_metadata_text.py
- search_router.py

## Repository Rules

- Reuse existing files whenever possible.
- Do not create duplicate datasets.
- Do not delete files without approval.
- Document architectural changes in README.md.
