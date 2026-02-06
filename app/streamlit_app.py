import logging
import streamlit as st
import sys
from pathlib import Path
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger(__name__)

# Add path for reference implementations
sys.path.insert(0, str(Path(__file__).parent.parent))

from workflow_definitions.system_design.functions_companion import load_workspace_state

# Import services
from app.services.session_manager import (
    initialize_session_state, 
    get_workflow_phase
)
from app.services.workflow_service import (
    initialize_workflows, 
    process_pending_solution_step
)
from app.services.agent_service import handle_agent_input

# Import UI components
from app.components.problem_ui import render_problem_space_content
from app.components.solution_ui import (
    render_brainstorming_candidates, 
    render_shortlist_view, 
    render_deep_dive_view, 
    render_final_view
)

load_dotenv()

st.set_page_config(page_title="System Design Companion", layout="wide")

# Inject custom CSS
st.markdown("""
    <style>
        .block-container {
            padding-left: 2rem;
            padding-right: 2rem;
            max-width: 100%;
        }
        [data-testid="stSidebar"] {
            min-width: 25vw !important;
            max-width: 25vw !important;
        }
    </style>
""", unsafe_allow_html=True)

BLOCKING_CSS = """
    <style>
        [data-testid="stMain"] {
            opacity: 0.35;
            pointer-events: none;
            transition: opacity 120ms ease-in-out;
        }
    </style>
"""

UNBLOCK_CSS = """
    <style>
        [data-testid="stMain"] {
            opacity: 1;
            pointer-events: auto;
            transition: opacity 120ms ease-in-out;
        }
    </style>
"""

# Initialize State & Workflows
initialize_session_state()
initialize_workflows()

# --- Main Execution ---

# Fetch Current State
current_ws_data = load_workspace_state(st.session_state.current_workspace_id, st.session_state.current_version_id)
ps = current_ws_data.get("problem_space", {})
ss = current_ws_data.get("solution_space", {})

phase = get_workflow_phase(ss)

# Sidebar
with st.sidebar:
    st.subheader("Workspace")
    workspaces = st.session_state.workspace_manager.list_workspaces()

    if workspaces:
        index = 0
        if st.session_state.current_workspace_id in workspaces:
             index = workspaces.index(st.session_state.current_workspace_id)

        selected_ws = st.selectbox("Select", workspaces, index=index, label_visibility="collapsed")

        if selected_ws and selected_ws != st.session_state.current_workspace_id:
            st.session_state.current_workspace_id = selected_ws
            versions = st.session_state.workspace_manager.list_versions(selected_ws)
            st.session_state.current_version_id = versions[-1] if versions else "v1"
            st.session_state.messages = []
            st.rerun()
    else:
        st.caption("No saved workspaces yet.")

    if st.button("New", use_container_width=True):
        import uuid

        new_id = str(uuid.uuid4())
        st.session_state.current_workspace_id = new_id
        st.session_state.current_version_id = "v1"
        st.session_state.messages = []
        st.rerun()

    st.caption(f"Version: `{st.session_state.current_version_id}`")
    st.caption(f"Phase: {phase}")
    st.divider()

    st.header("Chat")
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if st.session_state.pending_agent_input:
        st.markdown(BLOCKING_CSS, unsafe_allow_html=True)
        label = st.session_state.current_action_label or "Processing request..."
        with st.spinner(label):
            prompt = st.session_state.pending_agent_input
            result = handle_agent_input(prompt, ps, ss)
            for message in result.get("messages", []):
                if not message:
                    continue
                st.session_state.messages.append({"role": "assistant", "content": message})
        st.session_state.pending_agent_input = None

        if st.session_state.get("pending_solution_step") is not None:
            label = st.session_state.current_action_label or "Processing workflow..."
            with st.spinner(label):
                process_pending_solution_step(show_spinner=False, spinner_label=label)

        st.markdown(UNBLOCK_CSS, unsafe_allow_html=True)
        st.rerun()

    if st.session_state.get("pending_solution_step") is not None:
        st.markdown(BLOCKING_CSS, unsafe_allow_html=True)
        label = st.session_state.current_action_label or "Processing workflow..."
        with st.spinner(label):
            process_pending_solution_step(show_spinner=False, spinner_label=label)
        st.markdown(UNBLOCK_CSS, unsafe_allow_html=True)
        st.rerun()

    if prompt := st.chat_input("Message the agent..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.session_state.pending_agent_input = prompt
        st.session_state.current_action_label = "Processing request..."
        st.rerun()

st.title("System Design Companion")
st.caption(
    "Chat with the agent to update the workspace. Examples: "
    "\"Design a rate limiter\", \"Brainstorm an option\", \"Shortlist 1 and 3\", "
    "\"Deep dive 1 and 3\", \"Compare options\", \"Finalize option 2\"."
)

# Main Tabs
tabs = st.tabs(["Problem Context", "Brainstorming", "Shortlist", "Deep Dive", "Comparison", "Final Solution"])

with tabs[0]:
    render_problem_space_content(ps)
    
with tabs[1]:
    st.header("Solution Space")
    render_brainstorming_candidates(ss)

with tabs[2]:
    render_shortlist_view(ss)
    
with tabs[3]:
    # Deep Dive - Enabled if we have candidates (so we can shortlist)
    if ss and ss.get("candidates"):
        render_deep_dive_view(ss, mode="expand")
    else:
        st.info("Ask the agent to brainstorm options before diving deep.")
        
with tabs[4]:
    # Comparison - Enabled if we have expanded candidates
    if ss and ss.get("expanded_candidates"):
         render_deep_dive_view(ss, mode="compare")
    else:
         st.info("Ask the agent to run a deep dive before comparing.")
         
with tabs[5]:
    # Final - Enabled if we have comparison (or just expanded?)
    # Usually Final requires Deep Comparison recommendation
    if ss and ss.get("deep_comparison"):
        render_final_view(ss)
    else:
        st.info("Ask the agent to compare options before finalizing.")

# Execution Loop moved into sidebar to keep spinner in chat zone.
