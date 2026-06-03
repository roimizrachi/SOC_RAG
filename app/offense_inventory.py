#!/usr/bin/env python3
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from metadata_records import DATA_DIR, REPO_ROOT, discover_metadata_record_files, offense_id_from_records_path

RAW_OFFENSE_FILENAME_RE = re.compile(r"^offense_(?P<offense_id>[^_]+).*\.json$")

INVENTORY_COLUMNS = [
    "offense_id",
    "number_of_events",
    "first_event_time",
    "last_event_time",
    "logsourceid",
    "metadata_file_path",
    "raw_offense_file_path",
]


def flatten_values(value):
    if value is None:
        return []
    if isinstance(value, list):
        values = []
        for item in value:
            values.extend(flatten_values(item))
        return values
    if value == "":
        return []
    return [value]


def relative_repo_path(path):
    return Path(path).resolve().relative_to(REPO_ROOT).as_posix()


def parse_timestamp(value):
    if value is None or value == "":
        return None

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if re.fullmatch(r"\d+(?:\.\d+)?", text):
            return parse_timestamp(float(text))
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    if isinstance(value, (int, float)):
        timestamp = float(value)
        if timestamp > 1_000_000_000_000_000_000:
            timestamp = timestamp / 1_000_000_000
        elif timestamp > 1_000_000_000_000_000:
            timestamp = timestamp / 1_000_000
        elif timestamp > 1_000_000_000_000:
            timestamp = timestamp / 1_000
        try:
            return datetime.fromtimestamp(timestamp, tz=timezone.utc)
        except (OSError, OverflowError, ValueError):
            return None

    return None


def format_timestamp(value):
    if value is None:
        return "Unknown"
    if value.microsecond:
        return value.isoformat(timespec="milliseconds")
    return value.isoformat(timespec="seconds")


def event_time(event):
    fields = event.get("fields", {})
    for field_name in ("qradar.starttime", "cisco.date"):
        for value in flatten_values(fields.get(field_name)):
            parsed = parse_timestamp(value)
            if parsed is not None:
                return parsed
    return None


def primary_logsourceid(events):
    values = []
    for event in events:
        values.extend(flatten_values(event.get("fields", {}).get("qradar.logsourceid")))

    if not values:
        return "Unknown"

    counts = Counter(str(value) for value in values)
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]


def discover_raw_offense_paths(data_dir=DATA_DIR):
    raw_paths = {}
    for path in sorted(Path(data_dir).glob("offense_*.json")):
        match = RAW_OFFENSE_FILENAME_RE.fullmatch(path.name)
        if not match:
            continue
        raw_paths.setdefault(match.group("offense_id"), []).append(path)
    return raw_paths


def raw_offense_file_path(offense_id, raw_paths):
    paths = raw_paths.get(str(offense_id), [])
    if len(paths) != 1:
        return "Unknown"
    return relative_repo_path(paths[0])


def load_metadata_file(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    events = data.get("events", [])
    if not isinstance(events, list):
        events = []
    return data, events


def offense_inventory_row(discovered_record, raw_paths):
    metadata_path = Path(discovered_record["path"])
    metadata_data, events = load_metadata_file(metadata_path)
    offense_id = str(
        metadata_data.get("offense_id")
        or discovered_record.get("offense_id")
        or offense_id_from_records_path(metadata_path)
        or ""
    )

    event_times = [time for time in (event_time(event) for event in events) if time is not None]

    return {
        "offense_id": offense_id,
        "number_of_events": len(events),
        "first_event_time": format_timestamp(min(event_times) if event_times else None),
        "last_event_time": format_timestamp(max(event_times) if event_times else None),
        "logsourceid": primary_logsourceid(events),
        "metadata_file_path": relative_repo_path(metadata_path),
        "raw_offense_file_path": raw_offense_file_path(offense_id, raw_paths),
    }


def build_offense_inventory_rows(data_dir=DATA_DIR):
    raw_paths = discover_raw_offense_paths(data_dir=data_dir)
    rows = [
        offense_inventory_row(discovered_record, raw_paths)
        for discovered_record in discover_metadata_record_files(data_dir=data_dir)
    ]
    return [{column: row[column] for column in INVENTORY_COLUMNS} for row in rows]
