"""Agent manager for storing and retrieving agent configurations"""
import os
import json
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any

from ..schemas.agent import AgentConfig

logger = logging.getLogger(__name__)

class AgentManager:
    """Agent manager for storing and retrieving agent configurations"""
    
    def __init__(self, agents_dir: str = None):
        """Initialize agent manager with agents directory"""
        self.agents_dir = agents_dir or os.path.join(os.getcwd(), "agents")
        os.makedirs(self.agents_dir, exist_ok=True)
        logger.debug(f"Initialized agent manager with directory: {self.agents_dir}")
    
    def list_agents(self) -> List[str]:
        """List all available agent IDs"""
        agent_files = Path(self.agents_dir).glob("*.json")
        return [os.path.splitext(os.path.basename(f))[0] for f in agent_files]
    
    def get_agent(self, agent_id: str) -> Optional[AgentConfig]:
        """Get agent configuration by ID"""
        agent_path = os.path.join(self.agents_dir, f"{agent_id}.json")
        if not os.path.exists(agent_path):
            logger.warning(f"Agent {agent_id} not found")
            return None
        
        try:
            with open(agent_path, "r", encoding="utf-8") as f:
                agent_data = json.load(f)
            return AgentConfig(**agent_data)
        except Exception as e:
            logger.error(f"Error loading agent {agent_id}: {e}")
            return None
    
    def create_agent(self, agent_config: AgentConfig) -> bool:
        """Create new agent configuration"""
        agent_path = os.path.join(self.agents_dir, f"{agent_config.agent_id}.json")
        if os.path.exists(agent_path):
            logger.warning(f"Agent {agent_config.agent_id} already exists")
            return False
        
        try:
            with open(agent_path, "w", encoding="utf-8") as f:
                json.dump(agent_config.model_dump(), f, indent=2)
            logger.info(f"Created agent {agent_config.agent_id}")
            return True
        except Exception as e:
            logger.error(f"Error creating agent {agent_config.agent_id}: {e}")
            return False
    
    def update_agent(self, agent_config: AgentConfig) -> bool:
        """Update existing agent configuration"""
        agent_path = os.path.join(self.agents_dir, f"{agent_config.agent_id}.json")
        if not os.path.exists(agent_path):
            logger.warning(f"Agent {agent_config.agent_id} not found for update")
            return False
        
        try:
            with open(agent_path, "w", encoding="utf-8") as f:
                json.dump(agent_config.model_dump(), f, indent=2)
            logger.info(f"Updated agent {agent_config.agent_id}")
            return True
        except Exception as e:
            logger.error(f"Error updating agent {agent_config.agent_id}: {e}")
            return False
    
    def delete_agent(self, agent_id: str) -> bool:
        """Delete agent configuration"""
        agent_path = os.path.join(self.agents_dir, f"{agent_id}.json")
        if not os.path.exists(agent_path):
            logger.warning(f"Agent {agent_id} not found for deletion")
            return False
        
        try:
            os.remove(agent_path)
            logger.info(f"Deleted agent {agent_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting agent {agent_id}: {e}")
            return False
    
    def get_all_agents(self) -> Dict[str, AgentConfig]:
        """Get all agent configurations"""
        agents = {}
        for agent_id in self.list_agents():
            agent = self.get_agent(agent_id)
            if agent:
                agents[agent_id] = agent
        return agents
    
    def create_default_agents(self):
        """Create default agents if no agents exist"""
        if not self.list_agents():
            logger.info("Creating default agents")
            
            # Create default agents with template names (not full template content)
            default_agents = [
                AgentConfig(
                    agent_id="gpt-4o-default",
                    model="gpt-4o",
                    temperature=0.7,
                    system_template="system_role.jinja",
                    action_template="reasoning.jinja",
                    description="Default GPT-4o agent with standard prompt templates"
                ),
                AgentConfig(
                    agent_id="claude-3-haiku-default",
                    model="claude-3-haiku-20240307",
                    temperature=0.7,
                    system_template="system_role.jinja", 
                    action_template="reasoning.jinja",
                    description="Default Claude 3 Haiku agent with standard prompt templates"
                )
            ]
            
            for agent in default_agents:
                self.create_agent(agent)