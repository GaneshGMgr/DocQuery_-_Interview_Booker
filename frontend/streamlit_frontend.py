import streamlit as st
import requests
import uuid
from datetime import datetime

# Initialize session state
def init_session_state():
    if 'current_thread' not in st.session_state:
        st.session_state.current_thread = {
            'id': str(uuid.uuid4()),
            'title': "New Chat",
            'messages': []
        }
    
    if 'thread_list' not in st.session_state:
        st.session_state.thread_list = []
    
    if 'show_interview_form' not in st.session_state:
        st.session_state.show_interview_form = False

# API configuration
API_BASE_URL = "http://localhost:8000"

def get_all_threads():
    """Fetch all conversation threads from backend"""
    try:
        response = requests.get(f"{API_BASE_URL}/threads")
        response.raise_for_status()
        return response.json().get("threads", [])
    except Exception as e:
        st.error(f"Failed to load threads: {str(e)}")
        return []

def get_thread_messages(thread_id):
    """Get full conversation history for a thread"""
    try:
        response = requests.get(f"{API_BASE_URL}/conversation/{thread_id}")
        response.raise_for_status()
        messages = response.json().get("messages", [])
        
        # Convert message format if needed
        formatted_messages = []
        for msg in messages:
            formatted_msg = {
                'role': msg['role'],
                'content': msg['content'],
                'timestamp': msg.get('timestamp', datetime.now().timestamp())
            }
            formatted_messages.append(formatted_msg)
            
        return formatted_messages
    except Exception as e:
        st.error(f"Failed to load messages: {str(e)}")
        return []

def send_chat_message(thread_id, message):
    """Send message and stream response"""
    try:
        with requests.post(
            f"{API_BASE_URL}/query_stream",
            json={"question": message, "thread_id": thread_id},
            stream=True
        ) as response:
            response.raise_for_status()
            
            full_response = ""
            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8')
                    if decoded_line.startswith('data: '):
                        full_response += decoded_line[6:]
            return full_response
    except Exception as e:
        st.error(f"Error during chat: {str(e)}")
        return None

def create_new_thread():
    """Initialize a new conversation thread"""
    try:
        thread_id = str(uuid.uuid4())
        response = requests.post(
            f"{API_BASE_URL}/init_thread",
            json={"thread_id": thread_id}
        )
        response.raise_for_status()
        return {
            'id': thread_id,
            'title': "New Chat",
            'messages': []
        }
    except Exception as e:
        st.error(f"Failed to create thread: {str(e)}")
        return None

def update_thread_title(thread_id, title):
    """Update thread title in backend"""
    try:
        response = requests.put(
            f"{API_BASE_URL}/thread_title",
            json={"thread_id": thread_id, "title": title}
        )
        response.raise_for_status()
        return True
    except Exception as e:
        st.error(f"Failed to update title: {str(e)}")
        return False

# Initialize session
init_session_state()

# Load initial data if needed
if not st.session_state.thread_list:
    st.session_state.thread_list = get_all_threads()

if not st.session_state.current_thread['messages']:
    st.session_state.current_thread['messages'] = get_thread_messages(
        st.session_state.current_thread['id']
    )

# Dark Theme CSS
st.markdown("""
<style>
    :root {
        --dark-bg: #1a1a1a;
        --darker-bg: #121212;
        --dark-text: #e0e0e0;
        --dark-border: #333333;
        --dark-accent: #4a6fa5;
    }
    .stApp {
        background-color: var(--dark-bg);
        color: var(--dark-text);
    }
    [data-testid="stSidebar"] {
        background-color: var(--darker-bg) !important;
    }
    .stChatMessage {
        border-radius: 10px;
        padding: 12px;
        margin-bottom: 12px;
    }
    .stTextInput input {
        background-color: var(--darker-bg);
        color: var(--dark-text);
    }
</style>
""", unsafe_allow_html=True)

# Sidebar UI
with st.sidebar:
    st.title("Chat Threads")
    
    # New Chat button
    if st.button("+ New Chat", use_container_width=True):
        new_thread = create_new_thread()
        if new_thread:
            st.session_state.current_thread = new_thread
            st.session_state.thread_list = get_all_threads()
            st.rerun()
    
    st.divider()
    st.subheader("Your Conversations")
    
    # Thread list
    for thread in st.session_state.thread_list:
        title = str(thread.get('title', 'New Chat'))  # Ensure it's a string
        if st.button(
            title,
            key=f"thread_{thread['id']}",
            use_container_width=True,
            help=f"Last updated: {datetime.fromtimestamp(thread['timestamp']).strftime('%Y-%m-%d %H:%M') if thread.get('timestamp') else 'N/A'}"
        ):
            st.session_state.current_thread = {
                'id': thread['id'],
                'title': title,
                'messages': get_thread_messages(thread['id'])
            }
            st.rerun()
    
    st.divider()
    
    # File uploader
    uploaded_file = st.file_uploader(
        "Upload Document",
        type=["pdf", "docx", "txt"],
        label_visibility="collapsed"
    )
    
    if uploaded_file:
        st.session_state.current_thread['messages'].append({
            'role': 'user',
            'content': f"Uploaded file: {uploaded_file.name}",
            'timestamp': datetime.now().timestamp()
        })

# Main chat interface
st.title(st.session_state.current_thread.get('title', 'New Chat'))

# Display messages
for msg in st.session_state.current_thread['messages']:
    with st.chat_message(msg['role'], avatar="🧑" if msg['role'] == 'user' else "🤖"):
        st.markdown(msg['content'])
        if msg.get('timestamp'):
            st.caption(datetime.fromtimestamp(msg['timestamp']).strftime('%Y-%m-%d %H:%M'))

# Message input
if prompt := st.chat_input("Type your message..."):
    # Add user message
    user_msg = {
        'role': 'user',
        'content': prompt,
        'timestamp': datetime.now().timestamp()
    }
    st.session_state.current_thread['messages'].append(user_msg)
    
    # Display user message
    with st.chat_message('user'):
        st.markdown(prompt)
        st.caption(datetime.now().strftime('%Y-%m-%d %H:%M'))
    
    # Get and display assistant response
    with st.chat_message('assistant'):
        response = send_chat_message(st.session_state.current_thread['id'], prompt)
        if response:
            st.markdown(response)
            st.caption(datetime.now().strftime('%Y-%m-%d %H:%M'))
    
    # Update thread title if first message
    if len(st.session_state.current_thread['messages']) <= 2:
        update_thread_title(st.session_state.current_thread['id'], prompt[:30])
    
    # Refresh data
    st.session_state.current_thread['messages'] = get_thread_messages(st.session_state.current_thread['id'])
    st.session_state.thread_list = get_all_threads()
    st.rerun()