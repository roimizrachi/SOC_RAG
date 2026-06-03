#!/usr/bin/env python3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
APP_DIR = REPO_ROOT / "app"
DATA_DIR = REPO_ROOT / "data"
RECORDS_PATH = DATA_DIR / "event_metadata_records_82303.json"

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from answer_event_question import answer_event_question  # noqa: E402
from search_metadata_text import search_metadata_text_bm25, search_metadata_text_fuzzy  # noqa: E402
from search_router import route_metadata_text_search, route_search, run_exact_field_search  # noqa: E402


REQUIRED_RESULT_KEYS = {
    "event_index",
    "event_id",
    "score",
    "matched_terms",
    "matched_identifiers",
    "fields",
    "method",
}


def assert_condition(condition, message):
    if not condition:
        raise AssertionError(message)


def assert_metadata_result_shape(result):
    assert_condition(result["query"], "Search result must include the original query")
    assert_condition(result["method"] in {"bm25_metadata_text", "fuzzy_metadata_text"}, "Unexpected metadata method")
    assert_condition(result["query_type"] in {"identifier_like", "free_text"}, "Unexpected query type")
    assert_condition(isinstance(result["query_identifiers"], dict), "Search result must include query identifiers")
    assert_condition(isinstance(result["results"], list), "Search result must include a results list")

    previous_score = None
    for event_result in result["results"]:
        missing = REQUIRED_RESULT_KEYS - set(event_result)
        assert_condition(not missing, f"Result missing keys: {sorted(missing)}")
        assert_condition(isinstance(event_result["event_index"], int), "event_index must be an integer")
        assert_condition(event_result["event_id"] is not None, "event_id must be present")
        assert_condition(isinstance(event_result["score"], float), "score must be a float")
        assert_condition(isinstance(event_result["matched_terms"], list), "matched_terms must be a list")
        assert_condition(isinstance(event_result["matched_identifiers"], list), "matched_identifiers must be a list")
        assert_condition(isinstance(event_result["fields"], dict), "fields must be a dict")
        if previous_score is not None:
            assert_condition(
                event_result["score"] <= previous_score,
                "Results must be ranked in descending score order",
            )
        previous_score = event_result["score"]


def assert_routed_shape(result):
    assert_condition(result["search_mode"] in {"auto_routed", "exact_field", "metadata_text"}, "Unexpected search mode")
    assert_condition(
        result["method"] in {"exact_field", "bm25_metadata_text", "fuzzy_metadata_text"},
        "Unexpected routed method",
    )
    assert_condition(isinstance(result["result_count"], int), "Routed result_count must be an integer")
    assert_condition(isinstance(result["route"], list), "Routed result must include route decisions")
    assert_condition(isinstance(result["thresholds"], dict), "Routed result must include thresholds")
    assert_condition("result" in result, "Routed result must include nested result")


def assert_metadata_query_returns(query, mode="bm25"):
    if mode == "bm25":
        result = search_metadata_text_bm25(query, records_path=RECORDS_PATH)
    else:
        result = search_metadata_text_fuzzy(query, records_path=RECORDS_PATH)
    assert_metadata_result_shape(result)
    assert_condition(result["results"], f"{mode} query should include at least one ranked event")
    return result


def validate_bm25_detection_search():
    result = assert_metadata_query_returns("Winlogon UserInit Registry Key Modification")
    terms = {match["matched_term"] for match in result["results"][0]["matched_terms"]}
    assert_condition("winlogon" in terms, "Detection query should match winlogon")
    assert_condition("userinit" in terms, "Detection query should match userinit")
    assert_condition(result["method"] == "bm25_metadata_text", "Detection search must use BM25 method")
    print("PASS BM25 detection search")


def validate_bm25_process_identifier_search():
    result = assert_metadata_query_returns("setupplatform.exe")
    top = result["results"][0]
    terms = {match["matched_term"] for match in top["matched_terms"]}
    assert_condition("setupplatform" in terms, "Process query should match setupplatform")
    assert_condition("setupplatform.exe" in top["matched_identifiers"], "Process query should exact-match file identifier")
    print("PASS BM25 process identifier search")


def validate_bm25_registry_search():
    result = assert_metadata_query_returns("CurrentVersion Winlogon USERINIT")
    terms = {match["matched_term"] for match in result["results"][0]["matched_terms"]}
    assert_condition("currentversion" in terms, "Registry query should match currentversion")
    assert_condition("winlogon" in terms, "Registry query should match winlogon")
    assert_condition("userinit" in terms, "Registry query should match userinit")
    print("PASS BM25 registry search")


def validate_fuzzy_search():
    result = assert_metadata_query_returns("setuppaltform.exe", mode="fuzzy")
    assert_condition(result["query_type"] == "identifier_like", "File-name typo should classify as identifier-like")
    fuzzy_matches = [
        match
        for match in result["results"][0]["matched_terms"]
        if match["match_type"] in {"fuzzy", "partial"}
    ]
    assert_condition(fuzzy_matches, "Typo query should include at least one fuzzy or partial match")
    assert_condition(
        any(match["matched_term"] in {"setupplatform", "setupplatform.exe"} for match in fuzzy_matches),
        "Typo query should fuzzy-match setupplatform",
    )
    assert_condition(result["method"] == "fuzzy_metadata_text", "Typo search must use fuzzy method")
    print("PASS fuzzy typo search")


def validate_free_text_partial_fuzzy_search():
    bm25_result = search_metadata_text_bm25("setup", records_path=RECORDS_PATH)
    assert_metadata_result_shape(bm25_result)
    assert_condition(bm25_result["query_type"] == "free_text", "setup should classify as free text")

    fuzzy_result = search_metadata_text_fuzzy("setup", records_path=RECORDS_PATH)
    assert_metadata_result_shape(fuzzy_result)
    assert_condition(fuzzy_result["query_type"] == "free_text", "setup fuzzy search should remain free text")
    assert_condition(fuzzy_result["results"], "Free-text setup query should return fuzzy partial matches")
    matches = fuzzy_result["results"][0]["matched_terms"]
    assert_condition(
        any(
            match["query_term"] == "setup"
            and match["matched_term"] == "setupplatform"
            and match["match_type"] == "partial"
            for match in matches
        ),
        "Free-text setup query should partial-match setupplatform",
    )

    routed = route_metadata_text_search("setup", records_path=RECORDS_PATH)
    assert_routed_shape(routed)
    assert_condition(routed["method"] == "fuzzy_metadata_text", "Free-text setup should use fuzzy fallback when BM25 is empty")
    assert_condition(routed["result"]["query_type"] == "free_text", "Routed setup query should remain free text")
    print("PASS free-text partial fuzzy search")


def validate_weak_free_text_fuzzy_suppressed():
    routed = route_search("typo", records_path=RECORDS_PATH)
    assert_routed_shape(routed)
    assert_condition(routed["method"] == "fuzzy_metadata_text", "typo should reach fuzzy fallback")
    assert_condition(routed["result_count"] == 0, "typo must not return the dataset via weak typo -> type fuzzy match")
    assert_condition(not routed["result"]["results"], "typo should have no strong metadata text result")
    print("PASS weak free-text fuzzy suppressed")


def validate_event_indexes():
    result = assert_metadata_query_returns("wcapwlistener")
    indexes = [event_result["event_index"] for event_result in result["results"]]
    assert_condition(all(isinstance(index, int) for index in indexes), "Every result must include event_index")
    assert_condition(len(indexes) == len(set(indexes)), "Returned event indexes must be unique")
    print("PASS event indexes")


def validate_identifier_exact_match():
    result = search_metadata_text_bm25("10.147.9.58", records_path=RECORDS_PATH)
    assert_metadata_result_shape(result)
    assert_condition(result["results"], "Existing IP identifier should return a BM25 result")
    top = result["results"][0]
    assert_condition(top["event_index"] == 5, "Existing IP should rank event_index 5 first")
    assert_condition("10.147.9.58" in top["matched_identifiers"], "Existing IP must be an exact identifier match")
    print("PASS identifier exact match")


def validate_hostname_exact_match():
    result = search_metadata_text_bm25("WK-MOKEDM-5342.OPENU.LAN", records_path=RECORDS_PATH, limit=10)
    assert_metadata_result_shape(result)
    assert_condition(result["query_type"] == "identifier_like", "Full hostname should classify as identifier-like")
    indexes = [event_result["event_index"] for event_result in result["results"]]
    assert_condition(indexes == [0], "Full hostname query should return only event_index 0")
    top = result["results"][0]
    assert_condition(
        "wk-mokedm-5342.openu.lan" in top["matched_identifiers"],
        "Full hostname query must exact-match the hostname identifier",
    )
    print("PASS hostname exact match")


def validate_hostname_prefix_match():
    result = search_metadata_text_bm25("WK-MOKEDM-5342", records_path=RECORDS_PATH, limit=10)
    assert_metadata_result_shape(result)
    assert_condition(result["query_type"] == "identifier_like", "Short hostname should classify as identifier-like")
    indexes = [event_result["event_index"] for event_result in result["results"]]
    assert_condition(indexes == [0], "Hostname prefix query should return only event_index 0")
    top = result["results"][0]
    assert_condition(
        "wk-mokedm-5342.openu.lan" in top["matched_identifiers"],
        "Hostname prefix query must match the full candidate hostname identifier",
    )

    hostnames = {event_result["fields"]["computer.hostname"] for event_result in result["results"]}
    blocked_hostnames = {
        "WK-MOKEDM-5341.OPENU.LAN",
        "WK-MOKEDM-5414.OPENU.LAN",
        "WK-MOKEDM-5345.OPENU.LAN",
    }
    assert_condition(not (hostnames & blocked_hostnames), "Hostname prefix query returned nearby unrelated hosts")
    print("PASS hostname prefix match")


def validate_hostname_bounded_fuzzy_match():
    routed = route_search("WK-MOKDP-5534", records_path=RECORDS_PATH)
    assert_routed_shape(routed)
    assert_condition(routed["method"] == "fuzzy_metadata_text", "Bounded hostname typo should use fuzzy fallback")
    assert_condition(routed["result_count"] == 1, "Bounded hostname typo should return one event")
    result = routed["result"]["results"][0]
    assert_condition(result["event_index"] == 5, "Bounded hostname typo should match event_index 5")
    assert_condition(
        result["fields"]["computer.hostname"] == "WK-MOKEDP-5534.OPENU.LAN",
        "Bounded hostname typo should match WK-MOKEDP-5534.OPENU.LAN",
    )
    assert_condition(
        "wk-mokedp-5534.openu.lan" in result["matched_identifiers"],
        "Bounded hostname typo should expose the matched hostname identifier",
    )
    assert_condition(
        all("5534" in identifier for identifier in result["matched_identifiers"]),
        "Bounded hostname fuzzy must preserve the numeric station segment",
    )
    print("PASS bounded hostname fuzzy match")


def validate_missing_identifier_no_weak_bm25_match():
    result = search_metadata_text_bm25("10.147.63.36", records_path=RECORDS_PATH)
    assert_metadata_result_shape(result)
    assert_condition(not result["results"], "Missing IP must not produce BM25 hits from weak fragments")

    routed = route_search("Does 10.147.63.36 appear in the offense?", records_path=RECORDS_PATH)
    assert_routed_shape(routed)
    assert_condition(routed["method"] == "fuzzy_metadata_text", "Missing IP should fall back to fuzzy result")
    assert_condition(routed["result_count"] == 0, "Missing IP should clearly show no strong match")
    print("PASS missing identifier avoids weak BM25 false positive")


def validate_nonexistent_identifiers_no_strong_match():
    hostname = route_search("WK-NOTREAL-9999", records_path=RECORDS_PATH)
    assert_routed_shape(hostname)
    assert_condition(hostname["method"] == "fuzzy_metadata_text", "Nonexistent hostname should reach fuzzy fallback")
    assert_condition(hostname["result_count"] == 0, "Nonexistent hostname should have no strong match")

    ip = route_search("192.0.2.123", records_path=RECORDS_PATH)
    assert_routed_shape(ip)
    assert_condition(ip["method"] == "fuzzy_metadata_text", "Nonexistent IP should reach fuzzy fallback")
    assert_condition(ip["result_count"] == 0, "Nonexistent IP should have no strong match")
    print("PASS nonexistent identifiers no strong match")


def validate_phase_1_exact_search():
    result = answer_event_question("What is the source ip?")
    assert_condition(result["resolved_field"] == "qradar.sourceip", "Phase 1 source IP field resolution changed")
    assert_condition(result["event_count"] > 0, "Phase 1 exact search should still return events")
    assert_condition(result["values"], "Phase 1 exact search should still return values")
    assert_condition(result["matching_event_indexes"] == list(range(10)), "Source IP exact search should return event indexes")

    direct = answer_event_question("source ip")
    assert_condition(direct["resolved_field"] == "qradar.sourceip", "source ip should resolve to qradar.sourceip")
    assert_condition(direct["matching_event_indexes"] == list(range(10)), "source ip should return matching event indexes")

    registry = answer_event_question("What registry key was modified?")
    assert_condition(registry["resolved_field"] == "registry_set.key", "Registry question should resolve to registry_set.key")
    assert_condition(registry["matching_event_indexes"] == list(range(10)), "Registry exact search should return event indexes")
    print("PASS Phase 1 exact search")


def validate_router_exact():
    source = route_search("source", records_path=RECORDS_PATH)
    assert_routed_shape(source)
    assert_condition(source["result_count"] >= 0, "source query should not crash")

    source_ip = route_search("source ip", records_path=RECORDS_PATH)
    assert_routed_shape(source_ip)
    assert_condition(source_ip["method"] == "exact_field", "source ip should prefer exact field search")
    assert_condition(source_ip["result"]["resolved_field"] == "qradar.sourceip", "source ip should resolve source IP")

    result = route_search("What is the source IP?", records_path=RECORDS_PATH)
    assert_routed_shape(result)
    assert_condition(result["search_mode"] == "auto_routed", "Default router must use auto routed mode")
    assert_condition(result["method"] == "exact_field", "Source IP question should route to exact field search")
    assert_condition(result["result"]["resolved_field"] == "qradar.sourceip", "Router exact result should resolve source IP")
    print("PASS router exact field")


def validate_router_bm25():
    result = route_search("Does setupplatform.exe appear in the offense?", records_path=RECORDS_PATH)
    assert_routed_shape(result)
    assert_condition(result["method"] == "bm25_metadata_text", "Process identifier query should route to BM25")
    assert_condition(result["result_count"] > 0, "BM25 routed query should return results")
    print("PASS router BM25 metadata text")


def validate_router_fuzzy():
    result = route_search("setuppaltform.exe", records_path=RECORDS_PATH)
    assert_routed_shape(result)
    assert_condition(result["method"] == "fuzzy_metadata_text", "Typo query should route to fuzzy fallback")
    assert_condition(result["result_count"] > 0, "Fuzzy routed query should return results")
    print("PASS router fuzzy fallback")


def validate_ui_mode_entry_points():
    exact = run_exact_field_search("What is the source IP?", records_path=RECORDS_PATH)
    assert_routed_shape(exact)
    assert_condition(exact["search_mode"] == "exact_field", "Exact UI mode should use exact_field search mode")
    assert_condition(exact["method"] == "exact_field", "Exact UI mode should use exact_field method")

    text = route_metadata_text_search("setupplatform.exe", records_path=RECORDS_PATH)
    assert_routed_shape(text)
    assert_condition(text["search_mode"] == "metadata_text", "Metadata Text UI mode should use metadata_text mode")
    assert_condition(text["method"] == "bm25_metadata_text", "Metadata Text UI mode should use BM25 when useful")

    fallback = route_metadata_text_search("setup", records_path=RECORDS_PATH)
    assert_routed_shape(fallback)
    assert_condition(
        [step["method"] for step in fallback["route"]] == ["bm25_metadata_text", "fuzzy_metadata_text"],
        "Metadata Text mode should run BM25 before fuzzy fallback",
    )
    assert_condition(fallback["method"] == "fuzzy_metadata_text", "Metadata Text setup query should use fuzzy fallback")
    print("PASS UI mode entry points")


def validate_no_duplicate_active_dataset():
    duplicates = sorted(DATA_DIR.glob("event_metadata_records_82303*.json"))
    assert_condition(
        duplicates == [RECORDS_PATH],
        "Do not create duplicate active event metadata datasets",
    )
    print("PASS no duplicate active dataset")


def main():
    validate_bm25_detection_search()
    validate_bm25_process_identifier_search()
    validate_bm25_registry_search()
    validate_fuzzy_search()
    validate_free_text_partial_fuzzy_search()
    validate_weak_free_text_fuzzy_suppressed()
    validate_event_indexes()
    validate_identifier_exact_match()
    validate_hostname_exact_match()
    validate_hostname_prefix_match()
    validate_hostname_bounded_fuzzy_match()
    validate_missing_identifier_no_weak_bm25_match()
    validate_nonexistent_identifiers_no_strong_match()
    validate_phase_1_exact_search()
    validate_router_exact()
    validate_router_bm25()
    validate_router_fuzzy()
    validate_ui_mode_entry_points()
    validate_no_duplicate_active_dataset()
    print("PASS metadata text search validation complete")


if __name__ == "__main__":
    main()
