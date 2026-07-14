"""Write a finished table to xlsx + csv. Full rebuild (no append)."""
from __future__ import annotations

import datetime as _dt
import logging
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import settings  # noqa: E402

log = logging.getLogger("export")

EXCEL_ROW_LIMIT = 1_048_575  # 1,048,576 incl. header

REPO_ROOT = Path(__file__).resolve().parent.parent
README = REPO_ROOT / "README.md"
_STAMP_RE = re.compile(r"^\*\*Останнє оновлення:.*$", re.MULTILINE)


def save_table(df: pd.DataFrame, name: str) -> None:
    settings.EXCEL_DIR.mkdir(parents=True, exist_ok=True)
    csv_dir = settings.DATA_DIR / "csv"
    csv_dir.mkdir(parents=True, exist_ok=True)

    df.to_csv(csv_dir / f"{name}.csv", index=False, encoding="utf-8-sig")

    if len(df) > EXCEL_ROW_LIMIT:
        log.warning("%s has %d rows > Excel limit; csv written, xlsx skipped", name, len(df))
        return
    df.to_excel(settings.EXCEL_DIR / f"{name}.xlsx", index=False, engine="xlsxwriter")


def stamp_readme(when: _dt.datetime | None = None) -> None:
    """Refresh the "Останнє оновлення" line in README so the weekly run advertises freshness."""
    if not README.exists():
        return
    when = when or _dt.datetime.now()
    line = f"**Останнє оновлення: {when:%Y-%m-%d %H:%M}**"
    text = README.read_text(encoding="utf-8")
    new_text, n = _STAMP_RE.subn(line, text, count=1)
    if n:
        README.write_text(new_text, encoding="utf-8")
        log.info("stamped README: %s", line)
    else:
        log.warning("README date line not found; skipped stamping")
