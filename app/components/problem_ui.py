import streamlit as st

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
