from langchain_core.prompts import ChatPromptTemplate

EXTRACT_PROBLEM_PROMPT = ChatPromptTemplate.from_template(
    """You are a System Design Companion which helps a user to think about the design of a system.
    
    Current Problem Space:
    Context: {context}
    Invariants: {invariants}
    Goal: {goal}
    Problem: {problem}
    Variants: {variants}
    
    User Input: {chat_input}
    
    **Role:**
    Your goal is to analyze a user's unstructured description (user input) and structure it into a formal "Problem Space" definition taking into account the current Problem Space. 

    DEFINITIONS
    Context = single sentence describing what the system is.
    Invariant = non-negotiable constraint stated or strongly implied as fixed. Should contain word "must". (e.g., "must be on-premise", "must be secure", "must be scalable", "must support 1M users")
    Goal = one sentence desired outcome.
    Problem = the tension preventing the goal under invariants. No solutions.
    Variant = a DECISION DIMENSION / degree of freedom that is negotiable or unknown.
    Variants must be stated as “what could vary” + “possible options”, NOT “what to do”.
    Variants always should include current state.

    HARD BANS (ABSOLUTE)
    - Do not output verbs that prescribe actions in variants, such as: "use", "add", "move", "decouple", "introduce", "implement", "adopt", "create", "migrate", "build", "switch", "separate", "set up".
    - Do not output architecture proposals or workflows as actions.
    - Do not output “do X” statements anywhere.

    FORM RULES FOR VARIANTS
    - Each variant must be a neutral axis phrased as a noun phrase (e.g., “Hardware resources”, "Team size").
    - If the user text contains an action request, convert it into an axis.
    ---

    ### Example Interaction (Few-Shot)

    **User Input:**

    > "We need to scale our payment processing system to handle 50k transactions per second for Black Friday. Right now it's a legacy SQL based monolith running on-premise (12 CPU x 64Gb RAM) and the database locks up around 5k TPS. We can't move to the cloud due to data residency laws, but we have budget to buy more hardware or change the code."

    **Model Output:**

    "context": "A payment processing system",
    "invariants": [
        "Deployment: Must be on-premise infrastructure because of residency laws",
    ],
    "goal": "Scale the payment processing system to reliably handle 50,000 transactions per second.",
    "problem": "Current state is a single SQL-based monolith, which hits concurrency limits (locking) at 5k TPS, while cloud scaling is prohibited by data residency invariants.",
    "variants": [
        "Hardware resources (currently: 12 CPU x 64Gb RAM)",
        "Application architecture (currently: Monolith)",
        "DB Strategy (currently: SQL based)",
        "Caching strategy (currently: None  )"
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
