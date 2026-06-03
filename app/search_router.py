#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
DEFAULT_ALIASES = REPO_ROOT / "mappings" / "event_field_aliases_v1.json"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from answer_event_question import answer_event_question  # noqa: E402
from metadata_records import load_event_metadata_records  # noqa: E402
from resolve_query_field import load_aliases, resolve, tokens  # noqa: E402
from search_metadata_text import extract_identifiers, identifier_values, search_metadata_text_bm25, search_metadata_text_fuzzy  # noqa: E402

EXACT_FIELD_MIN_SCORE = 0.75
EXACT_FIELD_MIN_GAP = 0.10
BM25_MIN_SCORE = 0.10
BM25_LONG_EXACT_TOKEN_MIN_LENGTH = 6
EXACT_STRONG_REASONS = {
    "exact_question_match",
    "alias_phrase_in_question",
    "question_phrase_in_alias",
}
EXACT_REASONS_WITHOUT_GAP_CHECK = set()

THRESHOLDS = {
    "exact_field_min_score": EXACT_FIELD_MIN_SCORE,
    "exact_field_min_gap": EXACT_FIELD_MIN_GAP,
    "bm25_min_score_non_identifier": BM25_MIN_SCORE,
    "bm25_long_exact_token_min_length": BM25_LONG_EXACT_TOKEN_MIN_LENGTH,
}


def result_count(method, result):
    if method == "exact_field":
        return result.get("event_count", 0)
    return len(result.get("results", []))


def has_query_identifiers(result):
    return any(result.get("query_identifiers", {}).values())


def query_has_identifiers(question):
    return bool(identifier_values(extract_identifiers(question)))


def exact_field_candidate_decision(question, aliases_path=DEFAULT_ALIASES):
    if query_has_identifiers(question):
        return {
            "method": "exact_field",
            "status": "rejected",
            "reason": "identifier_query_skips_exact_field",
            "matches": [],
        }

    alias_map = load_aliases(aliases_path)
    matches = resolve(question, alias_map, top=5, threshold=0.25)

    if not matches:
        return {
            "method": "exact_field",
            "status": "rejected",
            "reason": "no_resolver_candidate",
            "matches": [],
        }

    top = matches[0]
    second_score = matches[1]["score"] if len(matches) > 1 else 0.0
    score_gap = round(top["score"] - second_score, 4)
    top_alias_tokens = tokens(top.get("matched_alias") or "")
    question_tokens = tokens(question)

    if top["reason"] == "alias_phrase_in_question" and len(top_alias_tokens) == 1 and len(question_tokens) > 1:
        return {
            "method": "exact_field",
            "status": "rejected",
            "reason": "single_token_alias_inside_multi_token_query",
            "top_match": top,
            "score_gap": score_gap,
            "matches": matches,
        }

    if top["score"] < EXACT_FIELD_MIN_SCORE:
        return {
            "method": "exact_field",
            "status": "rejected",
            "reason": "resolver_score_below_threshold",
            "top_match": top,
            "score_gap": score_gap,
            "matches": matches,
        }

    if top["reason"] not in EXACT_STRONG_REASONS:
        return {
            "method": "exact_field",
            "status": "rejected",
            "reason": "resolver_reason_not_strong",
            "top_match": top,
            "score_gap": score_gap,
            "matches": matches,
        }

    tied_top_matches = [
        match
        for match in matches
        if match["score"] == top["score"]
        and match["reason"] == top["reason"]
        and match.get("matched_alias") == top.get("matched_alias")
    ]
    if top["reason"] not in EXACT_REASONS_WITHOUT_GAP_CHECK and score_gap < EXACT_FIELD_MIN_GAP:
        if len(tied_top_matches) > 1:
            return {
                "method": "exact_field",
                "status": "candidate_accepted",
                "reason": "resolver_tied_exact_alias_candidates",
                "top_match": top,
                "score_gap": score_gap,
                "matches": matches,
            }
        return {
            "method": "exact_field",
            "status": "rejected",
            "reason": "resolver_candidate_ambiguous",
            "top_match": top,
            "score_gap": score_gap,
            "matches": matches,
        }

    return {
        "method": "exact_field",
        "status": "candidate_accepted",
        "reason": "resolver_candidate_confident",
        "top_match": top,
        "score_gap": score_gap,
        "matches": matches,
    }


def exact_field_is_useful(result):
    return bool(result.get("values")) and result.get("event_count", 0) > 0


def bm25_is_useful(result):
    results = result.get("results", [])
    if not results:
        return False, "no_bm25_results"

    top = results[0]
    if top.get("score", 0.0) <= 0:
        return False, "bm25_score_not_positive"
    if not top.get("matched_terms"):
        return False, "no_exact_matched_terms"

    if has_query_identifiers(result):
        if top.get("matched_identifiers"):
            return True, "exact_identifier_match"
        return False, "identifier_query_without_exact_identifier_match"

    if top["score"] >= BM25_MIN_SCORE:
        return True, "bm25_score_useful"

    exact_terms = [
        match.get("query_term", "")
        for match in top.get("matched_terms", [])
        if match.get("match_type") == "exact"
        and match.get("query_term") == match.get("matched_term")
    ]
    if any(len(term) >= BM25_LONG_EXACT_TOKEN_MIN_LENGTH for term in exact_terms):
        return True, "long_exact_free_text_match"

    return False, "bm25_score_below_threshold"


def routed_response(query, search_mode, method, route, result):
    return {
        "query": query,
        "search_mode": search_mode,
        "method": method,
        "result_count": result_count(method, result),
        "route": route,
        "thresholds": THRESHOLDS,
        "result": result,
    }


def run_exact_field_search(
    query,
    records_path=None,
    aliases_path=DEFAULT_ALIASES,
    offense_id=None,
    all_offenses=False,
    records=None,
):
    result = answer_event_question(
        query,
        records_path=records_path,
        aliases_path=aliases_path,
        offense_id=offense_id,
        all_offenses=all_offenses,
        records=records,
    )
    route = [
        {
            "method": "exact_field",
            "status": "returned",
            "reason": "direct_exact_field_mode",
        }
    ]
    return routed_response(query, "exact_field", "exact_field", route, result)


def route_metadata_text_search(
    query,
    records_path=None,
    limit=10,
    existing_route=None,
    search_mode="metadata_text",
    offense_id=None,
    all_offenses=False,
    records=None,
):
    route = list(existing_route or [])

    loaded_records = records or load_event_metadata_records(
        records_path=records_path,
        offense_id=offense_id,
        all_offenses=all_offenses,
    )
    bm25_result = search_metadata_text_bm25(query, limit=limit, records=loaded_records)
    useful, reason = bm25_is_useful(bm25_result)
    route.append(
        {
            "method": "bm25_metadata_text",
            "status": "accepted" if useful else "rejected",
            "reason": reason,
            "result_count": len(bm25_result.get("results", [])),
            "top_score": bm25_result["results"][0]["score"] if bm25_result.get("results") else 0.0,
            "query_type": bm25_result.get("query_type"),
            "query_identifiers": bm25_result.get("query_identifiers", {}),
        }
    )
    if useful:
        return routed_response(query, search_mode, "bm25_metadata_text", route, bm25_result)

    fuzzy_result = search_metadata_text_fuzzy(query, limit=limit, records=loaded_records)
    route.append(
        {
            "method": "fuzzy_metadata_text",
            "status": "returned",
            "reason": "fallback_after_bm25_weak_or_empty",
            "result_count": len(fuzzy_result.get("results", [])),
            "top_score": fuzzy_result["results"][0]["score"] if fuzzy_result.get("results") else 0.0,
            "query_type": fuzzy_result.get("query_type"),
            "query_identifiers": fuzzy_result.get("query_identifiers", {}),
        }
    )
    return routed_response(query, search_mode, "fuzzy_metadata_text", route, fuzzy_result)


def route_search(
    query,
    records_path=None,
    aliases_path=DEFAULT_ALIASES,
    limit=10,
    offense_id=None,
    all_offenses=False,
    records=None,
):
    query = query.strip()
    if not query:
        empty = {"question": query, "resolved_field": None, "values": [], "event_count": 0, "matching_event_indexes": []}
        return routed_response(query, "auto_routed", "exact_field", [], empty)

    loaded_records = records or load_event_metadata_records(
        records_path=records_path,
        offense_id=offense_id,
        all_offenses=all_offenses,
    )
    route = []
    candidate_decision = exact_field_candidate_decision(query, aliases_path=aliases_path)

    if candidate_decision["status"] != "candidate_accepted":
        route.append(candidate_decision)
        return route_metadata_text_search(
            query,
            limit=limit,
            existing_route=route,
            search_mode="auto_routed",
            records=loaded_records,
        )

    exact_result = answer_event_question(query, aliases_path=aliases_path, records=loaded_records)
    if exact_field_is_useful(exact_result):
        candidate_decision = dict(candidate_decision)
        candidate_decision["status"] = "accepted"
        candidate_decision["reason"] = "exact_field_confident_and_useful"
        candidate_decision["event_count"] = exact_result["event_count"]
        route.append(candidate_decision)
        return routed_response(query, "auto_routed", "exact_field", route, exact_result)

    candidate_decision = dict(candidate_decision)
    candidate_decision["status"] = "rejected"
    candidate_decision["reason"] = "exact_field_empty_or_not_useful"
    candidate_decision["event_count"] = exact_result["event_count"]
    route.append(candidate_decision)
    return route_metadata_text_search(
        query,
        limit=limit,
        existing_route=route,
        search_mode="auto_routed",
        records=loaded_records,
    )


def main():
    parser = argparse.ArgumentParser(description="Route analyst queries through deterministic Event Metadata search.")
    parser.add_argument("--query", required=True, help="Analyst query")
    parser.add_argument("--records", default=None, help="Path to one event metadata records JSON file")
    parser.add_argument("--offense-id", default=None, help="Search one discovered offense ID")
    parser.add_argument("--all-offenses", action="store_true", help="Search all discovered metadata files")
    parser.add_argument("--aliases", default=str(DEFAULT_ALIASES), help="Path to event field aliases JSON")
    parser.add_argument("--limit", type=int, default=10, help="Maximum number of ranked metadata text events")
    parser.add_argument(
        "--mode",
        choices=["auto", "exact", "metadata-text"],
        default="auto",
        help="Search mode to run",
    )
    args = parser.parse_args()

    if args.mode == "exact":
        result = run_exact_field_search(
            args.query,
            records_path=args.records,
            aliases_path=args.aliases,
            offense_id=args.offense_id,
            all_offenses=args.all_offenses,
        )
    elif args.mode == "metadata-text":
        result = route_metadata_text_search(
            args.query,
            records_path=args.records,
            limit=args.limit,
            offense_id=args.offense_id,
            all_offenses=args.all_offenses,
        )
    else:
        result = route_search(
            args.query,
            records_path=args.records,
            aliases_path=args.aliases,
            limit=args.limit,
            offense_id=args.offense_id,
            all_offenses=args.all_offenses,
        )

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
