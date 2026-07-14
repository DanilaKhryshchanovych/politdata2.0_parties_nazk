# Для розробників

Як зібрати таблиці локально та як влаштований пайплайн.

## Запустити самостійно

```bash
pip install -r requirements.txt

# 1. Завантажити сирі звіти в кеш (інкрементально; --full для повного перезбору)
python -m src.downloader

# 2. Завантажити картки партій/осередків (адреси, party_main) — інкрементально
python -m src.card_downloader

# 3. Побудувати всі таблиці з кешу (повний детермінований перезбір)
python main.py               # -> data/excel_tables/*.xlsx + data/csv/*.csv
python main.py --limit 5000  # швидкий прогін на підмножині (для розробки)

# Тести
python -m pytest tests/ -q
```

## Архітектура

```
API v2 ──downloader──> data/raw/<report_id>.json      (сирий кеш звітів, ~1.5 ГБ, git-ignored)
       ──card_downloader─> data/raw/_party_cards.json  (картки: адреси + parent)
                                     │
        load.stage (один прохід) ─> meta + сирі секції
                                     │
        enrich (party_main, region) + clean (назви, IBAN, деперсоналізація)
                                     │
        tables/build (build_*)  ─> validate (проти golden) ─> export (xlsx + csv)
```

- **Розділення download / transform** через сирий кеш: трансформації ганяються офлайн будь-скільки разів.
- **Повний перезбір щоразу** (без append) — детерміновано, без фантомних дублів; downloader тягне лише нові JSON.
- **Один прохід** по кешу (`load.stage`) замість N — увесь ребілд читає ~1.5 ГБ раз.

## Публікація

Таблиці **не** зберігаються в історії git (важкі xlsx-бінарники, що оновлюються щотижня). Щотижневий
запуск (`.github/workflows/weekly.yml`) публікує їх у **GitHub Releases**; посилання в README
(`../../releases/latest/download/<файл>`) завжди ведуть на останній випуск.
