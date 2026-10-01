import uuid

import requests
import streamlit as st

DEFAULT_API_URL = "https://restaurant-agent-oarq.onrender.com/chat"

st.set_page_config(page_title="AI Restaurant Order Agent", layout="centered")

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Karla:wght@300;400;500;600;700&family=Playfair+Display+SC:wght@400;700&display=swap');

html, body, [class*="css"]  {
    font-family: 'Karla', sans-serif !important;
}

h1, h2, h3, h4, h5, h6 {
    font-family: 'Playfair Display SC', serif !important;
    color: #DC2626 !important;
}

.stApp {
    background-color: #FEF2F2;
    color: #450A0A;
}

[data-testid="stHeader"] {
    background-color: rgba(254,242,242,0.9) !important;
}

/* Chat Bubbles */
[data-testid="stChatMessage"] {
    background-color: #FFFFFF;
    border: 2px solid #FECACA;
    border-radius: 12px;
    box-shadow: 4px 4px 0px #F87171;
    margin-bottom: 20px;
}

/* Buttons */
.stButton > button {
    background-color: #DC2626;
    color: #FFFFFF;
    font-family: 'Karla', sans-serif;
    font-weight: 700;
    font-size: 1.1rem;
    border: none;
    border-radius: 4px;
    box-shadow: 4px 4px 0px #450A0A;
    transition: all 0.1s ease-in-out;
    text-transform: uppercase;
}

.stButton > button:hover {
    background-color: #F87171;
    color: #FFFFFF;
}

.stButton > button:active {
    box-shadow: 0px 0px 0px #450A0A;
    transform: translate(4px, 4px);
}

/* Inputs */
.stChatInputContainer > div {
    background-color: #FFFFFF;
    border: 2px solid #FECACA;
    border-radius: 8px;
    box-shadow: 4px 4px 0px #F87171;
}
.stChatInputContainer > div:focus-within {
    border-color: #DC2626;
}

hr {
    border-color: #FECACA !important;
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

with st.sidebar:
    st.header("Session Details")
    st.write(f"**Thread ID:** `{st.session_state.thread_id[:8]}`")
    st.write(f"**Order Status:** `{st.session_state.status}`")
    if st.session_state.final_result:
        st.write(f"**Result:** `{st.session_state.final_result}`")

    if st.button("Start New Order"):
        st.session_state.thread_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.session_state.status = "new"
        st.session_state.final_result = None
        st.rerun()

st.title("AI Restaurant Order Agent")
st.write("Welcome! Tell me what you'd like to order today.")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("I would like to order..."):
    # 1. Display user message in chat message container
    st.chat_message("user").markdown(prompt)

    # 2. Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})

    # 3. Call the API
    with st.spinner("Agent is thinking..."):
        try:
            response = requests.post(
                DEFAULT_API_URL,
                json={"thread_id": st.session_state.thread_id, "message": prompt},
                timeout=120,
            )
            response.raise_for_status()
            data = response.json()

            # 4. Display agent responses and save to history
            agent_replies = data.get("responses", [])

            if not agent_replies:
                agent_replies = ["*(No message returned from agent)*"]

            for reply in agent_replies:
                with st.chat_message("assistant"):
                    st.markdown(reply)
                st.session_state.messages.append(
                    {"role": "assistant", "content": reply}
                )

            # Update status in sidebar
            st.session_state.status = data.get("status", st.session_state.status)
            st.session_state.final_result = data.get("final_result")

        except requests.exceptions.RequestException as e:
            st.error(f"Failed to connect to the backend API: {e}")
            st.info("Make sure your FastAPI server is running and the URL is correct.")

# Optional: Disable input if order is finished
if st.session_state.status in ["done", "failed"]:
    st.info(
        "This ordering session has ended. Click 'Start New Order' in the sidebar to begin again."
    )
