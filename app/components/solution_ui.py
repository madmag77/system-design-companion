import streamlit as st

def render_brainstorming_candidates(ss):
    current_candidates = ss.get("candidates", []) if ss else []
    if not ss or not current_candidates:
        if not ss:
            st.info("Solution space not yet generated. Ask the agent to brainstorm options.")
        return

    for c in current_candidates:
        with st.container(border=True):
            st.markdown(f"### Option {c['id']}")
            st.markdown(f"**Hypothesis:** {c['hypothesis']}")
            st.markdown(f"**Model:** {str(c.get('model', ''))}")
            st.markdown(f"**Reasoning:** {c.get('reasoning', '')}")

    if ss.get("comparison"):
        st.subheader("Comparison")
        st.markdown(ss["comparison"].get("analysis", ""))
        st.markdown(f"**Recommendation:** {ss['comparison'].get('recommendation', '')}")
        
    if ss.get("simplification_feedback"):
        st.info(f"**Simplification Idea:** {ss['simplification_feedback']}")

def render_shortlist_view(ss):
    st.header("Shortlist Candidates")
    st.write("Tell the agent which 1-3 options to shortlist.")
    
    if not ss:
        st.write("No candidates to shortlist.")
        return
        
    candidates = ss.get("candidates", [])
    if not candidates:
        st.write("No candidates to shortlist.")
        return

    selected_ids = ss.get("shortlisted_ids", []) if ss else []
    if selected_ids:
        st.success(f"Shortlisted: {', '.join(map(str, selected_ids))}")
    else:
        st.info("No shortlist yet. Example: \"Shortlist 1 and 3\".")

    cols = st.columns(2)
    for i, c in enumerate(candidates):
        with cols[i % 2]:
            with st.container(border=True):
                is_selected = c['id'] in selected_ids
                status = " (Shortlisted)" if is_selected else ""
                st.markdown(f"**Option {c['id']}**{status}")
                st.write(c['hypothesis'])

def render_deep_dive_view(ss, mode="expand"):
    # mode: 'expand' or 'compare'
    
    if mode == "expand":
        st.header("Deep Dive Analysis")
        selected_ids = ss.get("shortlisted_ids", []) if ss else []

        if not selected_ids:
            st.info("No shortlist yet. Ask the agent to shortlist options before diving deep.")
            return

        expanded = ss.get("expanded_candidates", [])
        if not expanded:
            st.info("No deep dive results yet. Ask the agent to run a deep dive.")
            return

        for c in expanded:
            with st.container(border=True):
                st.subheader(f"Option {c['id']}: {c['hypothesis']}")

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
                st.markdown("#### Data Flow")
                st.write(c.get('data_flow'))
                
    elif mode == "compare":
        st.header("Deep Comparison")
        
        # Check if Deep Dive is done
        if not ss.get("expanded_candidates"):
             st.info("Please complete a deep dive before comparing options.")
             return

        comp = ss.get("deep_comparison")
        if not comp:
             st.info("No comparison yet. Ask the agent to compare the deep-dive options.")
             return
             
        st.markdown(str(comp.get('analysis')))
        st.markdown(f"### Recommendation: {comp.get('recommendation')}")
        st.info(f"Trade-offs: {comp.get('trade_offs')}")

def render_final_view(ss):
    st.header("Final Architecture Definition")
    
    # Check if comparison is done (optional but good flow)
    if not ss.get("deep_comparison"):
        st.info("Please complete a comparison before finalizing.")
        return
        
    doc = ss.get("final_solution")
    
    if not doc:
        expanded = ss.get("expanded_candidates", [])
        opts = [c['id'] for c in expanded]
        if opts:
            st.info(
                f"No final document yet. Ask the agent to finalize an option "
                f"(available: {', '.join(map(str, opts))})."
            )
        else:
            st.info("No solutions to finalize yet.")
        return
        
    st.title(doc.get("title", "System Design Document"))
    st.markdown("### Executive Summary")
    st.write(doc.get("executive_summary"))

    st.markdown("### Detailed Architecture")
    st.write(doc.get("detailed_architecture"))

    st.markdown("### Implementation Plan")
    st.write(doc.get("implementation_plan"))

    st.markdown("### FAQ")
    st.write(doc.get("faq"))
