#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_utf8_payload(event):
    payload = event.get("utf8_payload")
    if payload is None:
        return {}
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, str):
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            return {}
    return {}


def path_has_array(path):
    return "[]" in path


def split_path(path):
    return path.split(".")


def extract_values(current, tokens):
    if not tokens:
        return [current]

    token = tokens[0]
    rest = tokens[1:]
    is_array = token.endswith("[]")
    key = token[:-2] if is_array else token

    if isinstance(current, dict):
        if key not in current:
            return []
        value = current[key]
    else:
        return []

    if is_array:
        if not isinstance(value, list):
            return []
        results = []
        for item in value:
            results.extend(extract_values(item, rest))
        return results

    return extract_values(value, rest)


def normalize_values(values, expect_array):
    clean = [v for v in values if v is not None]

    if expect_array:
        deduped = []
        seen = set()
        for value in clean:
            marker = json.dumps(value, sort_keys=True, ensure_ascii=False)
            if marker not in seen:
                seen.add(marker)
                deduped.append(value)
        return deduped

    if not values:
        return None
    return values[0]


def extract_path(event, decoded_payload, path):
    root = {
        "event": event,
        "utf8_payload": decoded_payload,
    }
    values = extract_values(root, split_path(path))
    return normalize_values(values, path_has_array(path))


def extract_event_metadata(events, mapping, offense_id):
    documents = []

    for event_index, event in enumerate(events):
        decoded_payload = parse_utf8_payload(event)

        event_identity = {}
        for field_name, path in mapping.get("event_identity", {}).items():
            if path == "provided_by_pipeline":
                event_identity[field_name] = offense_id
            elif path == "generated_by_pipeline":
                event_identity[field_name] = event_index
            else:
                event_identity[field_name] = extract_path(event, decoded_payload, path)

        fields = {}
        for field_name, path in mapping.get("fields", {}).items():
            fields[field_name] = extract_path(event, decoded_payload, path)

        documents.append({
            "event_identity": event_identity,
            "fields": fields,
        })

    return documents


def main():
    parser = argparse.ArgumentParser(description="Extract Event Metadata Index documents from QRadar offense events.")
    parser.add_argument("--events", required=True, help="Path to offense events JSON file")
    parser.add_argument("--mapping", required=True, help="Path to event metadata mapping JSON file")
    parser.add_argument("--offense-id", required=True, help="Offense ID supplied by the pipeline")
    parser.add_argument("--output", required=True, help="Output JSON path")
    args = parser.parse_args()

    offense_data = load_json(args.events)
    mapping = load_json(args.mapping)

    events = offense_data.get("events", [])
    documents = extract_event_metadata(events, mapping, args.offense_id)

    output = {
        "offense_id": args.offense_id,
        "event_count": len(documents),
        "events": documents,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"Extracted {len(documents)} event metadata documents to {output_path}")


if __name__ == "__main__":
    main()
