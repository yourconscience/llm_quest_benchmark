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