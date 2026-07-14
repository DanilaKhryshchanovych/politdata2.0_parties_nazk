"""
Downloader: walk the API v2 tree and populate the raw cache.

    parties (central)  ─┬─> each party id
                        └─> each nested regional_office id
        └─> POST /party/{id}/reports        (cheap: metadata only)
              └─> GET  /party/report/{id}    (full detail, all sections nested)
                    └─> data/raw/<report_id>.json

Incremental by default: a report's detail is fetched only when it is new or its
(signed_date, special_status) fingerprint changed since we last saw it. `--full`
re-fetches everything. Failures are collected, retried once, and the survivors
written to data/state/error_report_ids.txt (matching the old pipeline's contract).
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import settings  # noqa: E402
from src import raw_store  # noqa: E402
from src.api_client import ApiClient, ApiError  # noqa: E402

try:
    from tqdm import tqdm
except ImportError:  # tqdm is optional; degrade to a no-op wrapper
    def tqdm(iterable, **_kwargs):
        return iterable

log = logging.getLogger("downloader")


@dataclass
class RunStats:
    parties: int = 0
    offices: int = 0
    reports_seen: int = 0
    new: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    seconds: float = 0.0

    def summary(self) -> str:
        return (
            f"parties={self.parties} offices={self.offices} "
            f"reports_seen={self.reports_seen} new={self.new} updated={self.updated} "
            f"skipped={self.skipped} errors={len(self.errors)} "
            f"elapsed={self.seconds:.0f}s"
        )


def _collect_party_ids(parties: list[dict]) -> list[tuple[str, bool, str]]:
    """Flatten central parties + nested offices into (id, is_office, label) tuples."""
    seen: set[str] = set()
    out: list[tuple[str, bool, str]] = []
    for party in parties:
        pid = party.get("id")
        if pid and pid not in seen:
            seen.add(pid)
            out.append((pid, False, str(party.get("code") or pid)))
        for office in party.get("regional_offices") or []:
            oid = office.get("id")
            if oid and oid not in seen:
                seen.add(oid)
                out.append((oid, True, str(office.get("code") or oid)))
    return out


def _fetch_detail(client: ApiClient, report_meta: dict, stats: RunStats,
                  state: dict, was_known: bool, failures: list[dict]) -> None:
    report_id = report_meta["id"]
    try:
        detail = client.get_report_detail(report_id)
    except ApiError as exc:
        log.warning("detail fetch failed for %s: %s", report_id, exc)
        failures.append(report_meta)
        return
    raw_store.save_raw_report(report_id, detail)
    raw_store.mark_downloaded(state, report_meta)
    if was_known:
        stats.updated += 1
    else:
        stats.new += 1


def run(full: bool = False, party_limit: int | None = None) -> RunStats:
    started = time.monotonic()
    stats = RunStats()
    client = ApiClient()
    state = raw_store.load_state()

    log.info("fetching party directory ...")
    parties = client.get_parties()
    raw_store.save_parties(parties)
    party_ids = _collect_party_ids(parties)
    stats.parties = sum(1 for _, is_office, _ in party_ids if not is_office)
    stats.offices = sum(1 for _, is_office, _ in party_ids if is_office)
    if party_limit is not None:
        party_ids = party_ids[:party_limit]
    log.info("directory: %d parties, %d offices (%d ids to walk)",
             stats.parties, stats.offices, len(party_ids))

    failures: list[dict] = []
    for pid, _is_office, label in tqdm(party_ids, desc="parties", unit="party"):
        try:
            reports = client.get_party_reports(pid)
        except ApiError as exc:
            log.warning("reports list failed for party %s: %s", label, exc)
            stats.errors.append(f"party:{pid}")
            continue
        downloaded_before = stats.new + stats.updated
        for meta in reports:
            if not meta.get("id"):
                continue
            stats.reports_seen += 1
            was_known = meta["id"] in state
            if raw_store.needs_download(state, meta, full):
                _fetch_detail(client, meta, stats, state, was_known, failures)
            else:
                stats.skipped += 1
        # Persist progress after every party that actually fetched something, so an
        # interrupted run resumes from the last completed party instead of from zero.
        # Ordering per report is raw JSON -> mark_downloaded (in _fetch_detail) ->
        # save_state (here), and save_state writes atomically (tmp + replace), so the
        # persisted state can never name a report whose raw file isn't already on disk.
        if stats.new + stats.updated > downloaded_before:
            raw_store.save_state(state)

    # One retry pass over transient failures, mirroring the old pipeline.
    if failures:
        log.info("retrying %d failed reports ...", len(failures))
        retry_round, failures = failures, []
        for meta in tqdm(retry_round, desc="retry", unit="report"):
            was_known = meta["id"] in state
            _fetch_detail(client, meta, stats, state, was_known, failures)

    raw_store.reset_errors()
    for meta in failures:
        raw_store.record_error(meta["id"], "detail fetch failed after retry")
        stats.errors.append(meta["id"])

    raw_store.save_state(state)
    stats.seconds = time.monotonic() - started
    log.info("done: %s", stats.summary())
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Download ПОЛІТДАТА v2 reports into the raw cache.")
    parser.add_argument("--full", action="store_true",
                        help="re-fetch every report, ignoring existing state")
    parser.add_argument("--party-limit", type=int, default=None,
                        help="only walk the first N party/office ids (for testing)")
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    run(full=args.full, party_limit=args.party_limit)


if __name__ == "__main__":
    main()
