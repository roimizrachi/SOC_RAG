# Search Architecture

## Search Layers

### Exact Match
Used for:
- IPs
- Hashes
- Users
- Hostnames
- CVEs

### BM25
Used for:
- Detection names
- Process names
- Commands

### Fuzzy Search
Used for:
- Typos
- Partial matches

### Semantic Search
Used for:
- Similar offenses
- Similar attack patterns

## Architecture

```text
Metadata
    ↓
Exact Match

Metadata Text
    ↓
BM25

Metadata Text
    ↓
Fuzzy Search

Normalized Offense Representation
    ↓
Embeddings
```

## Conclusion

Expected distribution:

```text
Metadata + BM25 + Fuzzy
≈ 80-90% of analyst queries
```

Embeddings mainly solve meaning-based questions.
