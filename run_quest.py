#!/usr/bin/env python3
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

print("Script starting...")

# Create logs directory
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

# Create log file
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = log_dir / f"quest_run_{timestamp}.log"

print(f"Logging to: {log_file}")

# Command to run
cmd = [
    sys.executable,
    "-m", "llm_quest_benchmark.scripts.cli",
    "run",
    "-q", "quests/boat.qm",
    "--metrics",
    "--log-level", "debug",
    "--model", "sonnet"
]

print(f"Running command: {' '.join(cmd)}")

# Run the command and capture output
with open(log_file, "w") as f:
    f.write(f"Starting quest run at {datetime.now()}\n")
    f.write(f"Command: {' '.join(cmd)}\n")
    f.write(f"Python executable: {sys.executable}\n")
    f.write(f"Working directory: {os.getcwd()}\n\n")
    f.flush()

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )

        start_time = time.time()
        while True:
            if process.poll() is not None:
                # Process finished
                break

            if time.time() - start_time > 60:
                process.kill()
                msg = "\nProcess killed after 60 seconds timeout\n"
                print(msg, end="")
                f.write(msg)
                break

            # Read output
            output = process.stdout.readline()
            if output:
                print(output, end="")  # Print to console in real-time
                f.write(output)
                f.flush()

        # Get any remaining output
        remaining_output, _ = process.communicate()
        if remaining_output:
            print(remaining_output, end="")
            f.write(remaining_output)

        f.write(f"\nProcess ended at {datetime.now()}\n")
        f.write(f"Exit code: {process.returncode}\n")
        print(f"Exit code: {process.returncode}")

    except Exception as e:
        msg = f"\nError: {e}\n"
        print(msg, end="")
        f.write(msg)

print(f"Log file written to: {log_file}")