# LLM Quest Benchmark Roadmap

## Web UI for Benchmark Implementation Plan

This plan outlines the steps to implement a web UI for benchmark functionality, adding to the existing web interface.

### Core Components

#### 1. Benchmark Configuration
- Use a shared default configuration source for both CLI and web UI
- Simple YAML editor with validation feedback
- "Run Benchmark" button to start benchmarks
- Support for basic configuration options

#### 2. Progress Tracking Component
- Create a reusable component for progress tracking
- Implement in both benchmark view and quest monitor view
- Show progress bar, current task, and status
- Support real-time updates

#### 3. Benchmark Results View
- Integrate with existing analysis tools
- Show summary statistics (success rate, model comparison)
- Display detailed quest outcomes
- Link to full run details in the analysis section

### Implementation Plan

#### Step 1: Update Configuration Handling
1. Create a central source for default benchmark configuration
2. Use this configuration in both CLI and web UI
3. Implement simple validation with helpful error messages

#### Step 2: Create Reusable Progress Tracker
1. Develop a progress tracking component
2. Implement backend API for status updates
3. Create frontend component for displaying progress
4. Integrate with both benchmark and quest runner views

#### Step 3: Update Benchmark Controller
1. Add endpoints for starting and monitoring benchmarks
2. Implement background processing for benchmark runs
3. Store benchmark results in the database
4. Create API for retrieving benchmark status and results

#### Step 4: Enhance Analysis Views
1. Update analyze views to better support benchmark results
2. Create a dedicated benchmark analysis view
3. Implement visualization of benchmark results
4. Provide links between benchmark and detailed run analysis

#### Step 5: Database Updates
1. Add benchmark run table to store benchmark metadata
2. Track benchmark progress and results
3. Link benchmark runs to individual quest runs

### Technical Details

#### Database Schema
```python
class BenchmarkRun(db.Model):
    """Benchmark run record"""
    id = db.Column(db.Integer, primary_key=True)
    benchmark_id = db.Column(db.String(64), unique=True, nullable=False)
    name = db.Column(db.String(128))
    config = db.Column(db.Text)  # JSON string of benchmark config
    status = db.Column(db.String(32), default='running')  # running, complete, error
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    end_time = db.Column(db.DateTime, nullable=True)
    results = db.Column(db.Text, nullable=True)  # JSON string of results
    error = db.Column(db.Text, nullable=True)
```

#### Benchmark Status Tracking
```python
class BenchmarkStatus:
    """Benchmark status tracker"""
    def __init__(self, benchmark_id, config_dict):
        self.benchmark_id = benchmark_id
        self.config_dict = config_dict
        self.status = 'initializing'
        self.progress = 0
        self.current_task = 'Starting benchmark'
        self.start_time = datetime.now()
        self.end_time = None
        self.result = None
        self.error = None
```

#### Progress Tracker Component
The progress tracker will be a reusable component that can be included in any page that needs to show progress:

```html
<!-- Progress Tracker Component -->
<div class="card border-0 shadow-sm mb-4" id="progressTrackerCard" style="display: none;">
    <div class="card-header bg-white">
        <h5 class="card-title mb-0" id="progressTrackerTitle">Progress</h5>
    </div>
    <div class="card-body">
        <div class="mb-3">
            <p id="progressInfo">Running...</p>
            <div class="progress mb-3">
                <div id="progressBar" class="progress-bar progress-bar-striped progress-bar-animated" 
                     role="progressbar" style="width: 0%"></div>
            </div>
            <div id="currentTask">Initializing...</div>
        </div>
    </div>
</div>
```

### Next Steps

Once the basic implementation is complete, potential enhancements include:

1. Add support for cancelling running benchmarks
2. Implement comparison between different benchmark runs
3. Add export functionality for benchmark results
4. Create visualizations for tracking performance over time