# NEXT_PHASE.md

# SOC RAG - Phase 2

## Deterministic Event Metadata Search MVP

### Context

We are building a SOC RAG platform incrementally.

Current scope:

-   Single Offense only
-   Event-level search only
-   No Offense Metadata Index yet
-   No Offense Profiles yet
-   No Embeddings
-   No Vector Search
-   No RAG

Current architecture:

``` text
Raw Offense JSON
        ↓
extract_event_metadata.py
        ↓
event_metadata_records_82303.json
        ↓
event_field_aliases_v1.json
        ↓
resolve_query_field.py
```

Existing files:

``` text
event_metadata_records_82303.json
event_field_aliases_v1.json
resolve_query_field.py
```

## Goal

Build the first analyst-facing search application.

The application must answer deterministic questions using Event Metadata
Records only.

## Files To Create

``` text
answer_event_question.py
app.py
```

## answer_event_question.py

Responsibilities:

1.  Receive analyst question.
2.  Use resolve_query_field.py.
3.  Resolve question into metadata field.
4.  Load event_metadata_records_82303.json.
5.  Collect values for the resolved field.
6.  Remove duplicates.
7.  Return structured result.

Return format:

``` python
{
    "question": question,
    "resolved_field": field_name,
    "values": unique_values,
    "event_count": count,
    "matching_event_indexes": indexes
}
```

Requirements:

-   Deterministic only.
-   No LLM.
-   No AI reasoning.
-   No Embeddings.
-   No Vector Search.

## app.py

Build a Streamlit application.

Run:

``` bash
streamlit run app.py
```

Display: - Question input - Ask button - Resolved field - Values - Event
count - Matching events table

## Supported Questions

Examples:

-   What is the source ip?
-   What is the destination ip?
-   What is the hostname?
-   What registry key was modified?
-   What file hash was detected?
-   What is the sha256?
-   What MITRE technique was detected?
-   What tactic was detected?

Use:

``` text
event_field_aliases_v1.json
```

## Constraints

Do NOT implement:

-   RAG
-   Embeddings
-   Semantic Search
-   Vector Search
-   OpenAI API Calls
-   Offense Profiles
-   Multi-Offense Search

## Validation

Before finishing:

1.  Run locally.
2.  Verify Streamlit starts.
3.  Verify example questions work.
4.  Verify duplicate values are removed.
5.  Verify event indexes are returned.

## Deliverables

``` text
answer_event_question.py
app.py
```
