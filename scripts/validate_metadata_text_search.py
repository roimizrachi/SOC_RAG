#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
APP_DIR = REPO_ROOT / "app"
DATA_DIR = REPO_ROOT / "data"
MAPPINGS_DIR = REPO_ROOT / "mappings"
RAW_OFFENSE_RE = re.compile(r"^offense_(?P<offense_id>[^_]+).*\.json$")

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from answer_event_question import answer_event_question  # noqa: E402
from metadata_records import discover_metadata_record_files, load_event_metadata_records  # noqa: E402
from search_metadata_text import search_metadata_text_bm25, search_metadata_text_fuzzy  # noqa: E402
from search_router import route_metadata_text_search, route_search, run_exact_field_search  # noqa: E402


REQUIRED_RESULT_KEYS = {
    "offense_id",
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


def flatten_values(value):
    if value is None:
        return []
    if isinstance(value, list):
        values = []
        for item in value:
            values.extend(flatten_values(item))
        return values
    if isinstance(value, dict):
        return [value]
    if value == "":
        return []
    return [value]


def event_index(event, fallback_index):
    return event.get("event_identity", {}).get("event_index", fallback_index)


def field_values(records, field_name):
    values = []
    for event in records["events"]:
        values.extend(flatten_values(event.get("fields", {}).get(field_name)))
    return values


def field_has_value(records, field_name, expected):
    expected_text = str(expected).lower()
    return any(str(value).lower() == expected_text for value in field_values(records, field_name))


def field_contains_value(records, field_name, expected):
    expected_text = str(expected).lower()
    return any(expected_text in str(value).lower() for value in field_values(records, field_name))


def indexes_with_value(records, field_name, expected=None):
    indexes = []
    expected_text = str(expected).lower() if expected is not None else None
    for fallback_index, event in enumerate(records["events"]):
        values = flatten_values(event.get("fields", {}).get(field_name))
        if not values:
            continue
        if expected_text is None or any(str(value).lower() == expected_text for value in values):
            indexes.append(event_index(event, fallback_index))
    return indexes


def find_records(description, predicate):
    for discovered in discover_metadata_record_files():
        records = load_event_metadata_records(records_path=discovered["path"])
        if predicate(records):
            return discovered, records
    raise AssertionError(f"Could not find metadata records for {description}")


def offense_id(records):
    return str(records.get("offense_id"))


def discover_raw_offense_files():
    records = []
    for path in sorted(DATA_DIR.glob("offense_*.json")):
        match = RAW_OFFENSE_RE.fullmatch(path.name)
        if match:
            records.append({"offense_id": match.group("offense_id"), "path": path})
    return records


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
        assert_condition(event_result["offense_id"] is not None, "offense_id must be present")
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


def assert_metadata_query_returns(query, records, mode="bm25"):
    if mode == "bm25":
        result = search_metadata_text_bm25(query, records=records)
    else:
        result = search_metadata_text_fuzzy(query, records=records)
    assert_metadata_result_shape(result)
    assert_condition(result["results"], f"{mode} query should include at least one ranked event")
    return result


def validate_dynamic_discovery():
    discovered = discover_metadata_record_files()
    assert_condition(len(discovered) >= 2, "Expected at least two discovered metadata record files")
    offense_ids = [record["offense_id"] for record in discovered]
    assert_condition(len(offense_ids) == len(set(offense_ids)), "Discovered offense IDs must be unique")
    assert_condition(
        all(record["path"].name.startswith("event_metadata_records_") for record in discovered),
        "Discovered files must use the metadata records naming convention",
    )
    print("PASS dynamic metadata discovery")
    return discovered


def validate_mapping_alias_and_description_coverage():
    mapping = json.loads((MAPPINGS_DIR / "event_metadata_mapping_v2_reviewed_fixed.json").read_text(encoding="utf-8"))
    aliases = json.loads((MAPPINGS_DIR / "event_field_aliases_v1.json").read_text(encoding="utf-8"))["aliases"]
    descriptions = json.loads((MAPPINGS_DIR / "event_metadata_fields_v1.json").read_text(encoding="utf-8"))

    mapped_fields = set(mapping["fields"])
    identity_fields = set(mapping["event_identity"])
    assert_condition(mapped_fields == set(aliases), "Every mapped data field must have aliases")
    assert_condition(mapped_fields | identity_fields <= set(descriptions), "Every mapped field must have a description")
    print("PASS mapping alias and description coverage")


def validate_canonical_raw_offense_files():
    raw_files = discover_raw_offense_files()
    metadata_files = discover_metadata_record_files()
    raw_ids = [record["offense_id"] for record in raw_files]
    metadata_ids = [record["offense_id"] for record in metadata_files]

    assert_condition(raw_files, "Expected at least one canonical raw offense file under data/")
    assert_condition(len(raw_ids) == len(set(raw_ids)), "Do not create duplicate raw offense datasets")
    assert_condition(
        set(metadata_ids) <= set(raw_ids),
        "Every metadata records file must have a matching canonical raw offense file",
    )
    print("PASS canonical raw offense files")


def validate_bm25_detection_search(records):
    result = assert_metadata_query_returns("Winlogon UserInit Registry Key Modification", records)
    terms = {match["matched_term"] for match in result["results"][0]["matched_terms"]}
    assert_condition("winlogon" in terms, "Detection query should match winlogon")
    assert_condition("userinit" in terms, "Detection query should match userinit")
    assert_condition(result["method"] == "bm25_metadata_text", "Detection search must use BM25 method")
    print("PASS BM25 detection search")


def validate_bm25_process_identifier_search(records):
    result = assert_metadata_query_returns("setupplatform.exe", records)
    top = result["results"][0]
    terms = {match["matched_term"] for match in top["matched_terms"]}
    assert_condition("setupplatform" in terms, "Process query should match setupplatform")
    assert_condition("setupplatform.exe" in top["matched_identifiers"], "Process query should exact-match file identifier")
    print("PASS BM25 process identifier search")


def validate_bm25_registry_search(records):
    result = assert_metadata_query_returns("CurrentVersion Winlogon USERINIT", records)
    terms = {match["matched_term"] for match in result["results"][0]["matched_terms"]}
    assert_condition("currentversion" in terms, "Registry query should match currentversion")
    assert_condition("winlogon" in terms, "Registry query should match winlogon")
    assert_condition("userinit" in terms, "Registry query should match userinit")
    print("PASS BM25 registry search")


def validate_fuzzy_search(records):
    result = assert_metadata_query_returns("setuppaltform.exe", records, mode="fuzzy")
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


def validate_free_text_partial_fuzzy_search(records):
    bm25_result = search_metadata_text_bm25("setup", records=records)
    assert_metadata_result_shape(bm25_result)
    assert_condition(bm25_result["query_type"] == "free_text", "setup should classify as free text")

    fuzzy_result = search_metadata_text_fuzzy("setup", records=records)
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

    routed = route_metadata_text_search("setup", records=records)
    assert_routed_shape(routed)
    assert_condition(routed["method"] == "fuzzy_metadata_text", "Free-text setup should use fuzzy fallback")
    assert_condition(routed["result"]["query_type"] == "free_text", "Routed setup query should remain free text")
    print("PASS free-text partial fuzzy search")


def validate_weak_free_text_fuzzy_suppressed(records):
    routed = route_search("typo", records=records)
    assert_routed_shape(routed)
    assert_condition(routed["method"] == "fuzzy_metadata_text", "typo should reach fuzzy fallback")
    assert_condition(routed["result_count"] == 0, "typo must not return the dataset via weak typo -> type fuzzy match")
    assert_condition(not routed["result"]["results"], "typo should have no strong metadata text result")
    print("PASS weak free-text fuzzy suppressed")


def validate_event_indexes(records):
    result = assert_metadata_query_returns("wcapwlistener", records)
    indexes = [event_result["event_index"] for event_result in result["results"]]
    assert_condition(all(isinstance(index, int) for index in indexes), "Every result must include event_index")
    assert_condition(len(indexes) == len(set(indexes)), "Returned event indexes must be unique")
    print("PASS event indexes")


def validate_identifier_exact_match(records):
    result = search_metadata_text_bm25("10.147.9.58", records=records)
    assert_metadata_result_shape(result)
    assert_condition(result["results"], "Existing IP identifier should return a BM25 result")
    expected_indexes = indexes_with_value(records, "computer.network_ips", "10.147.9.58")
    assert_condition(expected_indexes, "Baseline records must include the expected IP")
    top = result["results"][0]
    assert_condition(top["event_index"] == expected_indexes[0], "Existing IP should rank the matching event first")
    assert_condition("10.147.9.58" in top["matched_identifiers"], "Existing IP must be an exact identifier match")
    print("PASS identifier exact match")


def validate_hostname_exact_match(records):
    result = search_metadata_text_bm25("WK-MOKEDM-5342.OPENU.LAN", records=records, limit=10)
    assert_metadata_result_shape(result)
    assert_condition(result["query_type"] == "identifier_like", "Full hostname should classify as identifier-like")
    indexes = [event_result["event_index"] for event_result in result["results"]]
    expected_indexes = indexes_with_value(records, "computer.hostname", "WK-MOKEDM-5342.OPENU.LAN")
    assert_condition(indexes == expected_indexes, "Full hostname query should return only the exact hostname event")
    top = result["results"][0]
    assert_condition(
        "wk-mokedm-5342.openu.lan" in top["matched_identifiers"],
        "Full hostname query must exact-match the hostname identifier",
    )
    print("PASS hostname exact match")


def validate_hostname_prefix_match(records):
    result = search_metadata_text_bm25("WK-MOKEDM-5342", records=records, limit=10)
    assert_metadata_result_shape(result)
    assert_condition(result["query_type"] == "identifier_like", "Short hostname should classify as identifier-like")
    indexes = [event_result["event_index"] for event_result in result["results"]]
    expected_indexes = indexes_with_value(records, "computer.hostname", "WK-MOKEDM-5342.OPENU.LAN")
    assert_condition(indexes == expected_indexes, "Hostname prefix query should return only the matching event")
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


def validate_hostname_bounded_fuzzy_match(records):
    routed = route_search("WK-MOKDP-5534", records=records)
    assert_routed_shape(routed)
    assert_condition(routed["method"] == "fuzzy_metadata_text", "Bounded hostname typo should use fuzzy fallback")
    assert_condition(routed["result_count"] == 1, "Bounded hostname typo should return one event")
    result = routed["result"]["results"][0]
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


def validate_missing_identifier_no_weak_bm25_match(records):
    result = search_metadata_text_bm25("10.147.63.36", records=records)
    assert_metadata_result_shape(result)
    assert_condition(not result["results"], "Missing IP must not produce BM25 hits from weak fragments")

    routed = route_search("Does 10.147.63.36 appear in the offense?", records=records)
    assert_routed_shape(routed)
    assert_condition(routed["method"] == "fuzzy_metadata_text", "Missing IP should fall back to fuzzy result")
    assert_condition(routed["result_count"] == 0, "Missing IP should clearly show no strong match")
    print("PASS missing identifier avoids weak BM25 false positive")


def validate_nonexistent_identifiers_no_strong_match(records):
    hostname = route_search("WK-NOTREAL-9999", records=records)
    assert_routed_shape(hostname)
    assert_condition(hostname["method"] == "fuzzy_metadata_text", "Nonexistent hostname should reach fuzzy fallback")
    assert_condition(hostname["result_count"] == 0, "Nonexistent hostname should have no strong match")

    ip = route_search("192.0.2.123", records=records)
    assert_routed_shape(ip)
    assert_condition(ip["method"] == "fuzzy_metadata_text", "Nonexistent IP should reach fuzzy fallback")
    assert_condition(ip["result_count"] == 0, "Nonexistent IP should have no strong match")
    print("PASS nonexistent identifiers no strong match")


def validate_phase_1_exact_search(records):
    expected_source_indexes = indexes_with_value(records, "qradar.sourceip")
    result = answer_event_question("What is the source ip?", records=records)
    assert_condition(result["resolved_field"] == "qradar.sourceip", "Phase 1 source IP field resolution changed")
    assert_condition(result["event_count"] > 0, "Phase 1 exact search should still return events")
    assert_condition(result["values"], "Phase 1 exact search should still return values")
    assert_condition(result["matching_event_indexes"] == expected_source_indexes, "Source IP exact search indexes changed")

    direct = answer_event_question("source ip", records=records)
    assert_condition(direct["resolved_field"] == "qradar.sourceip", "source ip should resolve to qradar.sourceip")
    assert_condition(direct["matching_event_indexes"] == expected_source_indexes, "source ip should return matching event indexes")

    registry = answer_event_question("What registry key was modified?", records=records)
    assert_condition(registry["resolved_field"] == "registry_set.key", "Registry question should resolve to registry_set.key")
    assert_condition(registry["matching_event_indexes"] == indexes_with_value(records, "registry_set.key"), "Registry exact indexes changed")
    print("PASS Phase 1 exact search")


def validate_router_exact(records):
    source = route_search("source", records=records)
    assert_routed_shape(source)
    assert_condition(source["result_count"] >= 0, "source query should not crash")

    source_ip = route_search("source ip", records=records)
    assert_routed_shape(source_ip)
    assert_condition(source_ip["method"] == "exact_field", "source ip should prefer exact field search")
    assert_condition(source_ip["result"]["resolved_field"] == "qradar.sourceip", "source ip should resolve source IP")

    result = route_search("What is the source IP?", records=records)
    assert_routed_shape(result)
    assert_condition(result["search_mode"] == "auto_routed", "Default router must use auto routed mode")
    assert_condition(result["method"] == "exact_field", "Source IP question should route to exact field search")
    assert_condition(result["result"]["resolved_field"] == "qradar.sourceip", "Router exact result should resolve source IP")
    print("PASS router exact field")


def validate_router_bm25(records):
    result = route_search("Does setupplatform.exe appear in the offense?", records=records)
    assert_routed_shape(result)
    assert_condition(result["method"] == "bm25_metadata_text", "Process identifier query should route to BM25")
    assert_condition(result["result_count"] > 0, "BM25 routed query should return results")
    assert_condition(
        result["route"][0]["reason"] == "identifier_query_skips_exact_field",
        "Identifier queries must skip exact-field routing",
    )
    print("PASS router BM25 metadata text")


def validate_router_fuzzy(records):
    result = route_search("setuppaltform.exe", records=records)
    assert_routed_shape(result)
    assert_condition(result["method"] == "fuzzy_metadata_text", "Typo query should route to fuzzy fallback")
    assert_condition(result["result_count"] > 0, "Fuzzy routed query should return results")
    print("PASS router fuzzy fallback")


def validate_ui_mode_entry_points(records):
    exact = run_exact_field_search("What is the source IP?", records=records)
    assert_routed_shape(exact)
    assert_condition(exact["search_mode"] == "exact_field", "Exact UI mode should use exact_field search mode")
    assert_condition(exact["method"] == "exact_field", "Exact UI mode should use exact_field method")

    text = route_metadata_text_search("setupplatform.exe", records=records)
    assert_routed_shape(text)
    assert_condition(text["search_mode"] == "metadata_text", "Metadata Text UI mode should use metadata_text mode")
    assert_condition(text["method"] == "bm25_metadata_text", "Metadata Text UI mode should use BM25 when useful")

    fallback = route_metadata_text_search("setup", records=records)
    assert_routed_shape(fallback)
    assert_condition(
        [step["method"] for step in fallback["route"]] == ["bm25_metadata_text", "fuzzy_metadata_text"],
        "Metadata Text mode should run BM25 before fuzzy fallback",
    )
    assert_condition(fallback["method"] == "fuzzy_metadata_text", "Metadata Text setup query should use fuzzy fallback")
    print("PASS UI mode entry points")


def validate_new_offense_exact_search(records):
    source = run_exact_field_search("source ip", records=records)
    assert_routed_shape(source)
    assert_condition(source["method"] == "exact_field", "New source IP exact search should use exact field")
    assert_condition(source["result"]["resolved_field"] == "qradar.sourceip", "New source IP should resolve qradar.sourceip")

    command = run_exact_field_search("command line", records=records)
    assert_routed_shape(command)
    assert_condition(command["method"] == "exact_field", "New command line exact search should use exact field")
    assert_condition(
        command["result"]["resolved_field"] == "registry_set.cmd_line",
        "New command line exact search should fall through to registry_set.cmd_line",
    )
    assert_condition(
        any("codex-windows-sandbox-setup.exe" in str(value).lower() for value in command["result"]["values"]),
        "New command line exact search should expose the registry-set command line",
    )

    registry_value = run_exact_field_search("modified registry value", records=records)
    assert_routed_shape(registry_value)
    assert_condition(registry_value["result"]["resolved_field"] == "registry_set.value", "Registry value should resolve")
    assert_condition(set(registry_value["result"]["values"]) >= {"CodexSandboxOnline", "CodexSandboxOffline"}, "Registry values should be extracted")
    print("PASS new offense exact search")


def validate_new_offense_metadata_search(records):
    detection = assert_metadata_query_returns("Hidden User Created", records)
    assert_condition(detection["query_type"] == "free_text", "Detection query should classify as free text")

    online = search_metadata_text_bm25("CodexSandboxOnline", records=records)
    assert_metadata_result_shape(online)
    assert_condition(len(online["results"]) == 1, "Online registry value should return one event")
    assert_condition(online["results"][0]["event_index"] in indexes_with_value(records, "registry_set.value", "CodexSandboxOnline"), "Online value should match its event")

    offline = search_metadata_text_bm25("CodexSandboxOffline", records=records)
    assert_metadata_result_shape(offline)
    assert_condition(len(offline["results"]) == 1, "Offline registry value should return one event")
    assert_condition(offline["results"][0]["event_index"] in indexes_with_value(records, "registry_set.value", "CodexSandboxOffline"), "Offline value should match its event")

    process = route_search("codex-windows-sandbox-setup.exe", records=records)
    assert_routed_shape(process)
    assert_condition(process["method"] == "bm25_metadata_text", "New process identifier should route to BM25")
    assert_condition(process["result_count"] == len(indexes_with_value(records, "registry_set.app.name", "codex-windows-sandbox-setup.exe")), "New process query should return matching events")
    assert_condition(process["route"][0]["reason"] == "identifier_query_skips_exact_field", "Identifier query must skip exact field")

    hash_result = route_search("3f1377fc199edf10b213dc52f20b4c273848ddc108d8a017d080607bc5d7284f", records=records)
    assert_routed_shape(hash_result)
    assert_condition(hash_result["method"] == "bm25_metadata_text", "New hash identifier should route to BM25")
    assert_condition(hash_result["result_count"] > 0, "New hash query should return matching events")

    missing_ip = route_search("10.149.99.99", records=records)
    assert_routed_shape(missing_ip)
    assert_condition(missing_ip["result_count"] == 0, "Missing new-offense IP must not match weak fragments")
    print("PASS new offense metadata search")


def validate_specific_and_cross_offense_search(legacy_records, new_records):
    legacy_id = offense_id(legacy_records)
    new_id = offense_id(new_records)
    assert_condition(legacy_id != new_id, "Fixture offense IDs should be distinct")

    specific_new = route_search("CodexSandboxOnline", offense_id=new_id)
    assert_routed_shape(specific_new)
    assert_condition(specific_new["result_count"] == 1, "Specific new-offense search should return its event")
    assert_condition(
        {result["offense_id"] for result in specific_new["result"]["results"]} == {new_id},
        "Specific new-offense search leaked another offense",
    )

    no_leak_legacy = route_search("CodexSandboxOnline", offense_id=legacy_id)
    assert_routed_shape(no_leak_legacy)
    assert_condition(no_leak_legacy["result_count"] == 0, "Specific legacy search should not return new-offense values")

    no_leak_new = route_search("setupplatform.exe", offense_id=new_id)
    assert_routed_shape(no_leak_new)
    assert_condition(
        no_leak_new["result_count"] == 0,
        "Specific new-offense search should not fuzzy-match unrelated setup filename fragments",
    )

    cross_new = route_search("Hidden User Created", all_offenses=True)
    assert_routed_shape(cross_new)
    assert_condition(cross_new["result_count"] >= len(new_records["events"]), "Cross-offense search should find new offense events")
    assert_condition(
        new_id in {result["offense_id"] for result in cross_new["result"]["results"]},
        "Cross-offense result must include the new offense ID",
    )

    cross_legacy = route_search("setupplatform.exe", all_offenses=True)
    assert_routed_shape(cross_legacy)
    assert_condition(cross_legacy["result_count"] > 0, "Cross-offense search should find legacy process events")
    assert_condition(
        legacy_id in {result["offense_id"] for result in cross_legacy["result"]["results"]},
        "Cross-offense result must include the legacy offense ID",
    )
    print("PASS specific-offense and cross-offense search")


def validate_no_duplicate_active_dataset():
    discovered = discover_metadata_record_files()
    offense_ids = [record["offense_id"] for record in discovered]
    assert_condition(len(offense_ids) == len(set(offense_ids)), "Do not create duplicate active metadata datasets")
    print("PASS no duplicate active dataset")


def main():
    validate_dynamic_discovery()
    validate_mapping_alias_and_description_coverage()
    validate_canonical_raw_offense_files()

    _, legacy_records = find_records(
        "Phase 2 baseline data",
        lambda records: field_has_value(records, "registry_set.app.name", "setupplatform.exe")
        and field_has_value(records, "registry_set.value", "USERINIT"),
    )
    _, new_records = find_records(
        "new hidden-user data",
        lambda records: field_has_value(records, "cisco.detection", "Hidden User Created")
        and field_has_value(records, "registry_set.value", "CodexSandboxOnline"),
    )

    validate_bm25_detection_search(legacy_records)
    validate_bm25_process_identifier_search(legacy_records)
    validate_bm25_registry_search(legacy_records)
    validate_fuzzy_search(legacy_records)
    validate_free_text_partial_fuzzy_search(legacy_records)
    validate_weak_free_text_fuzzy_suppressed(legacy_records)
    validate_event_indexes(legacy_records)
    validate_identifier_exact_match(legacy_records)
    validate_hostname_exact_match(legacy_records)
    validate_hostname_prefix_match(legacy_records)
    validate_hostname_bounded_fuzzy_match(legacy_records)
    validate_missing_identifier_no_weak_bm25_match(legacy_records)
    validate_nonexistent_identifiers_no_strong_match(legacy_records)
    validate_phase_1_exact_search(legacy_records)
    validate_router_exact(legacy_records)
    validate_router_bm25(legacy_records)
    validate_router_fuzzy(legacy_records)
    validate_ui_mode_entry_points(legacy_records)
    validate_new_offense_exact_search(new_records)
    validate_new_offense_metadata_search(new_records)
    validate_specific_and_cross_offense_search(legacy_records, new_records)
    validate_no_duplicate_active_dataset()
    print("PASS metadata text search validation complete")


if __name__ == "__main__":
    main()
