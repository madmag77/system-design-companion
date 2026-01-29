import logging
import json
from typing import Dict, Any, List
from langchain_ollama import ChatOllama
from app.backend.workspace import WorkspaceManager, Workspace, ProblemSpace, SolutionSpace, SolutionCandidate, Comparison
from workflow_definitions.system_design.prompts_companion import (
    EXTRACT_PROBLEM_PROMPT
)

logger = logging.getLogger(__name__)

def get_llm(config: dict = None):
    model = "gemma3:27b"
    if config:
        model = config.get("model", model)
    return ChatOllama(model=model, temperature=0.1)

def save_state(problem_space: dict, workspace_id: str, has_changes: bool, config: dict = None) -> dict:
    if not workspace_id or not problem_space:
        logger.warning("save_state missing inputs")
        return {}
    
    if not has_changes:
        return {
            "final_version_id": workspace_id
        }
    
    save_res = update_workspace(workspace_id, problem_space, None, config)
    new_version_id = save_res.get("new_version_id")
    
    return {
        "final_version_id": new_version_id
    }

# --- Node Functions ---

def load_workspace_state(workspace_id: str, version_id: str, config: dict = None) -> dict:
    manager = WorkspaceManager()
    try:
        ws = manager.load_workspace(workspace_id, version_id)
        return {
            "problem_space": ws.problem_space.model_dump(),
            "solution_space": ws.solution_space.model_dump() if ws.solution_space else None
        }
    except FileNotFoundError:
        # Return empty if not found, assuming new workspace request
        return {
            "problem_space": ProblemSpace().model_dump(),
            "solution_space": None
        }

def extract_problem(chat_input: str, current_problem: dict, config: dict = None) -> dict:
    llm = get_llm(config)
    structured_llm = llm.with_structured_output(ProblemSpace)
    
    chain = EXTRACT_PROBLEM_PROMPT | structured_llm
    
    # Format inputs
    inputs = {
        "context": current_problem.get("context", ""),
        "invariants": current_problem.get("invariants", []),
        "goal": current_problem.get("goal", ""),
        "problem": current_problem.get("problem", ""),
        "variants": current_problem.get("variants", []),
        "chat_input": chat_input
    }
    
    result: ProblemSpace = chain.invoke(inputs)
    
    # Check for changes (simple equality check)
    has_changes = result.model_dump() != current_problem
    
    return {
        "new_problem_space": result.model_dump(),
        "has_changes": has_changes
    }


def update_workspace(workspace_id: str, problem_space: dict, solution_space: dict = None, config: dict = None, **kwargs) -> dict:
    logger.info(f"update_workspace called. ProblemSpace: {bool(problem_space)}, SolutionSpace: {bool(solution_space)}")

    manager = WorkspaceManager()
    
    # Generate new version ID (simple incremental or UUID)
    import uuid
    new_version = str(uuid.uuid4())[:8]
    
    # Reconstruct objects
    ps = ProblemSpace(**problem_space)
    # Solution space is optional/null now
    ss = SolutionSpace(**solution_space) if solution_space else None
    
    ws = Workspace(
        id=workspace_id,
        version=new_version,
        problem_space=ps,
        solution_space=ss
    )
    
    manager.save_workspace(ws)
    
    return {
        "new_version_id": new_version
    }
