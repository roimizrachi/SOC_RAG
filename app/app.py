import streamlit as st

from answer_event_question import answer_event_question, get_matching_event_rows


st.set_page_config(page_title="Event Metadata Search", layout="wide")

st.title("Event Metadata Search")

question = st.text_input("Question", placeholder="What is the source ip?")
ask = st.button("Ask", type="primary")

if ask:
    if not question.strip():
        st.warning("Enter a question.")
    else:
        result = answer_event_question(question)

        if result["resolved_field"] is None:
            st.warning("No matching metadata field found.")
        else:
            field_col, count_col = st.columns(2)
            field_col.text_input("Resolved field", value=result["resolved_field"], disabled=True)
            count_col.metric("Event count", result["event_count"])

            st.subheader("Values")
            if result["values"]:
                st.dataframe(
                    [{"value": value} for value in result["values"]],
                    hide_index=True,
                    use_container_width=True,
                )
            else:
                st.info("No values found.")

            st.subheader("Matching events")
            rows = get_matching_event_rows(result)
            if rows:
                st.dataframe(rows, hide_index=True, use_container_width=True)
            else:
                st.info("No matching events found.")
