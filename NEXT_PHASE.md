# NEXT_PHASE

## Goal

Build the first analyst-facing deterministic search application for Event Metadata Records.

## Existing Files

- event_metadata_records_82303.json
- event_field_aliases_v1.json
- resolve_query_field.py

## Files To Create

- answer_event_question.py
- app.py

## Requirements

### answer_event_question.py

Responsibilities:

1. Receive analyst question.
2. Resolve question to a metadata field using resolve_query_field.py.
3. Load event_metadata_records_82303.json.
4. Collect values for the resolved field.
5. Remove duplicates.
6. Return:

```python
{
    "question": question,
    "resolved_field": field_name,
    "values": unique_values,
    "event_count": count,
    "matching_event_indexes": indexes
}
```

### app.py

Build a Streamlit application.

Run:

```bash
streamlit run app.py
```

UI:

- Question input
- Ask button
- Resolved field
- Values
- Event count
- Matching events table

## Supported Questions

Examples:

- What is the source ip?
- What is the destination ip?
- What is the hostname?
- What registry key was modified?
- What file hash was detected?
- What is the sha256?
- What MITRE technique was detected?
- What tactic was detected?

Use:

- event_field_aliases_v1.json

## Constraints

Do NOT implement:

- RAG
- Embeddings
- Semantic Search
- Vector Search
- OpenAI API calls
- Multi-Offense Search

## Validation

Before finishing:

1. Verify Streamlit starts successfully.
2. Verify example questions return results.
3. Verify duplicate values are removed.
4. Verify event indexes are returned.

## Deliverables

- answer_event_question.py
- app.py
