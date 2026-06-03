from pathlib import Path
import sys

import streamlit as st

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import offense_inventory


st.set_page_config(page_title="Offenses Inventory", layout="wide")

st.title("Offenses Inventory")

rows = offense_inventory.build_offense_inventory_rows()

if not rows:
    st.error("No event metadata record files found.")
    st.stop()

st.metric("Discovered offenses", len(rows))
st.dataframe(
    rows,
    column_order=offense_inventory.INVENTORY_COLUMNS,
    hide_index=True,
    width="stretch",
)
