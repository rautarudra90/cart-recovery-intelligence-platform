#!/usr/bin/env python3
"""
End-to-End Orchestration Script for CartRecover-AI Platform.
Executes data generation, SQLite relational indexing, strict validation,
and reproducibility verification in a single automated pipeline.
Usage:
    python scripts/run_pipeline.py [--scale starter|full]
"""
import sys
import argparse
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from cart_recover.database.connection import load_dataset_to_sqlite

def run_step(step_name: str, cmd: list):
    print("\n" + "=" * 60)
    print(f"STEP: {step_name}")
    print("=" * 60)
    res = subprocess.run(cmd)
    if res.returncode != 0:
        print(f"FAILED: {step_name} exited with code {res.returncode}")
        sys.exit(res.returncode)

def main():
    parser = argparse.ArgumentParser(description="End-to-end pipeline runner.")
    parser.add_argument("--scale", choices=["starter", "full"], default="starter", help="Scale preset")
    parser.add_argument("--seed", type=int, default=20261022, help="Deterministic seed")
    args = parser.parse_args()

    data_dir = ROOT_DIR / "data" / args.scale

    # 1. Generate Dataset
    gen_cmd = [
        sys.executable,
        str(ROOT_DIR / "generate_data.py"),
        "--scale", args.scale,
        "--seed", str(args.seed),
        "--out", str(data_dir)
    ]
    run_step(f"Generate Synthetic Dataset ({args.scale})", gen_cmd)

    # 2. Populate SQLite Database
    print("\n" + "=" * 60)
    print("STEP: Index Relational SQLite Database")
    print("=" * 60)
    db_file = load_dataset_to_sqlite(data_dir)
    print(f"Database indexed at: {db_file}")

    # 3. Validate Dataset
    val_cmd = [
        sys.executable,
        str(ROOT_DIR / "validate_data.py"),
        "--data", str(data_dir)
    ]
    run_step("Run Comprehensive Acceptance Validation", val_cmd)

    # 4. Check Reproducibility
    repro_cmd = [
        sys.executable,
        str(ROOT_DIR / "repro_check.py"),
        "--out", str(data_dir),
        "--scale", args.scale,
        "--seed", str(args.seed)
    ]
    run_step("Verify Deterministic Reproducibility (SHA-256)", repro_cmd)

    print("\n" + "*" * 60)
    print("✨ ALL PIPELINE STAGES PASSED SUCCESSFULLY!")
    print(f"To launch the interactive dashboard, run:\n  streamlit run app.py")
    print("*" * 60 + "\n")

if __name__ == "__main__":
    main()
