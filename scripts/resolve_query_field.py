#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ALIASES = REPO_ROOT / "mappings" / "event_field_aliases_v1.json"

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "did", "do", "does", "for",
    "from", "give", "in", "is", "it", "me", "of", "on", "show", "tell", "the",
    "this", "to", "was", "were", "what", "when", "where", "which", "who", "with",
    "offense", "event", "events"
}


def normalize(text):
    text = text.lower()
    text = text.replace("_", " ").replace(".", " ").replace("-", " ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def tokens(text):
    return [t for t in normalize(text).split() if t and t not in STOPWORDS]


def contains_token_sequence(haystack_tokens, needle_tokens):
    if not needle_tokens or len(needle_tokens) > len(haystack_tokens):
        return False
    n = len(needle_tokens)
    for i in range(0, len(haystack_tokens) - n + 1):
        if haystack_tokens[i:i+n] == needle_tokens:
            return True
    return False


def load_aliases(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if "aliases" not in data or not isinstance(data["aliases"], dict):
        raise ValueError("Alias file must contain an 'aliases' object")
    return data["aliases"]


def score_field(question, field, aliases):
    q_norm = normalize(question)
    q_token_list = tokens(question)
    q_tokens = set(q_token_list)

    phrases = [field] + aliases
    best = 0.0
    best_alias = None
    best_reason = "no_match"

    for phrase in phrases:
        p_norm = normalize(phrase)
        p_token_list = tokens(phrase)
        p_tokens = set(p_token_list)
        if not p_tokens:
            continue

        score = 0.0
        reason = "token_overlap"

        if p_norm == q_norm:
            score = 1.0
            reason = "exact_question_match"
        elif contains_token_sequence(q_token_list, p_token_list):
            # Strong signal: full alias appears as whole words inside the user question.
            score = 0.90 + min(len(p_tokens), 5) * 0.01
            reason = "alias_phrase_in_question"
        elif contains_token_sequence(p_token_list, q_token_list) and len(q_token_list) >= 1:
            score = 0.75
            reason = "question_phrase_in_alias"
        else:
            overlap = q_tokens & p_tokens
            if overlap:
                precision = len(overlap) / len(p_tokens)
                recall = len(overlap) / max(len(q_tokens), 1)
                score = (0.65 * precision) + (0.35 * recall)

                # Prefer more specific aliases over generic one-token matches like "source".
                if len(p_tokens) == 1 and len(q_tokens) > 1:
                    score *= 0.70

        if score > best:
            best = score
            best_alias = phrase
            best_reason = reason

    return best, best_alias, best_reason


def resolve(question, alias_map, top=5, threshold=0.25):
    matches = []
    for field, aliases in alias_map.items():
        score, alias, reason = score_field(question, field, aliases)
        if score >= threshold:
            matches.append({
                "field": field,
                "score": round(score, 4),
                "matched_alias": alias,
                "reason": reason
            })

    matches.sort(key=lambda x: (-x["score"], x["field"]))
    return matches[:top]


def main():
    parser = argparse.ArgumentParser(description="Resolve a natural-language question to event metadata field names.")
    parser.add_argument("--aliases", default=str(DEFAULT_ALIASES), help="Path to alias JSON file")
    parser.add_argument("--question", required=True, help="User question, for example: 'What is the source ip in this offense?'")
    parser.add_argument("--top", type=int, default=5, help="Number of candidate fields to return")
    parser.add_argument("--threshold", type=float, default=0.25, help="Minimum score to include")
    args = parser.parse_args()

    alias_map = load_aliases(args.aliases)
    matches = resolve(args.question, alias_map, top=args.top, threshold=args.threshold)

    output = {
        "question": args.question,
        "best_field": matches[0]["field"] if matches else None,
        "matches": matches
    }
    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
