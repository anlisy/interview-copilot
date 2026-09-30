import subprocess
import sys
from pathlib import Path


def test_cli_b_help():
    env = dict(**__import__("os").environ)
    env["PYTHONPATH"] = str(Path.cwd())
    p = subprocess.run([sys.executable, "-m", "stage7.cli_b", "--help"], text=True, capture_output=True, env=env)
    assert p.returncode == 0
    assert "cross-session evidence aggregation" in p.stdout
