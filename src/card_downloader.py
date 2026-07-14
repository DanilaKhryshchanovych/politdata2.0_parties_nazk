"""
One-time (then incremental) download of party/office cards.

The /parties directory lists offices with only {id, code, name, is_active} and no
address; the report detail carries no address either. `GET /party/{id}`, however,
returns the full card — register_address, actual_address, parent, head_info — for
BOTH central parties and offices. Table 1 (and the region column in almost every
table) needs those addresses, so we fetch one card per directory id and cache them
in data/raw/_party_cards.json as {id: card}. Resumable: already-cached ids are skipped.
"""
from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import settings  # noqa: E402
from src.api_client import ApiClient, ApiError  # noqa: E402

try:
    from tqdm import tqdm
except ImportError:
    def tqdm(it, **_k):
        return it

log = logging.getLogger("card_downloader")

CARDS_FILE = settings.RAW_DIR / "_party_cards.json"


def _all_ids(parties: list[dict]) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()
    for p in parties:
        for node in (p, *(p.get("regional_offices") or [])):
            i = node.get("id")
            if i and i not in seen:
                seen.add(i)
                ids.append(i)
    return ids


def load_cards() -> dict[str, dict]:
    if CARDS_FILE.exists():
        return json.loads(CARDS_FILE.read_text(encoding="utf-8"))
    return {}


def _save(cards: dict) -> None:
    tmp = CARDS_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(cards, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(CARDS_FILE)


def run(sleep: float = 0.2) -> None:
    parties = json.loads((settings.RAW_DIR / "_parties.json").read_text(encoding="utf-8"))
    ids = _all_ids(parties)
    cards = load_cards()
    todo = [i for i in ids if i not in cards]
    log.info("cards: %d total ids, %d already cached, %d to fetch", len(ids), len(cards), len(todo))

    client = ApiClient(sleep_between=sleep)
    errors = 0
    for n, pid in enumerate(tqdm(todo, desc="cards", unit="card"), 1):
        try:
            card = client.unwrap_obj(client._request("GET", f"/party/{pid}"))
        except Exception as exc:  # noqa: BLE001 — one bad card must not kill the run
            log.warning("card fetch failed for %s: %s", pid, exc)
            errors += 1
            continue
        if card:
            cards[pid] = card
        if n % 200 == 0:
            _save(cards)
    _save(cards)
    log.info("done: %d cards cached, %d errors", len(cards), errors)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        datefmt="%H:%M:%S")
    run()
