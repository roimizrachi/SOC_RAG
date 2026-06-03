# Decisions Log

## Confirmed Decisions

1. Semantic search is performed on offenses.
2. Events are raw material only.
3. Offense Profile is the source of truth.
4. No LLM Summary before embedding generation.
5. Embeddings are generated from serialized Offense Profiles.
6. MITRE enrichment is dictionary-based.
7. Lookup tables are preferred over LLM enrichment.
8. MITRE dataset is processed offline.
9. Llama 3.2 3B Q4 is the current baseline model.

## Current Open Questions

- Final Offense Profile schema.
- Event aggregation strategy.
- Which fields participate in embeddings.
- Serialization format standardization.
