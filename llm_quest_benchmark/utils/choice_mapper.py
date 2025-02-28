"""Choice mapping utilities"""
from typing import Dict, List, Any, Optional
from llm_quest_benchmark.schemas.response import LLMResponse
from llm_quest_benchmark.utils.text_processor import clean_qm_text

class ChoiceMapper:
    """Maps between sequential choice numbers and choice IDs"""

    def __init__(self, choices: list):
        """
        Args:
            choices: List of choices with 'id' fields
        """
        self.choices = choices
        self.mapping = {i+1: choice['id'] for i, choice in enumerate(choices)}
        self.reverse_mapping = {v: k for k, v in self.mapping.items()}

    def get_choice_number(self, choice_id: str) -> int:
        """Get sequential choice number for a choice ID"""
        return self.reverse_mapping.get(choice_id)

    def get_jump_id(self, choice_number: int) -> str:
        """Get choice ID for a sequential choice number"""
        return self.mapping.get(choice_number)

    def get_valid_choices(self) -> list:
        """Get list of valid choice numbers"""
        return sorted(self.mapping.keys())

    def __contains__(self, choice_number: int) -> bool:
        """Check if choice number is valid"""
        return choice_number in self.mapping

    def get_numbered_choices(self) -> List[Dict[str, str]]:
        """Get choices with sequential numbers and cleaned text.

        Returns:
            List of choices with sequential numbers as IDs and cleaned text
        """
        formatted_choices = []
        for i, choice in enumerate(self.choices, 1):
            formatted_choices.append({
                'id': str(i),
                'text': clean_qm_text(choice['text']) if choice.get('text') else choice.get('text', '')
            })
        return formatted_choices

    @staticmethod
    def format_agent_response(response: LLMResponse, choices: List[Dict[str, str]]) -> LLMResponse:
        """Format agent response to ensure action is valid for given choices.

        Args:
            response: Agent's response
            choices: Available choices

        Returns:
            Formatted response with validated action number
        """
        # For single choice, always use action 1
        if len(choices) == 1:
            return LLMResponse(
                action=1,
                analysis=response.analysis,
                reasoning=response.reasoning,
                is_default=response.is_default
            )

        # Validate action is in range
        if not (1 <= response.action <= len(choices)):
            return LLMResponse(
                action=1,  # Default to first choice
                analysis=response.analysis,
                reasoning=response.reasoning,
                is_default=True  # Mark as default since action was invalid
            )

        return response

    @staticmethod
    def format_choices_for_display(choices: List[Dict[str, str]]) -> List[str]:
        """Format choices for display with cleaned text.

        Args:
            choices: List of choice dictionaries

        Returns:
            List of formatted choice strings with cleaned text
        """
        return [f"{i+1}. {clean_qm_text(choice['text'])}" for i, choice in enumerate(choices)]