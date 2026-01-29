
import unittest
from unittest.mock import MagicMock, patch
from app.backend.workspace import ProblemSpace
from workflow_definitions.system_design.functions_companion import extract_problem

class TestContextVerification(unittest.TestCase):
    def test_extract_problem_with_context(self):
        # Mock input data
        chat_input = "I want to build a URL shortener like bit.ly"
        current_problem = ProblemSpace().model_dump()
        config = {}

        # Define the expected ProblemSpace output
        expected_problem_space = ProblemSpace(
            context="A URL shortening service similar to bit.ly.",
            invariants=[],
            goal="Build a URL shortener.",
            problem="",
            variants=[]
        )
        
        # Patch the EXTRACT_PROBLEM_PROMPT to mock the chain execution
        with patch('workflow_definitions.system_design.functions_companion.EXTRACT_PROBLEM_PROMPT') as mock_prompt:
            mock_chain = MagicMock()
            # When prompt | llm is called, it returns a chain. We mock the pipe logic or just the result if we could.
            # IN the code: chain = EXTRACT_PROBLEM_PROMPT | structured_llm
            # So mock_prompt.__or__ should return the chain
            mock_prompt.__or__.return_value = mock_chain
            mock_chain.invoke.return_value = expected_problem_space
            
            # We also need to mock get_llm so it doesn't try to instantiate real ChatOllama
            with patch('workflow_definitions.system_design.functions_companion.get_llm') as mock_get_llm:
                mock_get_llm.return_value = MagicMock()
                
                result = extract_problem(chat_input, current_problem, config)
                
                self.assertEqual(result["new_problem_space"]["context"], "A URL shortening service similar to bit.ly.")
                self.assertTrue(result["has_changes"])
                print("Context verification passed!")

if __name__ == "__main__":
    unittest.main()
