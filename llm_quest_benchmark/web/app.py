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
import threading
from streamlit.runtime.scriptrunner import add_script_run_ctx
from threading import current_thread
import tempfile
import subprocess
import sys
from streamlit_ace import st_ace  # Requires pip install streamlit-ace

from llm_quest_benchmark.constants import (
    MODEL_CHOICES,
    DEFAULT_MODEL,
    DEFAULT_TEMPLATE,
    DEFAULT_TEMPERATURE,
    PROMPT_TEMPLATES_DIR,
    DEFAULT_QUEST_TIMEOUT,
    SYSTEM_ROLE_TEMPLATE,
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
from llm_quest_benchmark.llm.prompt import PromptRenderer

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

def run_quest(quest_path: str, agent: QuestPlayer, timeout: int):
    """Run quest with callbacks for UI updates"""
    try:
        quest_name = Path(quest_path).name
        steps = []  # Store all steps for final display
        skip_single = getattr(agent, 'skip_single', False)  # Get skip_single setting from agent

        # Create containers for UI
        status_container = st.empty()
        output_container = st.empty()  # Changed to empty() since we'll fill it at the end
        final_status_container = st.empty()

        def handle_callback(event: str, data: Any) -> None:
            """Unified callback handler for quest events"""
            try:
                ctx = add_script_run_ctx(thread=current_thread())

                if event == "progress":
                    status_container.info(f"Step {data['step']}: {data['message']}")
                elif event == "game_state":
                    # Skip storing single-choice steps if skip_single is enabled
                    if skip_single and data.choices and len(data.choices) == 1:
                        return

                    # Store step for final display
                    steps.append(data)
                elif event == "error":
                    st.error(str(data))
            except Exception as e:
                logger.error(f"Error in callback: {e}")

        # Run quest with custom timeout
        with st.spinner("Running quest..."):
            result = run_quest_with_timeout(
                quest_path=quest_path,
                agent=agent,
                timeout=timeout,
                debug=True,
                callbacks=[handle_callback]
            )

            # Outcome display (show it first and make it prominent)
            if result and isinstance(result, dict) and 'outcome' in result:
                try:
                    outcome = QuestOutcome[result['outcome']]
                except KeyError:
                    outcome = QuestOutcome.UNKNOWN

                if outcome == QuestOutcome.SUCCESS:
                    final_status_container.success("# Quest completed successfully! 🎉")
                elif outcome == QuestOutcome.FAILURE:
                    final_status_container.error("# Quest failed! 😔")
                else:
                    final_status_container.warning("# Quest ended with unknown outcome")
            else:
                final_status_container.error("# Quest failed to complete")

            # Render all steps together
            with output_container.container():
                st.markdown("## Complete Quest Log")

                # Add collapse/expand controls
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Expand All Steps"):
                        st.session_state["expand_all"] = True
                with col2:
                    if st.button("Collapse All Steps"):
                        st.session_state["expand_all"] = False

                # Display all steps with synchronized expansion state
                expand_all = st.session_state.get("expand_all", False)

                # Create tabs for different views
                tab1, tab2 = st.tabs(["Step by Step", "Full Story"])

                # Step by Step view
                with tab1:
                    for step in steps:
                        with st.expander(f"Step {step.step}", expanded=expand_all):
                            st.markdown("**Observation:**")
                            st.markdown(text_processor.clean_qm_text(step.observation))

                            if step.choices:
                                st.markdown("**Available Choices:**")
                                for choice in step.choices:
                                    st.markdown(f"- {choice['text']}")

                            if step.llm_response:
                                st.markdown("**Agent's Response**")
                                st.markdown(f"```\n{str(step.llm_response)}\n```")

                # Full Story view
                with tab2:
                    # Combine all observations into a continuous story
                    story = "\n\n".join([
                        f"{text_processor.clean_qm_text(step.observation)}\n" +
                        (f"*Agent chose: {step.action}*" if step.action else "")
                        for step in steps
                    ])
                    st.markdown(story)

    except Exception as e:
        st.error(f"Failed to run quest: {str(e)}")
        logger.exception("Quest run failed")
        return False
    return bool(result and result.get('outcome') == QuestOutcome.SUCCESS)

def show_quest_runner():
    """Main quest runner interface"""
    st.header("Quest Runner")

    # Initialize prompt renderer
    prompt_renderer = PromptRenderer(env=None)

    # Get template contents
    system_template = prompt_renderer.get_system_template_content()
    action_template = prompt_renderer.get_action_template_content()

    # Quest selection
    quests = get_available_quests()
    if not quests:
        st.error("No quests found in quests/kr1/")
        return

    # Configuration columns
    col1, col2 = st.columns(2)

    # CSS для выравнивания контента вниз
    st.markdown("""
    <style>
        .st-emotion-cache-1v7f65g {
            align-items: flex-end !important;
        }
    </style>
    """, unsafe_allow_html=True)

    with col1:
        st.subheader("Quest Configuration")
        with st.container(height=650):  # Фиксированная высота контейнера
            selected_quest = st.selectbox("Select Quest", quests)
            skip_single = st.checkbox(
                "Skip steps with single choice",
                value=True,
                help="Automatically proceed when only one choice is available"
            )
            timeout = st.number_input(
                "Timeout (seconds)",
                min_value=1,
                value=DEFAULT_QUEST_TIMEOUT,
                help="Maximum time allowed for quest completion"
            )
            system_prompt = st.text_area(
                "System Prompt Template",
                value=system_template,
                height=350,  # Reduced height to accommodate timeout field
                help="Jinja2 template for system instructions"
            )

    with col2:
        st.subheader("Agent Configuration")
        with st.container(height=650):  # Фиксированная высота контейнера
            model = st.selectbox(
                "Model",
                MODEL_CHOICES,
                index=MODEL_CHOICES.index(DEFAULT_MODEL)
            )
            temperature = st.slider(
                "Temperature",
                0.0, 1.0,
                value=DEFAULT_TEMPERATURE,
                step=0.1
            )
            action_prompt = st.text_area(
                "Action Prompt Template",
                value=action_template,
                height=400,
                help="Jinja2 template for action selection"
            )

    if st.button("Run Quest"):
        quest_path = f"quests/kr1/{selected_quest}"
        # Save edited templates
        (PROMPT_TEMPLATES_DIR / SYSTEM_ROLE_TEMPLATE).write_text(system_prompt)
        (PROMPT_TEMPLATES_DIR / DEFAULT_TEMPLATE).write_text(action_prompt)
        agent = create_agent(
            model=model,
            system_template=SYSTEM_ROLE_TEMPLATE,
            action_template=DEFAULT_TEMPLATE,
            temperature=temperature,
            skip_single=skip_single,
            debug=True
        )
        run_quest(quest_path, agent, timeout)

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

def render_benchmark_tab():
    """Render benchmark configuration and execution tab"""
    st.header("Benchmark Configuration")

    # YAML Editor
    st.subheader("Benchmark Configuration YAML")
    default_config = """# Main LLM benchmark configuration
quests:
  - quests/kr1/test.qm  # Example quest path
agents:
  - model: claude-3-5-sonnet-20240122
    skip_single: true
    temperature: 0.5
    template: reasoning.jinja
  - model: gpt-4
    skip_single: true
    temperature: 0.5
    template: reasoning.jinja
debug: false
quest_timeout: 90
max_workers: 2"""

    yaml_content = st_ace(
        value=default_config,
        language="yaml",
        theme="monokai",
        key="yaml_editor",
        height=400
    )

    # Save and Run buttons in columns
    col1, col2 = st.columns(2)

    with col1:
        if st.button("Save Configuration"):
            try:
                # Validate YAML
                config_dict = yaml.safe_load(yaml_content)

                # Save to temporary file
                with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                    yaml.dump(config_dict, f)
                    st.session_state['config_path'] = f.name
                st.success("Configuration saved successfully!")
            except Exception as e:
                st.error(f"Failed to save configuration: {str(e)}")
                return

    with col2:
        if st.button("Run Benchmark"):
            if 'config_path' not in st.session_state:
                st.error("Please save the configuration first!")
                return

            try:
                # Create progress containers
                progress_container = st.empty()
                output_container = st.container()

                def progress_callback(event: str, data: Any) -> None:
                    """Handle benchmark progress updates"""
                    try:
                        if event == "progress":
                            progress_container.info(f"Progress: {data['message']}")
                        elif event == "quest_start":
                            with output_container:
                                st.markdown(f"Starting quest: {data['quest']}")
                        elif event == "quest_complete":
                            with output_container:
                                st.markdown(f"Completed quest: {data['quest']} - Outcome: {data['outcome']}")
                        elif event == "error":
                            st.error(f"Error: {str(data)}")
                    except Exception as e:
                        logger.error(f"Error in callback: {e}")

                # Run benchmark
                with st.spinner("Running benchmark..."):
                    result = run_benchmark(
                        config_path=st.session_state['config_path'],
                        callbacks=[progress_callback]
                    )

                # Display results
                if result:
                    st.success("Benchmark completed!")
                    st.json(result)
                else:
                    st.error("Benchmark failed!")
            except Exception as e:
                st.error(f"Failed to run benchmark: {str(e)}")

def render_analyze_tab():
    """Render analysis of benchmark results"""
    st.header("Benchmark Analysis")

    try:
        with get_db() as conn:
            # Get unique quests and models
            cursor = conn.cursor()

            # Get all runs with their steps
            cursor.execute("""
                SELECT DISTINCT
                    r.quest_name,
                    json_extract(s.llm_response, '$.model') as model,
                    r.id as run_id,
                    r.start_time,
                    COUNT(s.step) as total_steps,
                    MAX(s.step) as last_step,
                    s.llm_response
                FROM runs r
                JOIN steps s ON r.id = s.run_id
                GROUP BY r.quest_name, json_extract(s.llm_response, '$.model'), r.id
                ORDER BY r.start_time DESC
            """)

            runs = cursor.fetchall()

            if not runs:
                st.warning("No benchmark data found. Run some benchmarks first!")
                return

            # Process runs into a DataFrame
            data = []
            for run in runs:
                quest_name, model, run_id, start_time, total_steps, last_step, llm_response = run

                # Extract outcome from the last step's response
                try:
                    response_dict = json.loads(llm_response)
                    outcome = response_dict.get('outcome', 'UNKNOWN')
                except (json.JSONDecodeError, TypeError):
                    outcome = 'UNKNOWN'

                data.append({
                    'Quest': quest_name,
                    'Model': model,
                    'Run ID': run_id,
                    'Start Time': start_time,
                    'Steps': total_steps,
                    'Outcome': outcome
                })

            df = pd.DataFrame(data)

            # Get latest run for each quest-model pair
            latest_runs = df.sort_values('Start Time').groupby(['Quest', 'Model']).last().reset_index()

            # Create pivot table for quest x model grid
            pivot_df = latest_runs.pivot(index='Quest', columns='Model', values=['Outcome', 'Steps'])

            # Display the grid
            st.subheader("Latest Run Results")

            # Format the grid with custom styling
            def color_outcomes(val):
                if val == 'SUCCESS':
                    return 'background-color: #90EE90'  # Light green
                elif val == 'FAILURE':
                    return 'background-color: #FFB6C1'  # Light red
                return 'background-color: #F0F0F0'  # Light gray for unknown

            # Display outcomes
            st.markdown("### Outcomes")
            styled_outcomes = pivot_df['Outcome'].style.applymap(color_outcomes)
            st.dataframe(styled_outcomes)

            # Display steps
            st.markdown("### Steps Taken")
            st.dataframe(pivot_df['Steps'])

            # Add detailed view for selected run
            st.subheader("Run Details")
            selected_run = st.selectbox(
                "Select Run",
                options=df['Run ID'].unique(),
                format_func=lambda x: f"Run {x} - {df[df['Run ID']==x].iloc[0]['Quest']} ({df[df['Run ID']==x].iloc[0]['Model']})"
            )

            if selected_run:
                cursor.execute("""
                    SELECT step, location_id, observation, choices, action, llm_response
                    FROM steps
                    WHERE run_id = ?
                    ORDER BY step
                """, (selected_run,))

                steps = cursor.fetchall()

                for step in steps:
                    step_num, location, obs, choices, action, response = step
                    with st.expander(f"Step {step_num} - {location}"):
                        st.markdown("**Observation:**")
                        st.markdown(text_processor.clean_qm_text(obs))

                        if choices:
                            st.markdown("**Choices:**")
                            choices_list = json.loads(choices)
                            for choice in choices_list:
                                st.markdown(f"- {choice['text']}")

                        st.markdown("**Action Taken:**")
                        st.markdown(action)

                        if response:
                            st.markdown("**Agent Response:**")
                            try:
                                response_dict = json.loads(response)
                                st.json(response_dict)
                            except json.JSONDecodeError:
                                st.code(response)

    except Exception as e:
        st.error(f"Failed to load analysis: {str(e)}")
        logger.exception("Analysis failed")

def main():
    """Main application entry point"""
    st.title("🎯 LLM Quest Benchmark")

    # Initialize database
    try:
        init_db()
    except Exception as e:
        st.error(f"Failed to initialize database: {e}")
        return

    # Navigation with key for testing
    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", ["Monitor", "Benchmark", "Analyze"], key="nav")

    if page == "Monitor":
        show_quest_runner()
    elif page == "Benchmark":
        render_benchmark_tab()
    elif page == "Analyze":
        render_analyze_tab()
    else:
        show_metrics()

if __name__ == "__main__":
    main()