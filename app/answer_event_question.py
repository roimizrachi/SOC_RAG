#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
DEFAULT_RECORDS = REPO_ROOT / "data" / "event_metadata_records_82303.json"
DEFAULT_ALIASES = REPO_ROOT / "mappings" / "event_field_aliases_v1.json"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from resolve_query_field import load_aliases, resolve  # noqa: E402


def load_event_metadata_records(path=DEFAULT_RECORDS):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if "events" not in data or not isinstance(data["events"], list):
        raise ValueError("Event metadata records file must contain an 'events' list")
    return data


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
    records_path=DEFAULT_RECORDS,
    aliases_path=DEFAULT_ALIASES,
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

    resolved_field = matches[0]["field"]
    records = load_event_metadata_records(records_path)
    values = []
    matching_event_indexes = []

    for fallback_index, event in enumerate(records["events"]):
        event_values = value_items(event.get("fields", {}).get(resolved_field))
        if not event_values:
            continue

        event_index = event.get("event_identity", {}).get("event_index", fallback_index)
        matching_event_indexes.append(event_index)
        values.extend(event_values)

    return {
        "question": question,
        "resolved_field": resolved_field,
        "values": dedupe_values(values),
        "event_count": len(matching_event_indexes),
        "matching_event_indexes": matching_event_indexes,
    }


def display_value(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return value


def get_matching_event_rows(result, records_path=DEFAULT_RECORDS):
    records = load_event_metadata_records(records_path)
    wanted_indexes = set(result["matching_event_indexes"])
    resolved_field = result["resolved_field"]
    rows = []

    for fallback_index, event in enumerate(records["events"]):
        identity = event.get("event_identity", {})
        event_index = identity.get("event_index", fallback_index)
        if event_index not in wanted_indexes:
            continue

        fields = event.get("fields", {})
        row = {
            "offense_id": identity.get("offense_id"),
            "event_index": event_index,
            "event_id": identity.get("event_id"),
            "resolved_value": display_value(fields.get(resolved_field)),
        }
        for field_name, field_value in fields.items():
            row[field_name] = display_value(field_value)
        rows.append(row)

    return rows


def main():
    parser = argparse.ArgumentParser(description="Answer deterministic questions over Event Metadata Records.")
    parser.add_argument("--question", required=True, help="Analyst question")
    parser.add_argument("--records", default=str(DEFAULT_RECORDS), help="Path to event metadata records JSON")
    parser.add_argument("--aliases", default=str(DEFAULT_ALIASES), help="Path to event field aliases JSON")
    parser.add_argument("--top", type=int, default=5, help="Number of field candidates to consider")
    parser.add_argument("--threshold", type=float, default=0.25, help="Minimum resolver score")
    args = parser.parse_args()

    result = answer_event_question(
        args.question,
        records_path=args.records,
        aliases_path=args.aliases,
        top=args.top,
        threshold=args.threshold,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
