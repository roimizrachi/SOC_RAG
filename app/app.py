import importlib

import streamlit as st

import answer_event_question
import metadata_records
import offense_intake
import search_metadata_text
import search_router

metadata_records = importlib.reload(metadata_records)
answer_event_question = importlib.reload(answer_event_question)
offense_intake = importlib.reload(offense_intake)
search_metadata_text = importlib.reload(search_metadata_text)
search_router = importlib.reload(search_router)

display_value = answer_event_question.display_value
get_matching_event_rows = answer_event_question.get_matching_event_rows
discover_metadata_record_files = metadata_records.discover_metadata_record_files
load_event_metadata_records = metadata_records.load_event_metadata_records
route_metadata_text_search = search_router.route_metadata_text_search
route_search = search_router.route_search
run_exact_field_search = search_router.run_exact_field_search


MODE_AUTO = "Auto / Routed Search"
MODE_EXACT = "Exact Field Search"
MODE_TEXT = "Metadata Text Search"
SCOPE_SPECIFIC = "Search inside a specific offense"
SCOPE_ALL = "Search across all offenses"


st.set_page_config(page_title="Event Metadata Search", layout="wide")

st.title("Event Metadata Search")

if "search_requested" not in st.session_state:
    st.session_state["search_requested"] = False

if "intake_report" not in st.session_state:
    st.session_state["intake_report"] = None


def request_search():
    st.session_state["search_requested"] = True


def status_icon(status):
    if status == "pass":
        return "OK"
    if status == "warning":
        return "WARNING"
    if status == "error":
        return "ERROR"
    return status.upper()


def intake_check_rows(report):
    return [
        {
            "status": status_icon(check["status"]),
            "check": check["check"],
            "detail": check["detail"],
        }
        for check in report.get("checks", [])
    ]


def render_intake_report(report):
    if not report:
        return

    if report["status"] == "success":
        st.success(f"Intake completed for offense {report.get('offense_id')}.")
    else:
        st.error("Intake did not complete.")

    metric_cols = st.columns(4)
    metric_cols[0].metric("Offense ID", report.get("offense_id") or "Unknown")
    metric_cols[1].metric("Source events", report.get("event_count", 0))
    metric_cols[2].metric("Discovered offenses", report.get("discovered_offense_count", 0))
    metric_cols[3].metric("Avg non-empty fields", report.get("non_empty_field_avg") or "Unknown")

    path_rows = [
        {"path_type": "uploaded filename", "path": report.get("uploaded_filename") or "Unknown"},
        {"path_type": "raw offense file", "path": report.get("raw_file_path") or "Not written"},
        {"path_type": "metadata output", "path": report.get("metadata_file_path") or "Not written"},
    ]
    st.dataframe(path_rows, hide_index=True, width="stretch")

    st.subheader("Intake checks")
    st.dataframe(intake_check_rows(report), hide_index=True, width="stretch")

    if report.get("smoke_results"):
        st.subheader("Smoke search results")
        st.dataframe(report["smoke_results"], hide_index=True, width="stretch")


def render_intake_panel():
    with st.expander("Offense Intake", expanded=False):
        uploaded_file = st.file_uploader(
            "Upload offense JSON",
            type=["json"],
            accept_multiple_files=False,
            key="offense_intake_upload",
        )
        allow_overwrite = st.checkbox(
            "Allow overwrite for an existing raw offense file or metadata output",
            value=False,
            key="offense_intake_allow_overwrite",
        )

        if st.button("Run intake", type="secondary", key="run_offense_intake"):
            if uploaded_file is None:
                st.session_state["intake_report"] = offense_intake.empty_upload_report()
            else:
                st.session_state["intake_report"] = offense_intake.run_offense_intake(
                    uploaded_file.name,
                    uploaded_file.getvalue(),
                    allow_overwrite=allow_overwrite,
                )

        render_intake_report(st.session_state["intake_report"])


def format_matched_terms(matches):
    formatted = []
    for match in matches:
        query_term = match["query_term"]
        matched_term = match["matched_term"]
        match_type = match["match_type"]
        if query_term == matched_term:
            formatted.append(f"{matched_term} ({match_type})")
        else:
            formatted.append(f"{query_term} -> {matched_term} ({match_type})")
    return ", ".join(formatted)


def route_rows(route):
    rows = []
    for step_number, step in enumerate(route, start=1):
        row = {"step": step_number}
        for key, value in step.items():
            row[key] = display_value(value)
        rows.append(row)
    return rows


def metadata_result_rows(search_result):
    rows = []
    for rank, event_result in enumerate(search_result.get("results", []), start=1):
        row = {
            "rank": rank,
            "offense_id": event_result.get("offense_id"),
            "event_index": event_result["event_index"],
            "event_id": event_result["event_id"],
            "score": event_result["score"],
            "matched_terms": format_matched_terms(event_result["matched_terms"]),
            "matched_identifiers": display_value(event_result.get("matched_identifiers", [])),
        }
        for field_name, field_value in event_result["fields"].items():
            row[field_name] = display_value(field_value)
        rows.append(row)
    return rows


def render_exact_result(search_result, records):
    if search_result["resolved_field"] is None:
        st.warning("No matching metadata field found.")
        return

    field_col, count_col = st.columns(2)
    field_col.text_input("Resolved field", value=search_result["resolved_field"], disabled=True)
    count_col.metric("Exact event count", search_result["event_count"])

    st.subheader("Values")
    if search_result["values"]:
        st.dataframe(
            [{"value": value} for value in search_result["values"]],
            hide_index=True,
            use_container_width=True,
        )
    else:
        st.info("No values found.")

    st.subheader("Matching events")
    rows = get_matching_event_rows(search_result, records=records)
    if rows:
        st.dataframe(rows, hide_index=True, use_container_width=True)
    else:
        st.info("No matching events found.")


def render_metadata_result(search_result):
    rows = metadata_result_rows(search_result)
    if rows:
        st.dataframe(rows, hide_index=True, use_container_width=True)
    else:
        st.info("No strong metadata text match found.")


def run_selected_mode(selected_mode, query, limit, records):
    if selected_mode == MODE_EXACT:
        return run_exact_field_search(query, records=records)
    if selected_mode == MODE_TEXT:
        return route_metadata_text_search(query, limit=limit, records=records)
    return route_search(query, limit=limit, records=records)


def render_search(selected_scope, selected_offense_id, selected_mode, query, limit, records):
    if not query.strip():
        st.warning("Enter a query.")
        return

    routed_result = run_selected_mode(selected_mode, query, limit, records)
    result = routed_result["result"]

    scope_metric, mode_metric, method_metric, count_metric = st.columns(4)
    scope_value = selected_scope if selected_scope == SCOPE_ALL else f"{selected_scope}: {selected_offense_id}"
    scope_metric.text_input("Selected search scope", value=scope_value, disabled=True)
    mode_metric.text_input("Selected search mode", value=selected_mode, disabled=True)
    method_metric.text_input("Method actually used", value=routed_result["method"], disabled=True)
    count_metric.metric("Result count", routed_result["result_count"])

    if "query_type" in result:
        st.text_input("Query type", value=result["query_type"], disabled=True)

    st.subheader("Route decisions")
    rows = route_rows(routed_result["route"])
    if rows:
        st.dataframe(rows, hide_index=True, use_container_width=True)
    else:
        st.info("No route decisions recorded.")

    if routed_result["method"] == "exact_field":
        render_exact_result(result, records)
    else:
        st.subheader("Ranked events")
        render_metadata_result(result)


render_intake_panel()

available_records = discover_metadata_record_files()

if not available_records:
    st.error("No event metadata record files found.")
    st.stop()

scope_col, offense_col = st.columns([3, 2])
selected_scope = scope_col.radio(
    "Search scope",
    [SCOPE_SPECIFIC, SCOPE_ALL],
    index=0,
    horizontal=True,
    key="selected_search_scope",
)

selected_offense_id = None
if selected_scope == SCOPE_SPECIFIC:
    offense_options = [record["offense_id"] for record in available_records]
    selected_offense_id = offense_col.selectbox("Offense ID", offense_options, index=0, key="selected_offense_id")
    active_records = load_event_metadata_records(offense_id=selected_offense_id)
else:
    offense_col.text_input("Offense ID", value="All discovered offenses", disabled=True)
    active_records = load_event_metadata_records(all_offenses=True)

mode_col, limit_col = st.columns([3, 1])
selected_mode = mode_col.selectbox(
    "Search mode",
    [MODE_AUTO, MODE_EXACT, MODE_TEXT],
    index=0,
    key="selected_search_mode",
)
limit = limit_col.number_input("Result limit", min_value=1, max_value=10, value=10, step=1, key="result_limit")

query = st.text_input(
    "Analyst query",
    placeholder="What is the source IP?",
    key="analyst_query",
    on_change=request_search,
)
st.button("Search", type="primary", on_click=request_search)

if st.session_state["search_requested"]:
    st.session_state["search_requested"] = False
    render_search(selected_scope, selected_offense_id, selected_mode, query, limit, active_records)
