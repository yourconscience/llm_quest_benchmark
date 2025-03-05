"""Check benchmark results"""
import sqlite3
import json

# Connect to the database
conn = sqlite3.connect('metrics.db')
conn.row_factory = sqlite3.Row  # This enables column access by name
cursor = conn.cursor()

# Check available tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
print("Available tables:")
tables = cursor.fetchall()
for table in tables:
    print(f"- {table['name']}")

# Check recent runs
cursor.execute("SELECT id, benchmark_id, quest_name, agent_id, outcome FROM runs ORDER BY id DESC LIMIT 10;")
print("\nRecent runs:")
runs = cursor.fetchall()
for run in runs:
    print(f"Run {run['id']}: {run['benchmark_id']} - {run['quest_name']} - {run['agent_id']} - {run['outcome']}")

# Check benchmarks
cursor.execute("SELECT * FROM benchmark_runs ORDER BY id DESC LIMIT 5;")
benchmarks = cursor.fetchall()
print("\nRecent benchmarks:")
for benchmark in benchmarks:
    print(f"Benchmark {benchmark['id']}: {benchmark['benchmark_id']} - {benchmark['name']} - {benchmark['status']}")
    
    # Try to access results if they exist
    if benchmark['results']:
        try:
            results = json.loads(benchmark['results'])
            print(f"  - Results count: {len(results)}")
        except:
            print(f"  - Results available but not JSON: {type(benchmark['results'])}")
    else:
        print("  - No results")

conn.close()