import streamlit as st

from answer_event_question import display_value, get_matching_event_rows
from search_router import route_metadata_text_search, route_search, run_exact_field_search


MODE_AUTO = "Auto / Routed Search"
MODE_EXACT = "Exact Field Search"
MODE_TEXT = "Metadata Text Search"


st.set_page_config(page_title="Event Metadata Search", layout="wide")

st.title("Event Metadata Search")

if "search_requested" not in st.session_state:
    st.session_state["search_requested"] = False


def request_search():
    st.session_state["search_requested"] = True


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


def render_exact_result(search_result):
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
    rows = get_matching_event_rows(search_result)
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


def run_selected_mode(selected_mode, query, limit):
    if selected_mode == MODE_EXACT:
        return run_exact_field_search(query)
    if selected_mode == MODE_TEXT:
        return route_metadata_text_search(query, limit=limit)
    return route_search(query, limit=limit)


def render_search(selected_mode, query, limit):
    if not query.strip():
        st.warning("Enter a query.")
        return

    routed_result = run_selected_mode(selected_mode, query, limit)
    result = routed_result["result"]

    mode_metric, method_metric, count_metric = st.columns(3)
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
        render_exact_result(result)
    else:
        st.subheader("Ranked events")
        render_metadata_result(result)


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
    render_search(selected_mode, query, limit)
