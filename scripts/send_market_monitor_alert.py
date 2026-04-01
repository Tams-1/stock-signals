#!/usr/bin/env python3
"""
Run production_simple.py and emit only the formatted alert payload.
"""

import subprocess
import sys
from pathlib import Path
from typing import Optional


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALERT_MARKER = "🚨 TOP TRADING OPPORTUNITIES"
NO_ACTIONABLE_SIGNALS = "No actionable signals"


def extract_alert(output: str) -> Optional[str]:
    """Return only the formatted alert block from production output."""
    marker_index = output.find(ALERT_MARKER)
    if marker_index == -1:
        return None
    return output[marker_index:].strip()


def main() -> int:
    try:
        completed = subprocess.run(
            ["python3", "production_simple.py"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except OSError as exc:
        print(f"Failed to run production_simple.py: {exc}", file=sys.stderr)
        return 1

    if completed.returncode != 0:
        error_output = completed.stderr.strip() or completed.stdout.strip()
        if error_output:
            print(error_output, file=sys.stderr)
        return completed.returncode

    alert = extract_alert(completed.stdout)
    print(alert or NO_ACTIONABLE_SIGNALS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
