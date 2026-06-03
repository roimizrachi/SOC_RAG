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

from metadata_records import load_event_metadata_records  # noqa: E402
from resolve_query_field import load_aliases, resolve  # noqa: E402


def value_items(value):
    if value is None:
        return []
    if isinstance(value, list):
        items = []
        for item in value:
            items.extend(value_items(item))
        return items
    if value == "":
        return []
    return [value]


def dedupe_values(values):
    deduped = []
    seen = set()
    for value in values:
        marker = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
        if marker not in seen:
            seen.add(marker)
            deduped.append(value)
    return deduped


def answer_event_question(
    question,
    records_path=None,
    aliases_path=DEFAULT_ALIASES,
    offense_id=None,
    all_offenses=False,
    records=None,
    top=5,
    threshold=0.25,
):
    question = question.strip()
    if not question:
        return {
            "question": question,
            "resolved_field": None,
            "values": [],
            "event_count": 0,
            "matching_event_indexes": [],
        }

    alias_map = load_aliases(aliases_path)
    matches = resolve(question, alias_map, top=top, threshold=threshold)
    if not matches:
        return {
            "question": question,
            "resolved_field": None,
            "values": [],
            "event_count": 0,
            "matching_event_indexes": [],
        }

    loaded_records = records or load_event_metadata_records(
        records_path=records_path,
        offense_id=offense_id,
        all_offenses=all_offenses,
    )
    top_empty_result = None
    candidate_results = []

    for match in matches:
        resolved_field = match["field"]
        values = []
        matching_event_indexes = []
        matching_events = []

        for fallback_index, event in enumerate(loaded_records["events"]):
            event_values = value_items(event.get("fields", {}).get(resolved_field))
            if not event_values:
                continue

            identity = event.get("event_identity", {})
            event_index = identity.get("event_index", fallback_index)
            matching_event_indexes.append(event_index)
            matching_events.append(
                {
                    "offense_id": identity.get("offense_id"),
                    "event_index": event_index,
                }
            )
            values.extend(event_values)

        result = {
            "question": question,
            "resolved_field": resolved_field,
            "resolved_fields": [resolved_field],
            "values": dedupe_values(values),
            "event_count": len(matching_event_indexes),
            "matching_event_indexes": matching_event_indexes,
            "matching_events": matching_events,
            "_resolver_match": match,
        }
        if result["event_count"] > 0:
            candidate_results.append(result)
        if top_empty_result is None:
            top_empty_result = result

    if candidate_results:
        top_score = candidate_results[0]["_resolver_match"]["score"]
        top_alias = candidate_results[0]["_resolver_match"].get("matched_alias")
        tied_results = [
            result
            for result in candidate_results
            if result["_resolver_match"]["score"] == top_score
            and result["_resolver_match"].get("matched_alias") == top_alias
        ]
        if len(tied_results) > 1:
            combined_values = []
            combined_indexes = []
            combined_events = []
            combined_fields = []
            seen_events = set()
            for result in tied_results:
                combined_fields.extend(result["resolved_fields"])
                combined_values.extend(result["values"])
                for event in result["matching_events"]:
                    marker = (event.get("offense_id"), event.get("event_index"))
                    if marker in seen_events:
                        continue
                    seen_events.add(marker)
                    combined_events.append(event)
                    combined_indexes.append(event.get("event_index"))
            return {
                "question": question,
                "resolved_field": ", ".join(combined_fields),
                "resolved_fields": combined_fields,
                "values": dedupe_values(combined_values),
                "event_count": len(combined_events),
                "matching_event_indexes": combined_indexes,
                "matching_events": combined_events,
            }

        result = dict(candidate_results[0])
        result.pop("_resolver_match", None)
        return result

    if top_empty_result is not None:
        top_empty_result.pop("_resolver_match", None)
    return top_empty_result


def display_value(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return value


def get_matching_event_rows(
    result,
    records_path=None,
    offense_id=None,
    all_offenses=False,
    records=None,
):
    loaded_records = records or load_event_metadata_records(
        records_path=records_path,
        offense_id=offense_id,
        all_offenses=all_offenses,
    )
    wanted_events = {
        (event.get("offense_id"), event.get("event_index"))
        for event in result.get("matching_events", [])
    }
    wanted_indexes = set(result["matching_event_indexes"])
    resolved_fields = result.get("resolved_fields") or [result["resolved_field"]]
    rows = []

    for fallback_index, event in enumerate(loaded_records["events"]):
        identity = event.get("event_identity", {})
        event_index = identity.get("event_index", fallback_index)
        event_key = (identity.get("offense_id"), event_index)
        if wanted_events:
            if event_key not in wanted_events:
                continue
        elif event_index not in wanted_indexes:
            continue

        fields = event.get("fields", {})
        resolved_values = {
            field_name: fields.get(field_name)
            for field_name in resolved_fields
            if value_items(fields.get(field_name))
        }
        if len(resolved_values) == 1:
            resolved_value = next(iter(resolved_values.values()))
        else:
            resolved_value = resolved_values
        row = {
            "offense_id": identity.get("offense_id"),
            "event_index": event_index,
            "event_id": identity.get("event_id"),
            "resolved_value": display_value(resolved_value),
        }
        for field_name, field_value in fields.items():
            row[field_name] = display_value(field_value)
        rows.append(row)

    return rows


def main():
    parser = argparse.ArgumentParser(description="Answer deterministic questions over Event Metadata Records.")
    parser.add_argument("--question", required=True, help="Analyst question")
    parser.add_argument("--records", default=None, help="Path to one event metadata records JSON file")
    parser.add_argument("--offense-id", default=None, help="Search one discovered offense ID")
    parser.add_argument("--all-offenses", action="store_true", help="Search all discovered metadata files")
    parser.add_argument("--aliases", default=str(DEFAULT_ALIASES), help="Path to event field aliases JSON")
    parser.add_argument("--top", type=int, default=5, help="Number of field candidates to consider")
    parser.add_argument("--threshold", type=float, default=0.25, help="Minimum resolver score")
    args = parser.parse_args()

    result = answer_event_question(
        args.question,
        records_path=args.records,
        offense_id=args.offense_id,
        all_offenses=args.all_offenses,
        aliases_path=args.aliases,
        top=args.top,
        threshold=args.threshold,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
