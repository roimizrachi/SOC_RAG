# SOC RAG / Vector Search Design Summary

## Project Goal

Build a SOC RAG platform for:

- QRadar
- Cisco Secure Endpoint
- IBM SOAR

The platform should support:

- Exact Match Search
- Metadata Filtering
- BM25 Search
- Fuzzy Search
- Semantic Search
- RAG Explanations

---

# Search Architecture

```text
Metadata
    ↓
Exact Match / Filters

Metadata Text
    ↓
BM25 (+ Fuzzy / n-grams)

Normalized Offense Representation
    ↓
Embeddings
```

---

# Search Layer Responsibilities

## Exact Match

Best for:

- IPs
- Hashes
- Usernames
- Hostnames
- CVEs
- IDs

Examples:

```text
source_ip = 10.149.9.32
sha256 = ...
offense_id = 82303
```

---

## BM25 / Keyword Search

Best for:

- Detection names
- Process names
- Event names
- Command lines
- Log source names

Examples:

```text
Winlogon UserInit Registry Key Modification
setupplatform.exe
powershell.exe
```

---

## Fuzzy Search

Best for:

- Typos
- Partial matching
- Similar spellings

Examples:

```text
persistance
winlogn
```

---

## Semantic Search

Best for:

- Similar offenses
- Conceptual similarity
- Related attack patterns
- Cross-language meaning
- RAG reasoning

---

# Key Conclusion

For a SOC environment:

```text
Metadata + BM25 + Fuzzy
```

will likely answer:

```text
80-90%
```

of analyst questions.

Embeddings provide value mainly when meaning matters more than exact fields.

---

# Important Design Decision

Semantic Search is performed on:

```text
OFFENSES
```

NOT:

```text
EVENTS
```

Wrong:

```text
Query
   ↓
Similar Events
```

Correct:

```text
Query / Offense
      ↓
Similar Offenses
```

Events are raw material.

Offense is the semantic unit.

---

# Why Offense-Level Search?

A QRadar offense can contain:

- dozens of events
- hundreds of events
- multiple hosts
- multiple detections

Searching at Event level loses context.

The semantic meaning exists at Offense level.

---

# Offense Processing Pipeline

```text
Raw Events
      ↓
Field Extraction
      ↓
Enrichment
      ↓
Offense Profile
      ↓
Serialize Profile To Text
      ↓
Embedding
      ↓
Vector DB
```

---

# Offense Profile

The Offense Profile is the source of truth.

It contains structured facts extracted from the offense.

Example:

```json
{
  "main_detection": "Winlogon UserInit Registry Key Modification",
  "tactics": [
    "Persistence"
  ],
  "techniques": [
    "Winlogon Helper DLL"
  ],
  "processes": [
    "setupplatform.exe"
  ],
  "publishers": [
    "Microsoft"
  ],
  "affected_hosts": 10,
  "severity": "medium"
}
```

Important:

```text
Facts only
```

No LLM interpretation.

No generated summary.

---

# Normalized Offense Representation

The Offense Profile is converted into text.

Example:

```text
winlogon userinit registry key modification
persistence
winlogon helper dll
setupplatform.exe
microsoft
10 affected hosts
medium severity
```

This text is generated automatically from the profile.

---

# Important Clarification

There is NO separate LLM Summary stage.

Old idea:

```text
Events
    ↓
LLM Summary
    ↓
Embedding
```

Rejected.

Current design:

```text
Events
    ↓
Offense Profile
    ↓
Serialize Profile To Text
    ↓
Embedding
```

Reason:

- deterministic
- consistent
- easier debugging
- no hallucinations
- faster ingestion

---

# Metadata vs Embedding Content

Everything can originate from metadata.

Example:

```json
{
  "detection": "Winlogon UserInit Registry Key Modification",
  "process_name": "setupplatform.exe",
  "publisher": "Microsoft",
  "severity": "Medium"
}
```

Converted into:

```text
detection: Winlogon UserInit Registry Key Modification
process_name: setupplatform.exe
publisher: Microsoft
severity: Medium
```

for embedding.

---

# Metadata vs Exact Match

Metadata:

```json
{
  "source_ip": "10.149.9.32"
}
```

Exact Match:

```text
source_ip = 10.149.9.32
```

Metadata is data.

Exact Match is a search method.

---

# Enrichment Strategy

Do NOT use an LLM.

Use deterministic lookup dictionaries.

Pipeline:

```text
Raw Data
     ↓
Lookup Dictionaries
     ↓
Enriched Metadata
     ↓
Offense Profile
```

---

# MITRE Enrichment

Raw offense data may contain:

```text
TA0003
T1547.004
```

These IDs alone are not meaningful to embeddings.

Enrichment adds:

```text
TA0003
    ↓
Persistence
```

```text
T1547.004
    ↓
Winlogon Helper DLL
```

Result:

```json
{
  "tactics": [
    "TA0003"
  ],
  "tactic_names": [
    "Persistence"
  ],
  "techniques": [
    "T1547.004"
  ],
  "technique_names": [
    "Winlogon Helper DLL"
  ]
}
```

---

# MITRE Classification Hierarchy

MITRE hierarchy:

```text
Tactic
    ↓
Technique
    ↓
Sub-Technique
```

Example:

```text
TA0003
Persistence
```

Represents:

```text
What is the attacker trying to achieve?
```

Example:

```text
T1547
Boot or Logon Autostart Execution
```

Represents:

```text
How is the attacker achieving it?
```

Example:

```text
T1547.004
Winlogon Helper DLL
```

Represents:

```text
Specific implementation
```

Simplified:

```text
TA0003 = Goal
T1547.004 = Method
```

---

# MITRE Dictionary Strategy

MITRE ATT&CK publishes a large dataset:

```text
enterprise-attack-19.1.json
~45 MB
```

This file is NOT used during runtime.

One-time process:

```text
enterprise-attack-19.1.json
          ↓
Parser
          ↓
mitre_tactics.json
mitre_techniques.json
```

Example:

```json
{
  "TA0003": {
    "name": "Persistence",
    "description": "The adversary is trying to maintain their foothold..."
  }
}
```

Example:

```json
{
  "T1547.004": {
    "name": "Winlogon Helper DLL",
    "description": "..."
  }
}
```

Runtime loads only the lightweight dictionaries.

---

# Additional Enrichment Sources

## QRadar QID Dictionary

```json
{
  "111250108": "Winlogon UserInit Registry Key Modification"
}
```

## Log Source Dictionary

```json
{
  "964": "Cisco Secure Endpoint"
}
```

## Internal SOC Dictionary

```json
{
  "setupplatform.exe": [
    "windows upgrade",
    "os deployment"
  ]
}
```

---

# Storage Concept (Current Thinking)

The important object is:

```text
Offense Profile
```

Stored together with:

```text
Embedding
```

inside the vector database.

Conceptually:

```text
Offense
      ↓
Offense Profile
      ↓
Embedding
      ↓
Qdrant
```

The exact database schema is still open and not finalized.

---

# Current LLM Decision

Primary local model:

```text
Llama 3.2 3B Q4
```

Future comparison candidates:

- Llama 3 8B
- Llama 2 7B

---

# Current Open Question

Define the final Offense Profile schema.

Need to decide:

- Which fields enter the profile?
- Which fields stay as metadata only?
- Which fields participate in embeddings?
- How event aggregation should work?
- How host counts, processes, detections and MITRE information should be represented?
- Whether serialization should be template-based or dynamically generated?