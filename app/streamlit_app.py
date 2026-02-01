import logging
import streamlit as st
import sys
import uuid
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
    run_problem_workflow, 
    process_pending_solution_step,
    run_solution_step
)

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
        
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("New", use_container_width=True):
            new_id = str(uuid.uuid4())
            st.session_state.current_workspace_id = new_id
            st.session_state.current_version_id = "v1"
            st.rerun()
            
    st.divider()
    
    st.header("Chat")
    # Chat History
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            
    # Chat Input
    if phase != "BRAINSTORM":
        st.info(f"Phase: {phase}. Chat updates to Problem Space might invalidate solutions.")
    
    if prompt := st.chat_input("Input..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
                
            has_solutions = ss is not None and len(ss.get("candidates", [])) > 0
            
            if has_solutions and phase == "BRAINSTORM":
                st.session_state.confirm_solution_removal = "pending"
                st.session_state.pending_chat_input = prompt
                st.rerun()
            elif phase != "BRAINSTORM":
                success = run_problem_workflow(prompt, remove_solutions=False)
                if success:
                    st.rerun()
            else:
                success = run_problem_workflow(prompt, remove_solutions=True)
                if success:
                    st.rerun()

# Main Tabs
tabs = st.tabs(["Problem Context", "Brainstorming", "Shortlist", "Deep Dive", "Comparison", "Final Solution"])

with tabs[0]:
    render_problem_space_content(ps)
    
with tabs[1]:
    st.header("Solution Space")
    render_brainstorming_candidates(ss, allow_add=True)

with tabs[2]:
    render_shortlist_view(ss)
    
with tabs[3]:
    # Deep Dive - Enabled if we have candidates (so we can shortlist)
    if ss and ss.get("candidates"):
        render_deep_dive_view(ss, mode="expand")
    else:
        st.info("Complete Brainstorming to proceed to Deep Dive.")
        
with tabs[4]:
    # Comparison - Enabled if we have expanded candidates
    if ss and ss.get("expanded_candidates"):
         render_deep_dive_view(ss, mode="compare")
    else:
         st.info("Complete Deep Dive to proceed to Comparison.")
         
with tabs[5]:
    # Final - Enabled if we have comparison (or just expanded?)
    # Usually Final requires Deep Comparison recommendation
    if ss and ss.get("deep_comparison"):
        render_final_view(ss)
    else:
        st.info("Complete Comparison to generate Final Solution.")

# Execution Loop
process_pending_solution_step()
