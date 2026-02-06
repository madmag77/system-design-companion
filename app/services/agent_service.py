from typing import List, Optional, Dict, Any, Literal

import streamlit as st
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.services.session_manager import get_workflow_phase
from app.services.workflow_service import run_problem_workflow, run_solution_step
from workflow_definitions.system_design.functions_companion import get_llm


UI_HELP_TEXT = (
    "You're in a workspace that moves through six phases: "
    "Problem Context -> Brainstorming -> Shortlist -> Deep Dive -> Comparison -> Final Solution. "
    "Use this chat to update the workspace at any time. For example: "
    "\"Design a rate limiter\", \"Brainstorm a new option\", \"Shortlist 1 and 3\", "
    "\"Deep dive 1 and 3\", \"Compare the shortlisted options\", or \"Finalize option 2\"."
)

AGENT_ACTION_PROMPT = ChatPromptTemplate.from_template(
    """You are the System Design Companion. Decide the next action and provide a response.
You may only choose one action from:
- respond
- explain_ui
- list_workspaces
- new_workspace
- switch_workspace
- update_problem
- confirm_destructive
- brainstorm
- shortlist
- deep_dive
- compare
- finalize

Rules:
- Use respond to ask a clarifying question or answer without changing the workspace.
- Only update the workspace by choosing a non-respond action.
- If a destructive change is pending, and the user confirms, choose confirm_destructive with confirm=true.
- If the user declines, choose confirm_destructive with confirm=false.
- If you need missing IDs, ask a short question via respond.
- If a destructive change is pending, resolve it before taking other actions.
- Do not ask for confirmation yourself. Use update_problem to trigger confirmation.
- If the user requests edits to the problem space (context, invariants, goal, problem, variants), choose update_problem.
- If the user asks to generate, brainstorm, add, or create another solution/option/candidate, choose brainstorm.
- Never write solution candidates directly in respond. Use brainstorm to create them.
Field requirements:
- switch_workspace: set workspace_id
- shortlist/deep_dive: set option_ids (list of integers)
- finalize: set option_id
- brainstorm: set hint if the user specifies a theme or focus area
- confirm_destructive: set confirm true or false

Workspace:
ID: {workspace_id}
Version: {version_id}
Phase: {phase}
Pending: {pending}

Problem Space:
Context: {context}
Goal: {goal}
Problem: {problem}
Invariants: {invariants}
Variants: {variants}

Solution Space:
Candidates: {candidates}
Shortlisted IDs: {shortlisted_ids}
Expanded Candidates: {expanded_candidates}
Deep Comparison: {has_comparison}
Final Solution: {has_final}

Last assistant message: {last_assistant}
User message: {user_text}
"""
)


class AgentAction(BaseModel):
    action: Literal[
        "respond",
        "explain_ui",
        "list_workspaces",
        "new_workspace",
        "switch_workspace",
        "update_problem",
        "confirm_destructive",
        "brainstorm",
        "shortlist",
        "deep_dive",
        "compare",
        "finalize",
    ]
    response: str = Field(default="", description="Assistant response to show the user.")
    workspace_id: Optional[str] = None
    option_ids: Optional[List[int]] = None
    option_id: Optional[int] = None
    confirm: Optional[bool] = None
    hint: Optional[str] = None


def handle_agent_input(user_text: str, ps: dict, ss: Optional[dict]) -> Dict[str, Any]:
    """Handle a single user turn using a tool-like LLM decision."""
    if st.session_state.solution_processing:
        return {
            "messages": [
                "I'm still processing the previous step. Once it finishes, we can continue."
            ],
            "rerun": False,
        }

    phase = get_workflow_phase(ss)
    pending = st.session_state.get("agent_pending")
    if pending and pending.get("type") == "confirm_problem_update":
        normalized = user_text.strip().lower()
        if _is_affirmative(normalized):
            response = _confirm_destructive(True)
            return {"messages": [response], "rerun": st.session_state.agent_needs_rerun}
        if _is_negative(normalized):
            response = _confirm_destructive(False)
            return {"messages": [response], "rerun": st.session_state.agent_needs_rerun}

    st.session_state.agent_context = {
        "problem_space": ps or {},
        "solution_space": ss or {},
        "phase": phase,
        "pending": pending,
        "workspace_id": st.session_state.current_workspace_id,
        "version_id": st.session_state.current_version_id,
    }
    st.session_state.agent_needs_rerun = False

    try:
        action = _decide_action(user_text, ps or {}, ss or {}, phase, pending)
    except Exception:
        return {
            "messages": ["I had trouble understanding that. Could you rephrase?"],
            "rerun": False,
        }

    response = _execute_action(action, user_text, ps or {}, ss or {})
    return {"messages": [response], "rerun": st.session_state.agent_needs_rerun}


def _decide_action(user_text: str, ps: dict, ss: dict, phase: str, pending: Optional[dict]) -> AgentAction:
    candidates = ss.get("candidates", []) if ss else []
    expanded = ss.get("expanded_candidates", []) if ss else []
    shortlisted = ss.get("shortlisted_ids", []) if ss else []
    has_comparison = bool(ss.get("deep_comparison")) if ss else False
    has_final = bool(ss.get("final_solution")) if ss else False

    pending_line = "None"
    if pending and pending.get("type") == "confirm_problem_update":
        pending_line = "Confirmation required to update the problem space (would clear solutions)."

    candidate_lines = [f"{c.get('id')}: {c.get('hypothesis', '')}" for c in candidates]
    expanded_lines = [f"{c.get('id')}: {c.get('hypothesis', '')}" for c in expanded]

    last_assistant = _last_assistant_message()
    prompt = AGENT_ACTION_PROMPT.format_prompt(
        workspace_id=st.session_state.current_workspace_id,
        version_id=st.session_state.current_version_id,
        phase=phase,
        pending=pending_line,
        context=ps.get("context", ""),
        goal=ps.get("goal", ""),
        problem=ps.get("problem", ""),
        invariants=ps.get("invariants", []),
        variants=ps.get("variants", []),
        candidates=candidate_lines or "None",
        shortlisted_ids=shortlisted,
        expanded_candidates=expanded_lines or "None",
        has_comparison=has_comparison,
        has_final=has_final,
        user_text=user_text,
        last_assistant=last_assistant,
    )

    llm = get_llm()
    structured_llm = llm.with_structured_output(AgentAction)
    return structured_llm.invoke(prompt.to_messages())


def _execute_action(action: AgentAction, user_text: str, ps: dict, ss: dict) -> str:
    if action.action == "respond":
        return action.response or "What would you like to do next?"
    if action.action == "explain_ui":
        return UI_HELP_TEXT
    if action.action == "list_workspaces":
        return _list_workspaces()
    if action.action == "new_workspace":
        st.session_state.current_action_label = "Creating new workspace..."
        return _new_workspace()
    if action.action == "switch_workspace":
        st.session_state.current_action_label = "Switching workspace..."
        return _switch_workspace(action.workspace_id)
    if action.action == "update_problem":
        st.session_state.current_action_label = "Updating problem space..."
        return _update_problem(user_text)
    if action.action == "confirm_destructive":
        if action.confirm is None:
            return "Please confirm with yes or no."
        st.session_state.current_action_label = "Updating problem space..."
        return _confirm_destructive(action.confirm)
    if action.action == "brainstorm":
        st.session_state.current_action_label = "Generating a solution candidate..."
        return _brainstorm_candidate(action.hint)
    if action.action == "shortlist":
        st.session_state.current_action_label = "Updating shortlist..."
        return _shortlist_candidates(action.option_ids)
    if action.action == "deep_dive":
        st.session_state.current_action_label = "Running deep dive..."
        return _deep_dive_candidates(action.option_ids)
    if action.action == "compare":
        st.session_state.current_action_label = "Comparing deep-dive options..."
        return _compare_candidates()
    if action.action == "finalize":
        st.session_state.current_action_label = "Generating final solution..."
        return _finalize_solution(action.option_id)
    return action.response or "What would you like to do next?"


def _last_assistant_message() -> str:
    history = st.session_state.messages if st.session_state.messages else []
    for msg in reversed(history):
        if msg.get("role") == "assistant":
            return msg.get("content", "")
    return ""


def _is_affirmative(text: str) -> bool:
    return text in {
        "yes",
        "yes please",
        "yep",
        "yeah",
        "sure",
        "ok",
        "okay",
        "do it",
        "go ahead",
        "confirm",
    }


def _is_negative(text: str) -> bool:
    return text in {
        "no",
        "nope",
        "nah",
        "stop",
        "cancel",
        "don't",
        "do not",
    }


def _list_workspaces() -> str:
    workspaces = st.session_state.workspace_manager.list_workspaces()
    if not workspaces:
        return "No saved workspaces yet. Say 'new workspace' to start one."
    items = ", ".join(workspaces)
    return f"Available workspaces: {items}."


def _new_workspace() -> str:
    import uuid

    new_id = str(uuid.uuid4())
    st.session_state.current_workspace_id = new_id
    st.session_state.current_version_id = "v1"
    st.session_state.messages = []
    st.session_state.agent_needs_rerun = True
    return f"Created a new workspace: {new_id}."


def _switch_workspace(workspace_id: Optional[str]) -> str:
    if not workspace_id:
        return "Which workspace should I open?"
    workspaces = st.session_state.workspace_manager.list_workspaces()
    if workspace_id not in workspaces:
        return f"I could not find workspace '{workspace_id}'. Try list_workspaces first."

    st.session_state.current_workspace_id = workspace_id
    versions = st.session_state.workspace_manager.list_versions(workspace_id)
    st.session_state.current_version_id = versions[-1] if versions else "v1"
    st.session_state.messages = []
    st.session_state.agent_needs_rerun = True
    return f"Switched to workspace {workspace_id}."


def _update_problem(prompt: str) -> str:
    context = st.session_state.get("agent_context", {})
    ss = context.get("solution_space") or {}
    has_solutions = bool(ss.get("candidates"))

    if has_solutions:
        st.session_state.agent_pending = {
            "type": "confirm_problem_update",
            "payload": {"prompt": prompt},
        }
        return (
            "Updating the problem space will clear existing solutions to keep the workspace in sync. "
            "Reply 'yes' to confirm or 'no' to cancel."
        )

    with st.spinner(st.session_state.current_action_label):
        success = run_problem_workflow(prompt, remove_solutions=True, show_spinner=False)
    if success:
        st.session_state.agent_needs_rerun = True
        return "Updated the problem context."
    return "I couldn't update the problem space just now."


def _confirm_destructive(confirm: bool) -> str:
    pending = st.session_state.get("agent_pending")
    if not pending or pending.get("type") != "confirm_problem_update":
        return "There is no pending change to confirm."

    if not confirm:
        st.session_state.agent_pending = None
        return "Okay, I did not change the workspace."

    prompt = pending.get("payload", {}).get("prompt", "")
    st.session_state.agent_pending = None
    with st.spinner(st.session_state.current_action_label):
        success = run_problem_workflow(prompt, remove_solutions=True, show_spinner=False)
    if success:
        st.session_state.agent_needs_rerun = True
        return "Updated the problem context and cleared the solution space."
    return "I ran into an issue updating the problem space."


def _brainstorm_candidate(hint: Optional[str] = None) -> str:
    context = st.session_state.get("agent_context", {})
    ss = context.get("solution_space") or {}
    candidates = ss.get("candidates", [])
    if len(candidates) >= 10:
        return "We already have 10 options, which is the current limit."

    inputs = {}
    if hint:
        inputs["hint"] = hint
    run_solution_step(inputs, workflow_type="generate")
    st.session_state.agent_needs_rerun = True
    if hint:
        return f"Adding a new solution candidate with a focus on: {hint}."
    return "Adding a new solution candidate now."


def _shortlist_candidates(option_ids: Optional[List[int]]) -> str:
    context = st.session_state.get("agent_context", {})
    ss = context.get("solution_space") or {}
    candidates = ss.get("candidates", [])
    if not candidates:
        return "There are no brainstormed options yet. Ask me to generate some first."

    available = [c.get("id") for c in candidates]
    if not option_ids:
        return f"Which options should I shortlist? Available options: {available}."

    invalid = [oid for oid in option_ids if oid not in available]
    if invalid:
        return f"Unknown option IDs: {invalid}. Available options: {available}."

    if len(option_ids) > 3:
        return "Please pick up to 3 options to shortlist."

    run_solution_step({"selected_candidate_ids": option_ids}, workflow_type="shortlist")
    st.session_state.agent_needs_rerun = True
    return f"Shortlisting options {option_ids}."


def _deep_dive_candidates(option_ids: Optional[List[int]] = None) -> str:
    context = st.session_state.get("agent_context", {})
    ss = context.get("solution_space") or {}
    candidates = ss.get("candidates", [])
    if not candidates:
        return "There are no options to expand yet. Ask me to brainstorm first."

    available = [c.get("id") for c in candidates]
    selected = option_ids or ss.get("shortlisted_ids", [])

    if not selected:
        return f"Which options should I dive into? Available options: {available}."

    invalid = [oid for oid in selected if oid not in available]
    if invalid:
        return f"Unknown option IDs: {invalid}. Available options: {available}."

    run_solution_step({"selected_candidate_ids": selected}, workflow_type="deep_dive")
    st.session_state.agent_needs_rerun = True
    return f"Running a deep dive on options {selected}."


def _compare_candidates() -> str:
    context = st.session_state.get("agent_context", {})
    ss = context.get("solution_space") or {}
    if not ss.get("expanded_candidates"):
        return "I need deep-dive details before I can compare. Tell me which options to deep dive first."

    run_solution_step({"selected_candidate_ids": []}, workflow_type="deep_dive")
    st.session_state.agent_needs_rerun = True
    return "Generating a comparison of the deep-dive options now."


def _finalize_solution(option_id: Optional[int]) -> str:
    context = st.session_state.get("agent_context", {})
    ss = context.get("solution_space") or {}
    expanded = ss.get("expanded_candidates", [])
    if not expanded:
        return "I need deep-dive options before finalizing. Ask me to run a deep dive first."

    if option_id is None:
        available = [c.get("id") for c in expanded]
        return f"Which option should I finalize? Available options: {available}."

    available = [c.get("id") for c in expanded]
    if option_id not in available:
        return f"Unknown option ID: {option_id}. Available options: {available}."

    run_solution_step({"final_selected_id": option_id}, workflow_type="final")
    st.session_state.agent_needs_rerun = True
    return f"Finalizing option {option_id}."
