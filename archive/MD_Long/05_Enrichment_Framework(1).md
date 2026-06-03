# Enrichment Framework

## Principle

Use deterministic lookup dictionaries.

Do not use an LLM for enrichment.

## Pipeline

```text
Raw Data
    ↓
Lookup Dictionaries
    ↓
Enriched Metadata
    ↓
Offense Profile
```

## MITRE Example

Input:

```text
TA0003
T1547.004
```

Output:

```text
TA0003 -> Persistence
T1547.004 -> Winlogon Helper DLL
```

## Future Dictionaries

### QRadar QID Dictionary

```json
{
  "111250108": "Winlogon UserInit Registry Key Modification"
}
```

### Log Source Dictionary

```json
{
  "964": "Cisco Secure Endpoint"
}
```

### Internal SOC Dictionary

```json
{
  "setupplatform.exe": [
    "windows upgrade",
    "os deployment"
  ]
}
```
