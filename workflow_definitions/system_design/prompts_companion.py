from langchain_core.prompts import ChatPromptTemplate

EXTRACT_PROBLEM_PROMPT = ChatPromptTemplate.from_template(
    """You are a System Design Companion. Your goal is to help defining the Problem Space.
    
    Current Problem Space:
    Invariants: {invariants}
    Goal: {goal}
    Problem: {problem}
    Variants: {variants}
    
    User Input: {chat_input}
    
    Based on the User Input, update the Problem Space.
    - If the user provides a new constraint, add as Invariant.
    - If the user defines the goal, set the Goal.
    - If the user describes the conflict, set the Problem.
    - If the user suggests degrees of freedom, add to Variants.
    - Maintain existing values unless the user explicitly changes them.
    
    Return the full updated Problem Space.
    """
)

DRAFT_SOLUTIONS_PROMPT = ChatPromptTemplate.from_template(
    """You are a System Design expert. Given the following Problem Space, generate 3 distinct solution candidates.
    
    Problem Space:
    Invariants: {invariants}
    Goal: {goal}
    Problem: {problem}
    Variants: {variants}
    
    Generate 3 candidates. For each candidate:
    1. Hypothesis: What changes in Variants enable the solution?
    2. Model: Brief technical description.
    
    Then provide a comparison and a recommendation.
    """
)

CRITIQUE_SOLUTIONS_PROMPT = ChatPromptTemplate.from_template(
    """Critique the following solution candidates against the Invariants.
    
    Invariants: {invariants}
    
    Candidates:
    {candidates}
    
    Check for:
    1. Do they strictly adhere to invariants?
    2. Are they over-engineered?
    3. Is the reasoning sound?
    
    Provide a critique summary.
    """
)

REFINE_SOLUTIONS_PROMPT = ChatPromptTemplate.from_template(
    """Refine the solution candidates based on the critique.
    
    Critique: {critique}
    
    Current Candidates:
    {candidates}
    
    Return the refined Solution Space including candidates, comparison, and simplification feedback.
    """
)
