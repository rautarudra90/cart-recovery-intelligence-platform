#!/usr/bin/env python3
"""
CLI entrypoint to generate synthetic cart recovery data and populate SQLite.
Usage:
    python scripts/run_generator.py --scale starter
    python scripts/run_generator.py --scale full
"""
import sys
import argparse
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from cart_recover.database.connection import load_dataset_to_sqlite

def main():
    parser = argparse.ArgumentParser(description="Generate synthetic cart recovery dataset.")
    parser.add_argument("--scale", choices=["starter", "full"], default="starter", help="Dataset volume scale")
    parser.add_argument("--seed", type=int, default=20261022, help="Deterministic random seed")
    parser.add_argument("--out", type=str, default=None, help="Output directory path")
    args = parser.parse_args()

    out_dir = Path(args.out) if args.out else ROOT_DIR / "data" / args.scale
    out_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        str(ROOT_DIR / "generate_data.py"),
        "--scale", args.scale,
        "--seed", str(args.seed),
        "--out", str(out_dir)
    ]

    print(f"Executing: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

    print("Populating SQLite relational database...")
    db_path = load_dataset_to_sqlite(out_dir)
    print(f"SQLite database ready at: {db_path}")

if __name__ == "__main__":
    main()
