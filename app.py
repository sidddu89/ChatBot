import streamlit as st
import requests

API = "http://localhost:8000"

st.set_page_config(page_title="AskFirst · Clary", layout="wide")
st.title("💬 AskFirst — Clary")

# ── Cache thread list so it doesn't refetch on every rerun ───────────────────
@st.cache_data(ttl=2)
def get_threads():
    return requests.get(f"{API}/threads").json()

@st.cache_data(ttl=2)
def get_messages(thread_id):
    return requests.get(f"{API}/threads/{thread_id}/messages").json()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("🧵 Threads")

    if st.button("➕ New Thread", use_container_width=True):
        r = requests.post(f"{API}/threads", json={"title": "New Thread"})
        st.session_state["active_thread"] = r.json()["id"]
        st.cache_data.clear()
        st.rerun()

    threads = get_threads()
    for t in threads:
        is_active = st.session_state.get("active_thread") == t["id"]
        label = f"{'▶ ' if is_active else ''}{t['title']}"
        if st.button(label, key=f"thread_{t['id']}", use_container_width=True):
            st.session_state["active_thread"] = t["id"]
            st.rerun()

# ── Main chat area ────────────────────────────────────────────────────────────
thread_id = st.session_state.get("active_thread")

if not thread_id:
    st.info("👈 Create or select a thread to start chatting.")
    st.stop()

messages = get_messages(thread_id)

for msg in messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ── Input ─────────────────────────────────────────────────────────────────────
user_input = st.chat_input("Message Clary…")
if user_input:
    # Show user message immediately without waiting
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.spinner("Clary is thinking…"):
        r = requests.post(f"{API}/chat", json={
            "thread_id": thread_id,
            "message": user_input
        })

    if r.status_code == 200:
        reply = r.json()["reply"]
        with st.chat_message("assistant"):
            st.markdown(reply)
        st.cache_data.clear()  # clear cache so threads/messages refresh
        st.rerun()
    else:
        st.error(f"Error {r.status_code}: {r.text}")