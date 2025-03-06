import pytest
from unittest.mock import MagicMock, patch

from llm_quest_benchmark.agents.llm_agent import LLMAgent
from llm_quest_benchmark.constants import ToolType
from llm_quest_benchmark.llm.prompt import PromptRenderer
from llm_quest_benchmark.schemas.agent import AgentConfig, MemoryConfig
from llm_quest_benchmark.schemas.state import QMState


class TestMemoryAndTools:
    """Tests for memory and tool functionality."""

    @pytest.fixture
    def mock_llm_client(self):
        """Create a mock LLM client."""
        mock_client = MagicMock()
        mock_client.get_completion.return_value = "I choose option 1"
        return mock_client

    def test_memory_configuration(self):
        """Test memory configuration in PromptRenderer."""
        # Create a PromptRenderer with message history configuration
        memory_config = {"type": "message_history", "max_history": 3}

        renderer = PromptRenderer(None, memory_config=memory_config)

        # Add some states to history
        for i in range(5):
            state = {"text": f"Step {i+1}", "action": f"Action {i+1}"}
            renderer.add_to_history(state)

        # Get memory context
        memory_context = renderer._get_memory_context()

        # Verify memory context
        assert "memory" in memory_context
        memory_history = memory_context["memory"]

        # Should have 3 items (max_history=3)
        assert len(memory_history) == 3

        # Should have states 3, 4, and 5 (not 1 and 2, which should be evicted)
        assert any("Step 3" in str(entry) for entry in memory_history)
        assert any("Step 4" in str(entry) for entry in memory_history)
        assert any("Step 5" in str(entry) for entry in memory_history)
        assert not any("Step 1" in str(entry) for entry in memory_history)
        assert not any("Step 2" in str(entry) for entry in memory_history)

    def test_calculator_tool(self):
        """Test calculator tool functionality."""
        # Create PromptRenderer instance
        renderer = PromptRenderer(None)

        # Test calculator function
        result = renderer.handle_calculator_tool("2 + 2")
        assert "4" in result

        result = renderer.handle_calculator_tool("calculate 10 * 5")
        assert "50" in result

        result = renderer.handle_calculator_tool("what is 100 / 4")
        assert "25" in result
