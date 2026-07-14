# План: politdata_nazk_tables v2 — переписування пайплайна під новий API ПОЛІТДАТИ

> Документ для Claude Code. Мета: відтворити функціонал репозиторію
> [texty/politdata_nazk_tables](https://github.com/texty/politdata_nazk_tables) на новому
> публічному API `https://politdata.nazk.gov.ua/api/v2`. Результат — щотижневий пайплайн на Python,
> який викачує всі звіти політичних партій, чистить і збагачує дані та зберігає ~21 «чистий»
> Excel-файл, готовий до аналізу без додаткової обробки.

---

## 1. Як працював старий пайплайн (реверс-інженіринг репозиторію)

### 1.1 Потік даних

```
getpartylistmain ─┐
getpartylistregion ┴─> party_list, party_region_list (довідник партій/осередків, EDRPOU)

getreportslist ──> список id всіх звітів
getreport/{id} ──> ОДИН великий JSON на звіт: плоскі метадані + вкладені списки
                   (propertyObjects, propertyMovables, propertyTransport, propertyPapers,
                    propertyNoMoney, propertyMoney, contributionConMoney, contributionOtherCon,
                    contributionCosts, contributionOtherCosts, paymentGov, paymentOther,
                    paymentCostsPaymentReceive, paymentOtherCostsPaymentReceive, obligate,
                    tablets1, tablets2)

r_df (усі звіти в одному DataFrame, 1 рядок = 1 звіт)
  └─> збагачення party_main_* ──> чистка назв ──> 21 функція table_*() ──> Excel ──> git push
```

### 1.2 Ключові механіки, які ТРЕБА зберегти

1. **Інкрементальність.** `downloaded_report_ids.txt` — список уже завантажених `report_id`.
   При `full_update=False` качаються лише нові id; нові рядки **доклеюються** до наявних Excel
   (`save_as_excel` в append-режимі). При `full_update=True` всі xlsx видаляються і будуються з нуля.
2. **Обробка помилок завантаження.** Невдалі id складаються в `errs`, після основного циклу —
   одна повторна спроба; остаточні невдачі пишуться в `error_report_ids.txt`. Між запитами `sleep(1)`.
3. **Збагачення `party_main_name` / `party_main_EDRPOU`.** У кожному звіті знаходиться рядок з
   `officeType == "Центральний офіс"`, його `partyCode/partyName` приклеюються ДО ВСІХ рядків того ж
   `report_id`. Так кожен регіональний осередок отримує «материнську» партію.
4. **Уніфікація назв у часі** (`unify_party_main_name`): для кожного EDRPOU береться назва з
   **найсвіжішого за датою** звіту й підставляється в усі старі рядки — щоб одна партія не мала
   5 варіантів написання за різні роки.
5. **Розгортання вкладених списків** (`list_to_rows`): список словників у клітинці → окремі рядки,
   до кожного доклеюються метадані звіту (period, year, partyName, partyCode, region,
   party_main_*, report_id), потім перейменування колонок за ренеймером.
6. **Деперсоналізація**: клітинки, що складаються лише з `*` (та `_`) → `None` (`replace_stars`).

### 1.3 Каталог правил чистки та збагачення (НАЙВАЖЛИВІША ЧАСТИНА)

Перенести в новий код **дослівно** (усі функції вже є в `main_functions.py` старого репо — їх можна
скопіювати майже без змін, вони працюють на рівні pandas і не залежать від API):

**A. `party_name_cleaner` — чистка назв партій (для `party_main_name`):**
- upper case;
- видалення префіксів regex-ами: `^ПОЛІТИЧНА ПАРТІЯ`, `^ВСЕУКРАЇНСЬКЕ ОБ'ЄДНАННЯ`,
  `ВСЕУКРАЇНСЬКЕ ПОЛІТИЧНЕ ОБ'ЄДНАННЯ`, `ПОЛІТИЧНОЇ ПАРТІЇ`, `ПОЛІТИЧЯНА ПАРТІЯ` (sic, одруківка в даних),
  `СОЦІАЛЬНО-ЕКОЛОГІЧНА ПАРТІЯ`, `СОЦІАЛЬНО-ПОЛІТИЧНИЙ СОЮЗ`, лапки `«»"`;
- колапс пробілів `\s+ -> ' '`, strip;
- словник ручних правок (~14 партій: «РІШУЧИХ ДІЙ» → «ПАРТІЯ РІШУЧИХ ДІЙ», «МИР» →
  «ВСЕУКРАЇНСЬКЕ ОБ'ЄДНАННЯ «МИР»» тощо — повний словник у `main_functions.py`).
  ⚠️ Словник треба буде РОЗШИРЮВАТИ на нових даних — передбачити його як конфіг
  (`config/party_renamer.json`), а не хардкод.

**B. `org_name_clean` — нормалізація назв контрагентів** (донорів, отримувачів, власників, банків):
- upper case, колапс пробілів;
- ~10 варіантів написання «ФІЗИЧНА ОСОБА-ПІДПРИЄМЕЦЬ» (включно з одруківками
  «ПІДРИЄМЕЦЬ», «ОБОБА», «ПІДПРИМЕЦЬ») → `ФОП`;
- «ТОВАРИСТВО З ОБМЕЖЕНОЮ ВІДПОВІДАЛЬНІСТЮ» (+одруківка «ВІДПРОВІДАЛЬНІСТЮ») → `ТОВ`;
- «ПРИВАТНЕ АКЦІОНЕРНЕ ТОВАРИСТВО» → `ПрАТ`; «ПУБЛІЧНЕ АКЦІОНЕРНЕ ТОВАРИСТВО» → `ПАТ`;
- «АКЦІОНЕРНЕ ТОВАРИСТВО» (+«ТОВАРИВСТВО») → `АТ`; «ДЕРЖАВНА ПОДАТКОВА СЛУЖБА / ДЕРЖАВНОЇ ПОДАТКОВОЇ СЛУЖБИ» → `ДПС`;
- «ПОЛІТИЧНА ПАРТІЯ» → `ПП`;
- ФОП на початку рядка переноситься в кінець: `ФОП ІВАНОВ І.І.` → `ІВАНОВ І.І. ФОП`;
- словник ручних злипань (`org_names_to_rename`): 5 варіантів «ТОВ ПІДПРИЄМСТВО "КИЇВ"» → один канон;
  «РАЙФФАЙЗЕН БАНК» → «РАЙФФАЙЗЕН БАНК АВАЛЬ». Теж винести в конфіг.

**C. Пост-обробка після `org_name_clean` (застосовується разом, до тієї ж колонки):**
- уніфікація апострофів: `(?<=\w)[’"`](?=\w)` → `'`;
- заміна латинських літер, що «загубилися» в кирилиці: якщо рядок містить `[А-Я]`,
  то `C`→`С`, `I`→`І`.

**D. `clean_bank_account` — чистка IBAN:** видалити `№`, пробіли, `:`, `\n`, strip.

**E. `check_edrpou_for_party` — збагачення типу контрагента:** якщо EDRPOU донора/отримувача/власника
є в довіднику партій або осередків → тип = `Партійний осередок`. Застосовується до:
donor_type (5, 6), recipient_type (9.1, 9.2), object_owner_type (3.3).

**F. Регіон для центрального офісу:** у всіх таблицях, де є `legal_entity_region`,
для рядків `officeType == 'Центральний офіс'` → `legal_entity_region = 'Україна'`.
⚠️ У новому API значення `office_type` може мати інший вигляд — з'ясувати на Фазі 0 і
замапити на старе значення.

**G. Фільтри порожніх рядків (по-таблично):**
- 2.2: викинути рядки, де name == '0' і EDRPOU == '00000000';
- 3.1: `object_type.notna()`; 3.3: `object_type.notna() & object_brand.notna()`;
- 5: `donor_name.notna() & bank_edrpou.notna()`; 6: `donor_name.notna() & donor_type.notna()`;
- 9.2: `bank_EDRPOU.notna() & account_number.notna()`; 10: `name.notnull()`;
- 6: у donor_edrpou / donor_birth_date / object_registration_number, що містять `*` → None
  (плюс глобальний `replace_stars` всюди).

**H. Типи:** 7_state_funding: `transaction_sum` → int. Решта сум лишаються як є (рядки/float —
звірити з еталонними Excel).

### 1.4 Цільові вихідні таблиці (контракт на виході — колонки мають збігтися)

Точні схеми зафіксовані в наявних Excel у старому репо (`data/excel_tables/*.xlsx`) — вони і є
еталоном (golden files). Список:

| Файл | Джерело в старому API | Аналог у новому API v2 |
|---|---|---|
| 1_legal_entity_report_info | плоскі поля getreport | GET `/party/report/{id}` + GET `/party/{id}` (адреси, голова) |
| 2.1_local_orgs_info | tablets1 | ❓ POST `/parties` (parent!=null) або поле у звіті — з'ясувати |
| 2.2_other_party_orgs_info | tablets2 | ❓ з'ясувати на Фазі 0 |
| 3.1_property_objects | propertyObjects | POST `/party/report/{id}/realty` |
| 3.2_movable_property | propertyMovables | POST `/party/report/{id}/movable` |
| 3.3_vehicles | propertyTransport | POST `/party/report/{id}/transport` |
| 3.4_securities | propertyPapers | POST `/party/report/{id}/paper` |
| 3.5_intangible_assets | propertyNoMoney | POST `/party/report/{id}/intangible` |
| 4_bank_accounts | propertyMoney | POST `/party/report/{id}/money` |
| 5_private_contributions | contributionConMoney | POST `.../payments/monetary_contributions` |
| 6_in_kind_donations | contributionOtherCon | POST `.../payments/other_contributions` |
| 7_state_funding_transactions | contributionCosts | POST `.../payments/state_funding` |
| 8_other_income | contributionOtherCosts | POST `.../payments/other_incomes` |
| 9.1_expenditures_public_funding | paymentGov | POST `.../payments/budget_expenses` |
| 9.2_expenditures_private_funds | paymentOther | POST `.../payments/outgoing_expenses` |
| 9.3_false_donations_info | paymentCostsPaymentReceive | ❓ ймовірно `.../payments/return_expenses` |
| 9.4_false_donations_returning | (не існувало в старому) | ❓ ймовірно `.../payments/return_expenses` або `transfer_expenses` |
| 9.5_false_in_kind_donations_info | paymentOtherCostsPaymentReceive | ❓ з'ясувати (можливо `transfer_expenses`) |
| 10_liabilities | obligate | POST `/party/report/{id}/obligations` |
| 0_report_duplcates | дублікати по (period, year, partyName, partyCode) | та сама логіка |
| 0_reports_per_period_per_party | pivot з таблиці 1 | та сама логіка |
| 0_files_where_to_look_for_local_parties | membership-матриця по всіх xlsx | та сама логіка |

Мапінг `payments/{type}` на таблиці — **гіпотеза за змістом**, її треба підтвердити реальними
відповідями на Фазі 0 (порівняти поля відповіді з ренеймерами 10–19 старого репо).

---

## 2. Новий API v2 — що відомо і що ні

**Відомо (зі Swagger/PDF):**
- База: `https://politdata.nazk.gov.ua/api/v2`.
- `POST /parties` — список партій та осередків; body `{"filters": null, "order": null, "pager": {"page": 1, "size": N}}`;
  відповідь `DataTableResponse {list, count}` — тобто **пагінація обов'язкова**.
  Модель партії: `id, parent, is_active, code (EDRPOU), name, web_site_url, register_address{...}, actual_address{...}, actual_address_same_register`.
  Поле `parent` пов'язує осередок з центральною партією — це заміна старому merge по `politPartyUnitId`.
- `GET /party/{id}` — облікова картка партії/осередку.
- `POST /party/{id}/reports` — список звітів партії (ймовірно теж body з pager).
  PartyReportModel: `id, document_id, report_type_id, office_type, report_number, period_from,
  period_till, employees_by_employment_contract, employees_by_civil_contract, party_info_id,
  head_id, head_reason_id, report_type, year, quarter, head_reason, deleted, status, signed`.
- `GET /party/report/{id}` — деталізація звіту (та сама модель).
- `POST /party/report/{id}/{realty|movable|transport|paper|intangible|money|obligations|payments|payments/{type}}` —
  секції звіту. `{type}` ∈ monetary_contributions, other_contributions, state_funding, other_incomes,
  budget_expenses, outgoing_expenses, return_expenses, transfer_expenses.

**Невідомо (розвідати на Фазі 0):**
1. Точні схеми рядків кожної секції (Swagger в Example Value показує модель звіту, а не рядків —
   схоже на неповну документацію). Чи поля тепер іменовані (не `conMoney1`)?
2. Чи POST-секції приймають/вимагають pager у body; ліміти `size`; загальний rate limit.
3. Значення `office_type` (чи є «Центральний офіс» дослівно), `status`, `signed`, `deleted` —
   які звіти вважати «чинними» (ймовірний фільтр: `deleted != true` і `signed == true`).
4. Де тепер дані для таблиць 2.1/2.2 (колишні tablets1/tablets2).
5. Чи міграція охопила історичні звіти з 2021 року, чи лише нові (це визначає, чи можна
   відмовитися від старих xlsx як бекфілу).
6. Формат дат, формат сум (рядок/число), як позначена деперсоналізація (все ще `***`?).
7. Кількість третіх «числових» ключів: у старому 1_legal_entity було 3 показники зайнятості
   (contract / civil / volunteers), у новій моделі видно лише 2 (employment/civil) — куди подівся
   третій, або він у GET `/party/report/{id}`.

---

## 3. Архітектура нового пайплайна

```
politdata_v2/
├── config/
│   ├── settings.py            # base_url, page_size, sleep, retries, шляхи
│   ├── party_renamer.json     # ручні правки назв партій (з старого + нові)
│   ├── org_renamer.json       # ручні злипання контрагентів
│   └── schemas/               # цільові колонки кожної з 21 таблиці (контракт)
├── src/
│   ├── api_client.py          # requests.Session, retry з backoff, пагінація POST-ендпоінтів,
│   │                          # sleep між запитами, логування помилок у error_ids
│   ├── downloader.py          # обхід: parties -> reports -> секції; інкрементальний стан
│   ├── raw_store.py           # ⭐ НОВЕ: зберігати сирі JSON на диск (data/raw/{report_id}/{section}.json)
│   │                          #   — щоб при зміні логіки чистки НЕ перекачувати все з API
│   ├── enrich.py              # party_main_*, unify names, check_edrpou_for_party, region='Україна'
│   ├── clean.py               # party_name_cleaner, org_name_clean, clean_bank_account,
│   │                          # replace_stars, апострофи, латиниця→кирилиця
│   ├── tables/                # по модулю на таблицю: build_3_1(), build_5(), ... (чиста функція:
│   │                          # raw json -> DataFrame цільової схеми)
│   ├── export.py              # save_as_excel (full/append), оновлення README
│   └── validate.py            # ⭐ НОВЕ: перевірка колонок проти config/schemas, звіт по NaN,
│                              #   порівняння з golden files зі старого репо
├── data/
│   ├── raw/                   # сирі JSON (у .gitignore)
│   ├── state/                 # downloaded_report_ids.txt, error_report_ids.txt
│   └── excel_tables/          # фінальні xlsx (комітяться)
├── main.py                    # оркестрація: python main.py [--full]
├── tests/                     # юніт-тести чистки на реальних кейсах зі старих Excel
└── .github/workflows/weekly.yml  # cron щотижня: run -> commit -> push
```

Принципові покращення відносно старого коду (не змінюючи результат):
- **Розділити download і transform** через шар сирих JSON — старий код тримав усе в пам'яті і при
  падінні на 3000-му звіті втрачав усе; тепер transform можна ганяти офлайн скільки завгодно.
- `requests.Session` + `urllib3.Retry` (backoff, retry на 429/5xx) замість голого try/except.
- Ренеймери → якщо нові поля вже іменовані, ренеймери стають мапінгом «нове ім'я → старе ім'я
  колонки», щоб вихідний контракт (колонки Excel) не змінився для користувачів.
- Логи (logging + tqdm), підсумковий звіт запуску: скільки звітів нових, скільки помилок, дельти рядків.

---

## 4. Покроковий план виконання (фази для Claude Code)

### Фаза 0 — Розвідка API (обов'язково перша, ~півдня)
1. Написати одноразовий скрипт `explore_api.py`: викликати кожен ендпоінт на 2–3 реальних
   партіях/звітах, зберегти сирі відповіді у `exploration/`.
2. Задокументувати в `docs/api_v2_findings.md`: точні схеми рядків кожної секції, пагінацію,
   ліміти, значення office_type/status/signed/deleted, наявність історії з 2021, формат `***`.
3. Побудувати таблицю відповідності: поле нового API ↔ стара колонка Excel (звірити з
   renamer_1..renamer_20 — вони описують семантику кожного старого поля).
4. ⛔ STOP-пункт: якщо секції 2.1/2.2 або 9.3–9.5 не знаходяться — зафіксувати і погодити з
   власником репо, що з ними робити (пропустити / інше джерело).

### Фаза 1 — Клієнт і завантажувач (1 день)
5. `api_client.py`: пагінований POST, retries, sleep, ліміт швидкості.
6. `downloader.py` + `raw_store.py`: повний обхід parties → reports → секції; інкрементальний
   стан по `report_id` (враховуючи, що звіт може бути перепідписаний — тримати
   `(report_id, status, signed)` у стані, а не голий id).
7. Прогнати повне завантаження, оцінити обсяг і час (стара база ~ тисячі звітів; sleep підібрати
   так, щоб повний прогін вкладався в ніч).

### Фаза 2 — Трансформації (2–3 дні, серцевина роботи)
8. Перенести `clean.py`/`enrich.py` зі старого репо (функції з розділу 1.3 — копіюються майже 1:1).
9. Реалізувати 21 `build_*()` за контрактами з `config/schemas/` (взяти колонки з еталонних xlsx).
10. Особливі місця:
    - `party_main_*`: у v2 будувати з поля `parent` (`POST /parties`) + office_type звіту;
      залишити fallback на стару логіку «знайти звіт центрального офісу»;
    - `unify_party_main_name`: сортувати по даті подачі (з'ясувати, яке поле v2 = стара `date`;
      кандидат — щось на кшталт submission date у деталізації звіту);
    - дублікати (0_report_duplcates): ключ (period/quarter, year, partyCode) + врахувати
      нові поля `status/deleted` — можливо, «дублікатів» стане менше, бо їх можна фільтрувати.
11. `validate.py`: (a) колонки == контракту; (b) на спільному історичному періоді порівняти
    агрегати (кількість рядків, суми внесків по партіях за квартал) з golden files старого репо —
    це головний тест коректності міграції.

### Фаза 3 — Експорт, автоматизація, документація (1 день)
12. `export.py`: full/append як у старому, оновлення дати в README.
13. GitHub Actions weekly cron (або локальний cron): `main.py` → commit → push. Секрети не
    потрібні (API публічний).
14. README з описом таблиць (перенести з старого) + `docs/data_dictionary.md` — словник кожної
    колонки кожної таблиці (у старому репо його не було, а користувачам він потрібен).

### Фаза 4 — Бекфіл і запуск (0.5 дня)
15. Рішення по історії: якщо v2 віддає звіти з 2021 — повний `--full` прогін; якщо ні —
    залишити старі xlsx як заморожений архів і доклеювати нове (тоді звірити сумісність колонок).
16. Перший продакшн-прогін, ручна вибіркова звірка 20–30 рядків проти веб-інтерфейсу ПОЛІТДАТИ.

---

## 5. Ризики та підводні камені

- **Rate limiting / бан.** Старий код спав 1с між запитами; у v2 запитів буде у ~10 разів більше
  (10 секцій на звіт замість 1). Мітигація: сирий кеш (не перекачувати), інкрементальність,
  можливо batch по ночах, User-Agent з контактом.
- **Перепідписані/видалені звіти.** Поля `deleted/status/signed` — нові. Якщо ігнорувати, у
  таблицях будуть фантомні дублі. Інкрементальний стан має реагувати на зміну статусу вже
  завантаженого звіту (append-модель старого коду цього не вміла — це відома її слабкість).
- **`payments/{type}` може повертати різні схеми під одним ендпоінтом** — будувати парсер по
  фактичних відповідях, не по документації.
- **Деперсоналізація**: якщо `***` замінили на null/маску іншого виду — оновити `replace_stars`.
- **Ручні словники правок застаріють**: після першого прогону зробити частотний аудит
  `party_main_name` і donor/recipient names → поповнити словники новими злипаннями.
- **Excel-ліміт 1 048 576 рядків**: таблиці 9.1/9.2 ростуть найшвидше; закласти перевірку і
  план Б (розбивка по роках або паралельний parquet/csv).

## 6. Відкриті питання до власника (Даніла)

1. Пушити оновлення в той самий репозиторій texty чи у твій новий форк/репо?
2. Чи потрібен бекфіл історії 2021–2025, якщо v2 її не віддає (лишити старі файли як архів)?
3. Хостинг щотижневого запуску: GitHub Actions (безкоштовно, але ліміт часу джоби) чи свій сервер?
4. Формат: лишаємо тільки xlsx, чи додаємо csv/parquet поруч (дешево, а аналітикам зручніше)?
