import streamlit as st
import uuid
from app.backend.workspace import WorkspaceManager

def initialize_session_state():
    """Initialize all session state variables."""
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = str(uuid.uuid4())

    if "workspace_manager" not in st.session_state:
        st.session_state.workspace_manager = WorkspaceManager()

    if "current_workspace_id" not in st.session_state:
        # Default to a new workspace ID or first existing one
        existing = st.session_state.workspace_manager.list_workspaces()
        st.session_state.current_workspace_id = existing[0] if existing else str(uuid.uuid4())

    if "current_version_id" not in st.session_state:
        # Find latest version or start fresh
        if st.session_state.workspace_manager._get_workspace_dir(st.session_state.current_workspace_id).exists():
            versions = st.session_state.workspace_manager.list_versions(st.session_state.current_workspace_id)
            st.session_state.current_version_id = versions[-1] if versions else "v1"
        else:
            st.session_state.current_version_id = "v1"

    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    if "pending_solution_step" not in st.session_state:
        st.session_state.pending_solution_step = None

    if "solution_processing" not in st.session_state:
        st.session_state.solution_processing = False

    if "confirm_solution_removal" not in st.session_state:
        st.session_state.confirm_solution_removal = None
        
    if "pending_chat_input" not in st.session_state:
        st.session_state.pending_chat_input = None

def get_workflow_phase(ss):
    if not ss:
        return "BRAINSTORM"
    if ss.get("final_solution"):
        return "FINAL"
    if ss.get("deep_comparison"):
        return "COMPARISON"
    if ss.get("expanded_candidates"):
        return "DEEP_DIVE"
    if ss.get("shortlisted_ids"):
        return "SHORTLIST" 
    return "BRAINSTORM"

def get_shortlisted_ids(ss):
    """Helper to get selected IDs from session state based on checkbox keys"""
    ids = []
    if ss and ss.get("candidates"):
        for c in ss["candidates"]:
            if st.session_state.get(f"select_{c['id']}"):
                ids.append(c['id'])
    return ids
