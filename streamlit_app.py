import streamlit as st
import requests
import uuid

# --- CONFIGURATION ---
# Use the live API url (or allow overriding via sidebar)
DEFAULT_API_URL = "https://restaurant-agent-oarq.onrender.com/chat"

st.set_page_config(
    page_title="AI Restaurant Order Agent",
    page_icon="🍔",
    layout="centered"
)

# --- SESSION STATE INITIALIZATION ---
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []
if "status" not in st.session_state:
    st.session_state.status = "new"
if "final_result" not in st.session_state:
    st.session_state.final_result = None

# --- SIDEBAR ---
with st.sidebar:
    st.header("Settings")
    api_url = st.text_input("Backend API URL", DEFAULT_API_URL)
    
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

# --- MAIN UI ---
st.title("🍔 AI Restaurant Order Agent")
st.write("Welcome! Tell me what you'd like to order today.")

# Display chat messages from history on app rerun
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# React to user input
if prompt := st.chat_input("I would like to order..."):
    # 1. Display user message in chat message container
    st.chat_message("user").markdown(prompt)
    
    # 2. Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # 3. Call the API
    with st.spinner("Agent is thinking..."):
        try:
            response = requests.post(
                api_url,
                json={
                    "thread_id": st.session_state.thread_id,
                    "message": prompt
                },
                timeout=30
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
                st.session_state.messages.append({"role": "assistant", "content": reply})
            
            # Update status in sidebar
            st.session_state.status = data.get("status", st.session_state.status)
            st.session_state.final_result = data.get("final_result")

        except requests.exceptions.RequestException as e:
            st.error(f"Failed to connect to the backend API: {e}")
            st.info("Make sure your FastAPI server is running and the URL is correct.")

# Optional: Disable input if order is finished
if st.session_state.status in ["done", "failed"]:
    st.info("This ordering session has ended. Click 'Start New Order' in the sidebar to begin again.")
