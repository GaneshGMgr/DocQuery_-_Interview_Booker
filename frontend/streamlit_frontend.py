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

if "show_interview_form" not in st.session_state:
    st.session_state.show_interview_form = False

add_thread(st.session_state['thread_id'])

# --------------- Dark Theme CSS -------------------

st.markdown("""
<style>
    /* Dark theme base colors */
    :root {
        --dark-bg: #1a1a1a;
        --darker-bg: #121212;
        --dark-text: #e0e0e0;
        --dark-border: #333333;
        --dark-accent: #4a6fa5;
        --dark-hover: #3a5a8f;
        --dark-secondary: #2d3748;
    }
    
    /* Main app background */
    .stApp {
        background-color: var(--dark-bg);
        color: var(--dark-text);
    }
    
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background-color: var(--darker-bg) !important;
        border-right: 1px solid var(--dark-border);
        padding: 1rem;
    }
    
    /* Sidebar section headers */
    .sidebar-section {
        margin-top: 1rem;
        margin-bottom: 0.5rem;
        font-weight: 600;
        font-size: 0.85rem;
        color: var(--dark-text);
        letter-spacing: 0.5px;
        text-transform: uppercase;
    }
    
    /* Thread selection dropdown */
    .stSelectbox>div>div>div>div>div {
        background-color: var(--darker-bg);
        border: 1px solid var(--dark-border);
        color: var(--dark-text);
        border-radius: 6px;
        padding: 0.4rem;
    }
    
    /* File uploader styling */
    .file-uploader {
        border: 2px dashed var(--dark-border);
        border-radius: 8px;
        padding: 1.25rem;
        text-align: center;
        background-color: var(--darker-bg);
        transition: all 0.2s;
        margin-bottom: 0.5rem;
    }
    
    .file-uploader:hover {
        border-color: var(--dark-accent);
        background-color: rgba(74, 111, 165, 0.1);
    }
    
    .uploader-text {
        font-size: 0.75rem;
        color: #a0a0a0;
        margin: 0.25rem 0;
        line-height: 1.4;
    }
    
    /* Button styling */
    .sidebar-button {
        border-radius: 6px;
        padding: 0.5rem;
        font-weight: 500;
        border: none;
        transition: all 0.2s;
        width: 100%;
        margin: 0.25rem 0;
        font-size: 0.85rem;
    }
    
    .primary-button {
        background-color: var(--dark-accent);
        color: white;
    }
    
    .primary-button:hover {
        background-color: var(--dark-hover);
    }
    
    .secondary-button {
        background-color: var(--dark-secondary);
        color: var(--dark-text);
    }
    
    .secondary-button:hover {
        background-color: #3a4a5f;
    }
    
    /* Modal form styling */
    .modal-overlay {
        position: fixed;
        top: 0; left: 0;
        width: 100vw; height: 100vh;
        background-color: rgba(0,0,0,0.7);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 9999;
    }
    
    .modal-content {
        background: var(--darker-bg);
        padding: 1.5rem;
        border-radius: 10px;
        width: 380px;
        border: 1px solid var(--dark-border);
        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
    }
    
    .modal-title {
        font-size: 1.1rem;
        font-weight: 600;
        margin-bottom: 1.25rem;
        color: var(--dark-text);
    }
    
    /* Form input styling */
    .form-input {
        margin-bottom: 1rem;
    }
    
    .form-input label {
        font-size: 0.85rem;
        margin-bottom: 0.25rem;
        display: block;
        color: var(--dark-text);
    }
    
    /* Divider */
    .divider {
        border-top: 1px solid var(--dark-border);
        margin: 1rem 0;
    }
    
    /* Chat message styling */
    .chat-message {
        border-radius: 10px;
        padding: 0.75rem 1rem;
        margin-bottom: 0.75rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.2);
    }
    
    .user-message {
        background-color: rgba(74, 111, 165, 0.2);
        margin-left: 20%;
        border: 1px solid rgba(74, 111, 165, 0.3);
    }
    
    .assistant-message {
        background-color: rgba(45, 55, 72, 0.3);
        margin-right: 20%;
        border: 1px solid var(--dark-border);
    }
</style>
""", unsafe_allow_html=True)

# --------------- Sidebar UI -------------------

with st.sidebar:
    # New Chat button
    if st.button('+ New Chat', key='new_chat', use_container_width=True, 
                help="Start a new conversation"):
        reset_chat()
    
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    
    # Conversations section
    st.markdown('<div class="sidebar-section">My Conversations</div>', unsafe_allow_html=True)
    
    selected_thread = st.selectbox(
        "Select Thread",
        options=st.session_state['chat_threads'][::-1],
        index=0,
        label_visibility="collapsed",
        format_func=lambda x: f"{x[:8]}..." if len(x) > 8 else x,
        help="Select a previous conversation"
    )
    
    if selected_thread != st.session_state['thread_id']:
        st.session_state['thread_id'] = selected_thread
        messages = load_conversation(selected_thread)
        st.session_state['message_history'] = messages
    
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    
    # Actions section
    st.markdown('<div class="sidebar-section">Actions</div>', unsafe_allow_html=True)
    
    # File uploader
    st.markdown('<div class="file-uploader">Upload Document</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="uploader-text">Drag and drop file here<br>Limit 200MB per file • PDF, DOCX, DOC, TXT</div>',
        unsafe_allow_html=True
    )
    
    uploaded_file = st.file_uploader(
        "Upload Document",
        type=["pdf", "docx", "doc", "txt"],
        label_visibility="collapsed",
        key="file_uploader"
    )
    
    if uploaded_file is not None:
        st.session_state['message_history'].append({
            'role': 'user',
            'content': f"Uploaded file: {uploaded_file.name}"
        })
        with open(uploaded_file.name, "wb") as f:
            f.write(uploaded_file.getbuffer())
    
    # Interview form button
    if st.button("Check the latest form", 
                key='open_form', 
                use_container_width=True,
                help="Open interview appointment form"):
        st.session_state.show_interview_form = True

# --------------- Interview Form Modal -------------------

if st.session_state.show_interview_form:    
    with st.form("interview_form", clear_on_submit=True):
        st.markdown('<div class="form-input">', unsafe_allow_html=True)
        name = st.text_input("Name: ", key="name_input")
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="form-input">', unsafe_allow_html=True)
        email = st.text_input("Email: ", key="email_input")
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="form-input">', unsafe_allow_html=True)
        date = st.date_input("Date: ", key="date_input")
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="form-input">', unsafe_allow_html=True)
        time = st.time_input("Time: ", key="time_input")
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.form_submit_button("Submit", type="primary"):
                form_data = f"Name: {name}\nEmail: {email}\nDate: {date}\nTime: {time}"
                st.session_state['message_history'].append({'role': 'user', 'content': form_data})
                st.session_state.show_interview_form = False
                st.rerun()
        with col2:
            if st.form_submit_button("Cancel"):
                st.session_state.show_interview_form = False
                st.rerun()

# --------------- Main Chat UI -------------------

for message in st.session_state['message_history']:
    with st.chat_message(message['role'], 
                        avatar="🧑" if message['role'] == 'user' else "🤖"):
        st.markdown(message['content'])

# --------------- Chat Input -------------------

user_input = st.chat_input('Type your message here...')

if user_input:
    st.session_state['message_history'].append({'role': 'user', 'content': user_input})
    with st.chat_message('user'):
        st.markdown(user_input)
    
    # Placeholder to update assistant message incrementally
    assistant_message_placeholder = st.empty()
    full_response = ""

    # Streaming request
    response = requests.post(
        "http://localhost:8000/query_stream",
        json={"question": user_input, "thread_id": st.session_state['thread_id']},
        stream=True,
    )

    try:
        for line in response.iter_lines(decode_unicode=True):
            if line:
                # SSE format: data: chunk
                if line.startswith("data: "):
                    chunk = line[6:]
                    full_response += chunk
                    assistant_message_placeholder.markdown(full_response)
    except Exception as e:
        assistant_message_placeholder.markdown(f"Error during streaming: {e}")

    # Append full assistant message to history
    st.session_state['message_history'].append({'role': 'assistant', 'content': full_response})