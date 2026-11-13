#!/usr/bin/env python3
"""
CLI entrypoint to verify deterministic reproducibility via row counts and SHA-256 checksums.
Usage:
    python scripts/run_reproducibility.py --scale starter
    python scripts/run_reproducibility.py --scale full
"""
import sys
import argparse
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

def main():
    parser = argparse.ArgumentParser(description="Verify dataset reproducibility.")
    parser.add_argument("--scale", choices=["starter", "full"], default="starter", help="Dataset scale to test")
    parser.add_argument("--seed", type=int, default=20261022, help="Deterministic random seed")
    args = parser.parse_args()

    out_dir = ROOT_DIR / "data" / args.scale

    cmd = [
        sys.executable,
        str(ROOT_DIR / "repro_check.py"),
        "--out", str(out_dir),
        "--scale", args.scale,
        "--seed", str(args.seed)
    ]

    print(f"Executing reproducibility test for scale '{args.scale}' with seed {args.seed}...")
    res = subprocess.run(cmd)
    sys.exit(res.returncode)

if __name__ == "__main__":
    main()
