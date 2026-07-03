"""
run.py
======
Master pipeline orchestrator for the COVID-19 Data Analysis project.

Execution order
---------------
  Stage 1 → Data Collection  (src/data_collection.py)
  Stage 2 → Data Cleaning    (src/data_cleaning.py)
  Stage 3 → Analysis         (src/analysis.py)
  Stage 4 → Database Load    (src/database.py)

Flags
-----
  --skip-download   Skip Stage 1 (use cached data/raw/owid-covid-data.csv)
  --skip-cleaning   Skip Stage 2 (use cached data/processed/*.csv)
  --skip-analysis   Skip Stage 3
  --skip-db         Skip Stage 4 (useful if PostgreSQL is unavailable)
  --reload          Drop and recreate all DB tables before loading (Stage 4)

Usage examples
--------------
  python run.py                          # full pipeline
  python run.py --skip-download          # skip download, clean + load
  python run.py --skip-download --reload # reload DB from cached CSVs
  python run.py --skip-db                # clean + analyse, no DB
"""

import argparse
import logging
import sys
import time
from datetime import datetime

# ---------------------------------------------------------------------------
# Logging — configured before any module import so all loggers inherit it
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("run")


# ---------------------------------------------------------------------------
# Stage runner
# ---------------------------------------------------------------------------

def run_stage(name: str, fn, *args, **kwargs):
    """
    Execute a pipeline stage function, print timing, and catch errors.

    Returns
    -------
    (success: bool, result: any)
      success is False if an exception was raised.
      result  is the function's return value, or None on failure.
    """
    separator = "─" * 60
    log.info(separator)
    log.info("▶  STAGE START : %s", name)
    log.info("   Time        : %s", datetime.now().strftime("%H:%M:%S"))
    log.info(separator)

    t0 = time.perf_counter()
    try:
        result = fn(*args, **kwargs)
        elapsed = time.perf_counter() - t0
        log.info("✔  STAGE DONE  : %s  (%.1f s)", name, elapsed)
        return True, result

    except Exception as exc:
        elapsed = time.perf_counter() - t0
        log.error("✘  STAGE FAILED: %s  (%.1f s)", name, elapsed)
        log.error("   Error       : %s", exc, exc_info=True)
        return False, None


# ---------------------------------------------------------------------------
# CLI argument parsing
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="COVID-19 Data Analysis Pipeline — Master Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run.py                          Run the full pipeline
  python run.py --skip-download          Use cached raw CSV, re-clean and reload
  python run.py --skip-download --reload Drop DB tables and reload from cache
  python run.py --skip-db                Clean + analyse only (no PostgreSQL needed)
        """,
    )
    parser.add_argument(
        "--skip-download", action="store_true",
        help="Skip Stage 1 (data download). Requires owid-covid-data.csv to exist.",
    )
    parser.add_argument(
        "--skip-cleaning", action="store_true",
        help="Skip Stage 2 (cleaning). Requires processed CSVs to exist.",
    )
    parser.add_argument(
        "--skip-analysis", action="store_true",
        help="Skip Stage 3 (wave detection, correlation, risk scoring).",
    )
    parser.add_argument(
        "--skip-db", action="store_true",
        help="Skip Stage 4 (PostgreSQL load). Useful if DB is not available.",
    )
    parser.add_argument(
        "--reload", action="store_true",
        help="(Stage 4 only) Drop and recreate all tables before loading.",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------

def check_raw_file_exists() -> bool:
    """Return True if the cached raw CSV is present and non-empty."""
    from pathlib import Path
    raw = Path("data/raw/owid-covid-data.csv")
    if raw.exists() and raw.stat().st_size > 1_024 * 1_024:   # > 1 MB
        log.info("Cached raw file found: %s  (%s MB)",
                 raw, f"{raw.stat().st_size / 1_048_576:.1f}")
        return True
    log.error(
        "Raw file missing or too small: %s\n"
        "Remove --skip-download flag or place the file manually.", raw
    )
    return False


def check_processed_files_exist() -> bool:
    """Return True if all three processed CSVs exist."""
    from pathlib import Path
    needed = [
        "data/processed/covid_cleaned.csv",
        "data/processed/india_covid.csv",
        "data/processed/country_summary.csv",
    ]
    missing = [p for p in needed if not Path(p).exists()]
    if missing:
        log.error(
            "Processed files missing (remove --skip-cleaning to regenerate):\n  %s",
            "\n  ".join(missing),
        )
        return False
    log.info("All processed CSV files found.")
    return True


# ---------------------------------------------------------------------------
# Pipeline entry point
# ---------------------------------------------------------------------------

def main() -> int:
    """
    Run the pipeline.  Returns exit code (0 = success, 1 = at least one failure).
    """
    args        = parse_args()
    wall_start  = time.perf_counter()
    stage_results: dict[str, bool] = {}

    banner = """
╔══════════════════════════════════════════════════════════════╗
║       COVID-19 Data Analysis Pipeline — Starting             ║
╚══════════════════════════════════════════════════════════════╝"""
    print(banner)
    log.info("Run started at %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    log.info("Flags: skip-download=%s  skip-cleaning=%s  "
             "skip-analysis=%s  skip-db=%s  reload=%s",
             args.skip_download, args.skip_cleaning,
             args.skip_analysis, args.skip_db, args.reload)

    # ------------------------------------------------------------------
    # STAGE 1 — Data Collection
    # ------------------------------------------------------------------
    if args.skip_download:
        log.info("⏭  STAGE SKIPPED: Data Collection (--skip-download)")
        if not check_raw_file_exists():
            log.error("Cannot proceed without raw data. Exiting.")
            return 1
        stage_results["Data Collection"] = True
    else:
        from src.data_collection import download_owid_data
        ok, _ = run_stage("Data Collection", download_owid_data)
        stage_results["Data Collection"] = ok
        if not ok:
            log.warning(
                "Download failed. If a cached file exists you can re-run "
                "with --skip-download."
            )
            # Non-fatal: proceed only if cached file is present
            if not check_raw_file_exists():
                return 1

    # ------------------------------------------------------------------
    # STAGE 2 — Data Cleaning
    # ------------------------------------------------------------------
    if args.skip_cleaning:
        log.info("⏭  STAGE SKIPPED: Data Cleaning (--skip-cleaning)")
        if not check_processed_files_exist():
            return 1
        stage_results["Data Cleaning"] = True
    else:
        from src.data_cleaning import run_cleaning_pipeline
        ok, cleaned_df = run_stage("Data Cleaning", run_cleaning_pipeline)
        stage_results["Data Cleaning"] = ok
        if not ok:
            log.error("Cleaning failed. Cannot continue without cleaned data.")
            return 1

    # ------------------------------------------------------------------
    # STAGE 3 — Statistical Analysis
    # ------------------------------------------------------------------
    if args.skip_analysis:
        log.info("⏭  STAGE SKIPPED: Analysis (--skip-analysis)")
        stage_results["Analysis"] = True
    else:
        from src.analysis import run_analysis_pipeline
        ok, _ = run_stage("Analysis", run_analysis_pipeline)
        stage_results["Analysis"] = ok
        # Non-fatal: dashboard can still run without analysis outputs

    # ------------------------------------------------------------------
    # STAGE 4 — Database Load
    # ------------------------------------------------------------------
    if args.skip_db:
        log.info("⏭  STAGE SKIPPED: Database Load (--skip-db)")
        stage_results["Database Load"] = True
    else:
        from src.database import run_database_pipeline
        ok, _ = run_stage(
            "Database Load",
            run_database_pipeline,
            reload=args.reload,
        )
        stage_results["Database Load"] = ok
        if not ok:
            log.warning(
                "Database load failed. BI tools can still use CSV files in "
                "data/processed/. Re-run with --skip-db to bypass."
            )

    # ------------------------------------------------------------------
    # Summary report
    # ------------------------------------------------------------------
    wall_elapsed = time.perf_counter() - wall_start
    print()
    log.info("═" * 60)
    log.info("PIPELINE SUMMARY  (total time: %.1f s)", wall_elapsed)
    log.info("═" * 60)

    all_passed = True
    for stage, passed in stage_results.items():
        status = "✔ PASSED" if passed else "✘ FAILED"
        log.info("  %-25s %s", stage, status)
        if not passed:
            all_passed = False

    log.info("═" * 60)

    if all_passed:
        log.info("🎉 All stages completed successfully.")
        log.info("Next steps:")
        log.info("  • Explore: jupyter notebook notebooks/exploratory_analysis.ipynb")
        log.info("  • Connect Tableau/Power BI to PostgreSQL (host=localhost db=covid19_analysis)")
        log.info("  • Fallback CSVs for BI tools: data/processed/sql_results/")
    else:
        log.warning("⚠ One or more stages failed — see logs above for details.")

    return 0 if all_passed else 1


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sys.exit(main())
