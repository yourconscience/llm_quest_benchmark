"""Tests for logging dataclasses"""
from llm_quest_benchmark.schemas.state import AgentState
from llm_quest_benchmark.schemas.response import LLMResponse


def test_agent_state_basic():
    """Test basic AgentState functionality"""
    state = AgentState(
        step=1,
        location_id="room1",
        observation="You are in a room",
        choices=[{"id": "1", "text": "Go north"}, {"id": "2", "text": "Go south"}],
        action="1",
        llm_response=LLMResponse(action=1)
    )

    # Test basic attributes
    assert state.step == 1
    assert state.location_id == "room1"
    assert state.observation == "You are in a room"
    assert len(state.choices) == 2
    assert state.choices[0]["text"] == "Go north"
    assert state.action == "1"
    assert state.llm_response.action == 1

def test_agent_state_with_llm_response():
    """Test AgentState with detailed LLM response"""
    state = AgentState(
        step=1,
        location_id="room1",
        observation="You are in a room",
        choices=[{"id": "1", "text": "Go north"}, {"id": "2", "text": "Go south"}],
        action="1",
        llm_response=LLMResponse(
            action=1,
            analysis="The north path looks safer",
            reasoning="I can see better lighting in that direction"
        )
    )

    # Test LLM response fields
    assert state.llm_response.action == 1
    assert state.llm_response.analysis == "The north path looks safer"
    assert state.llm_response.reasoning == "I can see better lighting in that direction"

def test_llm_response_to_dict():
    """Test LLMResponse dictionary conversion"""
    response = LLMResponse(
        action=1,
        analysis="Let me think about this",
        reasoning="Based on the available information"
    )

    data = response.to_dict()
    assert data["action"] == 1
    assert data["analysis"] == "Let me think about this"
    assert data["reasoning"] == "Based on the available information"