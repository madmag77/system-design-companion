import re
from typing import List, Optional, Dict, Any

import streamlit as st
from langchain_core.prompts import ChatPromptTemplate

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

QUESTION_PROMPT = ChatPromptTemplate.from_template(
    """You are the System Design Companion. Answer the user's question clearly and concisely.
If you need missing info, ask one brief clarifying question.

Current Workspace Context:
Context: {context}
Goal: {goal}
Problem: {problem}
Invariants: {invariants}
Phase: {phase}

User Question: {question}
"""
)


def handle_agent_input(user_text: str, ps: dict, ss: Optional[dict]) -> Dict[str, Any]:
    """Handle a single user turn and decide how to respond and which workflow to run."""
    if st.session_state.solution_processing:
        return {
            "messages": [
                "I'm still processing the previous step. Once it finishes, we can continue."
            ],
            "rerun": False,
        }

    pending = st.session_state.get("agent_pending")
    if pending:
        return _handle_pending(pending, user_text, ps, ss)

    text = user_text.strip()
    lowered = text.lower()

    # Workspace management
    if _contains_any(
        lowered,
        [
            "new workspace",
            "create workspace",
            "start over",
            "start a new",
            "fresh workspace",
            "reset workspace",
            "new session",
            "new project",
        ],
    ):
        return _create_new_workspace()

    if _contains_any(lowered, ["list workspaces", "show workspaces", "available workspaces"]):
        return _list_workspaces()

    if _contains_any(lowered, ["switch workspace", "open workspace", "load workspace", "use workspace"]):
        return _switch_workspace(lowered)

    if _extract_workspace_id(text, st.session_state.workspace_manager.list_workspaces()):
        return _switch_workspace(text)

    # UI / workflow explanation
    if _is_ui_question(lowered):
        return {"messages": [UI_HELP_TEXT, _action_nudge("problem_update")], "rerun": False}

    # Intent routing (ordered from most specific to general)
    if _contains_any(lowered, ["final", "finalize", "finish", "recommendation", "decide"]):
        return _handle_finalize(text, ss)

    if _contains_any(lowered, ["compare", "comparison", "trade-off", "tradeoff"]):
        return _handle_compare(ss)

    if _contains_any(lowered, ["deep dive", "deep-dive", "expand", "details", "drill down"]):
        return _handle_deep_dive(text, ss)

    if _contains_any(lowered, ["shortlist", "short list", "select", "pick", "choose"]):
        return _handle_shortlist(text, ss)

    if _contains_any(
        lowered,
        [
            "brainstorm",
            "idea",
            "another idea",
            "new option",
            "another option",
            "add option",
            "add solution",
            "new solution",
            "another solution",
            "more solutions",
            "generate option",
            "generate solution",
        ],
    ):
        return _handle_brainstorm(ss)

    # General question (non-UI)
    if _looks_like_question(lowered):
        return _answer_general_question(text, ps, ss)

    mentioned = _extract_candidate_mentions(text, ss)
    if mentioned:
        st.session_state.agent_pending = {"type": "candidate_intent", "payload": {"ids": mentioned}}
        return {
            "messages": [
                f"I noticed you referenced option(s) {', '.join(map(str, mentioned))}. "
                "Should I shortlist them, run a deep dive, compare, or finalize?"
            ],
            "rerun": False,
        }

    # Default: treat as problem space update
    return _handle_problem_update(text, ps, ss)


def _handle_pending(pending: dict, user_text: str, ps: dict, ss: Optional[dict]) -> Dict[str, Any]:
    text = user_text.strip().lower()

    if pending.get("type") == "confirm_problem_update":
        if _is_affirmative(text):
            st.session_state.agent_pending = None
            prompt = pending.get("payload", {}).get("prompt", "")
            success = run_problem_workflow(prompt, remove_solutions=True)
            if success:
                return {
                    "messages": [
                        "Updated the problem context and cleared the solution space to keep everything consistent.",
                        _action_nudge("problem_update"),
                    ],
                    "rerun": True,
                }
            return {"messages": ["I ran into an issue updating the problem space."], "rerun": False}

        if _is_negative(text):
            st.session_state.agent_pending = None
            return {
                "messages": [
                    "No problem -- I didn't change the workspace. Let me know how you'd like to proceed."
                ],
                "rerun": False,
            }

        return {
            "messages": ["Please confirm: should I update the problem space and clear existing solutions?"],
            "rerun": False,
        }

    if pending.get("type") == "need_shortlist_ids":
        st.session_state.agent_pending = None
        return _handle_shortlist(user_text, ss)

    if pending.get("type") == "need_deep_dive_ids":
        st.session_state.agent_pending = None
        return _handle_deep_dive(user_text, ss)

    if pending.get("type") == "need_final_id":
        st.session_state.agent_pending = None
        return _handle_finalize(user_text, ss)

    if pending.get("type") == "need_workspace_id":
        st.session_state.agent_pending = None
        return _switch_workspace(user_text)

    if pending.get("type") == "candidate_intent":
        st.session_state.agent_pending = None
        ids = pending.get("payload", {}).get("ids", [])
        if not ids:
            return {"messages": ["Which option did you want to work with?"], "rerun": False}

        if _contains_any(text, ["shortlist", "short list", "select", "pick"]):
            return _handle_shortlist(f"shortlist {' '.join(map(str, ids))}", ss)
        if _contains_any(text, ["deep dive", "deep-dive", "expand", "details"]):
            return _handle_deep_dive(f"deep dive {' '.join(map(str, ids))}", ss)
        if _contains_any(text, ["compare", "comparison", "trade-off", "tradeoff"]):
            return _handle_compare(ss)
        if _contains_any(text, ["final", "finalize", "finish", "recommendation", "decide"]):
            return _handle_finalize(f"finalize {' '.join(map(str, ids))}", ss)

        if _is_negative(text):
            return {"messages": ["Okay, I won't take action yet."], "rerun": False}

        return {
            "messages": [
                "Should I shortlist, deep dive, compare, or finalize those options?"
            ],
            "rerun": False,
        }

    st.session_state.agent_pending = None
    return {"messages": ["I'm not sure what we were waiting on. Could you rephrase?"], "rerun": False}


def _handle_problem_update(text: str, ps: dict, ss: Optional[dict]) -> Dict[str, Any]:
    has_solutions = bool(ss and ss.get("candidates"))
    if has_solutions:
        st.session_state.agent_pending = {
            "type": "confirm_problem_update",
            "payload": {"prompt": text},
        }
        return {
            "messages": [
                "Updating the problem space will clear existing solutions to keep the workspace in sync. Proceed?"
            ],
            "rerun": False,
        }

    success = run_problem_workflow(text, remove_solutions=True)
    if success:
        return {
            "messages": [
                "Updated the problem context.",
                _action_nudge("problem_update"),
            ],
            "rerun": True,
        }
    return {"messages": ["I couldn't update the problem space just now."], "rerun": False}


def _handle_brainstorm(ss: Optional[dict]) -> Dict[str, Any]:
    current_candidates = ss.get("candidates", []) if ss else []
    if len(current_candidates) >= 10:
        return {
            "messages": [
                "We already have 10 options, which is the current limit. "
                "Tell me which ones to shortlist."
            ],
            "rerun": False,
        }

    run_solution_step({}, workflow_type="generate")
    return {
        "messages": [
            "Adding a new solution candidate now.",
            _action_nudge("brainstorm"),
        ],
        "rerun": False,
    }


def _handle_shortlist(text: str, ss: Optional[dict]) -> Dict[str, Any]:
    candidates = ss.get("candidates", []) if ss else []
    if not candidates:
        return {
            "messages": [
                "There are no brainstormed options yet. Ask me to generate some first."
            ],
            "rerun": False,
        }

    available_ids = [c["id"] for c in candidates]
    selected_ids = _extract_ids(text, available_ids)
    if not selected_ids:
        st.session_state.agent_pending = {"type": "need_shortlist_ids"}
        return {
            "messages": [
                f"Which options should I shortlist? Available options: {', '.join(map(str, available_ids))}."
            ],
            "rerun": False,
        }

    run_solution_step({"selected_candidate_ids": selected_ids}, workflow_type="shortlist")
    return {
        "messages": [
            f"Shortlisting options {', '.join(map(str, selected_ids))}.",
            _action_nudge("shortlist"),
        ],
        "rerun": False,
    }


def _handle_deep_dive(text: str, ss: Optional[dict]) -> Dict[str, Any]:
    candidates = ss.get("candidates", []) if ss else []
    if not candidates:
        return {
            "messages": [
                "There are no options to expand yet. Ask me to brainstorm first."
            ],
            "rerun": False,
        }

    available_ids = [c["id"] for c in candidates]
    selected_ids = _extract_ids(text, available_ids)
    if not selected_ids:
        shortlisted = ss.get("shortlisted_ids", []) if ss else []
        if shortlisted:
            selected_ids = shortlisted
        else:
            st.session_state.agent_pending = {"type": "need_deep_dive_ids"}
            return {
                "messages": [
                    f"Which options should I dive into? Available options: {', '.join(map(str, available_ids))}."
                ],
                "rerun": False,
            }

    run_solution_step({"selected_candidate_ids": selected_ids}, workflow_type="deep_dive")
    return {
        "messages": [
            f"Running a deep dive on options {', '.join(map(str, selected_ids))}.",
            _action_nudge("deep_dive"),
        ],
        "rerun": False,
    }


def _handle_compare(ss: Optional[dict]) -> Dict[str, Any]:
    if not ss or not ss.get("expanded_candidates"):
        return {
            "messages": [
                "I need deep-dive details before I can compare. "
                "Tell me which options to deep dive first."
            ],
            "rerun": False,
        }

    run_solution_step({"selected_candidate_ids": []}, workflow_type="deep_dive")
    return {
        "messages": [
            "Generating a comparison of the deep-dive options now.",
            _action_nudge("compare"),
        ],
        "rerun": False,
    }


def _handle_finalize(text: str, ss: Optional[dict]) -> Dict[str, Any]:
    expanded = ss.get("expanded_candidates", []) if ss else []
    if not expanded:
        return {
            "messages": [
                "I need deep-dive options before finalizing. Ask me to run a deep dive first."
            ],
            "rerun": False,
        }

    expanded_ids = [c["id"] for c in expanded]
    selected_id = _extract_single_id(text, expanded_ids)
    if selected_id is None:
        st.session_state.agent_pending = {"type": "need_final_id"}
        return {
            "messages": [
                f"Which option should I finalize? Available options: {', '.join(map(str, expanded_ids))}."
            ],
            "rerun": False,
        }

    run_solution_step({"final_selected_id": selected_id}, workflow_type="final")
    return {
        "messages": [
            f"Finalizing option {selected_id}.",
            _action_nudge("final"),
        ],
        "rerun": False,
    }


def _answer_general_question(text: str, ps: dict, ss: Optional[dict]) -> Dict[str, Any]:
    phase = get_workflow_phase(ss)
    try:
        llm = get_llm()
        prompt = QUESTION_PROMPT.format_prompt(
            context=ps.get("context", ""),
            goal=ps.get("goal", ""),
            problem=ps.get("problem", ""),
            invariants=ps.get("invariants", []),
            phase=phase,
            question=text,
        )
        response = llm.invoke(prompt.to_messages())
        answer = response.content.strip() if hasattr(response, "content") else str(response)
        if not answer:
            raise ValueError("Empty response")
        return {"messages": [answer], "rerun": False}
    except Exception:
        return {
            "messages": [
                "I can help with that. Could you clarify how this relates to the system you want to design?"
            ],
            "rerun": False,
        }


def _create_new_workspace() -> Dict[str, Any]:
    import uuid

    new_id = str(uuid.uuid4())
    st.session_state.current_workspace_id = new_id
    st.session_state.current_version_id = "v1"
    st.session_state.messages = []
    return {
        "messages": [f"Created a new workspace: `{new_id}`.", _action_nudge("problem_update")],
        "rerun": True,
    }


def _list_workspaces() -> Dict[str, Any]:
    workspaces = st.session_state.workspace_manager.list_workspaces()
    if not workspaces:
        return {
            "messages": [
                "No saved workspaces yet. Say \"new workspace\" to start one."
            ],
            "rerun": False,
        }

    items = ", ".join(f"`{ws}`" for ws in workspaces)
    return {"messages": [f"Available workspaces: {items}."], "rerun": False}


def _switch_workspace(text: str) -> Dict[str, Any]:
    workspaces = st.session_state.workspace_manager.list_workspaces()
    if not workspaces:
        return {
            "messages": [
                "No saved workspaces yet. Say \"new workspace\" to start one."
            ],
            "rerun": False,
        }

    target = _extract_workspace_id(text, workspaces)
    if not target:
        st.session_state.agent_pending = {"type": "need_workspace_id"}
        return {
            "messages": [
                f"Which workspace should I open? Available: {', '.join(workspaces)}."
            ],
            "rerun": False,
        }

    st.session_state.current_workspace_id = target
    versions = st.session_state.workspace_manager.list_versions(target)
    st.session_state.current_version_id = versions[-1] if versions else "v1"
    st.session_state.messages = []
    return {
        "messages": [f"Switched to workspace `{target}`."],
        "rerun": True,
    }


def _action_nudge(action: str) -> str:
    nudges = {
        "problem_update": "Want me to brainstorm solution options next?",
        "brainstorm": "Want to shortlist 1-3 options? Tell me the option numbers.",
        "shortlist": "Want a deep dive on the shortlisted options?",
        "deep_dive": "Want me to compare the deep-dive options and recommend one?",
        "compare": "Want me to finalize a recommendation? Tell me the option number.",
        "final": "We have a final solution. Want refinements, or should we wrap up?",
    }
    return nudges.get(action, "")


def _extract_ids(text: str, available_ids: List[int]) -> List[int]:
    found = [int(match) for match in re.findall(r"\b\d+\b", text)]
    filtered = [i for i in found if i in available_ids]
    # Preserve order and uniqueness
    seen = set()
    result = []
    for i in filtered:
        if i not in seen:
            result.append(i)
            seen.add(i)
    return result


def _extract_single_id(text: str, available_ids: List[int]) -> Optional[int]:
    ids = _extract_ids(text, available_ids)
    return ids[0] if ids else None


def _extract_candidate_mentions(text: str, ss: Optional[dict]) -> List[int]:
    candidates = ss.get("candidates", []) if ss else []
    if not candidates:
        return []
    available_ids = [c["id"] for c in candidates]
    return _extract_ids(text, available_ids)


def _extract_workspace_id(text: str, workspaces: List[str]) -> Optional[str]:
    lowered = text.lower()
    for ws in workspaces:
        if ws.lower() in lowered:
            return ws

    tokens = re.findall(r"[a-f0-9-]{6,}", lowered)
    for token in tokens:
        matches = [ws for ws in workspaces if ws.lower().startswith(token)]
        if len(matches) == 1:
            return matches[0]
    return None


def _contains_any(text: str, keywords: List[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _looks_like_question(text: str) -> bool:
    if text.endswith("?"):
        return True
    return any(
        text.startswith(prefix)
        for prefix in (
            "what",
            "why",
            "how",
            "when",
            "where",
            "who",
            "can ",
            "could ",
            "should ",
            "do ",
            "does ",
            "is ",
            "are ",
            "explain",
            "help",
        )
    )


def _is_ui_question(text: str) -> bool:
    if not _looks_like_question(text):
        return False
    return _contains_any(
        text,
        [
            "tab",
            "tabs",
            "problem context",
            "brainstorm",
            "shortlist",
            "deep dive",
            "comparison",
            "final",
            "workspace",
            "version",
            "phase",
            "ui",
            "screen",
            "interface",
        ],
    )


def _is_affirmative(text: str) -> bool:
    return _contains_any(
        text,
        [
            "yes",
            "yep",
            "yeah",
            "sure",
            "ok",
            "okay",
            "do it",
            "go ahead",
            "please",
            "confirm",
        ],
    )


def _is_negative(text: str) -> bool:
    return _contains_any(text, ["no", "nope", "nah", "stop", "cancel", "don't", "do not"])
