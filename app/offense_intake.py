#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path

from metadata_records import DATA_DIR, REPO_ROOT, discover_metadata_record_files, load_event_metadata_records
from search_router import route_search, run_exact_field_search

SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from extract_event_metadata import extract_event_metadata, parse_utf8_payload  # noqa: E402


DEFAULT_MAPPING_PATH = REPO_ROOT / "mappings" / "event_metadata_mapping_v2_reviewed_fixed.json"
RAW_OFFENSE_FILENAME_RE = re.compile(r"^offense_(?P<offense_id>[^_]+).*\.json$")
SAFE_JSON_FILENAME_RE = re.compile(r"^[A-Za-z0-9_.-]+\.json$")
SPARSE_NON_EMPTY_FIELD_THRESHOLD = 8
SMOKE_QUERY_FIELDS = [
    "cisco.detection",
    "cloud_ioc.short_description",
    "normalized.name",
    "computer.hostname",
    "qradar.sourceip",
    "registry_set.app.name",
    "actions.name",
    "observables.file.name",
    "registry_set.value",
]


def relative_path(path):
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(resolved)


def add_check(report, status, check, detail):
    report["checks"].append(
        {
            "status": status,
            "check": check,
            "detail": detail,
        }
    )


def empty_upload_report():
    report = new_report()
    add_check(report, "error", "upload file", "No offense JSON file was selected.")
    report["status"] = "failed"
    return report


def new_report():
    return {
        "status": "pending",
        "offense_id": None,
        "uploaded_filename": None,
        "raw_file_path": None,
        "metadata_file_path": None,
        "event_count": 0,
        "discovered_offense_count": 0,
        "non_empty_field_min": None,
        "non_empty_field_avg": None,
        "non_empty_field_max": None,
        "checks": [],
        "smoke_results": [],
    }


def blocking_errors(report):
    return [check for check in report["checks"] if check["status"] == "error"]


def finalize_report(report):
    report["status"] = "failed" if blocking_errors(report) else "success"
    return report


def safe_uploaded_filename(upload_filename):
    filename = Path(str(upload_filename or "")).name
    if filename != upload_filename:
        return filename, "Path components were removed from the uploaded filename."
    return filename, None


def offense_id_from_filename(filename):
    match = RAW_OFFENSE_FILENAME_RE.fullmatch(filename)
    if not match:
        return None
    return match.group("offense_id")


def load_uploaded_json(upload_bytes):
    text = upload_bytes.decode("utf-8-sig")
    return json.loads(text)


def load_json_file(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json_file(path, data):
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def raw_paths_for_offense(offense_id, data_dir):
    paths = []
    for path in sorted(Path(data_dir).glob("offense_*.json")):
        match = RAW_OFFENSE_FILENAME_RE.fullmatch(path.name)
        if match and match.group("offense_id") == str(offense_id):
            paths.append(path)
    return paths


def has_value(value):
    if value is None:
        return False
    if isinstance(value, list):
        return any(has_value(item) for item in value)
    if isinstance(value, dict):
        return bool(value)
    return value != ""


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


def sample_indexes(indexes, limit=5):
    shown = indexes[:limit]
    suffix = "" if len(indexes) <= limit else f" and {len(indexes) - limit} more"
    return ", ".join(str(index) for index in shown) + suffix


def validate_uploaded_shape(report, offense_data):
    if not isinstance(offense_data, dict):
        add_check(report, "error", "json shape", "Uploaded JSON must be an object with an events list.")
        return []

    events = offense_data.get("events")
    if not isinstance(events, list):
        add_check(report, "error", "events", "Uploaded JSON is missing an events list or events is not a list.")
        return []
    if not events:
        add_check(report, "error", "events", "Uploaded JSON contains an empty events list.")
        return []

    add_check(report, "pass", "events", f"Found {len(events)} source events.")
    return events


def warn_missing_payload_ids(report, events):
    missing_indexes = []
    for event_index, event in enumerate(events):
        decoded_payload = parse_utf8_payload(event) if isinstance(event, dict) else {}
        if not decoded_payload.get("id"):
            missing_indexes.append(event_index)

    if missing_indexes:
        add_check(
            report,
            "warning",
            "missing utf8_payload.id",
            f"{len(missing_indexes)} event(s) are missing utf8_payload.id; sample indexes: {sample_indexes(missing_indexes)}.",
        )
    else:
        add_check(report, "pass", "missing utf8_payload.id", "Every source event has utf8_payload.id.")


def resolve_target_paths(report, filename, offense_id, allow_overwrite, data_dir):
    data_dir = Path(data_dir)
    uploaded_target = data_dir / filename
    metadata_target = data_dir / f"event_metadata_records_{offense_id}.json"
    existing_raw_paths = raw_paths_for_offense(offense_id, data_dir)
    raw_target = uploaded_target

    if existing_raw_paths:
        existing_names = [path.name for path in existing_raw_paths]
        if filename not in existing_names:
            detail = (
                f"Offense {offense_id} already has raw file(s): {', '.join(existing_names)}. "
                f"Uploaded filename is {filename}."
            )
            if not allow_overwrite:
                add_check(report, "error", "existing raw filename", detail)
            elif len(existing_raw_paths) == 1:
                raw_target = existing_raw_paths[0]
                add_check(
                    report,
                    "warning",
                    "existing raw filename",
                    f"{detail} Overwrite is enabled, so uploaded content will replace {existing_raw_paths[0].name}.",
                )
            else:
                add_check(report, "error", "existing raw filename", f"{detail} Multiple existing raw files make overwrite ambiguous.")
        elif uploaded_target.exists():
            detail = f"Raw offense file already exists: {relative_path(uploaded_target)}."
            if allow_overwrite:
                add_check(report, "warning", "existing raw file", f"{detail} Overwrite is enabled.")
            else:
                add_check(report, "error", "existing raw file", detail)
    elif uploaded_target.exists():
        detail = f"Raw offense file already exists: {relative_path(uploaded_target)}."
        if allow_overwrite:
            add_check(report, "warning", "existing raw file", f"{detail} Overwrite is enabled.")
        else:
            add_check(report, "error", "existing raw file", detail)

    if metadata_target.exists():
        detail = f"Existing metadata output found: {relative_path(metadata_target)}."
        if allow_overwrite:
            add_check(report, "warning", "existing metadata output", f"{detail} Overwrite is enabled.")
        else:
            add_check(report, "error", "existing metadata output", detail)
    else:
        add_check(report, "pass", "existing metadata output", "No existing metadata output for this offense ID.")

    return raw_target, metadata_target


def extract_records(offense_data, mapping_path, offense_id):
    mapping = load_json_file(mapping_path)
    events = offense_data.get("events", [])
    documents = extract_event_metadata(events, mapping, str(offense_id))
    return {
        "offense_id": str(offense_id),
        "event_count": len(documents),
        "events": documents,
    }


def validate_metadata_output(report, records, expected_event_count, offense_id):
    events = records.get("events")
    if not isinstance(events, list):
        add_check(report, "error", "metadata validation", "Generated metadata does not contain an events list.")
        return

    if str(records.get("offense_id")) != str(offense_id):
        add_check(report, "error", "metadata validation", "Generated metadata offense_id does not match the upload.")
    else:
        add_check(report, "pass", "metadata offense_id", f"Generated metadata offense_id is {offense_id}.")

    if len(events) != expected_event_count:
        add_check(
            report,
            "error",
            "metadata event count",
            f"Generated {len(events)} metadata events, expected {expected_event_count}.",
        )
    else:
        add_check(report, "pass", "metadata event count", f"Generated {len(events)} metadata events.")

    bad_identity_indexes = []
    missing_event_id_indexes = []
    duplicate_indexes = set()
    seen_indexes = set()

    for fallback_index, event in enumerate(events):
        identity = event.get("event_identity", {})
        event_index = identity.get("event_index", fallback_index)
        if identity.get("offense_id") != str(offense_id) or not isinstance(event_index, int):
            bad_identity_indexes.append(fallback_index)
        if event_index in seen_indexes:
            duplicate_indexes.add(event_index)
        seen_indexes.add(event_index)
        if identity.get("event_id") in (None, ""):
            missing_event_id_indexes.append(event_index)
        if not isinstance(event.get("fields"), dict):
            bad_identity_indexes.append(fallback_index)

    if bad_identity_indexes:
        add_check(
            report,
            "error",
            "metadata identity",
            f"Invalid metadata identity/fields at source indexes: {sample_indexes(bad_identity_indexes)}.",
        )
    else:
        add_check(report, "pass", "metadata identity", "Every metadata event has offense identity, event index, and fields.")

    if duplicate_indexes:
        add_check(report, "error", "metadata event indexes", f"Duplicate metadata event indexes: {sample_indexes(sorted(duplicate_indexes))}.")
    else:
        add_check(report, "pass", "metadata event indexes", "Metadata event indexes are unique.")

    if missing_event_id_indexes:
        add_check(
            report,
            "warning",
            "metadata event_id",
            f"{len(missing_event_id_indexes)} metadata event(s) are missing event_id; sample indexes: {sample_indexes(missing_event_id_indexes)}.",
        )
    else:
        add_check(report, "pass", "metadata event_id", "Every metadata event has event_id.")


def validate_sparse_fields(report, records):
    counts = []
    sparse_indexes = []
    for fallback_index, event in enumerate(records.get("events", [])):
        identity = event.get("event_identity", {})
        event_index = identity.get("event_index", fallback_index)
        fields = event.get("fields", {})
        non_empty_count = sum(1 for value in fields.values() if has_value(value))
        counts.append(non_empty_count)
        if non_empty_count < SPARSE_NON_EMPTY_FIELD_THRESHOLD:
            sparse_indexes.append(event_index)

    if not counts:
        return

    report["non_empty_field_min"] = min(counts)
    report["non_empty_field_avg"] = round(sum(counts) / len(counts), 2)
    report["non_empty_field_max"] = max(counts)

    if sparse_indexes:
        add_check(
            report,
            "warning",
            "sparse mapped fields",
            (
                f"{len(sparse_indexes)} event(s) have fewer than {SPARSE_NON_EMPTY_FIELD_THRESHOLD} non-empty mapped fields; "
                f"sample indexes: {sample_indexes(sparse_indexes)}."
            ),
        )
    else:
        add_check(
            report,
            "pass",
            "sparse mapped fields",
            f"Non-empty mapped fields per event: min {report['non_empty_field_min']}, avg {report['non_empty_field_avg']}, max {report['non_empty_field_max']}.",
        )


def first_smoke_query(records):
    for event in records.get("events", []):
        fields = event.get("fields", {})
        for field_name in SMOKE_QUERY_FIELDS:
            for value in flatten_values(fields.get(field_name)):
                text = str(value).strip()
                if text:
                    return field_name, text
    return None, None


def smoke_row(name, query, result):
    nested_result = result.get("result", {})
    top_result = (nested_result.get("results") or [{}])[0]
    return {
        "check": name,
        "query": query,
        "method": result.get("method"),
        "query_type": nested_result.get("query_type"),
        "result_count": result.get("result_count"),
        "top_event_index": top_result.get("event_index"),
        "top_score": top_result.get("score"),
    }


def run_smoke_checks(report, records):
    exact_result = run_exact_field_search("source ip", records=records)
    report["smoke_results"].append(smoke_row("exact source ip", "source ip", exact_result))
    exact_payload = exact_result.get("result", {})
    if exact_result.get("method") == "exact_field" and exact_payload.get("resolved_field") == "qradar.sourceip" and exact_payload.get("event_count", 0) > 0:
        add_check(report, "pass", "search smoke exact", "Exact field smoke search resolved qradar.sourceip and returned events.")
    else:
        add_check(report, "warning", "search smoke exact", "Exact field smoke search did not return source IP events.")

    field_name, query = first_smoke_query(records)
    if not query:
        add_check(report, "warning", "search smoke metadata", "No non-empty mapped field value was available for metadata text smoke search.")
        return

    routed_result = route_search(query, records=records)
    report["smoke_results"].append(smoke_row(f"metadata text {field_name}", query, routed_result))
    if routed_result.get("result_count", 0) > 0:
        add_check(
            report,
            "pass",
            "search smoke metadata",
            f"Metadata text smoke search for {field_name} returned {routed_result['result_count']} event(s).",
        )
    else:
        add_check(report, "warning", "search smoke metadata", f"Metadata text smoke search for {field_name} returned no events.")


def validate_discovery(report, offense_id, data_dir):
    discovered = discover_metadata_record_files(data_dir=data_dir)
    report["discovered_offense_count"] = len(discovered)
    discovered_ids = [record["offense_id"] for record in discovered]
    if str(offense_id) in discovered_ids:
        add_check(report, "pass", "discovery refresh", f"Offense {offense_id} is discoverable after intake.")
    else:
        add_check(report, "warning", "discovery refresh", f"Offense {offense_id} was not found by metadata discovery after intake.")


def run_offense_intake(upload_filename, upload_bytes, allow_overwrite=False, data_dir=DATA_DIR, mapping_path=DEFAULT_MAPPING_PATH):
    report = new_report()
    filename, filename_warning = safe_uploaded_filename(upload_filename)
    report["uploaded_filename"] = filename

    if filename_warning:
        add_check(report, "warning", "uploaded filename", filename_warning)
    if not SAFE_JSON_FILENAME_RE.fullmatch(filename):
        add_check(report, "error", "uploaded filename", "Uploaded file must have a safe .json filename using letters, numbers, dots, dashes, or underscores.")
        return finalize_report(report)

    offense_id = offense_id_from_filename(filename)
    if not offense_id:
        add_check(report, "error", "missing offense_id", "Could not infer offense_id from filename. Expected data/offense_<offense_id>*.json.")
        return finalize_report(report)
    report["offense_id"] = offense_id

    try:
        offense_data = load_uploaded_json(upload_bytes)
    except UnicodeDecodeError:
        add_check(report, "error", "invalid JSON", "Uploaded file is not valid UTF-8 JSON.")
        return finalize_report(report)
    except json.JSONDecodeError as exc:
        add_check(report, "error", "invalid JSON", f"Uploaded file is not valid JSON: line {exc.lineno}, column {exc.colno}.")
        return finalize_report(report)

    events = validate_uploaded_shape(report, offense_data)
    if not events:
        return finalize_report(report)

    warn_missing_payload_ids(report, events)
    raw_target, metadata_target = resolve_target_paths(report, filename, offense_id, allow_overwrite, data_dir)
    report["raw_file_path"] = relative_path(raw_target)
    report["metadata_file_path"] = relative_path(metadata_target)
    if blocking_errors(report):
        return finalize_report(report)

    try:
        write_json_file(raw_target, offense_data)
        add_check(report, "pass", "save raw offense", f"Saved uploaded offense JSON to {relative_path(raw_target)}.")

        records = extract_records(offense_data, mapping_path, offense_id)
        write_json_file(metadata_target, records)
        report["event_count"] = records["event_count"]
        add_check(report, "pass", "extract metadata", f"Extracted metadata to {relative_path(metadata_target)}.")

        loaded_records = load_event_metadata_records(records_path=metadata_target)
        validate_metadata_output(report, loaded_records, len(events), offense_id)
        validate_sparse_fields(report, loaded_records)
        validate_discovery(report, offense_id, data_dir)
        run_smoke_checks(report, loaded_records)
    except Exception as exc:
        add_check(report, "error", "intake pipeline", f"{type(exc).__name__}: {exc}")

    return finalize_report(report)
