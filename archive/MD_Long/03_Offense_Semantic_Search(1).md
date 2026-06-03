# Offense Semantic Search

## Important Decision

Semantic search operates on OFFENSES, not EVENTS.

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

## Why?

An offense may contain:
- Many events
- Many hosts
- Multiple detections

Events alone lose context.

## Pipeline

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

## Example Offense Profile

```json
{
  "main_detection": "Winlogon UserInit Registry Key Modification",
  "tactics": ["Persistence"],
  "techniques": ["Winlogon Helper DLL"],
  "processes": ["setupplatform.exe"],
  "publishers": ["Microsoft"],
  "affected_hosts": 10,
  "severity": "medium"
}
```

## Serialized Representation

```text
winlogon userinit registry key modification
persistence
winlogon helper dll
setupplatform.exe
microsoft
10 affected hosts
medium severity
```
