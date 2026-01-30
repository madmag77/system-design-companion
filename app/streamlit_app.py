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
    save_state, 
    check_problem_space,
    load_workspace_state,
    extract_problem,
    save_state, 
    check_problem_space,
    refine_problem_space,
    generate_solutions
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
        "save_state": save_state,
        "check_problem_space": check_problem_space,
        "refine_problem_space": refine_problem_space,
    }
    workflow_path = "workflow_definitions/system_design/companion.wirl"
    st.session_state.app = build_pregel_graph(workflow_path, fn_map, checkpointer=MemorySaver())

if "app_solution" not in st.session_state:
    fn_map_sol = {
        "load_workspace_state": load_workspace_state,
        "generate_solutions": generate_solutions,
        "save_state": save_state,
    }
    sol_workflow_path = "workflow_definitions/system_design/solution_companion.wirl"
    st.session_state.app_solution = build_pregel_graph(sol_workflow_path, fn_map_sol, checkpointer=MemorySaver())

# --- UI Helpers ---

def render_workspace_view(ws_data):
    if not ws_data:
        st.info("No workspace data yet.")
        return

# --- UI Renderers ---

def render_problem_space(ps):
    st.header("Problem Space")

    # Start Solutioning Trigger
    # Placed at top or bottom? User said "below the problem definition" in my plan, but user didn't specify position in request.
    # "Once use tap a button instead of writing comments, we should fix the problem space and switch to solutioning workflow."
    # I'll put it at the top for visibility or bottom. Bottom seems more logical after reading.

    st.subheader("Context")
    st.write(ps.get("context") or "_No context defined_")
    
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

    st.divider()
    if st.button("Start Solutioning", type="primary", use_container_width=True):
        return True
    return False

def render_solution_space(ss):
    st.header("Solution Space")
    if not ss:
        st.info("Solution space not yet generated.")
        return

    candidates = ss.get("candidates", [])
    if not candidates:
        st.write("No candidates found.")
        return

    tabs = st.tabs([f"Option {c['id']}" for c in candidates])
    
    for i, tab in enumerate(tabs):
        with tab:
            c = candidates[i]
            st.markdown(f"**Hypothesis:** {c['hypothesis']}")
            st.markdown(f"**Model:**\n{c['model']}")
            st.markdown(f"**Reasoning:**\n{c.get('reasoning', '')}")

    if ss.get("comparison"):
        st.subheader("Comparison")
        st.markdown(ss["comparison"]["analysis"])
        st.markdown(f"**Recommendation:** {ss['comparison']['recommendation']}")
        
    if ss.get("simplification_feedback"):
        st.info(f"**Simplification Idea:** {ss['simplification_feedback']}")

# --- Main Layout ---

# Remove default sidebar and use columns
# Layout: [Menu+Chat (20%)] [Problem Space (40%)] [Solution Space (40%)]
col_nav, col_prob, col_sol = st.columns([2, 4, 4])

# --- Fetch Current State for Rendering ---
current_ws_data = load_workspace_state(st.session_state.current_workspace_id, st.session_state.current_version_id)
ps = current_ws_data.get("problem_space", {})
ss = current_ws_data.get("solution_space", {})

# --- Column 1: Menu & Chat ---
with col_nav:
    st.subheader("Workspace")
    workspaces = st.session_state.workspace_manager.list_workspaces()
    selected_ws = st.selectbox("Select", workspaces, index=workspaces.index(st.session_state.current_workspace_id) if st.session_state.current_workspace_id in workspaces else None, label_visibility="collapsed")
    
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
    
    st.caption(f"ID: {st.session_state.current_workspace_id[:8]}... v{st.session_state.current_version_id}")
    st.divider()
    
    st.header("Chat")
    # Chat History
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            
    # Chat Input
    if prompt := st.chat_input("Input..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
            
        # Run Workflow (Problem Space)
        # Note: If solution space is active, we might want to switch workflow? 
        # For now, adhering to instruction: "new workflow... run. don't amend current problem space" 
        # But this chat input is general. If user is in solutioning, maybe we shouldn't run problem extraction?
        # User said: "Once use tap a button instead of writing comments, we should fix the problem space and switch to solutioning workflow."
        # This implies chat might submit to different workflows depending on state. 
        # For this iteration, I'll keep chat bound to Problem Space workflow UNLESS we strictly switch modes.
        # But for now, "Start Solutioning" button triggers generation, chat triggers refinement.
        
        with st.spinner("Refining Problem Space..."):
            inputs = {
                "chat_input": prompt,
                "workspace_id": st.session_state.current_workspace_id,
                "version_id": st.session_state.current_version_id
            }
            config = {"configurable": {"thread_id": st.session_state.thread_id}}
            
            try:
                result = st.session_state.app.invoke(inputs, config)
                if result and result.get("SaveState.final_version_id"):
                     st.session_state.current_version_id = result["SaveState.final_version_id"]
                     st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

# --- Column 2: Problem Space ---
with col_prob:
    should_solve = render_problem_space(ps)
    if should_solve:
        with st.spinner("Generating Solution Space..."):
            inputs = {
                "chat_input": "Start Solutioning", # Dummy input
                "workspace_id": st.session_state.current_workspace_id,
                "version_id": st.session_state.current_version_id
            }
            config = {"configurable": {"thread_id": st.session_state.thread_id}}
            try:
                result = st.session_state.app_solution.invoke(inputs, config)
                if result and result.get("SaveState.final_version_id"):
                     st.session_state.current_version_id = result["SaveState.final_version_id"]
                     st.rerun()
            except Exception as e:
                st.error(f"Error generating solutions: {e}")

# --- Column 3: Solution Space ---
with col_sol:
    render_solution_space(ss)

