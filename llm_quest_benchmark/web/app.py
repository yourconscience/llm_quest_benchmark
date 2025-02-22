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
import queue
from typing import List, Dict, Any, Optional
from streamlit.runtime.scriptrunner import add_script_run_ctx
from threading import current_thread

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
from llm_quest_benchmark.renderers.terminal import RichRenderer

# Initialize logging
log_manager = LogManager()
logger = log_manager.get_logger()

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
    """Run quest with callbacks for UI updates"""
    try:
        quest_name = Path(quest_path).name
        steps = []  # Store all steps for final display

        # Create containers for UI
        status_container = st.empty()
        output_container = st.container()
        final_status_container = st.empty()

        def handle_callback(event: str, data: Any) -> None:
            """Unified callback handler for quest events"""
            try:
                ctx = add_script_run_ctx(thread=current_thread())
                
                if event == "progress":
                    status_container.info(f"Step {data['step']}: {data['message']}")
                elif event == "game_state":
                    # Store step for final display
                    steps.append(data)
                    
                    # Real-time update
                    with output_container:
                        st.markdown(f"## Step {data.step}")
                        st.markdown("### Current Situation")
                        st.markdown(text_processor.clean_qm_text(data.observation))
                        
                        if data.choices:
                            st.markdown("### Choices")
                            formatted_choices = choice_mapper.ChoiceMapper.format_choices_for_display(data.choices)
                            for choice in formatted_choices:
                                st.markdown(f"- {choice}")
                                
                        if data.llm_response:
                            st.markdown("### Agent's Response")
                            # Use the standardized string representation
                            st.code(str(data.llm_response), language="markdown")
                                
                        st.markdown("---")
                        
                elif event == "error":
                    st.error(str(data))
            except Exception as e:
                logger.error(f"Error in callback: {e}")

        # Run quest
        with st.spinner("Running quest..."):
            result = run_quest_with_timeout(
                quest_path=quest_path,
                agent=agent,
                timeout=DEFAULT_QUEST_TIMEOUT,
                debug=True,
                callbacks=[handle_callback]
            )

            # Final display of all steps
            with output_container:
                st.subheader("Complete Quest Log")
                for step in steps:
                    with st.expander(f"Step {step.step}", expanded=False):
                        st.markdown(f"**Location:** {step.location_id}")
                        st.markdown(f"**Observation:** {text_processor.clean_qm_text(step.observation)}")
                        
                        if step.choices:
                            st.markdown("**Available Choices:**")
                            for choice in step.choices:
                                st.markdown(f"- {choice['text']}")
                        
                        if step.llm_response:
                            st.markdown("**Agent's Response**")
                            # Use the full string representation from LLMResponse
                            st.markdown(f"```\n{str(step.llm_response)}\n```")

            # Outcome display
            if result and isinstance(result, dict) and 'outcome' in result:
                try:
                    outcome = QuestOutcome[result['outcome']]
                except KeyError:
                    outcome = QuestOutcome.UNKNOWN
                
                if outcome == QuestOutcome.SUCCESS:
                    final_status_container.success("Quest completed successfully! 🎉")
                elif outcome == QuestOutcome.FAILURE:
                    final_status_container.error("Quest failed! 😔")
                else:
                    final_status_container.warning("Quest ended with unknown outcome")
            else:
                final_status_container.error("Quest failed to complete")

    except Exception as e:
        st.error(f"Failed to run quest: {str(e)}")
        logger.exception("Quest run failed")
        return False
    return bool(result and result.get('outcome') == QuestOutcome.SUCCESS)

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