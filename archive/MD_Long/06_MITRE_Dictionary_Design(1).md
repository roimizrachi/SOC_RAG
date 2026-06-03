# MITRE Dictionary Design

## MITRE Hierarchy

```text
Tactic
   ↓
Technique
   ↓
Sub-Technique
```

Example:

```text
TA0003 = Persistence
T1547.004 = Winlogon Helper DLL
```

Meaning:

```text
TA0003 = Goal
T1547.004 = Method
```

## Source Dataset

```text
enterprise-attack-19.1.json
~45 MB
```

## Build Process

```text
enterprise-attack-19.1.json
          ↓
Parser
          ↓
mitre_tactics.json
mitre_techniques.json
```

## Example Output

```json
{
  "TA0003": {
    "name": "Persistence",
    "description": "The adversary is trying to maintain their foothold..."
  }
}
```

```json
{
  "T1547.004": {
    "name": "Winlogon Helper DLL"
  }
}
```
