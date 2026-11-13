#!/usr/bin/env python3
"""
CLI entrypoint to run strict validation and generate acceptance metrics.
Usage:
    python scripts/run_validation.py --scale starter
    python scripts/run_validation.py --scale full
"""
import sys
import argparse
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

def main():
    parser = argparse.ArgumentParser(description="Validate cart recovery dataset.")
    parser.add_argument("--scale", choices=["starter", "full"], default="starter", help="Dataset scale to validate")
    parser.add_argument("--data", type=str, default=None, help="Explicit data directory path")
    args = parser.parse_args()

    data_dir = Path(args.data) if args.data else ROOT_DIR / "data" / args.scale
    if not data_dir.exists():
        print(f"Error: Dataset directory not found: {data_dir}")
        sys.exit(1)

    cmd = [
        sys.executable,
        str(ROOT_DIR / "validate_data.py"),
        "--data", str(data_dir)
    ]

    print(f"Running validation on: {data_dir}")
    res = subprocess.run(cmd)
    sys.exit(res.returncode)

if __name__ == "__main__":
    main()
