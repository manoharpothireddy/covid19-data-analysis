"""
src/data_cleaning.py
====================
Cleans and transforms the raw OWID COVID-19 CSV into three export files:

  1. data/processed/covid_cleaned.csv   — global cleaned time-series
  2. data/processed/india_covid.csv     — India-only slice
  3. data/processed/country_summary.csv — latest-row aggregate per country

Pipeline steps
--------------
  1. Load raw CSV with correct dtypes
  2. Drop OWID aggregate rows (iso_code starts with "OWID_")
  3. Parse date column → datetime64
  4. Sort by (location, date) so rolling / ffill work correctly
  5. Forward-fill cumulative columns per country
  6. Zero-fill daily new_* columns
  7. Cast all numeric columns to float64
  8. Compute derived metrics
  9. Compute 7-day and 14-day rolling averages per country
 10. Extract date-part columns (year, month, week, day_of_week)
 11. Export the three output files
"""

import logging
import os
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
load_dotenv()

RAW_DIR       = Path(os.getenv("RAW_DATA_DIR",       "data/raw"))
PROCESSED_DIR = Path(os.getenv("PROCESSED_DATA_DIR", "data/processed"))

RAW_FILE      = RAW_DIR / "owid-covid-data.csv"
CLEANED_FILE  = PROCESSED_DIR / "covid_cleaned.csv"
INDIA_FILE    = PROCESSED_DIR / "india_covid.csv"
SUMMARY_FILE  = PROCESSED_DIR / "country_summary.csv"

# ---------------------------------------------------------------------------
# Column selections
# ---------------------------------------------------------------------------

# Columns we keep from the raw file (subset of the full OWID schema)
COLUMNS_TO_KEEP = [
    "iso_code", "continent", "location", "date",
    # Cases
    "total_cases", "new_cases", "new_cases_smoothed",
    "total_cases_per_million", "new_cases_per_million",
    # Deaths
    "total_deaths", "new_deaths", "new_deaths_smoothed",
    "total_deaths_per_million", "new_deaths_per_million",
    # Testing
    "total_tests", "new_tests", "positive_rate",
    # Hospitalisation (not all countries report; kept as optional)
    "icu_patients", "hosp_patients",
    # Vaccinations
    "total_vaccinations", "people_vaccinated",
    "people_fully_vaccinated", "total_boosters",
    "new_vaccinations", "new_vaccinations_smoothed",
    # Demographics & socio-economic (static per country)
    "population", "population_density", "median_age",
    "aged_65_older", "gdp_per_capita",
    "cardiovasc_death_rate", "diabetes_prevalence",
    "life_expectancy", "human_development_index",
    # Policy
    "stringency_index",
    # Reproduction number
    "reproduction_rate",
]

# Cumulative columns that should be forward-filled (never decrease)
CUMULATIVE_COLS = [
    "total_cases", "total_deaths",
    "total_tests", "total_vaccinations",
    "people_vaccinated", "people_fully_vaccinated", "total_boosters",
]

# Daily new-event columns that default to 0 when missing
DAILY_NEW_COLS = [
    "new_cases", "new_deaths",
    "new_tests", "new_vaccinations",
]

# All columns that should be numeric (excluding identifiers and date)
NUMERIC_COLS = [c for c in COLUMNS_TO_KEEP
                if c not in ("iso_code", "continent", "location", "date")]

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Step functions
# ---------------------------------------------------------------------------

def load_raw(path: Path = RAW_FILE) -> pd.DataFrame:
    """Load the raw OWID CSV keeping only the columns we need."""
    log.info("Loading raw data from: %s", path)

    # Read with low_memory=False to avoid mixed-type warnings
    df = pd.read_csv(path, low_memory=False)

    # Keep only the columns that actually exist in this version of the file
    available = [c for c in COLUMNS_TO_KEEP if c in df.columns]
    missing   = set(COLUMNS_TO_KEEP) - set(available)
    if missing:
        log.warning("Columns not found in raw file (will be skipped): %s", missing)

    df = df[available].copy()
    log.info("Raw shape after column filter: %s rows × %s cols", *df.shape)
    return df


def drop_aggregate_rows(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove OWID-defined aggregate rows whose iso_code starts with 'OWID_'.
    These represent continents, income groups, and the world total — not
    individual countries — and would inflate all aggregations.
    """
    before = len(df)
    df = df[~df["iso_code"].str.startswith("OWID_", na=False)].copy()
    log.info(
        "Dropped %s aggregate rows (OWID_ prefix). Remaining: %s",
        before - len(df), len(df),
    )
    return df


def parse_dates(df: pd.DataFrame) -> pd.DataFrame:
    """Convert the date column from string to datetime64[ns]."""
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    nat_count  = df["date"].isna().sum()
    if nat_count:
        log.warning("Dropped %s rows with un-parseable dates.", nat_count)
        df = df.dropna(subset=["date"])
    return df


def sort_dataset(df: pd.DataFrame) -> pd.DataFrame:
    """
    Sort by (location, date) ascending.
    This is CRITICAL: forward-fill and rolling windows are order-dependent.
    """
    df = df.sort_values(["location", "date"]).reset_index(drop=True)
    log.info("Dataset sorted by (location, date).")
    return df


def cast_numeric_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Coerce every numeric column to float64.
    Raw CSV may store numbers as strings (e.g. '1,234' or '').
    pd.to_numeric with errors='coerce' turns un-parseable values to NaN.
    """
    for col in NUMERIC_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    log.info("All numeric columns cast to float64.")
    return df


def forward_fill_cumulative(df: pd.DataFrame) -> pd.DataFrame:
    """
    Within each country group, forward-fill cumulative columns.
    Cumulative metrics should never decrease — if a day is missing it means
    no new report was published, not that numbers went to zero.
    groupby(..., group_keys=False) preserves the original index order.
    """
    existing_cum = [c for c in CUMULATIVE_COLS if c in df.columns]
    df[existing_cum] = (
        df.groupby("location", group_keys=False)[existing_cum]
        .apply(lambda g: g.ffill())
    )
    log.info("Forward-filled %s cumulative columns.", len(existing_cum))
    return df


def zero_fill_daily(df: pd.DataFrame) -> pd.DataFrame:
    """
    Replace NaN in daily new-event columns with 0.
    A missing daily report is treated as no new events that day.
    """
    existing_daily = [c for c in DAILY_NEW_COLS if c in df.columns]
    df[existing_daily] = df[existing_daily].fillna(0)
    log.info("Zero-filled %s daily columns.", len(existing_daily))
    return df


def compute_derived_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Create four derived metrics using NumPy-aware safe division.

    - case_fatality_rate        : deaths / cases (proportion, not %)
    - vaccination_rate          : fully vaccinated / population * 100
    - tests_per_case            : tests / cases
    - mortality_rate_per_million: deaths / population * 1 000 000
    """
    # np.where avoids division-by-zero and returns NaN when denominator is 0
    df["case_fatality_rate"] = np.where(
        df["total_cases"] > 0,
        df["total_deaths"] / df["total_cases"],
        np.nan,
    )

    df["vaccination_rate"] = np.where(
        df["population"] > 0,
        df["people_fully_vaccinated"] / df["population"] * 100,
        np.nan,
    )

    df["tests_per_case"] = np.where(
        (df["total_cases"] > 0) & df["total_tests"].notna(),
        df["total_tests"] / df["total_cases"],
        np.nan,
    )

    df["mortality_rate_per_million"] = np.where(
        df["population"] > 0,
        df["total_deaths"] / df["population"] * 1_000_000,
        np.nan,
    )

    log.info("Derived metrics computed: case_fatality_rate, vaccination_rate, "
             "tests_per_case, mortality_rate_per_million.")
    return df


def compute_rolling_averages(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute 7-day and 14-day rolling means of new_cases and new_deaths
    within each country group.

    We use min_periods=1 so countries with sparse early data still get a value
    (rather than NaN) — this prevents gaps in dashboard charts.
    """
    roll_cols = {
        "new_cases":  ["rolling_7day_cases",  "rolling_14day_cases"],
        "new_deaths": ["rolling_7day_deaths", "rolling_14day_deaths"],
    }

    for src_col, (col7, col14) in roll_cols.items():
        if src_col not in df.columns:
            continue
        grouped = df.groupby("location", group_keys=False)[src_col]
        df[col7]  = grouped.transform(lambda s: s.rolling(7,  min_periods=1).mean())
        df[col14] = grouped.transform(lambda s: s.rolling(14, min_periods=1).mean())

    log.info("Rolling averages computed (7-day and 14-day) for new_cases and new_deaths.")
    return df


def extract_date_parts(df: pd.DataFrame) -> pd.DataFrame:
    """Extract year, month, ISO week number, and day-of-week (0=Mon, 6=Sun)."""
    df["year"]        = df["date"].dt.year
    df["month"]       = df["date"].dt.month
    df["week"]        = df["date"].dt.isocalendar().week.astype("int64")
    df["day_of_week"] = df["date"].dt.dayofweek   # 0 = Monday
    log.info("Date parts extracted: year, month, week, day_of_week.")
    return df


def validate_cleaned_data(df: pd.DataFrame) -> None:
    """
    Quick sanity checks before exporting.
    Logs warnings — does NOT raise — so the pipeline continues.
    """
    cfr_bad = (df["case_fatality_rate"] > 1).sum()
    if cfr_bad:
        log.warning("%s rows have case_fatality_rate > 1 (>100%%) — investigate.", cfr_bad)

    vax_bad = (df["vaccination_rate"] > 150).sum()
    if vax_bad:
        log.warning(
            "%s rows have vaccination_rate > 150%% (boosters can exceed 100%% "
            "but 150%% suggests a data issue).", vax_bad
        )

    neg_cases = (df["new_cases"] < 0).sum()
    if neg_cases:
        log.warning(
            "%s rows have negative new_cases (backlog corrections in source data).",
            neg_cases,
        )


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------

def export_global(df: pd.DataFrame, path: Path = CLEANED_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    log.info("Exported global cleaned CSV → %s  (%s rows)", path, f"{len(df):,}")


def export_india(df: pd.DataFrame, path: Path = INDIA_FILE) -> None:
    india = df[df["location"] == "India"].copy()
    if india.empty:
        log.warning("No rows found for 'India' — india_covid.csv will be empty.")
    path.parent.mkdir(parents=True, exist_ok=True)
    india.to_csv(path, index=False)
    log.info("Exported India CSV → %s  (%s rows)", path, f"{len(india):,}")


def export_country_summary(df: pd.DataFrame, path: Path = SUMMARY_FILE) -> None:
    """
    One row per country: the latest record available for that country.
    For cumulative KPIs (total_cases, total_deaths, total_vaccinations) this
    gives the correct running total because cumulative columns are monotonic.
    NEVER aggregate cumulative columns with SUM across time.
    """
    summary = (
        df.sort_values("date")
        .groupby("location", as_index=False)
        .last()                           # keeps the most recent date's row
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(path, index=False)
    log.info(
        "Exported country summary CSV → %s  (%s countries)",
        path, f"{len(summary):,}",
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_cleaning_pipeline() -> pd.DataFrame:
    """
    Execute the full cleaning pipeline in sequence.
    Returns the cleaned global DataFrame (also written to disk).
    """
    df = load_raw()
    df = drop_aggregate_rows(df)
    df = parse_dates(df)
    df = sort_dataset(df)
    df = cast_numeric_columns(df)
    df = forward_fill_cumulative(df)
    df = zero_fill_daily(df)
    df = compute_derived_metrics(df)
    df = compute_rolling_averages(df)
    df = extract_date_parts(df)

    validate_cleaned_data(df)

    export_global(df)
    export_india(df)
    export_country_summary(df)

    log.info("=== Data cleaning complete. Final shape: %s rows × %s cols ===",
             *df.shape)
    return df


# ---------------------------------------------------------------------------
# Script entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    run_cleaning_pipeline()
