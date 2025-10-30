"""Test script to diagnose service stop issues.

Runs the server and simulates NSSM's stop behavior by sending SIGTERM.
Shows what happens during shutdown.
"""
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

def main():
    script_dir = Path(__file__).parent
    venv_python = script_dir / "venv" / "Scripts" / "python.exe"
    start_script = script_dir / "mcp-server" / "start_mcp_http.py"

    print("=== Service Stop Diagnostic Test ===")
    print(f"Python: {venv_python}")
    print(f"Script: {start_script}")
    print()

    # Start the server process
    print("Starting server process...")
    proc = subprocess.Popen(
        [str(venv_python), str(start_script)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        creationflags=subprocess.CREATE_NEW_CONSOLE  # Show console window
    )

    print(f"Server started with PID: {proc.pid}")
    print()
    print("Waiting 15 seconds for server to initialize...")
    print("(You should see a console window open)")
    time.sleep(15)

    print()
    print("Sending SIGTERM (simulating NSSM stop)...")
    try:
        proc.send_signal(signal.SIGTERM)
    except AttributeError:
        # Windows fallback
        proc.terminate()

    print("Waiting for clean shutdown (max 20 seconds)...")
    try:
        stdout, _ = proc.communicate(timeout=20)
        print()
        print("=== Server Output ===")
        print(stdout)
        print()
        print(f"Process exited with code: {proc.returncode}")
        print("✓ Clean shutdown successful!")
    except subprocess.TimeoutExpired:
        print()
        print("✗ TIMEOUT - Process did not exit within 20 seconds!")
        print("This explains the STOP_PENDING issue.")
        print()
        print("Force-killing process...")
        proc.kill()
        stdout, _ = proc.communicate()
        print()
        print("=== Server Output ===")
        print(stdout)
        print()
        print("Analysis: Python process is not exiting cleanly after shutdown.")
        print("Possible causes:")
        print("  - Daemon threads still running")
        print("  - Asyncio event loop not closing")
        print("  - Background tasks not cancelled")
        print("  - Resource cleanup incomplete")

if __name__ == "__main__":
    main()
