
import pytest
from unittest.mock import MagicMock, patch
from app.backend.workspace import ProblemSpace
from workflow_definitions.system_design.functions_companion import extract_problem

def test_extract_problem_with_context():
    # Mock input data
    chat_input = "I want to build a URL shortener like bit.ly"
    current_problem = ProblemSpace().model_dump()
    config = {}

    # Mock LLM response
    mock_llm = MagicMock()
    mock_structured_llm = MagicMock()
    
    # Define the expected ProblemSpace output
    expected_problem_space = ProblemSpace(
        context="A URL shortening service similar to bit.ly.",
        invariants=[],
        goal="Build a URL shortener.",
        problem="",
        variants=[]
    )
    
    # Setup chain mock
    mock_chain = MagicMock()
    mock_chain.invoke.return_value = expected_problem_space
    
    # Patch the chain creation in extract_problem
    # Since extract_problem creates the chain using a piped operator (|), it's harder to mock the chain directly if we don't mock get_llm or the chain construction.
    # Let's mock get_llm to return our mock_llm which returns our mock_structured_llm
    
    with patch('workflow_definitions.system_design.functions_companion.get_llm') as mock_get_llm:
        mock_get_llm.return_value = mock_llm
        mock_llm.with_structured_output.return_value = mock_structured_llm
        
        # We need to mock the pipe operation EXTRACT_PROBLEM_PROMPT | structured_llm
        # But `extract_problem` imports EXTRACT_PROBLEM_PROMPT. 
        # A easier way might be to patch the `chain.invoke` but `chain` is local.
        # Alternatively, we can rely on LangChain's structure.
        
        # Let's try to mock the chain execution by mocking the `invoke` method of the object returned by `EXTRACT_PROBLEM_PROMPT | structured_llm`.
        # This is a bit tricky with the pipe operator.
        
        # Instead, let's mock `EXTRACT_PROBLEM_PROMPT` in `workflow_definitions.system_design.functions_companion`
        # AND mock the result of the pipe.
        
        pass

    # A simpler approach: Mock the entire chain execution or the function that builds it? 
    # The function `extract_problem` builds the chain: `chain = EXTRACT_PROBLEM_PROMPT | structured_llm`
    # We can mock `EXTRACT_PROBLEM_PROMPT` and its `__or__` method.
    
    with patch('workflow_definitions.system_design.functions_companion.EXTRACT_PROBLEM_PROMPT') as mock_prompt:
        mock_chain = MagicMock()
        mock_prompt.__or__.return_value = mock_chain
        mock_chain.invoke.return_value = expected_problem_space
        
        result = extract_problem(chat_input, current_problem, config)
        
        assert result["new_problem_space"]["context"] == "A URL shortening service similar to bit.ly."
        assert result["has_changes"] is True
        print("Context verification passed!")

if __name__ == "__main__":
    try:
        test_extract_problem_with_context()
    except Exception as e:
        print(f"Test failed in main block: {e}")
        import traceback
        traceback.print_exc()
