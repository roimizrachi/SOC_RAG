# Offense Profile Design

## Source Of Truth

The Offense Profile is the authoritative representation of an offense.

No LLM-generated summary is used for embeddings.

## Design Principle

```text
Facts
   ↓
Normalization
   ↓
Embedding
```

## Candidate Fields

### Detection Information
- main_detection
- detection_family

### MITRE
- tactics
- techniques

### Process Information
- process names
- publishers

### Asset Information
- host count
- operating systems

### Risk Information
- severity

## Rejected Design

```text
Events
   ↓
LLM Summary
   ↓
Embedding
```

Reason:
- hallucinations
- inconsistent output
- harder debugging

## Accepted Design

```text
Events
   ↓
Offense Profile
   ↓
Text Serialization
   ↓
Embedding
```
