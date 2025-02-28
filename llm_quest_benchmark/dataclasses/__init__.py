"""Dataclass exports - fixes circular import issues by importing at usage time"""

# Import machinery to defer imports
import importlib
import sys
from types import ModuleType


class LazyLoader(ModuleType):
    """Lazily load a module only when attributes are accessed."""
    
    def __init__(self, name, module_path):
        super(LazyLoader, self).__init__(name)
        self._module_path = module_path
        self._module = None

    def __getattr__(self, name):
        if self._module is None:
            self._module = importlib.import_module(self._module_path)
        return getattr(self._module, name)


# Define what we export
__all__ = [
    'QMState',
    'AgentState', 
    'LLMResponse',
    'QMBridgeState',
    'BenchmarkConfig',
    'AgentConfig'
]

# Setup lazy loaders
state = LazyLoader('state', 'llm_quest_benchmark.dataclasses.state')
response = LazyLoader('response', 'llm_quest_benchmark.dataclasses.response')
bridge = LazyLoader('bridge', 'llm_quest_benchmark.dataclasses.bridge')
config = LazyLoader('config', 'llm_quest_benchmark.dataclasses.config')

# Add lazy modules to system modules
sys.modules['llm_quest_benchmark.dataclasses.state'] = state
sys.modules['llm_quest_benchmark.dataclasses.response'] = response
sys.modules['llm_quest_benchmark.dataclasses.bridge'] = bridge
sys.modules['llm_quest_benchmark.dataclasses.config'] = config

# Import symbols into the namespace for backward compatibility
QMState = state.QMState
AgentState = state.AgentState
LLMResponse = response.LLMResponse
QMBridgeState = bridge.QMBridgeState
BenchmarkConfig = config.BenchmarkConfig
AgentConfig = config.AgentConfig
