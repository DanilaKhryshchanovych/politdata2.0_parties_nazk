"""
Thin HTTP client for the ПОЛІТДАТА API v2.

Responsibilities (Phase 1):
  * one requests.Session with retry/backoff on 429 and 5xx;
  * unwrap the two response shapes seen in Phase 0
    (`results.list` for lists, `results` for the report detail);
  * paginate POST endpoints transparently;
  * expose the three endpoints the downloader needs.

The client does NOT know about pipeline state or disk layout — that lives in
raw_store/downloader. It raises on hard failures so the caller can log the id.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Allow running as `python -m src.api_client` or importing from anywhere.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import settings  # noqa: E402


class ApiError(RuntimeError):
    """Raised when a request ultimately fails (after retries) or returns junk."""


class ApiClient:
    def __init__(
        self,
        base_url: str = settings.BASE_URL,
        sleep_between: float = settings.SLEEP_BETWEEN,
        timeout: int = settings.REQUEST_TIMEOUT,
    ):
        self.base_url = base_url.rstrip("/")
        self.sleep_between = sleep_between
        self.timeout = timeout
        self.session = self._build_session()

    @staticmethod
    def _build_session() -> requests.Session:
        session = requests.Session()
        session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": settings.USER_AGENT,
        })
        retry = Retry(
            total=settings.MAX_RETRIES,
            backoff_factor=settings.BACKOFF_FACTOR,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET", "POST"}),
            raise_on_status=False,
            respect_retry_after_header=True,
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    # --- low-level ------------------------------------------------------
    def _request(self, method: str, path: str, json_body: dict | None = None) -> Any:
        url = f"{self.base_url}{path}"
        try:
            resp = self.session.request(
                method, url, json=json_body, timeout=self.timeout
            )
        except requests.RequestException as exc:
            raise ApiError(f"{method} {path} failed: {exc}") from exc
        finally:
            # Politeness delay applies whether or not the call succeeded.
            time.sleep(self.sleep_between)

        if resp.status_code == 204 or not resp.text.strip():
            return None
        if resp.status_code >= 400:
            raise ApiError(f"{method} {path} -> HTTP {resp.status_code}")
        try:
            return resp.json()
        except ValueError as exc:
            raise ApiError(f"{method} {path} -> non-JSON response") from exc

    # --- unwrapping -----------------------------------------------------
    @staticmethod
    def unwrap_list(payload: Any) -> list[dict]:
        """`{"results": {"list": [...]}}` -> the list (empty list on anything else)."""
        if not isinstance(payload, dict):
            return []
        node = payload.get("results", payload)
        if isinstance(node, dict):
            rows = node.get("list")
            return rows if isinstance(rows, list) else []
        return node if isinstance(node, list) else []

    @staticmethod
    def unwrap_obj(payload: Any) -> dict | None:
        """`{"results": {...}}` -> the object (the report detail case)."""
        if not isinstance(payload, dict):
            return None
        node = payload.get("results", payload)
        return node if isinstance(node, dict) else None

    @staticmethod
    def _pager(page: int, size: int) -> dict:
        return {"filters": None, "order": None, "pager": {"page": page, "size": size}}

    def paged_post(self, path: str, size: int = settings.DEFAULT_PAGE_SIZE) -> list[dict]:
        """POST a list endpoint page by page until a short/empty page is returned."""
        out: list[dict] = []
        for page in range(1, settings.MAX_PAGES + 1):
            payload = self._request("POST", path, self._pager(page, size))
            rows = self.unwrap_list(payload)
            if not rows:
                break
            out.extend(rows)
            if len(rows) < size:
                break
        else:
            raise ApiError(f"pagination did not terminate for {path} (>{settings.MAX_PAGES} pages)")
        return out

    # --- endpoints the downloader uses ----------------------------------
    def get_parties(self) -> list[dict]:
        """All central parties; each carries nested `regional_offices`."""
        return self.paged_post("/parties", size=settings.PARTIES_PAGE_SIZE)

    def get_party_reports(self, party_id: str) -> list[dict]:
        """Reports filed by one party/office id."""
        return self.paged_post(f"/party/{party_id}/reports", size=settings.REPORTS_PAGE_SIZE)

    def get_report_detail(self, report_id: str) -> dict:
        """Full report with all sections nested (one GET replaces ~10 POSTs)."""
        payload = self._request("GET", f"/party/report/{report_id}")
        obj = self.unwrap_obj(payload)
        if obj is None:
            raise ApiError(f"empty/invalid detail for report {report_id}")
        return obj


if __name__ == "__main__":
    # Quick manual smoke check.
    client = ApiClient()
    parties = client.get_parties()
    print(f"parties: {len(parties)}")
    if parties:
        p = parties[0]
        offices = p.get("regional_offices") or []
        print(f"first party: {p.get('code')} {p.get('name', '')[:40]!r}, offices={len(offices)}")
        reports = client.get_party_reports(p["id"])
        print(f"reports for first party: {len(reports)}")
        if reports:
            detail = client.get_report_detail(reports[0]["id"])
            print(f"detail keys: {list(detail.keys())}")
