"""Schema definitions for agent configuration"""
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

class AgentConfig(BaseModel):
    """Schema for agent configuration"""
    agent_id: str = Field(..., description="Unique identifier for the agent")
    model: str = Field(..., description="LLM model identifier")
    temperature: float = Field(0.7, description="Temperature parameter for the model", ge=0.0, le=1.0)
    system_template: Optional[str] = Field(None, description="System template for the agent")
    action_template: Optional[str] = Field(None, description="Action template for the agent")
    max_tokens: Optional[int] = Field(None, description="Maximum number of tokens to generate")
    top_p: Optional[float] = Field(None, description="Top P parameter for the model", ge=0.0, le=1.0)
    additional_params: Optional[Dict[str, Any]] = Field(None, description="Additional parameters for the model")
    description: Optional[str] = Field(None, description="Description of the agent")
    
    class Config:
        """Config for the agent schema"""
        title = "Agent Configuration"
        json_schema_extra = {
            "examples": [
                {
                    "agent_id": "my-gpt4-agent",
                    "model": "gpt-4o",
                    "temperature": 0.7,
                    "system_template": "You are a player in a text adventure game...",
                    "action_template": "You are presented with the following situation..."
                }
            ]
        }

class AgentList(BaseModel):
    """List of agent configurations"""
    agents: List[AgentConfig] = Field(..., description="List of agent configurations")