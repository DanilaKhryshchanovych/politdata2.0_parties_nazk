"""
Central configuration for the politdata v2 pipeline.

All paths are absolute, anchored at the repo root, so the pipeline runs the same
whether invoked from repo root, from `src/`, or by the scheduler.
"""
from pathlib import Path

# --- Paths ---------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"            # one JSON per report (git-ignored)
STATE_DIR = DATA_DIR / "state"       # download state + error ids (git-ignored)
EXCEL_DIR = DATA_DIR / "excel_tables"
PARQUET_DIR = DATA_DIR / "parquet"

# Raw artefacts written by the downloader
PARTIES_FILE = RAW_DIR / "_parties.json"        # party directory (central + nested offices)
STATE_FILE = STATE_DIR / "download_state.json"  # report_id -> freshness fingerprint
ERROR_IDS_FILE = STATE_DIR / "error_report_ids.txt"

# --- API -----------------------------------------------------------------
BASE_URL = "https://politdata.nazk.gov.ua/api/v2"

# Response wrappers observed in Phase 0:
#   list endpoints  -> {"code": .., "results": {"list": [...]}}
#   detail endpoint -> {"code": .., "results": { ...report... }}

# POST body shape for every list/section endpoint.
DEFAULT_PAGE_SIZE = 500      # rows per page for paginated POST endpoints
PARTIES_PAGE_SIZE = 1000     # party directory is small; one big page is enough
REPORTS_PAGE_SIZE = 300      # reports per party

# --- HTTP behaviour ------------------------------------------------------
REQUEST_TIMEOUT = 40         # seconds per request
SLEEP_BETWEEN = 0.4          # seconds between requests (politeness / rate-limit)
MAX_RETRIES = 4              # urllib3 retries on 429/5xx, with backoff
BACKOFF_FACTOR = 1.5         # 0, 1.5, 3.0, 6.0s ... between retries
MAX_PAGES = 1000             # hard stop against runaway pagination loops

USER_AGENT = "politdata-v2-pipeline/0.1 (research; danilakk14@gmail.com)"
