from langchain_core.prompts import ChatPromptTemplate

EXTRACT_PROBLEM_PROMPT = ChatPromptTemplate.from_template(
    """You are a System Design Companion which helps a user to think about the design of a system.
    
    Current Problem Space:
    Invariants: {invariants}
    Goal: {goal}
    Problem: {problem}
    Variants: {variants}
    
    User Input: {chat_input}
    
    **Role:**
    Your goal is to analyze a user's unstructured description (user input) and structure it into a formal "Problem Space" definition taking into account the current Problem Space. 

    DEFINITIONS
    Invariant = non-negotiable constraint stated or strongly implied as fixed.
    Goal = one sentence desired outcome.
    Problem = the tension preventing the goal under invariants. No solutions.
    Variant = a DECISION DIMENSION / degree of freedom that is negotiable or unknown.
    Variants must be stated as “what could vary” + “possible options”, NOT “what to do”.

    HARD BANS (ABSOLUTE)
    - Do not output verbs that prescribe actions in variants, such as: "use", "add", "move", "decouple", "introduce", "implement", "adopt", "create", "migrate", "build", "switch", "separate", "set up".
    - Do not output architecture proposals or workflows as actions.
    - Do not output “do X” statements anywhere.

    FORM RULES FOR VARIANTS
    - Each variant must be a neutral axis phrased as a noun phrase (e.g., “Change control rigor for config updates”).
    - Each variant must include 2–4 options, also neutral noun phrases (e.g., “Ad-hoc edits”, “PR-reviewed changes”, “Formal approval gate”).
    - If the user text contains an action request, convert it into an axis.
    
    EVIDENCE RULE
    Every item must include evidence as a short quote/paraphrase from the user text, unless source="proposed" (then evidence="none").

    SELF-CHECK (MANDATORY)
    Before finalizing:
    1) Scan all variants. If any variant.dimension or options contain banned verbs or read like an instruction, rewrite them into a neutral dimension + options.
    2) If you cannot rewrite without inventing facts, mark as source="proposed" and evidence="none".
    ---

    ### Example Interaction (Few-Shot)

    **User Input:**

    > "We need to scale our payment processing system to handle 50k transactions per second for Black Friday. Right now it's a legacy SQL based monolith running on-premise and the database locks up around 5k TPS. We can't move to the cloud due to data residency laws, but we have budget to buy more hardware or change the code."

    **Model Output:**

    "invariants": [
        "Deployment: On-premise infrastructure",
        "Constraint: Strict data residency laws (cannot use public cloud)",
        "Current State: Legacy SQL-based monolith",
        "Current Bottleneck: Database locking at ~5k TPS"
    ],
    "goal": "Scale the payment processing system to reliably handle 50,000 transactions per second.",
    "problem": "The goal of 50k TPS conflicts with the architectural invariant of a single SQL-based monolith, which hits concurrency limits (locking) at 5k TPS, while cloud scaling is prohibited by data residency invariants.",
    "variants": [
        "Hardware resources",
        "Application architecture",
        "Database sharding or partitioning strategies",
        "Caching strategy"
    ]

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
