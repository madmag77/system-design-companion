import streamlit as st
import sys
from pathlib import Path

# Add path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services.workflow_service import run_solution_step
from app.services.session_manager import get_shortlisted_ids

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
            # Fix button label logic if needed, original code:
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
            # FIX: final_id used before assignment if not careful.
            # Original code:
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
