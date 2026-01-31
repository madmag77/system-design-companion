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
    refine_problem_space,
    generate_candidate,
    compare_solutions
)
from app.backend.workspace import WorkspaceManager

load_dotenv()

st.set_page_config(page_title="System Design Companion", layout="wide")

# Inject custom CSS to reduce whitespace
st.markdown("""
    <style>
        .block-container {
            padding-left: 2rem;
            padding-right: 2rem;
            max-width: 100%;
        }
    </style>
""", unsafe_allow_html=True)

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
        "generate_candidate": generate_candidate,
        "compare_solutions": compare_solutions,
        "save_state": save_state,
    }
    sol_workflow_path = "workflow_definitions/system_design/solution_companion.wirl"
    st.session_state.app_solution = build_pregel_graph(sol_workflow_path, fn_map_sol, checkpointer=MemorySaver())

if "solution_processing" not in st.session_state:
    st.session_state.solution_processing = False

def start_solution_generation():
    st.session_state.solution_processing = True

# --- UI Helpers ---

def render_workspace_view(ws_data):
    if not ws_data:
        st.info("No workspace data yet.")
        return

def run_problem_workflow(prompt, remove_solutions=True):
    with st.spinner("Refining Problem Space..."):
        inputs = {
            "chat_input": prompt,
            "workspace_id": st.session_state.current_workspace_id,
            "version_id": st.session_state.current_version_id,
            "remove_solutions": remove_solutions
        }
        config = {"configurable": {"thread_id": st.session_state.thread_id}}
        
        try:
            result = st.session_state.app.invoke(inputs, config)
            if result and result.get("SaveState.final_version_id"):
                    st.session_state.current_version_id = result["SaveState.final_version_id"]
                    return True # Signal success
        except Exception as e:
            st.error(f"Error: {e}")
    return False

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
    
    # Check if we have reached the limit of 10 solutions
    # Moved to Solution Space as per user request
    return False

def render_solution_space(ss):
    st.header("Solution Space")
    
    # Add Solution Button (Top of Solution Space)
    # We check limit here
    current_candidates = ss.get("candidates", []) if ss else []
    
    # If no solution space yet, we still want to show the button to start?
    # But usually it starts from Problem Space? 
    # Actually, the user flow is: Problem defined -> "Add Solution".
    # If SS is empty, we still want the button here?
    # Previous logic was: Button in Problem Column triggered it.
    # Now button is in Solution Column.
    
    trigger_solution = False
    
    
    if len(current_candidates) >= 10:
         st.warning("Maximum of 10 solutions reached.")
    else:
        st.button(
            "Add Solution", 
            type="primary", 
            use_container_width=True,
            on_click=start_solution_generation,
            disabled=st.session_state.solution_processing
        )

    if not ss or not current_candidates:
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

    return trigger_solution

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
    # Chat Input & Confirmation Logic
    
    if "confirm_solution_removal" not in st.session_state:
        st.session_state.confirm_solution_removal = None
    if "pending_chat_input" not in st.session_state:
        st.session_state.pending_chat_input = None

    if st.session_state.confirm_solution_removal == "pending":
        with st.container(border=True):
            st.warning("Solution Space exists!")
            st.write("Updating the problem space usually requires clearing existing solutions.")
            st.write(f"**Input:** {st.session_state.pending_chat_input}")
            
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Remove Solutions & Update", type="primary", use_container_width=True):
                    success = run_problem_workflow(st.session_state.pending_chat_input, remove_solutions=True)
                    st.session_state.confirm_solution_removal = None
                    st.session_state.pending_chat_input = None
                    if success:
                        st.rerun()
            with c2:
                if st.button("Keep Solutions & Update", use_container_width=True):
                    success = run_problem_workflow(st.session_state.pending_chat_input, remove_solutions=False)
                    st.session_state.confirm_solution_removal = None
                    st.session_state.pending_chat_input = None
                    if success:
                        st.rerun()
            
            if st.button("Cancel", use_container_width=True):
                st.session_state.confirm_solution_removal = None
                st.session_state.pending_chat_input = None
                st.rerun()

    else:
        if prompt := st.chat_input("Input..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
                
            # Check if solution space exists
            has_solutions = ss is not None and len(ss.get("candidates", [])) > 0
            
            if has_solutions:
                st.session_state.confirm_solution_removal = "pending"
                st.session_state.pending_chat_input = prompt
                st.rerun()
            else:
                success = run_problem_workflow(prompt, remove_solutions=True)
                if success:
                    st.rerun()

# --- Column 2: Problem Space ---
with col_prob:
    render_problem_space(ps)

# --- Column 3: Solution Space ---
with col_sol:
    render_solution_space(ss)

if st.session_state.solution_processing:
    with col_nav:
        with st.spinner("Thinking..."):
            inputs = {
                "chat_input": "Add Solution", 
                "workspace_id": st.session_state.current_workspace_id,
                "version_id": st.session_state.current_version_id
            }
            config = {"configurable": {"thread_id": st.session_state.thread_id}}
            try:
                result = st.session_state.app_solution.invoke(inputs, config)
                st.session_state.solution_processing = False # Reset processing state
                if result and result.get("SaveState.final_version_id"):
                        st.session_state.current_version_id = result["SaveState.final_version_id"]
                        st.rerun()
            except Exception as e:
                st.session_state.solution_processing = False # Ensure reset on error
                st.error(f"Error generating solution: {e}")

