#!/usr/bin/env python3
import json
import re
from copy import deepcopy
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
RECORDS_FILENAME_RE = re.compile(r"^event_metadata_records_(?P<offense_id>[^\\/]+)\.json$")


def offense_id_from_records_path(path):
    match = RECORDS_FILENAME_RE.fullmatch(Path(path).name)
    if not match:
        return None
    return match.group("offense_id")


def discover_metadata_record_files(data_dir=DATA_DIR):
    records = []
    for path in sorted(Path(data_dir).glob("event_metadata_records_*.json")):
        offense_id = offense_id_from_records_path(path)
        if offense_id is None:
            continue
        records.append({"offense_id": offense_id, "path": path})
    return records


def available_offense_ids(data_dir=DATA_DIR):
    return [record["offense_id"] for record in discover_metadata_record_files(data_dir)]


def records_path_for_offense(offense_id, data_dir=DATA_DIR):
    wanted = str(offense_id)
    for record in discover_metadata_record_files(data_dir):
        if record["offense_id"] == wanted:
            return record["path"]
    raise FileNotFoundError(f"No metadata records file found for offense {wanted!r}")


def load_records_file(path):
    records_path = Path(path)
    data = json.loads(records_path.read_text(encoding="utf-8"))
    if "events" not in data or not isinstance(data["events"], list):
        raise ValueError("Event metadata records file must contain an 'events' list")

    offense_id = str(data.get("offense_id") or offense_id_from_records_path(records_path) or "")
    for event in data["events"]:
        identity = event.setdefault("event_identity", {})
        if offense_id and not identity.get("offense_id"):
            identity["offense_id"] = offense_id
    return data


def combine_records(record_sets):
    combined_events = []
    offense_ids = []

    for records in record_sets:
        offense_id = str(records.get("offense_id") or "")
        if offense_id and offense_id not in offense_ids:
            offense_ids.append(offense_id)
        for event in records.get("events", []):
            event_copy = deepcopy(event)
            identity = event_copy.setdefault("event_identity", {})
            if offense_id and not identity.get("offense_id"):
                identity["offense_id"] = offense_id
            combined_events.append(event_copy)

    return {
        "offense_id": "all",
        "offense_ids": offense_ids,
        "event_count": len(combined_events),
        "events": combined_events,
    }


def load_all_event_metadata_records(data_dir=DATA_DIR):
    discovered = discover_metadata_record_files(data_dir)
    if not discovered:
        raise FileNotFoundError(f"No metadata record files found in {Path(data_dir)}")
    return combine_records(load_records_file(record["path"]) for record in discovered)


def load_event_metadata_records(records_path=None, offense_id=None, all_offenses=False, data_dir=DATA_DIR):
    if records_path is not None:
        return load_records_file(records_path)
    if offense_id is not None:
        return load_records_file(records_path_for_offense(offense_id, data_dir=data_dir))
    if all_offenses:
        return load_all_event_metadata_records(data_dir=data_dir)
    return load_all_event_metadata_records(data_dir=data_dir)
