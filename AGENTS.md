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

Build a deterministic analyst search interface over Event Metadata Records.

## Important Files

- offense_82303_events_964_fixed.json
- event_metadata_records_82303.json
- event_field_aliases_v1.json
- resolve_query_field.py

## Repository Rules

- Reuse existing files whenever possible.
- Do not create duplicate datasets.
- Do not delete files without approval.
- Document architectural changes in README.md.
