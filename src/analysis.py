"""
src/analysis.py
===============
Statistical and time-series analysis on top of the cleaned data.

Responsibilities
----------------
1. Wave detection  — uses scipy.signal.find_peaks on India's smoothed new cases
                     to label pandemic wave numbers.
2. Correlation     — Pearson + Spearman between vaccination_rate and
                     case_fatality_rate across country-level summary rows.
3. Risk scoring    — composite normalised score per country; exported to CSV.

Outputs (written to data/processed/analysis/)
--------------
  - india_with_waves.csv        India time-series with wave_number column
  - correlation_matrix.csv      Correlation coefficients for key metrics
  - risk_scores.csv             Country risk ranking table
"""

import logging
import os
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from scipy.signal import find_peaks
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
load_dotenv()

PROCESSED_DIR = Path(os.getenv("PROCESSED_DATA_DIR", "data/processed"))
ANALYSIS_DIR  = PROCESSED_DIR / "analysis"

INDIA_FILE   = PROCESSED_DIR / "india_covid.csv"
SUMMARY_FILE = PROCESSED_DIR / "country_summary.csv"

# Wave detection parameters (tuned for COVID-19 national data)
PEAK_DISTANCE   = 30    # minimum days between two peaks
PEAK_PROMINENCE = 5_000 # min vertical prominence in new_cases_smoothed units

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
# 1. Wave Detection
# ---------------------------------------------------------------------------

def detect_waves(india_df: pd.DataFrame) -> pd.DataFrame:
    """
    Identify pandemic waves in India's time-series by locating local peaks in
    the 7-day smoothed new cases curve.

    Algorithm
    ---------
    • scipy.signal.find_peaks detects peak indices where the signal rises and
      falls by at least `prominence` counts and the next peak is at least
      `distance` days away.
    • Each row between two consecutive peaks is assigned the same wave_number.
    • Rows before the first peak are wave 1; rows after the last peak belong
      to the final detected wave.

    Parameters
    ----------
    india_df : Cleaned India time-series DataFrame (sorted by date).

    Returns
    -------
    DataFrame with a new integer column `wave_number` (1-indexed).
    """
    df = india_df.copy().sort_values("date").reset_index(drop=True)

    # Prefer smoothed; fall back to raw new_cases if smoothed column absent
    signal_col = (
        "new_cases_smoothed" if "new_cases_smoothed" in df.columns
        else "new_cases"
    )

    signal = df[signal_col].fillna(0).values

    peak_indices, properties = find_peaks(
        signal,
        distance=PEAK_DISTANCE,
        prominence=PEAK_PROMINENCE,
    )

    log.info(
        "India wave detection: found %s peaks at indices %s",
        len(peak_indices), peak_indices.tolist(),
    )
    if len(peak_indices) > 0:
        for i, idx in enumerate(peak_indices, start=1):
            log.info(
                "  Wave %d peak: date=%s  smoothed_cases=%.0f",
                i, df.loc[idx, "date"].date(), signal[idx],
            )

    # Assign wave number to every row
    # Rows up to (and including) peak_i → wave i
    # Rows after the last peak → wave len(peaks)
    wave_number = np.ones(len(df), dtype=int)          # everything starts as wave 1

    if len(peak_indices) > 0:
        # Build boundary array: [0, peak1, peak2, ..., end]
        boundaries = np.concatenate([[0], peak_indices, [len(df)]])
        for wave_idx in range(len(boundaries) - 1):
            start = boundaries[wave_idx]
            end   = boundaries[wave_idx + 1]
            # wave_idx 0 → wave 1, wave_idx 1 → wave 2, etc.
            wave_number[start:end] = wave_idx + 1
        # Rows after the final peak also belong to the last wave
        wave_number[peak_indices[-1]:] = len(peak_indices)

    df["wave_number"] = wave_number
    log.info("Wave numbers assigned. Unique waves: %s", df["wave_number"].nunique())
    return df


# ---------------------------------------------------------------------------
# 2. Correlation Analysis
# ---------------------------------------------------------------------------

def compute_correlations(summary_df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute Pearson and Spearman correlations between key country-level metrics.

    Metrics included in the correlation matrix:
      - vaccination_rate
      - case_fatality_rate
      - mortality_rate_per_million  (if available)
      - total_cases_per_million     (if available)
      - gdp_per_capita
      - median_age
      - human_development_index
      - life_expectancy

    Returns
    -------
    pd.DataFrame with a multi-index of (metric, correlation_type) and
    each metric as a column.
    """
    candidate_cols = [
        "vaccination_rate", "case_fatality_rate",
        "mortality_rate_per_million", "total_cases_per_million",
        "gdp_per_capita", "median_age",
        "human_development_index", "life_expectancy",
    ]
    available = [c for c in candidate_cols if c in summary_df.columns]
    numeric   = summary_df[available].apply(pd.to_numeric, errors="coerce")

    pearson  = numeric.corr(method="pearson")
    spearman = numeric.corr(method="spearman")

    # Log the most actionable pair
    if "vaccination_rate" in pearson.columns and "case_fatality_rate" in pearson.columns:
        p_val = pearson.loc["vaccination_rate", "case_fatality_rate"]
        s_val = spearman.loc["vaccination_rate", "case_fatality_rate"]
        log.info(
            "Vaccination Rate vs CFR  →  Pearson r=%.4f | Spearman ρ=%.4f",
            p_val, s_val,
        )

    # Concatenate both matrices with a label column
    pearson["correlation_type"]  = "pearson"
    spearman["correlation_type"] = "spearman"
    combined = pd.concat([pearson, spearman], ignore_index=False)
    combined.index.name = "metric"
    combined.reset_index(inplace=True)

    return combined


def run_scipy_correlation_test(summary_df: pd.DataFrame) -> None:
    """
    Run a formal scipy Pearson and Spearman test on the key pair
    (vaccination_rate vs case_fatality_rate) and log p-values.
    """
    pair_df = summary_df[["vaccination_rate", "case_fatality_rate"]].dropna()
    if len(pair_df) < 10:
        log.warning("Too few countries with complete data for correlation test.")
        return

    x = pair_df["vaccination_rate"].values
    y = pair_df["case_fatality_rate"].values

    p_r, p_p = stats.pearsonr(x, y)
    s_r, s_p = stats.spearmanr(x, y)

    log.info("Scipy Pearson  r=%.4f  p=%.6f", p_r, p_p)
    log.info("Scipy Spearman ρ=%.4f  p=%.6f", s_r, s_p)
    if p_p < 0.05:
        direction = "negative" if p_r < 0 else "positive"
        log.info(
            "⭢ Statistically significant %s correlation between "
            "vaccination_rate and case_fatality_rate (p < 0.05).", direction
        )


# ---------------------------------------------------------------------------
# 3. Country Risk Scoring
# ---------------------------------------------------------------------------

def compute_risk_scores(summary_df: pd.DataFrame) -> pd.DataFrame:
    """
    Build a composite risk score for each country using three normalised
    sub-scores (all scaled 0–1, where 1 = highest risk):

      score_cases   = normalised total_cases_per_million
      score_deaths  = normalised mortality_rate_per_million
      score_unvax   = 1 - normalised vaccination_rate
                      (lower vaccination → higher risk)

    composite_risk_score = mean(score_cases, score_deaths, score_unvax)

    Countries with missing values in any sub-score are excluded.

    Returns
    -------
    DataFrame sorted by composite_risk_score descending, with a rank column.
    """
    df = summary_df.copy()

    needed = {
        "cases_col": "total_cases_per_million",
        "deaths_col": "mortality_rate_per_million",
        "vax_col":   "vaccination_rate",
    }

    # Fallbacks if the preferred column is absent
    if "total_cases_per_million" not in df.columns and "total_cases" in df.columns:
        df["total_cases_per_million"] = df["total_cases"] / df["population"] * 1_000_000

    if "mortality_rate_per_million" not in df.columns and "total_deaths" in df.columns:
        df["mortality_rate_per_million"] = df["total_deaths"] / df["population"] * 1_000_000

    # Drop rows where any risk-relevant column is NaN
    risk_cols = [
        "total_cases_per_million",
        "mortality_rate_per_million",
        "vaccination_rate",
        "location", "continent",
    ]
    available_risk = [c for c in risk_cols if c in df.columns]
    df = df[available_risk].dropna(
        subset=["total_cases_per_million", "mortality_rate_per_million", "vaccination_rate"]
    ).copy()

    def min_max(series: pd.Series) -> pd.Series:
        """Normalise a series to [0, 1]; returns 0 if all values are equal."""
        lo, hi = series.min(), series.max()
        if hi == lo:
            return pd.Series(0.0, index=series.index)
        return (series - lo) / (hi - lo)

    df["score_cases"]  = min_max(df["total_cases_per_million"])
    df["score_deaths"] = min_max(df["mortality_rate_per_million"])
    df["score_unvax"]  = 1 - min_max(df["vaccination_rate"])  # invert: low vax = high risk

    df["composite_risk_score"] = df[["score_cases", "score_deaths", "score_unvax"]].mean(axis=1)
    df = df.sort_values("composite_risk_score", ascending=False).reset_index(drop=True)
    df.insert(0, "risk_rank", df.index + 1)

    log.info("Risk scores computed for %s countries.", len(df))
    log.info("Top 5 highest-risk countries:\n%s",
             df[["risk_rank", "location", "composite_risk_score"]].head(5).to_string(index=False))

    return df


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------

def _export(df: pd.DataFrame, filename: str) -> Path:
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    path = ANALYSIS_DIR / filename
    df.to_csv(path, index=False)
    log.info("Exported → %s  (%s rows)", path, f"{len(df):,}")
    return path


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_analysis_pipeline() -> None:
    """
    Load cleaned files, execute all analyses, and export results.
    """
    # ── Load inputs ───────────────────────────────────────────────────────
    if not INDIA_FILE.exists():
        raise FileNotFoundError(
            f"India CSV not found at {INDIA_FILE}. "
            "Run data_cleaning.py first."
        )
    if not SUMMARY_FILE.exists():
        raise FileNotFoundError(
            f"Country summary CSV not found at {SUMMARY_FILE}. "
            "Run data_cleaning.py first."
        )

    india_df   = pd.read_csv(INDIA_FILE,   parse_dates=["date"])
    summary_df = pd.read_csv(SUMMARY_FILE, low_memory=False)

    # ── 1. Wave detection ──────────────────────────────────────────────────
    log.info("--- Step 1: Wave Detection ---")
    india_waves = detect_waves(india_df)
    _export(india_waves, "india_with_waves.csv")

    # ── 2. Correlation analysis ────────────────────────────────────────────
    log.info("--- Step 2: Correlation Analysis ---")
    corr_matrix = compute_correlations(summary_df)
    run_scipy_correlation_test(summary_df)
    _export(corr_matrix, "correlation_matrix.csv")

    # ── 3. Risk scoring ────────────────────────────────────────────────────
    log.info("--- Step 3: Country Risk Scoring ---")
    risk_df = compute_risk_scores(summary_df)
    _export(risk_df, "risk_scores.csv")

    log.info("=== Analysis pipeline complete. Outputs in: %s ===", ANALYSIS_DIR)


# ---------------------------------------------------------------------------
# Script entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    run_analysis_pipeline()
