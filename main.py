"""
Orchestration: raw cache -> 21 clean tables (xlsx + csv), full deterministic rebuild.

    python main.py             # stage (if needed) then build everything
    python main.py --restage   # force re-read of the raw cache
    python main.py --limit N   # only first N reports (dev)
    python main.py --no-export # build + validate, skip writing files

Staging streams each section to data/staging/*.jsonl in one pass over the cache, so
memory stays bounded and re-runs can rebuild tables without re-reading 74k JSON files.
Tables are built one at a time and freed, keeping peak memory to a single section.
"""
from __future__ import annotations

import argparse
import gc
import logging
import time

from src import enrich, export, load, validate
from src.tables import build

log = logging.getLogger("main")


def run(limit: int | None = None, do_export: bool = True, restage: bool = False) -> list[dict]:
    started = time.monotonic()
    cards = load.load_cards()
    central, office = load.directory_codes()
    section_paths = [spec["section"] for spec in build.SECTION_SPECS.values()]

    if restage or not load.staging_exists():
        log.info("staging raw cache (single pass, cards=%d) ...", len(cards))
        meta = load.stage_to_disk(section_paths, cards, limit=limit)
        log.info("staged %d reports in %.0fs", len(meta), time.monotonic() - started)
    else:
        log.info("reusing existing staging (data/staging) — pass --restage to refresh")
        meta = load.load_staged_meta()

    meta = enrich.unify_names(enrich.clean_party_main(meta))
    log.info("meta: %d reports", len(meta))

    results: list[dict] = []
    membership: dict[str, set] = {}

    def emit(name, df):
        if do_export:
            export.save_table(df, name)
        results.append(validate.validate_table(name, df))

    table1 = build.build_table_1(meta)
    emit("1_legal_entity_report_info", table1)

    for schema, spec in build.SECTION_SPECS.items():
        t0 = time.monotonic()
        raw = load.read_staged_section(spec["section"])
        df = build.build_section_from_staged(schema, raw, meta, central, office)
        membership[schema] = build.membership_set(schema, df)
        emit(schema, df)
        log.info("built %-38s %8d rows  (%.0fs)", schema, len(df), time.monotonic() - t0)
        del raw, df
        gc.collect()

    # aggregates
    emit("0_reports_per_period_per_party", build.build_0_reports_per_period(table1))
    dups = build.build_0_duplicates(meta)
    if len(dups):
        emit("0_report_duplcates", dups)
    emit("0_files_where_to_look_for_local_parties", build.build_0_files(table1, membership))

    validate.print_report(results)
    if do_export:
        export.stamp_readme()
    log.info("done in %.0fs", time.monotonic() - started)
    return results


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--restage", action="store_true")
    p.add_argument("--no-export", action="store_true")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%H:%M:%S")
    run(limit=args.limit, do_export=not args.no_export, restage=args.restage)


if __name__ == "__main__":
    main()
