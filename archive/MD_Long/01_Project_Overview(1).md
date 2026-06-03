# Project Overview

## Vision
Build a SOC RAG platform for QRadar, Cisco Secure Endpoint and IBM SOAR.

## Goals
- Exact Match Search
- Metadata Filtering
- BM25 Search
- Fuzzy Search
- Semantic Search
- RAG Explanations

## Current LLM Decision
Primary model: Llama 3.2 3B Q4 (local).
Future comparison:
- Llama 3 8B
- Llama 2 7B

## Core Principle
Use structured security data first. Use LLMs mainly for explanation and reasoning, not for data normalization.

## High-Level Architecture

```text
Data Sources
    ↓
Normalization
    ↓
Enrichment
    ↓
Offense Profile
    ↓
Embeddings + Search
    ↓
RAG Responses
```
