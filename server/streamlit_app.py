from pathlib import Path
import os
import json
from datetime import datetime
from typing import List, Dict

import streamlit as st
try:
    # Optional auto-refresh helper
    from streamlit_autorefresh import st_autorefresh  # type: ignore
except Exception:  # pragma: no cover
    st_autorefresh = None

# Base path of the server directory (use absolute paths; do not change CWD to avoid Streamlit reload issues)
BASE_DIR = Path(__file__).parent.resolve()

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


st.set_page_config(page_title="Gerenciador de Cartões RFID ESP32", page_icon="🔐", layout="wide")

st.title("Gerenciador de Cartões RFID ESP32 🔐")

# Sidebar controls
with st.sidebar:
    st.header("Controles")
    auto_refresh = st.toggle("Atualizar automaticamente", value=True)
    refresh_every = st.selectbox("Intervalo de atualização (segundos)", options=[3, 5, 10, 30], index=1)
    if auto_refresh:
        if st_autorefresh:
            st_autorefresh(interval=refresh_every * 1000, key="auto_refresh")
        else:
            st.info("Pacote 'streamlit-autorefresh' não instalado. Use o botão abaixo ou desative o auto-refresh.")
            if st.button("Recarregar agora"):
                st.rerun()


tab_dashboard, tab_cards, tab_logs = st.tabs(["📊 Painel", "💳 Cartões", "🧾 Registros"]) 

with tab_dashboard:
    cards_data = _load_cards()
    cards = cards_data.get('cards', [])
    total = len(cards)
    authorized = sum(1 for c in cards if c.get('authorized'))
    denied = total - authorized

    c1, c2, c3 = st.columns(3)
    c1.metric("Total de Cartões", total)
    c2.metric("Autorizados", authorized)
    c3.metric("Negados", denied)

    st.subheader("Tentativas Recentes de Acesso")
    logs = _load_logs()
    if logs:
        # Prepare display-friendly rows
        rows = []
        for r in logs[:100]:
            rows.append({
                "Data/Hora": r.get('timestamp'),
                "ID do Cartão": r.get('card_id'),
                "Status": "AUTORIZADO" if r.get('authorized') else "NEGADO",
            })
        st.dataframe(rows, use_container_width=True, height=400)
    else:
        st.info("Ainda não há registros de acesso.")

with tab_cards:
    st.subheader("Cartões Autorizados")
    cards_data = _load_cards()
    current_cards = cards_data.get('cards', [])

    # Filter/Search
    q = st.text_input("Pesquisar por ID ou Nome", "")
    filtered = [c for c in current_cards if q.lower() in c.get('id', '').lower() or q.lower() in c.get('name', '').lower()]
    table_rows = [{"ID": c.get('id'), "Nome": c.get('name'), "Autorizado": c.get('authorized')} for c in filtered]
    st.dataframe(table_rows, use_container_width=True, height=300)

    st.divider()
    col_add, col_update = st.columns(2)

    with col_add:
        st.markdown("### Adicionar Cartão")
        with st.form("add_form", clear_on_submit=True):
            new_id = st.text_input("ID do Cartão", placeholder="ex.: 0x1a2b3c4d")
            new_name = st.text_input("Nome", placeholder="Nome do proprietário")
            new_auth = st.checkbox("Autorizado", value=True)
            submitted = st.form_submit_button("Adicionar Cartão")
        if submitted:
            if not new_id or not new_name:
                st.error("Por favor, informe o ID do Cartão e o Nome.")
            else:
                # Prevent duplicate add in UI (card_manager also checks)
                if any(c.get('id') == new_id for c in current_cards):
                    st.warning(f"O cartão {new_id} já existe.")
                else:
                    cm.add_card(new_id, new_name, new_auth)
                    st.success(f"Cartão adicionado: {new_id} ({'Autorizado' if new_auth else 'Negado'})")
                    st.rerun()

    with col_update:
        st.markdown("### Atualizar/Excluir Cartão")
        card_ids = [c.get('id') for c in current_cards]
        if not card_ids:
            st.info("Sem cartões para atualizar.")
        else:
            selected_id = st.selectbox("Selecione o ID do Cartão", options=card_ids)
            selected = next((c for c in current_cards if c.get('id') == selected_id), None)
            if selected:
                st.write(f"Nome: {selected.get('name')}")
                new_status = st.radio("Autorização", options=["Autorizado", "Negado"], index=0 if selected.get('authorized') else 1, horizontal=True)
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Salvar Status", use_container_width=True):
                        cm.update_card(selected_id, True if new_status == "Autorizado" else False)
                        st.success("Cartão atualizado.")
                        st.rerun()
                with c2:
                    if st.button("Excluir Cartão", use_container_width=True, type="primary"):
                        cm.delete_card(selected_id)
                        st.warning("Cartão excluído.")
                        st.rerun()

with tab_logs:
    st.subheader("Registros de Acesso")
    logs = _load_logs()

    colf1, colf2 = st.columns(2)
    with colf1:
        status_filter = st.selectbox("Status", options=["Todos", "Autorizado", "Negado"], index=0)
    with colf2:
        limit = st.selectbox("Mostrar os últimos N", options=[50, 100, 200, 500, 1000], index=1)

    if status_filter != "Todos":
        want = (status_filter == "Autorizado")
        logs = [r for r in logs if bool(r.get('authorized')) == want]

    rows = []
    for r in logs[:limit]:
        rows.append({
            "Data/Hora": r.get('timestamp'),
            "ID do Cartão": r.get('card_id'),
            "Status": "AUTORIZADO" if r.get('authorized') else "NEGADO",
        })

    if rows:
        st.dataframe(rows, use_container_width=True, height=500)
        if st.button("Limpar Registros"):
            # Simple clear: overwrite with empty list
            with open(ACCESS_LOG, 'w', encoding='utf-8') as f:
                json.dump([], f, indent=4)
            st.warning("Registros limpos.")
            st.rerun()
    else:
        st.info("Sem registros para exibir.")
