import streamlit as st
from langchain_core.messages import HumanMessage
import uuid
import requests
from PIL import Image

# --------------- Utility Functions -------------------

def retrieve_all_threads():
    try:
        response = requests.get("http://localhost:8000/threads")
        response.raise_for_status()
        return response.json().get("threads", [])
    except Exception as e:
        st.error(f"Error retrieving threads: {e}")
        return []

def generate_thread_id():
    return str(uuid.uuid4())

def reset_chat():
    thread_id = generate_thread_id()
    st.session_state['thread_id'] = thread_id
    add_thread(thread_id)
    st.session_state['message_history'] = []

def add_thread(thread_id):
    if thread_id not in st.session_state['chat_threads']:
        st.session_state['chat_threads'].append(thread_id)

def load_conversation(thread_id):
    try:
        response = requests.get(f"http://localhost:8000/conversation/{thread_id}")
        response.raise_for_status()
        return response.json().get("messages", [])
    except Exception as e:
        st.error(f"Failed to load conversation: {e}")
        return []

# --------------- Session Setup -------------------

if 'message_history' not in st.session_state:
    st.session_state['message_history'] = []

if 'thread_id' not in st.session_state:
    st.session_state['thread_id'] = generate_thread_id()

if 'chat_threads' not in st.session_state:
    st.session_state['chat_threads'] = retrieve_all_threads()

if "show_extra_form" not in st.session_state:
    st.session_state.show_extra_form = False

add_thread(st.session_state['thread_id'])

# --------------- Sidebar UI -------------------

st.sidebar.title('LangGraph Chatbot')

if st.sidebar.button('New Chat'):
    reset_chat()

st.sidebar.header('My Conversations')

# Optional improvement: use selectbox instead of buttons for thread selection
selected_thread = st.sidebar.selectbox("Select Thread", options=st.session_state['chat_threads'][::-1], index=0)

if selected_thread != st.session_state['thread_id']:
    st.session_state['thread_id'] = selected_thread
    messages = load_conversation(selected_thread)
    st.session_state['message_history'] = messages

st.sidebar.header('Chatbot Architecture')
try:
    graph_image = Image.open("chatbot_architecture.png")
    st.sidebar.image(graph_image, caption='Chatbot Architecture', use_column_width=True)
except FileNotFoundError:
    st.sidebar.write("Graph image not found. Please run backend to generate it.")

# --------------- Main UI -------------------

for message in st.session_state['message_history']:
    with st.chat_message(message['role']):
        st.text(message['content'])

uploaded_file = st.file_uploader(
    "Upload Document (Resume, PDF, DOCX, etc.)",
    type=["pdf", "docx", "doc", "txt"]
)

if uploaded_file is not None:
    st.session_state['message_history'].append({
        'role': 'user',
        'content': f"Uploaded file: {uploaded_file.name}"
    })
    with open(uploaded_file.name, "wb") as f:
        f.write(uploaded_file.getbuffer())

if not st.session_state.show_extra_form:
    if st.button("Open Interview Form"):
        st.session_state.show_extra_form = True

if st.session_state.show_extra_form:
    st.markdown("""
    <style>
    .modal-overlay {
        position: fixed;
        top: 0; left: 0;
        width: 100%; height: 100%;
        background-color: rgba(0,0,0,0.5);
        display: flex; align-items: center; justify-content: center;
        z-index: 9999;
    }
    .modal-box {
        background: white;
        padding: 20px;
        border-radius: 10px;
        width: 400px;
        box-shadow: 0px 4px 20px rgba(0,0,0,0.3);
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="modal-overlay">
        <div class="modal-box">
            <h4>Interview Details Form</h4>
        </div>
    </div>
    """, unsafe_allow_html=True)

    with st.form("interview_form", clear_on_submit=True):
        name = st.text_input("Name")
        email = st.text_input("Email")
        date = st.date_input("Interview Date")
        time = st.time_input("Interview Time")

        col1, col2 = st.columns(2)
        with col1:
            submit_form = st.form_submit_button("Submit")
        with col2:
            cancel_form = st.form_submit_button("Cancel")

        if submit_form:
            form_data = f"Name: {name}\nEmail: {email}\nDate: {date}\nTime: {time}"
            st.session_state['message_history'].append({'role': 'user', 'content': form_data})
            st.session_state.show_extra_form = False

        elif cancel_form:
            st.session_state.show_extra_form = False

user_input = st.chat_input('Type here')

if user_input:
    st.session_state['message_history'].append({'role': 'user', 'content': user_input})
    with st.chat_message('user'):
        st.text(user_input)

    try:
        response = requests.post(
            "http://localhost:8000/query",
            json={
                "question": user_input,
                "thread_id": st.session_state['thread_id'],
            }
        )
        response.raise_for_status()
        data = response.json()
        ai_message = data.get("response", "No response from backend.")
    except Exception as e:
        ai_message = f"Error communicating with backend: {e}"

    with st.chat_message('assistant'):
        st.text(ai_message)

    st.session_state['message_history'].append({'role': 'assistant', 'content': ai_message})
