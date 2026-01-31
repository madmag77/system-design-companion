import logging
import json
from typing import Dict, Any, List
from langchain_ollama import ChatOllama
from app.backend.workspace import WorkspaceManager, Workspace, ProblemSpace, SolutionSpace, SolutionCandidate, Comparison
from pydantic import BaseModel
from workflow_definitions.system_design.prompts_companion import (
    EXTRACT_PROBLEM_PROMPT,
    CHECK_PROBLEM_SPACE_PROMPT,
    REFINE_PROBLEM_SPACE_PROMPT,
    GENERATE_CANDIDATE_PROMPT,
    COMPARE_SOLUTIONS_PROMPT
)

logger = logging.getLogger(__name__)

def get_llm(config: dict = None):
    model = "gemma3:27b"
    temperature = 0.1
    if config:
        model = config.get("model", model)
        temperature = float(config.get("temperature", temperature))
    return ChatOllama(model=model, temperature=temperature)

def save_state(problem_space: dict, workspace_id: str, has_changes: bool = False, solution_space: dict = None, remove_solutions: bool = False, config: dict = None) -> dict:
    if not workspace_id or not problem_space:
        logger.warning("save_state missing inputs")
        return {}
    
    if not has_changes and not solution_space:
        return {
            "final_version_id": workspace_id
        }
    
    # Handle solution space logic
    # If remove_solutions is True (default), we clear solution_space
    # unless we are in the solution workflow (where solution_space is newly generated).
    # But this function is used by 'companion.wirl' (Problem Space flow) AND 'solution_companion.wirl' (Solution flow)?
    # We need to be careful.
    # In solution flow, 'remove_solutions' likely won't be passed or False.
    # Actually, solution flow calls save_state too?
    # Let's check 'functions_companion.py' imports again. 
    # Yes, one save_state shared.
    
    # Logic:
    # If remove_solutions is True, we FORCE solution_space to None (even if passed).
    # BUT wait, update_workspace takes solution_space.
    # If we are in Problem Space flow:
    #   Old solution_space is passed (from LoadWorkspace).
    #   If remove_solutions=True -> ss = None.
    #   If remove_solutions=False -> ss = Old solution_space.
    
    if remove_solutions:
         # Only clear if we are NOT passing a NEW solution space?
         # If this function is called from Solution Workflow, solution_space is NEWLY generated.
         # The 'remove_solutions' flag should probably default to False in Python, but True in WIRL (companion.wirl)?
         # Or better: check if solution_space is passed.
         
         # The issue: In Problem Space flow, solution_space passed is OLD.
         # In Solution Space flow, solution_space passed is NEW.
         # We need to distinguish.
         
         # Assuming 'remove_solutions' is mainly a flag from the UI/Problem Workflow.
         # If I don't pass it in Solution Workflow, it defaults to False (safe).
         # So change default to False?
         # If default is False, then existing calls (Solution Workflow) work.
         # In Companion Wirl, I will pass it explicitly.
         pass # Handled below
         
    if remove_solutions:
        solution_space = None

    save_res = update_workspace(workspace_id, problem_space, solution_space, config)
    new_version_id = save_res.get("new_version_id")
    
    return {
        "final_version_id": new_version_id
    }

# --- Node Functions ---

def load_workspace_state(workspace_id: str, version_id: str, config: dict = None) -> dict:
    manager = WorkspaceManager()
    try:
        ws = manager.load_workspace(workspace_id, version_id)
        
        # Sanitize solution space to remove duplicates if any exist
        if ws.solution_space and ws.solution_space.candidates:
            seen_ids = set()
            unique_candidates = []
            for cand in ws.solution_space.candidates:
                if cand.id not in seen_ids:
                    unique_candidates.append(cand)
                    seen_ids.add(cand.id)
            ws.solution_space.candidates = unique_candidates
            
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

class Observations(BaseModel):
    items: List[str]

def check_problem_space(problem_space: dict, config: dict = None) -> dict:
    llm = get_llm(config)
    structured_llm = llm.with_structured_output(Observations)
    
    chain = CHECK_PROBLEM_SPACE_PROMPT | structured_llm
    
    # Format inputs (unpacking the problem space dict)
    inputs = {
        "context": problem_space.get("context", ""),
        "invariants": problem_space.get("invariants", []),
        "goal": problem_space.get("goal", ""),
        "problem": problem_space.get("problem", ""),
        "variants": problem_space.get("variants", [])
    }
    
    result: Observations = chain.invoke(inputs)
    
    return {
        "observations": result.items
    }

def refine_problem_space(current_problem: dict, chat_input: str, observations: List[str], previous_has_changes: bool, config: dict = None) -> dict:
    if not observations or (len(observations) == 1 and observations[0].lower() == "consistent"):
        # No refinement needed
        return {
            "new_problem_space": current_problem,
            "has_changes": previous_has_changes
        }

    llm = get_llm(config)
    structured_llm = llm.with_structured_output(ProblemSpace)
    
    chain = REFINE_PROBLEM_SPACE_PROMPT | structured_llm
    
    inputs = {
        "context": current_problem.get("context", ""),
        "invariants": current_problem.get("invariants", []),
        "goal": current_problem.get("goal", ""),
        "problem": current_problem.get("problem", ""),
        "variants": current_problem.get("variants", []),
        "chat_input": chat_input,
        "observations": "\n".join(f"- {obs}" for obs in observations)
    }
    
    result: ProblemSpace = chain.invoke(inputs)
    
    # Check for changes
    refine_changes = result.model_dump() != current_problem
    
    return {
        "new_problem_space": result.model_dump(),
        "has_changes": previous_has_changes or refine_changes
    }

class ComparisonResult(BaseModel):
    analysis: str
    recommendation: str
    simplification_feedback: str

def generate_candidate(problem_space: dict, solution_space: dict = None, config: dict = None) -> dict:
    logger.info("generate_candidate called")
    llm = get_llm(config)
    structured_llm = llm.with_structured_output(SolutionCandidate)
    
    chain = GENERATE_CANDIDATE_PROMPT | structured_llm
    
    # Extract existing candidates
    existing_candidates = solution_space.get("candidates", []) if solution_space else []
    logger.info(f"Existing candidates count: {len(existing_candidates)}")
    
    # Format existing candidates for context
    existing_summary = ""
    if existing_candidates:
        for idx, c in enumerate(existing_candidates):
            existing_summary += f"\nCandidate {idx+1}: {c.get('hypothesis', '')} | {c.get('model', '')[:100]}..."
    else:
        existing_summary = "None"

    inputs = {
        "context": problem_space.get("context", ""),
        "invariants": problem_space.get("invariants", []),
        "goal": problem_space.get("goal", ""),
        "problem": problem_space.get("problem", ""),
        "variants": problem_space.get("variants", []),
        "existing_candidates": existing_summary
    }
    
    try:
        logger.info("Invoking LLM for generate_candidate")
        result: SolutionCandidate = chain.invoke(inputs)
        logger.info(f"LLM returned candidate: {result.hypothesis[:50]}...")
    except Exception as e:
        logger.error(f"Error in generate_candidate LLM invoke: {e}")
        raise e
    
    # Assign ID based on max existing ID + 1 to handle gaps
    next_id = 1
    if existing_candidates:
        # existing_candidates are dicts here (model_dump output)
        max_id = max((c.get('id', 0) for c in existing_candidates), default=0)
        next_id = max_id + 1
        
    result.id = next_id
    
    ret = {
        "candidate": result.model_dump()
    }
    logger.info(f"generate_candidate returning dict keys: {ret.keys()}")
    return ret

def compare_solutions(problem_space: dict, solution_space: dict = None, candidate: dict = None, config: dict = None) -> dict:
    logger.info(f"compare_solutions called. Has candidate: {candidate is not None}")
    
    
    # Combine old candidates and new candidate
    # Use deepcopy to avoid mutating the inputs which might be shared references in the workflow state
    import copy
    candidates = []
    if solution_space and "candidates" in solution_space:
        candidates = copy.deepcopy(solution_space["candidates"])
    
    if candidate:
        candidates.append(candidate)
    
    logger.info(f"Total candidates to compare: {len(candidates)}")
        
    if not candidates:
        logger.warning("No candidates to compare, returning empty dict")
        return {}

    llm = get_llm(config)
    structured_llm = llm.with_structured_output(ComparisonResult)
    
    chain = COMPARE_SOLUTIONS_PROMPT | structured_llm
    
    # Format candidates
    candidates_text = ""
    for c in candidates:
        candidates_text += f"\n-- Candidate {c['id']} --\nHypothesis: {c['hypothesis']}\nModel: {c['model']}\nReasoning: {c['reasoning']}\n"

    inputs = {
        "context": problem_space.get("context", ""),
        "invariants": problem_space.get("invariants", []),
        "goal": problem_space.get("goal", ""),
        "problem": problem_space.get("problem", ""),
        "candidates": candidates_text
    }
    
    result: ComparisonResult = chain.invoke(inputs)
    
    # Construct full SolutionSpace dict
    new_solution_space = {
        "candidates": candidates,
        "comparison": {
            "analysis": result.analysis,
            "recommendation": result.recommendation
        },
        "simplification_feedback": result.simplification_feedback
    }
    
    return {
        "solution_space": new_solution_space
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
