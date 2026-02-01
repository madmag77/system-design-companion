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

from wirl_pregel_runner.pregel_graph_builder import build_pregel_graph
from langgraph.checkpoint.memory import MemorySaver

from workflow_definitions.system_design.functions_companion import (
    load_workspace_state,
    extract_problem,
    save_state, 
    check_problem_space,
    refine_problem_space,
    generate_candidate,
    compare_solutions,
    expand_solution_candidates,
    generate_deep_comparison,
    generate_final_solution_document
)
from app.backend.workspace import WorkspaceManager

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

# --- Workflow Graphs ---
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


if "pending_solution_step" not in st.session_state:
    st.session_state.pending_solution_step = None

if "solution_processing" not in st.session_state:
    st.session_state.solution_processing = False

# --- Helpers ---

def run_solution_step(inputs, workflow_type="generate"):
    # workflow_type: 'generate', 'deep_dive', 'final'
    inputs["_workflow_type"] = workflow_type # Store type for execution loop
    st.session_state.pending_solution_step = inputs
    st.session_state.solution_processing = True

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
            logger.exception("Error running problem workflow")
    return False

def get_shortlisted_ids(ss):
    """Helper to get selected IDs from session state based on checkbox keys"""
    ids = []
    if ss and ss.get("candidates"):
        for c in ss["candidates"]:
            if st.session_state.get(f"select_{c['id']}"):
                ids.append(c['id'])
    return ids

# --- UI Renderers ---

def render_problem_space_content(ps):
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

def render_problem_space(ps):
    # Wrapper if needed, for legacy compatibility
    st.header("Problem Space")
    render_problem_space_content(ps)
    st.divider()

def render_brainstorming_candidates(ss, allow_add=True):
    current_candidates = ss.get("candidates", []) if ss else []
    
    if allow_add:
        if len(current_candidates) >= 10:
                st.warning("Maximum of 10 solutions reached.")
        else:
            st.button(
                "Add Solution", 
                type="primary", 
                use_container_width=True,
                on_click=lambda: run_solution_step({}, workflow_type="generate"),
                disabled=st.session_state.solution_processing
            )

    if not ss or not current_candidates:
        if not ss:
            st.info("Solution space not yet generated.")
        return

    tabs = st.tabs([f"Option {c['id']}" for c in current_candidates])
    
    for i, tab in enumerate(tabs):
        with tab:
            c = current_candidates[i]
            st.markdown(f"**Hypothesis:** {c['hypothesis']}")
            st.markdown(f"**Model:**\n{str(c.get('model', ''))}")
            st.markdown(f"**Reasoning:**\n{c.get('reasoning', '')}")

    if ss.get("comparison"):
        st.subheader("Comparison")
        st.markdown(ss["comparison"].get("analysis", ""))
        st.markdown(f"**Recommendation:** {ss['comparison'].get('recommendation', '')}")
        
    if ss.get("simplification_feedback"):
        st.info(f"**Simplification Idea:** {ss['simplification_feedback']}")

def render_shortlist_view(ss):
    st.header("Shortlist Candidates")
    st.write("Select 1-3 candidates to explore in depth.")
    
    if not ss:
        st.write("No candidates to shortlist.")
        return
        
    candidates = ss.get("candidates", [])
    if not candidates:
        st.write("No candidates to shortlist.")
        return

    # Display Candidates with Checkboxes
    selected_ids = get_shortlisted_ids(ss)
    
    cols = st.columns(2)
    for i, c in enumerate(candidates):
        with cols[i % 2]:
            with st.container(border=True):
                st.markdown(f"**Option {c['id']}**")
                st.write(c['hypothesis'])
                
                # Check restrictions
                is_selected = c['id'] in selected_ids
                disabled = len(selected_ids) >= 3 and not is_selected
                
                if st.checkbox("Select", key=f"select_{c['id']}", disabled=disabled):
                    pass # State updated auto
                    
    st.caption(f"Selected: {len(selected_ids)}/3")

def render_deep_dive_view(ss, mode="expand"):
    # mode: 'expand' or 'compare'
    
    if mode == "expand":
        st.header("Deep Dive Analysis")
        
        selected_ids = get_shortlisted_ids(ss)
        
        if not selected_ids:
            st.warning("Please go to 'Shortlist' tab and select 1-3 candidates.")
            return

        expanded = ss.get("expanded_candidates", [])
        expanded_ids = [c['id'] for c in expanded]
        
        # Check if selection matches data
        is_out_of_sync = set(selected_ids) != set(expanded_ids)
        
        # Always show button if missing or out of sync
        if not expanded or is_out_of_sync:
            btn_label = "Run Deep Dive" if not expanded else "Update Deep Dive (Selection Changed)"
            if st.button(btn_label, type="primary"):
                 run_solution_step({"selected_candidate_ids": selected_ids}, workflow_type="deep_dive")
            
            if not expanded:
                return
            st.divider()

        # If we have results, display them
        tabs = st.tabs([f"Option {c['id']}" for c in expanded])
        for i, t in enumerate(tabs):
            with t:
                c = expanded[i]
                st.subheader(c['hypothesis'])
                
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("#### Components")
                    for k in c.get('key_components', []):
                        st.markdown(f"- {k}")
                    st.markdown("#### Pros")
                    st.write(str(c.get('pros')))
                with c2:
                    st.markdown("#### Stats")
                    st.write(f"**Cost:** {c.get('estimated_cost')}")
                    st.write(f"**Complexity:** {c.get('implementation_complexity')}")
                    st.markdown("#### Cons")
                    st.write(str(c.get('cons')))
                    
                st.markdown("#### Architecture Description")
                st.write(c.get('architecture_diagram_description'))
                
    elif mode == "compare":
        st.header("Deep Comparison")
        
        # Check if Deep Dive is done
        if not ss.get("expanded_candidates"):
             st.warning("Please complete Deep Dive first.")
             return

        comp = ss.get("deep_comparison")
        if not comp:
             if st.button("Run Comparison", type="primary"):
                 run_solution_step({"current_phase": "DEEP_DIVE"}, workflow_type="deep_dive") 
             return
             
        st.markdown(str(comp.get('analysis')))
        st.markdown(f"### Recommendation: {comp.get('recommendation')}")
        st.info(f"Trade-offs: {comp.get('trade_offs')}")

def render_final_view(ss):
    st.header("Final Architecture Definition")
    
    # Check if comparison is done (optional but good flow)
    if not ss.get("deep_comparison"):
        st.warning("Please complete Deep Comparison first.")
        return
        
    doc = ss.get("final_solution")
    
    if not doc:
        # Show configuration for Final Gen
        expanded = ss.get("expanded_candidates", [])
        opts = [c['id'] for c in expanded]
        
        col1, col2 = st.columns([3, 1])
        with col1:
             # Default to first valid option if available, else 0
            idx = 0
            if opts:
                 final_id = st.selectbox("Select Solution to Finalize", opts)
            else:
                 st.write("No solutions to finalize.")
                 return
        with col2:
            st.write("")
            st.write("")
            if st.button("Generate Final SDD", type="primary"):
                 run_solution_step({"current_phase": "FINAL", "final_selected_id": final_id}, workflow_type="final")
        return
        
    st.title(doc.get("title", "System Design Document"))
    st.markdown("### Executive Summary")
    st.write(doc.get("executive_summary"))
    
    with st.expander("Detailed Architecture", expanded=True):
        st.write(doc.get("detailed_architecture"))
        
    with st.expander("Implementation Plan", expanded=True):
        st.write(doc.get("implementation_plan"))
        
    with st.expander("FAQ", expanded=False):
        st.write(doc.get("faq"))
        
    if st.button("Regenerate"):
        # Reset final?
        run_solution_step({"current_phase": "FINAL", "final_selected_id": ss.get("shortlisted_ids", [1])[0]}, workflow_type="final")


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
    if "confirm_solution_removal" not in st.session_state:
        st.session_state.confirm_solution_removal = None
    if "pending_chat_input" not in st.session_state:
        st.session_state.pending_chat_input = None

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
if st.session_state.pending_solution_step is not None:
    with st.spinner("Processing Workflow..."):
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
