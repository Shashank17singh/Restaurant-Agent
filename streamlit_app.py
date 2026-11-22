"""
Streamlit UI for the AI Restaurant Order Agent.
Manages chat session state, order status tracking, and communicates with the FastAPI backend.
Architecture note: Separates frontend concerns from agent logic running on the FastAPI backend.
"""

import uuid

import requests
import streamlit as st

DEFAULT_API_URL = "https://restaurant-agent-oarq.onrender.com/chat"

st.set_page_config(page_title="Restaurant Order Console", layout="centered")

CUSTOM_CSS = """
<style>
/* Hallmark & UI/UX Pro Max Design System · Modern Dining Console
 * Theme: Deep Slate Neutral (#0d1117) with Warm Terracotta Accent (#e05638)
 */
:root {
  --bg-canvas: #0d1117;
  --bg-surface: #161b22;
  --bg-surface-elevated: #21262d;
  --border-subtle: rgba(255, 255, 255, 0.08);
  --border-default: #30363d;
  --border-focus: #e05638;
  --text-primary: #f0f6fc;
  --text-secondary: #8b949e;
  --accent-primary: #e05638;
  --accent-hover: #c9462a;
  --accent-success: #10b981;
  --radius-sm: 4px;
  --radius-md: 8px;
  --radius-lg: 12px;
}

.stApp {
  background-color: var(--bg-canvas) !important;
  color: var(--text-primary) !important;
}

[data-testid="stHeader"] {
  background: transparent !important;
}

/* Chat bubble styling */
[data-testid="stChatMessage"] {
  background-color: var(--bg-surface) !important;
  border: 1px solid var(--border-subtle) !important;
  border-radius: var(--radius-md) !important;
  padding: 1rem 1.25rem !important;
  margin-bottom: 0.75rem !important;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2) !important;
}

/* Sidebar */
[data-testid="stSidebar"] {
  background-color: var(--bg-surface) !important;
  border-right: 1px solid var(--border-subtle) !important;
}

/* Order status badge */
.status-pill {
  display: inline-block;
  padding: 0.25rem 0.65rem;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.5rem;
}

.status-new {
  background-color: rgba(59, 130, 246, 0.12);
  border: 1px solid rgba(59, 130, 246, 0.3);
  color: #60a5fa;
}

.status-done {
  background-color: rgba(16, 185, 129, 0.12);
  border: 1px solid rgba(16, 185, 129, 0.3);
  color: #34d399;
}

.status-failed {
  background-color: rgba(239, 68, 68, 0.12);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: #f87171;
}

.menu-badge {
  display: inline-block;
  background-color: rgba(224, 86, 56, 0.12);
  border: 1px solid rgba(224, 86, 56, 0.3);
  color: #f87171;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 0.2rem 0.6rem;
  border-radius: 9999px;
  margin-bottom: 0.5rem;
}

/* Buttons */
.stButton > button {
  background-color: var(--bg-surface-elevated) !important;
  border: 1px solid var(--border-default) !important;
  color: var(--text-primary) !important;
  border-radius: var(--radius-sm) !important;
  font-weight: 500 !important;
}

.stButton > button:hover {
  background-color: #30363d !important;
  border-color: var(--text-secondary) !important;
}
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []
if "status" not in st.session_state:
    st.session_state.status = "new"
if "final_result" not in st.session_state:
    st.session_state.final_result = None

status_class = "status-done" if st.session_state.status == "done" else (
    "status-failed" if st.session_state.status == "failed" else "status-new"
)

with st.sidebar:
    st.subheader("Order Session")
    st.markdown(
        f'<span class="status-pill {status_class}">Status: {st.session_state.status}</span>',
        unsafe_allow_html=True,
    )
    st.caption(f"Session: `{st.session_state.thread_id[:8]}`")

    if st.session_state.final_result:
        st.markdown("**Order Confirmation:**")
        st.info(f"{st.session_state.final_result}")

    st.write("")
    if st.button("Start New Order", use_container_width=True):
        st.session_state.thread_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.session_state.status = "new"
        st.session_state.final_result = None
        st.rerun()

st.markdown(
    """
    <div style="margin-bottom: 1.5rem;">
        <span class="menu-badge">Interactive Dining</span>
        <h1 style="margin: 0.25rem 0 0.5rem 0; font-size: 2rem; font-weight: 700;">AI Restaurant Order Agent</h1>
        <p style="color: var(--text-secondary); margin: 0; font-size: 0.95rem;">
            Order food and beverages naturally. The agent will confirm items, customize options, and finalize your order.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Tell me what you'd like to order today..."):
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.spinner("Processing order details..."):
        try:
            response = requests.post(
                DEFAULT_API_URL,
                json={"thread_id": st.session_state.thread_id, "message": prompt},
                timeout=120,
            )
            response.raise_for_status()
            data = response.json()

            agent_replies = data.get("responses", [])

            if not agent_replies:
                agent_replies = ["*(No message returned from agent)*"]

            for reply in agent_replies:
                with st.chat_message("assistant"):
                    st.markdown(reply)
                st.session_state.messages.append(
                    {"role": "assistant", "content": reply}
                )

            st.session_state.status = data.get("status", st.session_state.status)
            st.session_state.final_result = data.get("final_result")

        except requests.exceptions.RequestException as e:
            st.error(f"Failed to connect to the ordering backend: {e}")
            st.info("Ensure the FastAPI backend service is reachable and running.")

if st.session_state.status in ["done", "failed"]:
    st.success(
        "Order finalized. Click 'Start New Order' in the sidebar to begin another ordering session."
    )
