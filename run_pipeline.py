"""
run_pipeline.py — Full Pipeline Orchestrator
Runs all pipeline steps in the correct order.
Each step checks for its required inputs and skips gracefully if they
are missing, so you can re-run the pipeline from any point.

Usage:
    python run_pipeline.py              # run all steps
    python run_pipeline.py --from 04   # restart from step 04
    python run_pipeline.py --skip 05   # skip step 05 (e.g. if no GPU)
    python run_pipeline.py --only 07   # run only step 07

Steps:
    01  Account Verification
    02  Post Collection
    03  Keyword Extraction + LDA
    04  Weekly Bluesky Search + Temporal Analysis
    04b İmamoğlu Protest Search + Timeline
    05  Sentiment & Hate Speech Analysis
    05b Ideology Classifier
    05c Statistical Tests
    06  Network Analysis
    07  Visualizations
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path


# --- Colour Helpers -----------------------------------------------------------

GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

def ok(msg: str)   -> None: print(f"{GREEN}  OK  {RESET} {msg}")
def warn(msg: str) -> None: print(f"{YELLOW} WARN {RESET} {msg}")
def err(msg: str)  -> None: print(f"{RED}  ERR {RESET} {msg}")
def info(msg: str) -> None: print(f"{CYAN} INFO {RESET} {msg}")


# --- Prerequisite Checks ------------------------------------------------------

def check_python_version() -> None:
    required = (3, 12)
    current  = sys.version_info[:2]
    if current < required:
        err(f"Python {required[0]}.{required[1]}+ required. Got {current[0]}.{current[1]}.")
        sys.exit(1)
    ok(f"Python {current[0]}.{current[1]}.{sys.version_info[2]}")


def check_env_file() -> None:
    if not Path(".env").exists():
        warn(".env not found — AT Protocol auth disabled. "
             "Create it from .env.example for authenticated requests.")
    else:
        ok(".env found")


def check_turkishbertweet() -> bool:
    if not Path("TurkishBERTweet").exists():
        warn("TurkishBERTweet/ not found.")
        warn("Step 05 (Sentiment Analysis) requires it:")
        warn("  git clone https://github.com/ViralLab/TurkishBERTweet.git")
        return False
    ok("TurkishBERTweet/ found")
    return True


def check_data_file() -> None:
    path = Path("data/combined_users_with_bsky_final.csv")
    if not path.exists():
        err(f"Input data not found: {path}")
        sys.exit(1)
    ok(f"Data file: {path}")


# --- Step Definitions ---------------------------------------------------------

STEPS: list[dict] = [
    {
        "id":       "01",
        "label":    "Account Verification",
        "script":   "src/01_verify_accounts.py",
        "requires": ["data/combined_users_with_bsky_final.csv"],
        "produces": ["outputs/verified_accounts.csv"],
        "optional": False,
    },
    {
        "id":       "02",
        "label":    "Post Collection",
        "script":   "src/02_fetch_posts.py",
        "requires": ["outputs/verified_accounts.csv"],
        "produces": ["outputs/all_posts_raw.jsonl"],
        "optional": False,
    },
    {
        "id":       "03",
        "label":    "Keyword Extraction + LDA",
        "script":   "src/03_keyword_extraction.py",
        "requires": ["outputs/all_posts_raw.jsonl"],
        "produces": ["outputs/political_keywords.json",
                     "outputs/search_keywords.json",
                     "outputs/search_keywords.csv"],
        "optional": False,
    },
    {
        "id":       "04",
        "label":    "Weekly Search + Temporal Analysis",
        "script":   "src/04_weekly_search.py",
        "requires": ["outputs/political_keywords.json", "outputs/verified_accounts.csv"],
        "produces": ["outputs/weekly_search_results.jsonl",
                     "outputs/weekly_distribution_stats.json"],
        "optional": False,
    },
    {
        "id":       "04b",
        "label":    "İmamoğlu Protest Search + Timeline",
        "script":   "src/04b_protest_search.py",
        "requires": ["outputs/verified_accounts.csv"],
        "produces": ["outputs/protest_posts.jsonl",
                     "outputs/protest_timeline.json"],
        "optional": False,
    },
    {
        "id":       "05",
        "label":    "Sentiment & Hate Speech Analysis",
        "script":   "src/05_sentiment_analysis.py",
        "requires": ["outputs/protest_posts.jsonl"],
        "produces": ["outputs/sentiment_results.csv"],
        "optional": True,   # requires TurkishBERTweet + torch
        "note":     "Requires: git clone https://github.com/ViralLab/TurkishBERTweet.git",
    },
    {
        "id":       "05b",
        "label":    "Ideology Classifier",
        "script":   "src/05b_ideology_classifier.py",
        "requires": ["outputs/all_posts_raw.jsonl"],
        "produces": ["outputs/ideology_classifier_results.json"],
        "optional": True,
    },
    {
        "id":       "05c",
        "label":    "Statistical Tests",
        "script":   "src/05c_statistical_tests.py",
        "requires": ["outputs/sentiment_results.csv"],
        "produces": ["outputs/statistical_test_results.json"],
        "optional": True,   # requires sentiment_results.csv from step 05
    },
    {
        "id":       "06",
        "label":    "Network Analysis",
        "script":   "src/06_network_analysis.py",
        "requires": ["outputs/all_posts_raw.jsonl", "outputs/verified_accounts.csv"],
        "produces": ["outputs/network_edges.csv", "outputs/network_metrics.json",
                     "outputs/network_node_metrics.csv", "outputs/network_summary.json",
                     "outputs/network_party_flow.csv", "outputs/network_community_summary.csv"],
        "optional": False,
    },
    {
        "id":       "07",
        "label":    "Visualizations",
        "script":   "src/07_visualizations.py",
        "requires": [],   # gracefully skips missing inputs internally
        "produces": ["outputs/figures/G1_party_post_counts.png"],
        "optional": False,
    },
]


# --- Runner -------------------------------------------------------------------

def run_step(step: dict, dry_run: bool = False) -> bool:
    """Run one pipeline step; return True on success."""
    step_id = step["id"]
    label   = step["label"]
    script  = step["script"]

    # Check required inputs
    missing = [f for f in step["requires"] if not Path(f).exists()]
    if missing:
        warn(f"[{step_id}] Skipping '{label}' — missing inputs: {missing}")
        return False

    if step.get("note"):
        info(f"[{step_id}] Note: {step['note']}")

    if dry_run:
        info(f"[{step_id}] DRY RUN: would execute {script}")
        return True

    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}[{step_id}] {label}{RESET}")
    print(f"{'='*60}")

    t_start = time.perf_counter()
    result  = subprocess.run([sys.executable, script],
                             capture_output=False, text=True)
    elapsed = time.perf_counter() - t_start

    if result.returncode == 0:
        ok(f"[{step_id}] Completed in {elapsed:.1f} s")
        return True
    else:
        err(f"[{step_id}] FAILED after {elapsed:.1f} s (exit code {result.returncode})")
        return False


# --- Main ---------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="BlueSky Political Analysis Pipeline")
    parser.add_argument("--from",   dest="from_step",  default=None,
                        help="Start from this step ID (e.g. 04)")
    parser.add_argument("--only",   dest="only_step",  default=None,
                        help="Run only this step ID")
    parser.add_argument("--skip",   dest="skip_steps", default="",
                        help="Comma-separated step IDs to skip (e.g. 05,05b)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be run without executing")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}  BlueSky Turkish Political Feed Analysis Pipeline{RESET}")
    print(f"{BOLD}{'='*60}{RESET}\n")

    # System checks
    check_python_version()
    check_env_file()
    check_data_file()
    has_bert = check_turkishbertweet()
    if not has_bert:
        info("TurkishBERTweet not found. Clone it or steps 05/05c will fail.")
        info("  git clone https://github.com/ViralLab/TurkishBERTweet.git")

    # Determine which steps to run
    skip_ids: set[str] = set(args.skip_steps.split(",")) - {""} if args.skip_steps else set()
    # NOTE: 05 and 05c are NOT auto-skipped even without TurkishBERTweet.
    # They are marked optional=True so the pipeline won't abort on failure.

    steps_to_run = STEPS

    if args.only_step:
        steps_to_run = [s for s in STEPS if s["id"] == args.only_step]
        if not steps_to_run:
            err(f"Unknown step ID: {args.only_step}")
            sys.exit(1)
    elif args.from_step:
        ids  = [s["id"] for s in STEPS]
        if args.from_step not in ids:
            err(f"Unknown step ID: {args.from_step}")
            sys.exit(1)
        idx          = ids.index(args.from_step)
        steps_to_run = STEPS[idx:]

    # Execute
    results: dict[str, bool] = {}
    pipeline_start = time.perf_counter()

    for step in steps_to_run:
        if step["id"] in skip_ids:
            warn(f"[{step['id']}] Skipping (--skip)")
            results[step["id"]] = None
            continue
        success = run_step(step, dry_run=args.dry_run)
        results[step["id"]] = success
        if not success and not step.get("optional"):
            err(f"Non-optional step {step['id']} failed — aborting pipeline.")
            break

    # Summary
    total_elapsed = time.perf_counter() - pipeline_start
    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}  Pipeline Summary  ({total_elapsed:.1f} s total){RESET}")
    print(f"{'='*60}")
    for step in steps_to_run:
        sid    = step["id"]
        status = results.get(sid)
        if status is True:
            label = f"{GREEN}PASS{RESET}"
        elif status is False:
            label = f"{RED}FAIL{RESET}"
        else:
            label = f"{YELLOW}SKIP{RESET}"
        print(f"  [{sid:>3}] {label}  {step['label']}")

    all_ok = all(v is True or v is None for v in results.values())
    print()
    if all_ok:
        ok("All steps completed successfully.")
    else:
        err("One or more steps failed. Check logs above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
