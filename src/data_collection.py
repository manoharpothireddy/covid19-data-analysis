"""
src/data_collection.py
======================
Downloads the OWID COVID-19 dataset from GitHub with:
  - tqdm progress bar
  - 3-attempt retry with exponential back-off
  - HTTP 200 + file-size validation
  - Row count and date-range summary after save
"""

import os
import time
import logging
import requests
from pathlib import Path
from tqdm import tqdm
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
load_dotenv()                                        # pull values from .env

OWID_URL: str = os.getenv(
    "OWID_CSV_URL",
    "https://raw.githubusercontent.com/owid/covid-19-data/master/public/data/owid-covid-data.csv",
)
RAW_DIR: Path  = Path(os.getenv("RAW_DATA_DIR", "data/raw"))
OUTPUT_FILE: Path = RAW_DIR / "owid-covid-data.csv"

MIN_FILE_SIZE_BYTES: int = 1 * 1024 * 1024          # 1 MB guard-rail
MAX_RETRIES:         int = 3
BACKOFF_BASE_SECS:   int = 5                         # wait 5 → 10 → 20 s

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
# Helpers
# ---------------------------------------------------------------------------

def _attempt_download(url: str, dest: Path) -> None:
    """
    Stream-download *url* to *dest* with a tqdm progress bar.
    Raises requests.HTTPError on non-200 status.
    """
    with requests.get(url, stream=True, timeout=60) as resp:
        resp.raise_for_status()                      # raises on 4xx / 5xx

        total_bytes = int(resp.headers.get("Content-Length", 0))
        chunk_size  = 8 * 1024                       # 8 KB chunks

        dest.parent.mkdir(parents=True, exist_ok=True)

        with open(dest, "wb") as fh, tqdm(
            desc=f"Downloading {dest.name}",
            total=total_bytes,
            unit="B",
            unit_scale=True,
            unit_divisor=1024,
            dynamic_ncols=True,
        ) as pbar:
            for chunk in resp.iter_content(chunk_size=chunk_size):
                if chunk:                            # filter keep-alive chunks
                    fh.write(chunk)
                    pbar.update(len(chunk))


def _validate_file(path: Path) -> None:
    """
    Ensure the file exists and is larger than MIN_FILE_SIZE_BYTES.
    Raises FileNotFoundError or ValueError if validation fails.
    """
    if not path.exists():
        raise FileNotFoundError(f"Expected file not found: {path}")

    size = path.stat().st_size
    if size < MIN_FILE_SIZE_BYTES:
        raise ValueError(
            f"Downloaded file is suspiciously small ({size:,} bytes < "
            f"{MIN_FILE_SIZE_BYTES:,} bytes). Check the URL or network."
        )
    log.info("File validation passed — size: %s bytes", f"{size:,}")


def _log_dataset_summary(path: Path) -> None:
    """
    Read the saved CSV and print row count and date range as a quick sanity
    check.  Import pandas lazily here so collection works even without the
    full env.
    """
    try:
        import pandas as pd

        df = pd.read_csv(path, usecols=["location", "date"], low_memory=False)
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

        log.info("Dataset summary:")
        log.info("  ├─ Total rows   : %s", f"{len(df):,}")
        log.info("  ├─ Countries    : %s", df["location"].nunique())
        log.info("  ├─ Earliest date: %s", df["date"].min().date())
        log.info("  └─ Latest date  : %s", df["date"].max().date())
    except Exception as exc:                         # non-fatal — just a summary
        log.warning("Could not compute dataset summary: %s", exc)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def download_owid_data(
    url:  str  = OWID_URL,
    dest: Path = OUTPUT_FILE,
) -> Path:
    """
    Download the OWID COVID-19 CSV with retry logic and progress bar.

    Parameters
    ----------
    url  : Download URL (defaults to OWID_CSV_URL from .env)
    dest : Local destination path (defaults to data/raw/owid-covid-data.csv)

    Returns
    -------
    Path : Path of the saved file.

    Raises
    ------
    RuntimeError if all retry attempts fail.
    """
    log.info("Starting download from:\n  %s", url)

    last_error: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            log.info("Attempt %d / %d …", attempt, MAX_RETRIES)
            _attempt_download(url, dest)
            _validate_file(dest)
            _log_dataset_summary(dest)
            log.info("Download complete → %s", dest.resolve())
            return dest

        except (requests.RequestException, ValueError, FileNotFoundError) as exc:
            last_error = exc
            wait = BACKOFF_BASE_SECS * (2 ** (attempt - 1))  # 5, 10, 20 s
            log.warning(
                "Attempt %d failed: %s. Retrying in %d s …",
                attempt, exc, wait,
            )
            if attempt < MAX_RETRIES:
                time.sleep(wait)

    # All retries exhausted
    log.error(
        "All %d download attempts failed. Last error: %s",
        MAX_RETRIES, last_error,
    )
    log.error(
        "Fallback: manually place owid-covid-data.csv in '%s' and re-run.",
        RAW_DIR.resolve(),
    )
    raise RuntimeError(
        f"Failed to download OWID data after {MAX_RETRIES} attempts."
    ) from last_error


# ---------------------------------------------------------------------------
# Script entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    download_owid_data()
