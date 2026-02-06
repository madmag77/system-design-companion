import streamlit as st
import logging
import sys
from pathlib import Path
from langgraph.checkpoint.memory import MemorySaver

# Add path for reference implementations
# Original was app/streamlit_app.py -> parent.parent is root.
# Now app/services/workflow_service.py -> parent.parent.parent is root.
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from wirl_pregel_runner.pregel_graph_builder import build_pregel_graph
from workflow_definitions.system_design.functions_companion import (
    load_workspace_state,
    extract_problem,
    save_state, 
    check_problem_space,
    refine_problem_space,
    generate_candidate,
    compare_solutions,
    update_shortlist,
    expand_solution_candidates,
    generate_deep_comparison,
    generate_final_solution_document
)

logger = logging.getLogger(__name__)

def initialize_workflows():
    """Initialize all workflow graphs in session state."""
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

    if "app_deep_dive" not in st.session_state:
        fn_map_dd = {
            "load_workspace_state": load_workspace_state,
            "expand_solution_candidates": expand_solution_candidates,
            "generate_deep_comparison": generate_deep_comparison,
            "save_state": save_state,
        }
        dd_workflow_path = "workflow_definitions/system_design/deep_dive_companion.wirl"
        st.session_state.app_deep_dive = build_pregel_graph(dd_workflow_path, fn_map_dd, checkpointer=MemorySaver())

    if "app_final" not in st.session_state:
        fn_map_final = {
            "load_workspace_state": load_workspace_state,
            "generate_final_solution_document": generate_final_solution_document,
            "save_state": save_state,
        }
        final_workflow_path = "workflow_definitions/system_design/final_solution_companion.wirl"
        st.session_state.app_final = build_pregel_graph(final_workflow_path, fn_map_final, checkpointer=MemorySaver())

    if "app_shortlist" not in st.session_state:
        fn_map_shortlist = {
            "load_workspace_state": load_workspace_state,
            "update_shortlist": update_shortlist,
            "save_state": save_state,
        }
        shortlist_workflow_path = "workflow_definitions/system_design/shortlist_companion.wirl"
        st.session_state.app_shortlist = build_pregel_graph(shortlist_workflow_path, fn_map_shortlist, checkpointer=MemorySaver())

def run_solution_step(inputs, workflow_type="generate"):
    # workflow_type: 'generate', 'deep_dive', 'final'
    inputs["_workflow_type"] = workflow_type # Store type for execution loop
    st.session_state.pending_solution_step = inputs
    st.session_state.solution_processing = True

def run_problem_workflow(prompt, remove_solutions=True, show_spinner=True, spinner_label="Refining Problem Space..."):
    def _run():
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
            logger.exception("Error running problem workflow")
        return False

    if show_spinner:
        with st.spinner(spinner_label):
            return _run()
    return _run()

def process_pending_solution_step(show_spinner=True, spinner_label="Processing Workflow..."):
    """Execution loop for pending solution steps."""
    if st.session_state.get("pending_solution_step") is None:
        return

    def _run():
        inputs = st.session_state.pending_solution_step
        workflow_type = inputs.pop("_workflow_type", "generate")
        
        config = {"configurable": {"thread_id": st.session_state.thread_id}}
        try:
            base_inputs = {
                "chat_input": "Execute Step", 
                "workspace_id": st.session_state.current_workspace_id,
                "version_id": st.session_state.current_version_id
            }
            final_inputs = {**base_inputs, **inputs}
            
            if workflow_type == "deep_dive":
                result = st.session_state.app_deep_dive.invoke(final_inputs, config)
            elif workflow_type == "final":
                result = st.session_state.app_final.invoke(final_inputs, config)
            elif workflow_type == "shortlist":
                result = st.session_state.app_shortlist.invoke(final_inputs, config)
            else:
                result = st.session_state.app_solution.invoke(final_inputs, config)
            
            st.session_state.pending_solution_step = None
            st.session_state.solution_processing = False
            
            if result and result.get("SaveState.final_version_id"):
                    st.session_state.current_version_id = result["SaveState.final_version_id"]
                    st.rerun()
        except Exception as e:
            st.session_state.pending_solution_step = None
            st.session_state.solution_processing = False
            st.error(f"Error executing solution step: {e}")
            logger.exception("Error during execution loop")

    if show_spinner:
        with st.spinner(spinner_label):
            _run()
    else:
        _run()
