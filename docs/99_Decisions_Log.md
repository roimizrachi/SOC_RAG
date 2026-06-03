# Decisions Log

- Semantic search works on Offenses, not Events.
- Offense Profile is the source of truth.
- No LLM Summary stage before embeddings.
- Embeddings are generated from serialized Offense Profiles.
- MITRE enrichment is dictionary-based.
- Llama 3.2 3B Q4 is the initial local model.
