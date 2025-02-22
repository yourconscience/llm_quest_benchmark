import streamlit as st
import sqlite3
import pandas as pd
from pathlib import Path
import yaml
import glob
from contextlib import contextmanager
import datetime
import json
import logging
from typing import List, Dict, Any, Optional
from streamlit.runtime.scriptrunner import add_script_run_ctx

from llm_quest_benchmark.constants import (
    MODEL_CHOICES,
    DEFAULT_MODEL,
    DEFAULT_TEMPLATE,
    DEFAULT_TEMPERATURE,
    PROMPT_TEMPLATES_DIR,
    DEFAULT_QUEST_TIMEOUT
)
from llm_quest_benchmark.core.runner import run_quest_with_timeout
from llm_quest_benchmark.agents.agent_factory import create_agent
from llm_quest_benchmark.executors.benchmark import run_benchmark
from llm_quest_benchmark.dataclasses.config import BenchmarkConfig, AgentConfig
from llm_quest_benchmark.core.logging import LogManager
from llm_quest_benchmark.agents.llm_agent import QuestPlayer
from llm_quest_benchmark.environments.state import QuestOutcome
from llm_quest_benchmark.renderers.base import BaseRenderer
from llm_quest_benchmark.utils import choice_mapper, text_processor
from llm_quest_benchmark.dataclasses.state import AgentState
from llm_quest_benchmark.dataclasses.response import LLMResponse

# Initialize logging
log_manager = LogManager()
logger = log_manager.get_logger()

class StreamlitRenderer(BaseRenderer):
    """Streamlit renderer for quest visualization"""

    def __init__(self):
        self.step_number = 0
        self.output = []
        self.quest_name = None
        self.start_time = datetime.datetime.now()
        self.run_id = None  # Initialize run_id as None

    def set_quest_name(self, name: str):
        """Set quest name for logging"""
        self.quest_name = name
        # Create run entry when quest name is set
        if self.quest_name:
            try:
                with get_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO runs (quest_name, start_time) VALUES (?, ?)",
                        (self.quest_name, self.start_time)
                    )
                    self.run_id = cursor.lastrowid
                    conn.commit()
            except Exception as e:
                logger.error(f"Failed to create run entry: {e}")

    def render_game_state(self, state: AgentState) -> None:
        """Collect game state for later display"""
        self.step_number += 1

        # Format response using ChoiceMapper
        formatted_response = choice_mapper.ChoiceMapper.format_agent_response(
            state.llm_response, state.choices
        ) if state.llm_response else None

        step_data = {
            'step': self.step_number,
            'text': text_processor.clean_qm_text(state.observation),
            'llm_response': formatted_response.to_dict() if formatted_response else {},
            'choices': state.choices
        }
        self.output.append(step_data)

        # Log step to database
        if self.run_id:  # Only log if we have a valid run_id
            try:
                with get_db() as conn:
                    cursor = conn.cursor()
                    # Insert step
                    cursor.execute("""
                        INSERT INTO steps (run_id, step, location_id, observation, choices, action, llm_response)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        self.run_id,
                        self.step_number,
                        state.location_id,
                        state.observation,
                        json.dumps(state.choices),
                        str(formatted_response.action) if formatted_response else "",
                        json.dumps(formatted_response.to_dict() if formatted_response else {})
                    ))
                    conn.commit()
            except Exception as e:
                logger.error(f"Failed to log step: {e}")

    def render_error(self, message: str) -> None:
        """Collect error message"""
        self.output.append({'error': message})

    def close(self) -> None:
        """Clean up resources and log completion"""
        if self.run_id:  # Only update if we have a valid run_id
            try:
                with get_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "UPDATE runs SET end_time = ? WHERE id = ?",
                        (datetime.datetime.now(), self.run_id)
                    )
                    conn.commit()
            except Exception as e:
                logger.error(f"Failed to log quest completion: {e}")

    def get_output(self) -> list:
        """Get collected output"""
        return self.output

# Set page config
st.set_page_config(page_title="LLM Quest Benchmark", layout="wide")

@contextmanager
def get_db():
    """Safe database connection context manager"""
    conn = None
    try:
        conn = sqlite3.connect('metrics.db')
        yield conn
    except Exception as e:
        logger.error(f"Database error: {e}")
        raise
    finally:
        if conn:
            conn.close()

def init_db():
    """Initialize database tables"""
    with get_db() as conn:
        cursor = conn.cursor()
        # Drop existing tables to ensure clean schema
        cursor.execute("DROP TABLE IF EXISTS steps")
        cursor.execute("DROP TABLE IF EXISTS runs")

        # Create tables with updated schema
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY,
                quest_name TEXT,
                start_time TIMESTAMP,
                end_time TIMESTAMP
            )''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS steps (
                run_id INTEGER,
                step INTEGER,
                location_id TEXT,
                observation TEXT,
                choices TEXT,  -- JSON array of choice objects
                action TEXT,   -- Chosen action
                llm_response TEXT,  -- JSON object of LLMResponse
                FOREIGN KEY(run_id) REFERENCES runs(id)
            )''')
        conn.commit()

def get_available_templates():
    """Get list of available templates"""
    template_files = glob.glob(str(PROMPT_TEMPLATES_DIR / "*.jinja"))
    return [Path(f).stem for f in template_files]

def get_available_quests():
    """Get list of available quests"""
    quest_files = glob.glob("quests/kr1/*.qm")
    return sorted([Path(f).name for f in quest_files])

def run_quest(quest_path: str, agent: QuestPlayer):
    """Run quest with streamlit UI updates"""
    try:
        renderer = StreamlitRenderer()
        quest_name = Path(quest_path).name
        renderer.set_quest_name(quest_name)

        # Create progress containers
        progress_container = st.empty()
        status_container = st.empty()
        quest_container = st.container()

        # Initialize progress bar
        progress_bar = progress_container.progress(0)
        status_text = status_container.text("Starting quest...")

        # Create a placeholder for the quest output
        quest_output = []

        def update_progress(step_num, total_steps=20):
            """Update progress bar and status"""
            progress = min(100, int((step_num / total_steps) * 100))
            progress_bar.progress(progress)
            status_text.text(f"Processing step {step_num}...")

        # Custom renderer that captures output and updates progress
        class ProgressRenderer(StreamlitRenderer):
            def render_game_state(self, state: AgentState):
                super().render_game_state(state)
                update_progress(state.step)

                # Format the step output
                step_data = {
                    'step': state.step,
                    'llm_response': state.llm_response.to_dict() if state.llm_response else {},
                    'text': text_processor.clean_qm_text(state.observation),
                    'choices': choice_mapper.ChoiceMapper.format_choices_for_display(state.choices)
                }
                quest_output.append(step_data)

                # Update the display
                with quest_container:
                    st.empty()  # Clear previous content
                    for step in quest_output:
                        st.markdown(f"### Step {step['step']}")

                        if step['llm_response']:
                            st.markdown("#### Agent's Thoughts")
                            if 'analysis' in step['llm_response']:
                                st.write("Analysis:", step['llm_response']['analysis'])
                            if 'reasoning' in step['llm_response']:
                                st.write("Reasoning:", step['llm_response']['reasoning'])
                            if 'action' in step['llm_response']:
                                st.write("Action:", step['llm_response']['action'])

                        st.markdown("#### Current Situation")
                        st.write(step['text'])

                        if step['choices']:
                            st.markdown("#### Choices")
                            for choice in step['choices']:
                                st.write(choice)

                        st.markdown("---")

        # Run quest with progress renderer
        with st.spinner("Running quest..."):
            result = run_quest_with_timeout(
                quest_path=quest_path,
                agent=agent,
                timeout=DEFAULT_QUEST_TIMEOUT,
                debug=True,
                renderer=ProgressRenderer()
            )

            # Show final outcome
            if isinstance(result, dict) and 'outcome' in result:
                progress_bar.progress(100)  # Complete the progress bar
                outcome = QuestOutcome[result['outcome']]
                if outcome == QuestOutcome.SUCCESS:
                    status_text.success("Quest completed successfully! 🎉")
                elif outcome == QuestOutcome.FAILURE:
                    status_text.error("Quest failed! 😔")
                else:
                    status_text.warning("Quest ended with unknown outcome")
            else:
                status_text.error("Quest failed to complete")

    except Exception as e:
        st.error(f"Failed to run quest: {str(e)}")
        logger.exception("Quest run failed")
        return False
    return bool(result == QuestOutcome.SUCCESS)

def show_quest_runner():
    """Main quest runner interface"""
    st.header("Quest Runner")

    # Quest selection
    quests = get_available_quests()
    if not quests:
        st.error("No quests found in quests/kr1/")
        return

    selected_quest = st.selectbox("Select Quest", quests)

    # Basic agent configuration
    model = st.selectbox("Model", MODEL_CHOICES, index=MODEL_CHOICES.index(DEFAULT_MODEL))
    temperature = st.slider("Temperature", 0.0, 1.0, DEFAULT_TEMPERATURE)

    if st.button("Run Quest"):
        quest_path = f"quests/kr1/{selected_quest}"
        agent = create_agent(
            model=model,
            template=DEFAULT_TEMPLATE,
            temperature=temperature,
            skip_single=True,
            debug=True
        )
        run_quest(quest_path, agent)

def show_metrics():
    """Show basic metrics"""
    st.header("Quest Metrics")

    try:
        with get_db() as conn:
            # Get quest summary
            df = pd.read_sql_query("""
                SELECT
                    r.quest_name,
                    COUNT(DISTINCT r.id) as runs,
                    COUNT(DISTINCT s.llm_response) as unique_responses,
                    AVG(CASE
                        WHEN json_extract(s.llm_response, '$.is_default') = 'true' THEN 1
                        ELSE 0
                    END) as default_response_rate
                FROM runs r
                LEFT JOIN steps s ON r.id = s.run_id
                GROUP BY r.quest_name
            """, conn)

            if not df.empty:
                st.subheader("Quest Summary")
                st.dataframe(df)

                # Show recent runs with responses
                st.subheader("Recent Quest Steps")
                recent_steps = pd.read_sql_query("""
                    SELECT
                        r.quest_name,
                        s.step,
                        s.location_id,
                        s.observation as text,
                        s.action,
                        json_extract(s.llm_response, '$.analysis') as analysis,
                        json_extract(s.llm_response, '$.reasoning') as reasoning,
                        json_extract(s.llm_response, '$.action') as chosen_action,
                        json_extract(s.llm_response, '$.is_default') as is_default_response
                    FROM runs r
                    JOIN steps s ON r.id = s.run_id
                    ORDER BY r.start_time DESC, s.step ASC
                    LIMIT 50
                """, conn)
                st.dataframe(recent_steps)
            else:
                st.info("No quest runs recorded yet")
    except Exception as e:
        st.error(f"Failed to load metrics: {e}")
        logger.error(f"Error loading metrics: {e}", exc_info=True)

def main():
    """Main application entry point"""
    st.title("🎯 LLM Quest Benchmark")

    # Initialize database
    try:
        init_db()
    except Exception as e:
        st.error(f"Failed to initialize database: {e}")
        return

    # Simple navigation
    page = st.sidebar.radio("Navigation", ["Quest Runner", "Metrics"])

    if page == "Quest Runner":
        show_quest_runner()
    else:
        show_metrics()

if __name__ == "__main__":
    main()