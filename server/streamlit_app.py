from pathlib import Path
import os
import json
from datetime import datetime
from typing import List, Dict

import streamlit as st

# Ensure relative file paths in card_manager work regardless of run location
BASE_DIR = Path(__file__).parent
os.chdir(BASE_DIR)

import card_manager as cm  # noqa: E402

ACCESS_LOG = BASE_DIR / 'access_log.json'
CARDS_FILE = BASE_DIR / 'authorized_cards.json'


def _load_logs() -> List[Dict]:
    try:
        with open(ACCESS_LOG, 'r', encoding='utf-8') as f:
            logs = json.load(f)
            # Normalize and sort by timestamp desc
            for row in logs:
                # Ensure iso timestamp string
                if isinstance(row.get('timestamp'), str):
                    try:
                        row['_ts'] = datetime.fromisoformat(row['timestamp'])
                    except Exception:
                        row['_ts'] = None
                else:
                    row['_ts'] = None
            logs.sort(key=lambda r: r.get('_ts') or datetime.min, reverse=True)
            return logs
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _load_cards() -> Dict:
    return cm.load_cards()


def _save_cards(data: Dict) -> None:
    cm.save_cards(data)


st.set_page_config(page_title="ESP32 RFID Manager", page_icon="🔐", layout="wide")

st.title("ESP32 RFID Card Manager")

# Sidebar controls
with st.sidebar:
    st.header("Controls")
    auto_refresh = st.toggle("Auto-refresh dashboard", value=True)
    refresh_every = st.selectbox("Refresh interval (seconds)", options=[3, 5, 10, 30], index=1)
    if auto_refresh:
        st.autorefresh(interval=refresh_every * 1000, key="auto_refresh")


tab_dashboard, tab_cards, tab_logs = st.tabs(["📊 Dashboard", "💳 Manage Cards", "🧾 Logs"]) 

with tab_dashboard:
    cards_data = _load_cards()
    cards = cards_data.get('cards', [])
    total = len(cards)
    authorized = sum(1 for c in cards if c.get('authorized'))
    denied = total - authorized

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Cards", total)
    c2.metric("Authorized", authorized)
    c3.metric("Denied", denied)

    st.subheader("Recent Access Attempts")
    logs = _load_logs()
    if logs:
        # Prepare display-friendly rows
        rows = []
        for r in logs[:100]:
            rows.append({
                "Time": r.get('timestamp'),
                "Card ID": r.get('card_id'),
                "Status": "AUTHORIZED" if r.get('authorized') else "DENIED",
            })
        st.dataframe(rows, use_container_width=True, height=400)
    else:
        st.info("No access logs yet.")

with tab_cards:
    st.subheader("Authorized Cards")
    cards_data = _load_cards()
    current_cards = cards_data.get('cards', [])

    # Filter/Search
    q = st.text_input("Search by ID or Name", "")
    filtered = [c for c in current_cards if q.lower() in c.get('id', '').lower() or q.lower() in c.get('name', '').lower()]
    table_rows = [{"ID": c.get('id'), "Name": c.get('name'), "Authorized": c.get('authorized')} for c in filtered]
    st.dataframe(table_rows, use_container_width=True, height=300)

    st.divider()
    col_add, col_update = st.columns(2)

    with col_add:
        st.markdown("### Add Card")
        with st.form("add_form", clear_on_submit=True):
            new_id = st.text_input("Card ID", placeholder="e.g., 0x1a2b3c4d")
            new_name = st.text_input("Name", placeholder="Owner name")
            new_auth = st.checkbox("Authorized", value=True)
            submitted = st.form_submit_button("Add Card")
        if submitted:
            if not new_id or not new_name:
                st.error("Please provide both Card ID and Name.")
            else:
                # Prevent duplicate add in UI (card_manager also checks)
                if any(c.get('id') == new_id for c in current_cards):
                    st.warning(f"Card {new_id} already exists.")
                else:
                    cm.add_card(new_id, new_name, new_auth)
                    st.success(f"Card added: {new_id} ({'Authorized' if new_auth else 'Denied'})")
                    st.rerun()

    with col_update:
        st.markdown("### Update/Delete Card")
        card_ids = [c.get('id') for c in current_cards]
        if not card_ids:
            st.info("No cards to update.")
        else:
            selected_id = st.selectbox("Select Card ID", options=card_ids)
            selected = next((c for c in current_cards if c.get('id') == selected_id), None)
            if selected:
                st.write(f"Name: {selected.get('name')}")
                new_status = st.radio("Authorization", options=["Authorized", "Denied"], index=0 if selected.get('authorized') else 1, horizontal=True)
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Save Status", use_container_width=True):
                        cm.update_card(selected_id, True if new_status == "Authorized" else False)
                        st.success("Card updated.")
                        st.rerun()
                with c2:
                    if st.button("Delete Card", use_container_width=True, type="primary"):
                        cm.delete_card(selected_id)
                        st.warning("Card deleted.")
                        st.rerun()

with tab_logs:
    st.subheader("Access Logs")
    logs = _load_logs()

    colf1, colf2 = st.columns(2)
    with colf1:
        status_filter = st.selectbox("Status", options=["All", "Authorized", "Denied"], index=0)
    with colf2:
        limit = st.selectbox("Show last N", options=[50, 100, 200, 500, 1000], index=1)

    if status_filter != "All":
        want = (status_filter == "Authorized")
        logs = [r for r in logs if bool(r.get('authorized')) == want]

    rows = []
    for r in logs[:limit]:
        rows.append({
            "Time": r.get('timestamp'),
            "Card ID": r.get('card_id'),
            "Status": "AUTHORIZED" if r.get('authorized') else "DENIED",
        })

    if rows:
        st.dataframe(rows, use_container_width=True, height=500)
        if st.button("Clear Logs"):
            # Simple clear: overwrite with empty list
            with open(ACCESS_LOG, 'w', encoding='utf-8') as f:
                json.dump([], f, indent=4)
            st.warning("Logs cleared.")
            st.rerun()
    else:
        st.info("No logs to display.")
