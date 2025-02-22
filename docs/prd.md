# Frontend Implementation Plan (2-Day Sprint)

## �� Core Objectives
1. ✅ Simple web interface for quest monitoring
2. ✅ Basic metrics storage
3. ✅ One-command Docker deployment

## 📦 Database Simplification
✅ **Use SQLite instead of PostgreSQL**
- ✅ File-based (no server setup)
- ✅ Same schema as existing JSONL metrics
- ✅ Simple migration path

## 🐳 Docker Simplification
**Single-container solution:**
```dockerfile:Dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
CMD ["python", "web/app.py"]
```

## 🌐 Web UI Implementation (Streamlit Version)
**Tech Stack:**
- ✅ Full-stack: Streamlit (single Python file)
- ✅ Built-in components for real-time updates
- ✅ Automatic UI state management

### Implementation Plan

**Day 1: Core Features (✅ Completed)**
1. ✅ Basic Streamlit app with navigation
2. ✅ Real-time quest monitoring
3. ✅ History view with metrics

**Day 2: Enhanced Features (🚧 In Progress)**
1. Quest Selection and Execution
   - [ ] Quest selector dialog showing quests from quests/kr1
   - [ ] LLM agent configuration (model, temperature, template)
   - [ ] Integration with llm-quest run command
   - [ ] Real-time progress monitoring

2. Benchmark Mode
   - [ ] YAML configuration editor
   - [ ] Benchmark run integration
   - [ ] Progress tracking
   - [ ] Results visualization

3. Analysis Dashboard
   - [ ] Quest success rates
   - [ ] Agent performance comparison
   - [ ] Decision pattern analysis
   - [ ] Export capabilities

## ✅ Acceptance Criteria
- ✅ Web UI shows real-time quest progress
- ✅ Metrics stored in SQLite file
- ✅ Docker container runs for 24h
- ✅ Existing CLI functionality preserved

## Additional Requirements
1. Quest Selection Interface
   - List all quests from quests/kr1 directory
   - Show quest metadata (name, description)
   - Support filtering and search
   - Preview quest content

2. LLM Agent Configuration
   - Model selection from constants.py
   - Temperature adjustment (0.0 - 1.0)
   - Template selection
   - Custom prompt options

3. Benchmark Configuration
   - YAML editor with syntax highlighting
   - Template configurations
   - Validation and error checking
   - Save/load configurations

4. Real-time Monitoring
   - Progress indicators
   - Step-by-step display
   - Agent decisions and rewards
   - Error handling and recovery

## 🛠️ Required Code Changes
1. ✅ Add SQLite support to QuestLogger
2. ✅ Create Streamlit interface
3. [ ] Implement quest selector
4. [ ] Add benchmark YAML editor
5. [ ] Integrate with CLI commands

## ⏰ Updated Time Allocation
| Task | Time | Status |
|------|------|--------|
| Database integration | 3h | ✅ Done |
| Streamlit core | 4h | ✅ Done |
| Real-time streaming | 3h | ✅ Done |
| Quest selector | 3h | 🚧 Todo |
| Benchmark editor | 3h | 🚧 Todo |
| Testing & fixes | 3h | 🚧 Todo |

**Key Advantages of This Approach:**
1. Eliminates 200+ lines of HTML/JS/Flask code
2. Built-in UI refresh mechanism instead of manual SSE
3. Single Python file for entire web interface
4. Maintains same SQLite storage backend
