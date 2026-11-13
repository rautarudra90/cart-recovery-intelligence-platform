#!/usr/bin/env python3
"""Regenerate twice with the same seed and compare row counts + SHA-256 of every file.

    python repro_check.py --out data/full [--scale full|starter]
Writes <out>/reproducibility_report.json (runs go to a scratch dir, not into --out).
"""
import argparse, json, os, shutil, subprocess, sys, tempfile
from generate_data import sha256


def run(scale, out, extra):
    subprocess.run([sys.executable, "generate_data.py", "--scale", scale, "--out", out] + extra, check=True, stdout=subprocess.DEVNULL)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/full")
    ap.add_argument("--scale", default="full")
    ap.add_argument("--seed", type=int, default=20261022)
    a = ap.parse_args()
    tmp = tempfile.mkdtemp(prefix="repro_")
    try:
        runs = []
        for i in (1, 2):
            o = os.path.join(tmp, "run%d" % i)
            run(a.scale, o, ["--seed", str(a.seed)])
            files = {os.path.relpath(os.path.join(dp, f), o).replace("\\", "/"): os.path.join(dp, f) for dp, _, fs in os.walk(o) for f in fs}
            runs.append({k: dict(sha256=sha256(p), rows=sum(1 for _ in open(p, "rb")) - 1 if k.endswith(".csv") else None) for k, p in sorted(files.items())})
        diff = [k for k in set(runs[0]) | set(runs[1]) if runs[0].get(k) != runs[1].get(k)]
        rep = dict(seed=a.seed, scale=a.scale, files_compared=len(runs[0]), identical=not diff, differing_files=sorted(diff), run1=runs[0], run2=runs[1])
        with open(os.path.join(a.out, "reproducibility_report.json"), "w", newline="\n") as f:
            json.dump(rep, f, indent=1)
        print("identical:", rep["identical"], "| files compared:", rep["files_compared"], "| differing:", rep["differing_files"])
        sys.exit(0 if rep["identical"] else 1)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
