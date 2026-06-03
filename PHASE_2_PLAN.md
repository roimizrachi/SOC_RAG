# PHASE_2_PLAN

## Goal

Implement deterministic BM25 + Fuzzy Search over Metadata Text for the existing single-offense Event Metadata Records.

Phase 2 should let analysts search free-text event metadata content when an exact field/value answer is not enough, while still staying fully deterministic.

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
Metadata Text -> BM25 + Fuzzy
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
- Return ranked matching events with event indexes.
- Keep exact field resolution from Phase 1 available.
- Update the Streamlit app to expose the Phase 2 metadata text search results.

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

- `app/search_metadata_text.py`
  - Builds metadata text from each Event Metadata Record.
  - Performs deterministic BM25 ranking.
  - Performs deterministic fuzzy matching.
  - Returns ranked event-level search results.

- `scripts/validate_metadata_text_search.py`
  - Runs deterministic validation queries for BM25 + fuzzy behavior.
  - Verifies ranked results, event indexes, and stable output shape.

Change:

- `app/app.py`
  - Add a metadata text search view or section.
  - Display ranked matching events, scores, matched terms, and event indexes.

- `README.md`
  - Document Phase 2 architecture, commands, constraints, and validation.

Do not create duplicate datasets. Reuse `data/event_metadata_records_82303.json`.

## Search Behavior

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

Fuzzy behavior:

- Apply fuzzy matching to query tokens against metadata text tokens.
- Support typo-tolerant matches such as misspelled detections, hostnames, file names, registry terms, and process names.
- Keep fuzzy scoring deterministic.
- Do not use embeddings or semantic similarity.

Result shape:

```python
{
    "query": query,
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
