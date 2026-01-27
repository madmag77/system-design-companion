import logging
import streamlit as st
import sys
import json
import uuid
from pathlib import Path
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger(__name__)

# Add path for reference implementations
sys.path.insert(0, str(Path(__file__).parent.parent))
# Assuming wirl packages are installed in environment, else add paths like before

from wirl_pregel_runner.pregel_graph_builder import build_pregel_graph
from langgraph.checkpoint.memory import MemorySaver

from workflow_definitions.system_design.functions_companion import (
    load_workspace_state,
    extract_problem,
    save_state
)
from app.backend.workspace import WorkspaceManager

load_dotenv()

st.set_page_config(page_title="System Design Companion", layout="wide")

# --- Session State Init ---
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

if "app" not in st.session_state:
    fn_map = {
        "load_workspace_state": load_workspace_state,
        "extract_problem": extract_problem,
        "save_state": save_state
    }
    workflow_path = "workflow_definitions/system_design/companion.wirl"
    st.session_state.app = build_pregel_graph(workflow_path, fn_map, checkpointer=MemorySaver())

# --- UI Helpers ---

def render_workspace_view(ws_data):
    if not ws_data:
        st.info("No workspace data yet.")
        return

    ps = ws_data.get("problem_space", {})
    ss = ws_data.get("solution_space", {})
    
    st.header("Problem Space")
    
    with st.expander("Invariants", expanded=True):
        if ps.get("invariants"):
            for inv in ps["invariants"]:
                st.markdown(f"- {inv}")
        else:
            st.write("_No invariants defined_")

    st.subheader("Goal")
    st.write(ps.get("goal") or "_No goal defined_")
    
    st.subheader("Problem")
    st.write(ps.get("problem") or "_No problem defined_")
    
    with st.expander("Variants", expanded=True):
        if ps.get("variants"):
            for v in ps["variants"]:
                st.markdown(f"- {v}")
        else:
            st.write("_No variants defined_")

    if ss:
        st.markdown("---")
        st.header("Solution Space")
        
        candidates = ss.get("candidates", [])
        tabs = st.tabs([f"Candidate {c['id']}" for c in candidates])
        
        for i, tab in enumerate(tabs):
            with tab:
                c = candidates[i]
                st.markdown(f"**Hypothesis:** {c['hypothesis']}")
                st.markdown(f"**Model:**\n{c['model']}")
        
        if ss.get("comparison"):
            st.subheader("Comparison")
            st.markdown(ss["comparison"]["analysis"])
            st.markdown(f"**Recommendation:** {ss['comparison']['recommendation']}")
            
        if ss.get("simplification_feedback"):
            st.info(f"**Simplification Idea:** {ss['simplification_feedback']}")

# --- Main Layout ---

st.title("System Design Companion")

# Sidebar for Workspace Management
with st.sidebar:
    st.header("Workspaces")
    # Simple selector
    workspaces = st.session_state.workspace_manager.list_workspaces()
    selected_ws = st.selectbox("Select Workspace", workspaces, index=workspaces.index(st.session_state.current_workspace_id) if st.session_state.current_workspace_id in workspaces else None)
    
    if selected_ws and selected_ws != st.session_state.current_workspace_id:
        st.session_state.current_workspace_id = selected_ws
        versions = st.session_state.workspace_manager.list_versions(selected_ws)
        st.session_state.current_version_id = versions[-1] if versions else "v1"
        st.session_state.messages = [] # Clear chat on switch
        st.rerun()
        
    if st.button("New Workspace"):
        new_id = str(uuid.uuid4())
        st.session_state.current_workspace_id = new_id
        st.session_state.current_version_id = "v1"
        st.rerun()

    st.divider()
    st.write(f"Workspace ID: `{st.session_state.current_workspace_id}`")
    st.write(f"Version: `{st.session_state.current_version_id}`")

# Split Layout
col_ws, col_chat = st.columns([1.5, 1])

# --- Fetch Current State for Rendering ---
# We can use the 'load_workspace_state' function directly or via the graph history. 
# For simplicity, let's load it directly for display
current_ws_data = load_workspace_state(st.session_state.current_workspace_id, st.session_state.current_version_id)

with col_ws:
    render_workspace_view(current_ws_data)

with col_chat:
    st.header("Chat")
    
    # Display chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            
    # Chat Input
    if prompt := st.chat_input("Describe the problem or suggest changes..."):
        # Add to history
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
            
        # Run Workflow
        with st.spinner("Thinking..."):
            inputs = {
                "chat_input": prompt,
                "workspace_id": st.session_state.current_workspace_id,
                "version_id": st.session_state.current_version_id
            }
            config = {"configurable": {"thread_id": st.session_state.thread_id}}
            
            try:
                # Invoke Graph
                result = st.session_state.app.invoke(inputs, config)
                
                if result:
                    if "SaveState.final_version_id" in result:
                        new_ver = result["SaveState.final_version_id"]

                    if new_ver:
                        st.session_state.current_version_id = new_ver
                        st.success(f"Workspace updated to version {new_ver}")
                        st.rerun()
                    else:
                        st.info("No structural changes detected.")
                    
            except Exception as e:
                st.error(f"Error: {e}")
                logger.error(f"Workflow error: {e}", exc_info=True)

