# Leaderboard Implementation Guide

## Overview

The leaderboard feature will provide a comprehensive view of agent performance across benchmarks and quests. It will serve as a "drop-in replacement" for the current benchmark analysis view while offering enhanced filtering, sorting, and visualization capabilities.

## Data Model Changes

### Database Enhancements

```python
# New fields for the Run model
class Run(db.Model):
    # ... existing fields ...

    # New fields for tracking performance metrics
    response_time = db.Column(db.Float, nullable=True)  # Average response time in seconds
    token_usage = db.Column(db.Integer, nullable=True)  # Token count for the run
    tool_usage_count = db.Column(db.Integer, nullable=True)  # Number of tool usages

    # Efficiency metrics
    efficiency_score = db.Column(db.Float, nullable=True)  # Custom score based on steps/reward ratio

# View for leaderboard aggregation (can be implemented as a SQL view or Python aggregation)
class LeaderboardEntry:
    agent_id = None
    model = None
    success_rate = None
    avg_reward = None
    avg_steps = None
    efficiency_score = None
    runs_count = None
    quest_distribution = None
    memory_type = None
    tools_used = None
```

## Backend Implementation

### Routes and Views

```python
# In /llm_quest_benchmark/web/views/analyze.py

@bp.route('/leaderboard')
def leaderboard():
    """Show leaderboard for all agents."""

    # Get filter parameters
    benchmark_id = request.args.get('benchmark', None)
    quest_type = request.args.get('quest_type', None)
    date_range = request.args.get('date_range', None)

    # Get all runs matching filters
    runs_query = Run.query

    if benchmark_id:
        runs_query = runs_query.filter_by(benchmark_id=benchmark_id)

    if quest_type:
        runs_query = runs_query.filter(Run.quest_name.like(f"%{quest_type}%"))

    if date_range:
        # Parse date range and filter
        start_date, end_date = parse_date_range(date_range)
        runs_query = runs_query.filter(Run.start_time.between(start_date, end_date))

    runs = runs_query.all()

    # Aggregate by agent
    agent_stats = {}
    for run in runs:
        agent_id = run.agent_id

        if agent_id not in agent_stats:
            agent_stats[agent_id] = {
                'runs': 0,
                'successes': 0,
                'failures': 0,
                'total_reward': 0,
                'total_steps': 0,
                'quests': set(),
            }

        stats = agent_stats[agent_id]
        stats['runs'] += 1
        stats['quests'].add(run.quest_name)

        if run.outcome == 'SUCCESS':
            stats['successes'] += 1
        else:
            stats['failures'] += 1

        stats['total_reward'] += run.reward or 0

        # Get step count
        step_count = Step.query.filter_by(run_id=run.id).count()
        stats['total_steps'] += step_count

    # Calculate derived metrics
    leaderboard_entries = []
    for agent_id, stats in agent_stats.items():
        success_rate = stats['successes'] / stats['runs'] if stats['runs'] > 0 else 0
        avg_reward = stats['total_reward'] / stats['runs'] if stats['runs'] > 0 else 0
        avg_steps = stats['total_steps'] / stats['runs'] if stats['runs'] > 0 else 0

        # Get agent config details
        agent_config = json.loads(Run.query.filter_by(agent_id=agent_id).first().agent_config)
        model = agent_config.get('model', 'unknown')
        memory_type = agent_config.get('memory', {}).get('type', 'none')
        tools = agent_config.get('tools', [])

        # Calculate efficiency score
        # Higher reward with fewer steps = more efficient
        if avg_steps > 0:
            efficiency_score = (avg_reward / avg_steps) * 100
        else:
            efficiency_score = 0

        leaderboard_entries.append({
            'agent_id': agent_id,
            'model': model,
            'success_rate': success_rate,
            'avg_reward': avg_reward,
            'avg_steps': avg_steps,
            'efficiency_score': efficiency_score,
            'runs_count': stats['runs'],
            'quest_count': len(stats['quests']),
            'memory_type': memory_type,
            'tools_used': tools,
        })

    # Sort by success rate descending by default
    sort_by = request.args.get('sort', 'success_rate')
    reverse = request.args.get('order', 'desc') == 'desc'

    leaderboard_entries.sort(
        key=lambda x: x[sort_by],
        reverse=reverse
    )

    # Get available benchmarks for filter dropdown
    benchmarks = BenchmarkRun.query.all()

    # Get unique quest types
    quest_types = db.session.query(Run.quest_name).distinct().all()
    quest_types = [q[0] for q in quest_types]

    return render_template(
        'analyze/leaderboard.html',
        entries=leaderboard_entries,
        benchmarks=benchmarks,
        quest_types=quest_types,
        current_filters={
            'benchmark': benchmark_id,
            'quest_type': quest_type,
            'date_range': date_range,
            'sort': sort_by,
            'order': 'desc' if reverse else 'asc'
        }
    )

@bp.route('/api/leaderboard', methods=['GET'])
def leaderboard_api():
    """API endpoint for leaderboard data (for AJAX refresh or export)."""
    # Similar logic to the leaderboard view but returns JSON
    # This will be useful for dynamic updates and exports

    # Implement similar filtering logic as the leaderboard route
    # Return as JSON for client-side rendering or export
    return jsonify(leaderboard_data)
```

## Frontend Implementation

### Leaderboard Template

```html
<!-- /llm_quest_benchmark/web/templates/analyze/leaderboard.html -->
{% extends 'base.html' %}

{% block title %}Agent Leaderboard{% endblock %}

{% block content %}
<div class="container mt-4">
  <h1>Agent Leaderboard</h1>

  <!-- Filters -->
  <div class="card mb-4">
    <div class="card-header">
      <h5 class="mb-0">Filters</h5>
    </div>
    <div class="card-body">
      <form id="filter-form" method="get" action="{{ url_for('analyze.leaderboard') }}">
        <div class="row">
          <div class="col-md-3">
            <div class="form-group">
              <label for="benchmark">Benchmark</label>
              <select class="form-control" id="benchmark" name="benchmark">
                <option value="">All Benchmarks</option>
                {% for benchmark in benchmarks %}
                <option value="{{ benchmark.benchmark_id }}" {% if current_filters.benchmark == benchmark.benchmark_id %}selected{% endif %}>
                  {{ benchmark.name }}
                </option>
                {% endfor %}
              </select>
            </div>
          </div>

          <div class="col-md-3">
            <div class="form-group">
              <label for="quest_type">Quest Type</label>
              <select class="form-control" id="quest_type" name="quest_type">
                <option value="">All Quests</option>
                {% for quest in quest_types %}
                <option value="{{ quest }}" {% if current_filters.quest_type == quest %}selected{% endif %}>
                  {{ quest }}
                </option>
                {% endfor %}
              </select>
            </div>
          </div>

          <div class="col-md-3">
            <div class="form-group">
              <label for="date_range">Date Range</label>
              <select class="form-control" id="date_range" name="date_range">
                <option value="">All Time</option>
                <option value="today" {% if current_filters.date_range == 'today' %}selected{% endif %}>Today</option>
                <option value="week" {% if current_filters.date_range == 'week' %}selected{% endif %}>This Week</option>
                <option value="month" {% if current_filters.date_range == 'month' %}selected{% endif %}>This Month</option>
              </select>
            </div>
          </div>

          <div class="col-md-3 d-flex align-items-end">
            <button type="submit" class="btn btn-primary">Apply Filters</button>
            <a href="{{ url_for('analyze.leaderboard') }}" class="btn btn-secondary ml-2">Reset</a>
          </div>
        </div>
      </form>
    </div>
  </div>

  <!-- Leaderboard Table -->
  <div class="card">
    <div class="card-header d-flex justify-content-between align-items-center">
      <h5 class="mb-0">Leaderboard Results</h5>
      <div class="btn-group">
        <button class="btn btn-sm btn-outline-secondary" id="export-csv">Export CSV</button>
        <button class="btn btn-sm btn-outline-secondary" id="export-json">Export JSON</button>
      </div>
    </div>
    <div class="card-body">
      <div class="table-responsive">
        <table class="table table-striped table-hover" id="leaderboard-table">
          <thead>
            <tr>
              <th>#</th>
              <th>
                <a href="{{ url_for('analyze.leaderboard', sort='agent_id', order='asc' if current_filters.sort == 'agent_id' and current_filters.order == 'desc' else 'desc', **{k:v for k,v in current_filters.items() if k not in ['sort', 'order']}) }}">
                  Agent
                  {% if current_filters.sort == 'agent_id' %}
                    <i class="fas fa-sort-{{ 'down' if current_filters.order == 'desc' else 'up' }}"></i>
                  {% endif %}
                </a>
              </th>
              <th>
                <a href="{{ url_for('analyze.leaderboard', sort='model', order='asc' if current_filters.sort == 'model' and current_filters.order == 'desc' else 'desc', **{k:v for k,v in current_filters.items() if k not in ['sort', 'order']}) }}">
                  Model
                  {% if current_filters.sort == 'model' %}
                    <i class="fas fa-sort-{{ 'down' if current_filters.order == 'desc' else 'up' }}"></i>
                  {% endif %}
                </a>
              </th>
              <th>
                <a href="{{ url_for('analyze.leaderboard', sort='success_rate', order='asc' if current_filters.sort == 'success_rate' and current_filters.order == 'desc' else 'desc', **{k:v for k,v in current_filters.items() if k not in ['sort', 'order']}) }}">
                  Success Rate
                  {% if current_filters.sort == 'success_rate' %}
                    <i class="fas fa-sort-{{ 'down' if current_filters.order == 'desc' else 'up' }}"></i>
                  {% endif %}
                </a>
              </th>
              <th>
                <a href="{{ url_for('analyze.leaderboard', sort='avg_reward', order='asc' if current_filters.sort == 'avg_reward' and current_filters.order == 'desc' else 'desc', **{k:v for k,v in current_filters.items() if k not in ['sort', 'order']}) }}">
                  Avg Reward
                  {% if current_filters.sort == 'avg_reward' %}
                    <i class="fas fa-sort-{{ 'down' if current_filters.order == 'desc' else 'up' }}"></i>
                  {% endif %}
                </a>
              </th>
              <th>
                <a href="{{ url_for('analyze.leaderboard', sort='avg_steps', order='asc' if current_filters.sort == 'avg_steps' and current_filters.order == 'desc' else 'desc', **{k:v for k,v in current_filters.items() if k not in ['sort', 'order']}) }}">
                  Avg Steps
                  {% if current_filters.sort == 'avg_steps' %}
                    <i class="fas fa-sort-{{ 'down' if current_filters.order == 'desc' else 'up' }}"></i>
                  {% endif %}
                </a>
              </th>
              <th>
                <a href="{{ url_for('analyze.leaderboard', sort='efficiency_score', order='asc' if current_filters.sort == 'efficiency_score' and current_filters.order == 'desc' else 'desc', **{k:v for k,v in current_filters.items() if k not in ['sort', 'order']}) }}">
                  Efficiency Score
                  {% if current_filters.sort == 'efficiency_score' %}
                    <i class="fas fa-sort-{{ 'down' if current_filters.order == 'desc' else 'up' }}"></i>
                  {% endif %}
                </a>
              </th>
              <th>Memory</th>
              <th>Tools</th>
              <th>Runs</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {% for entry in entries %}
            <tr {% if loop.index <= 3 %}class="table-success"{% endif %}>
              <td>{{ loop.index }}</td>
              <td>{{ entry.agent_id }}</td>
              <td>{{ entry.model }}</td>
              <td>
                <div class="progress" style="height: 20px;">
                  <div class="progress-bar bg-success" role="progressbar"
                       style="width: {{ (entry.success_rate * 100)|round }}%;"
                       aria-valuenow="{{ (entry.success_rate * 100)|round }}"
                       aria-valuemin="0" aria-valuemax="100">
                    {{ (entry.success_rate * 100)|round }}%
                  </div>
                </div>
              </td>
              <td>{{ entry.avg_reward|round(1) }}</td>
              <td>{{ entry.avg_steps|round(1) }}</td>
              <td>{{ entry.efficiency_score|round(1) }}</td>
              <td>
                {% if entry.memory_type == 'message_history' %}
                <span class="badge bg-primary">History</span>
                {% elif entry.memory_type == 'summary' %}
                <span class="badge bg-info">Summary</span>
                {% else %}
                <span class="badge bg-secondary">None</span>
                {% endif %}
              </td>
              <td>
                {% for tool in entry.tools_used %}
                <span class="badge bg-dark">{{ tool }}</span>
                {% else %}
                <span class="badge bg-light text-dark">None</span>
                {% endfor %}
              </td>
              <td>{{ entry.runs_count }}</td>
              <td>
                <a href="{{ url_for('analyze.agent_detail', agent_id=entry.agent_id) }}" class="btn btn-sm btn-outline-primary">Details</a>
              </td>
            </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- Charts Section -->
  <div class="row mt-4">
    <div class="col-md-6">
      <div class="card">
        <div class="card-header">
          <h5 class="mb-0">Success Rate by Model</h5>
        </div>
        <div class="card-body">
          <canvas id="modelSuccessChart"></canvas>
        </div>
      </div>
    </div>
    <div class="col-md-6">
      <div class="card">
        <div class="card-header">
          <h5 class="mb-0">Memory Type Comparison</h5>
        </div>
        <div class="card-body">
          <canvas id="memoryComparisonChart"></canvas>
        </div>
      </div>
    </div>
  </div>
</div>

{% block scripts %}
<script>
  // Chart data preparation
  const models = {{ entries|map(attribute='model')|list|tojson }};
  const successRates = {{ entries|map(attribute='success_rate')|list|tojson }};

  // Model Success Chart
  const modelCtx = document.getElementById('modelSuccessChart').getContext('2d');
  new Chart(modelCtx, {
    type: 'bar',
    data: {
      labels: models,
      datasets: [{
        label: 'Success Rate (%)',
        data: successRates.map(rate => rate * 100),
        backgroundColor: 'rgba(54, 162, 235, 0.5)',
        borderColor: 'rgba(54, 162, 235, 1)',
        borderWidth: 1
      }]
    },
    options: {
      scales: {
        y: {
          beginAtZero: true,
          max: 100
        }
      }
    }
  });

  // Memory comparison chart
  // ... similar implementation for memory type chart

  // Export functionality
  document.getElementById('export-csv').addEventListener('click', function() {
    window.location.href = "{{ url_for('analyze.leaderboard_api') }}?format=csv";
  });

  document.getElementById('export-json').addEventListener('click', function() {
    window.location.href = "{{ url_for('analyze.leaderboard_api') }}?format=json";
  });
</script>
{% endblock %}
{% endblock %}
```

### Agent Detail Template

```html
<!-- /llm_quest_benchmark/web/templates/analyze/agent_detail.html -->
{% extends 'base.html' %}

{% block title %}Agent Details: {{ agent_id }}{% endblock %}

{% block content %}
<div class="container mt-4">
  <h1>Agent Details: {{ agent_id }}</h1>

  <div class="row">
    <div class="col-md-4">
      <div class="card mb-4">
        <div class="card-header">
          <h5 class="mb-0">Agent Configuration</h5>
        </div>
        <div class="card-body">
          <dl class="row">
            <dt class="col-sm-4">Model</dt>
            <dd class="col-sm-8">{{ agent_config.model }}</dd>

            <dt class="col-sm-4">Temperature</dt>
            <dd class="col-sm-8">{{ agent_config.temperature }}</dd>

            <dt class="col-sm-4">Memory Type</dt>
            <dd class="col-sm-8">
              {% if agent_config.memory %}
              {{ agent_config.memory.type }}
              <small class="text-muted">({{ agent_config.memory.max_history }} entries)</small>
              {% else %}
              None
              {% endif %}
            </dd>

            <dt class="col-sm-4">Tools</dt>
            <dd class="col-sm-8">
              {% for tool in agent_config.tools %}
              <span class="badge bg-dark">{{ tool }}</span>
              {% else %}
              None
              {% endfor %}
            </dd>
          </dl>
        </div>
      </div>

      <div class="card mb-4">
        <div class="card-header">
          <h5 class="mb-0">Performance Summary</h5>
        </div>
        <div class="card-body">
          <dl class="row">
            <dt class="col-sm-6">Success Rate</dt>
            <dd class="col-sm-6">{{ (success_rate * 100)|round(1) }}%</dd>

            <dt class="col-sm-6">Average Reward</dt>
            <dd class="col-sm-6">{{ avg_reward|round(1) }}</dd>

            <dt class="col-sm-6">Average Steps</dt>
            <dd class="col-sm-6">{{ avg_steps|round(1) }}</dd>

            <dt class="col-sm-6">Efficiency Score</dt>
            <dd class="col-sm-6">{{ efficiency_score|round(1) }}</dd>

            <dt class="col-sm-6">Total Runs</dt>
            <dd class="col-sm-6">{{ runs_count }}</dd>
          </dl>
        </div>
      </div>
    </div>

    <div class="col-md-8">
      <div class="card mb-4">
        <div class="card-header">
          <h5 class="mb-0">Performance by Quest</h5>
        </div>
        <div class="card-body">
          <canvas id="questPerformanceChart"></canvas>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <h5 class="mb-0">Recent Runs</h5>
        </div>
        <div class="card-body">
          <div class="table-responsive">
            <table class="table table-striped">
              <thead>
                <tr>
                  <th>Quest</th>
                  <th>Date</th>
                  <th>Outcome</th>
                  <th>Reward</th>
                  <th>Steps</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {% for run in recent_runs %}
                <tr>
                  <td>{{ run.quest_name }}</td>
                  <td>{{ run.start_time.strftime('%Y-%m-%d %H:%M') }}</td>
                  <td>
                    {% if run.outcome == 'SUCCESS' %}
                    <span class="badge bg-success">Success</span>
                    {% else %}
                    <span class="badge bg-danger">Failure</span>
                    {% endif %}
                  </td>
                  <td>{{ run.reward or 0 }}</td>
                  <td>{{ run.step_count }}</td>
                  <td>
                    <a href="{{ url_for('analyze.run_details', run_id=run.id) }}" class="btn btn-sm btn-outline-primary">View</a>
                  </td>
                </tr>
                {% endfor %}
              </tbody>
            </table>
          </div>

          <div class="text-center mt-3">
            <a href="{{ url_for('analyze.index', agent_id=agent_id) }}" class="btn btn-primary">View All Runs</a>
          </div>
        </div>
      </div>
    </div>
  </div>
</div>

{% block scripts %}
<script>
  // Quest performance chart
  const quests = {{ quest_stats|map(attribute='quest')|list|tojson }};
  const successRates = {{ quest_stats|map(attribute='success_rate')|list|tojson }};

  const ctx = document.getElementById('questPerformanceChart').getContext('2d');
  new Chart(ctx, {
    type: 'bar',
    data: {
      labels: quests,
      datasets: [{
        label: 'Success Rate (%)',
        data: successRates.map(rate => rate * 100),
        backgroundColor: 'rgba(75, 192, 192, 0.5)',
        borderColor: 'rgba(75, 192, 192, 1)',
        borderWidth: 1
      }]
    },
    options: {
      scales: {
        y: {
          beginAtZero: true,
          max: 100
        }
      }
    }
  });
</script>
{% endblock %}
{% endblock %}
```

## Unified Run Analytics Implementation

1. Update the existing `/analyze` view to include both benchmark runs and individual quest runs
2. Add filtering options by agent, quest, date range, etc.
3. Enhance the display to show memory and tool usage info

## Adding Navbar Links

```html
<!-- Update in /llm_quest_benchmark/web/templates/base.html -->
<nav class="navbar navbar-expand-lg navbar-dark bg-dark">
  <!-- ... existing nav content ... -->
  <div class="collapse navbar-collapse" id="navbarNav">
    <ul class="navbar-nav">
      <!-- ... existing links ... -->
      <li class="nav-item">
        <a class="nav-link" href="{{ url_for('analyze.index') }}">Runs</a>
      </li>
      <li class="nav-item">
        <a class="nav-link" href="{{ url_for('analyze.leaderboard') }}">Leaderboard</a>
      </li>
      <!-- ... other links ... -->
    </ul>
  </div>
</nav>
```

## Implementation Steps

1. **Database Schema Updates**
   - Add new fields to Run model for detailed metrics
   - Update database migrations

2. **Backend Logic**
   - Implement leaderboard route and data aggregation
   - Create API endpoints for data export
   - Update existing routes to include all runs

3. **Frontend Development**
   - Create leaderboard template
   - Add agent detail template
   - Update navigation and links

4. **Testing**
   - Test with different agent configurations
   - Verify metrics accuracy
   - Test filtering and sorting functionality

5. **Documentation**
   - Update user documentation
   - Document new API endpoints
   - Add example usage in README
