# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow", "numpy"]
# ///
"""Diff a branch's screenshots against its own merge base.

The first thing to run when owidbot reports "N pages changed". Both the reported diff and
GitHub's compare link are three-dot diffs, so master's later reference commits are not part of
what the branch changed -- comparing against master's head instead invents differences.

    uv run mergebase-diff.py legend-tap timeline-end-period-labels

Prints, per changed screenshot: how many pixels differ, the largest per-channel delta, and the
contiguous row bands. Read them like this:

    deltas of 1-3 with a low maximum   resampling or a mid-decode capture
    maxdelta 255 and one side at 255   something is missing entirely (a blank chart)
    a band a few rows tall             one line of text: a date, a count, a label
    a size change plus everything      a height change cascading down the page
    below it differing

An identical pixel count on two branches that touch different code is the harness, not either
branch. That check has settled almost every class in this skill, so make it first.

Images land in ./mergebase-diff/ for cropping.
"""

import os
import subprocess
import sys
import urllib.request

import numpy as np
from PIL import Image

REPO = "owid/site-screenshots"
RAW = "https://raw.githubusercontent.com/" + REPO
OUT = os.path.join(os.getcwd(), "mergebase-diff")


def gh(path, jq):
    # gh rather than a bare token: the keyring login is what is set up on this machine, and
    # GITHUB_TOKEN in the environment is often a narrower one that 404s on this repo.
    env = {k: v for k, v in os.environ.items() if k != "GITHUB_TOKEN"}
    out = subprocess.run(
        ["gh", "api", f"repos/{REPO}/{path}", "--jq", jq],
        capture_output=True, text=True, env=env,
    )
    if out.returncode:
        raise SystemExit(f"gh api {path} failed: {out.stderr.strip()[:300]}")
    return out.stdout.strip()


def fetch(sha, path, dest):
    urllib.request.urlretrieve(f"{RAW}/{sha}/{path}", dest)


def bands(mask, gap=5):
    """Contiguous runs of differing rows, so a region can be found without scrolling an image."""
    rows = np.where(mask.any(axis=1))[0]
    if not len(rows):
        return []
    out, start, prev = [], rows[0], rows[0]
    for r in rows[1:]:
        if r > prev + gap:
            out.append((int(start), int(prev)))
            start = r
        prev = r
    out.append((int(start), int(prev)))
    return out


def compare(branch):
    base, head = gh(
        f"compare/master...{branch}",
        '"\\(.merge_base_commit.sha) \\(.commits[-1].sha)"',
    ).split()
    files = [f for f in gh(f"compare/{base}...{head}", ".files[].filename").splitlines() if f]
    print(f"\n{branch}\n  merge base {base[:8]}  head {head[:8]}  "
          f"{len(files) or 'no'} changed file(s)")
    os.makedirs(OUT, exist_ok=True)
    for path in files:
        name = os.path.basename(path).removesuffix(".png")
        a_path = os.path.join(OUT, f"{branch}__{name}__base.png")
        b_path = os.path.join(OUT, f"{branch}__{name}__head.png")
        fetch(base, path, a_path)
        fetch(head, path, b_path)
        a = np.asarray(Image.open(a_path).convert("RGB")).astype(np.int16)
        b = np.asarray(Image.open(b_path).convert("RGB")).astype(np.int16)
        note = ""
        if a.shape != b.shape:
            note = f"  HEIGHT {a.shape[0]} -> {b.shape[0]}"
            h = min(a.shape[0], b.shape[0])
            a, b = a[:h], b[:h]
        d = np.abs(a - b).max(axis=2)
        n = int((d > 0).sum())
        pct = 100 * n / d.size
        print(f"  {name}: {n} px ({pct:.4f}%) maxdelta {int(d.max())}{note}")
        # a side that is pure white where the other has content is a missing element
        sel = d > 0
        if sel.any():
            print(f"     mean base {a[sel].mean():.1f}, mean head {b[sel].mean():.1f}"
                  f"{'   <- head is blank here' if b[sel].mean() > 254.5 else ''}")
        for lo, hi in bands(d > 0)[:20]:
            print(f"     rows {lo}-{hi}: {int((d[lo:hi + 1] > 0).sum())} px")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    for branch in sys.argv[1:]:
        compare(branch)
