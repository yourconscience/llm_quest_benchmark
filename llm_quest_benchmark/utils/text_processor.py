"""Text processing utilities for Space Rangers quests"""
import re
from typing import Any, Dict, List


def clean_qm_text(text: str) -> str:
    """Remove QM-specific tags and normalize text"""
    # Remove color tags
    text = re.sub(r'<clr>|<clrEnd>', '', text)
    # Normalize newlines
    text = text.replace('\r\n', '\n')
    # Remove redundant newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def process_game_state(raw_state: Dict[str, Any]) -> Dict[str, Any]:
    """Process game state dictionary, cleaning all text fields"""
    return {
        'text':
            clean_qm_text(raw_state['text']),
        'paramsState':
            raw_state['paramsState'],
        'choices': [{
            **choice, 'text': clean_qm_text(choice['text'])
        } for choice in raw_state['choices']]
    }
