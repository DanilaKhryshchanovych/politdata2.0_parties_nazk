# API v2 — знахідки розвідки (Фаза 0)

> База: `https://politdata.nazk.gov.ua/api/v2`. Джерело — реальні відповіді, зібрані
> `exploration/explore_api.py` та `exploration/explore_complete.py` у `exploration/samples/`.
> Дата розвідки: 2026-07-12.

## 0. Головний висновок (впливає на всю архітектуру)

`GET /party/report/{id}` повертає **весь звіт одним JSON-об'єктом з усіма секціями вкладено** —
прямий аналог старого `getreport/{id}`. Тому завантажувач робить **один GET на звіт**, а не ~10 POST:
це знімає головний ризик rate-limit із вихідного плану. Окремі `POST .../{section}` лишаються як
**пагінований fallback** для дуже великих секцій (перевірити, чи `GET detail` не обрізає великі списки).

Історія доступна **з 2021 року** → повний бекфіл через `--full` можливий (питання власника закрите на користь бекфілу).

## 1. Обгортка відповідей і пагінація

- Усі списки загорнуті так: `{"results": {"list": [ ... ]}}`. Поля `count` на верхньому рівні **немає**.
- POST-ендпоінти приймають body: `{"filters": null, "order": null, "pager": {"page": N, "size": M}}`.
- `POST /parties` з `size=5000` повертає повний список (перевіряється в `explore_complete.py`).
  Механізм пагінації уточнюється (чи є стеля на `size`).
- Між запитами тримаємо `sleep` (у розвідці 0.3–0.4с; для продакшн-бекфілу підібрати безпечніше).

## 2. Ендпоінти та їхні реальні моделі

### `POST /parties` → партії та осередки
Row keys (факт): `id (UUID), is_active, code (EDRPOU), name, web_site_url,
actual_address_same_register, created_at, updated_at, email, phone, head_info{name,surname/...},
register_address{country,post_index,region,district,city,street,building,apartments,...},
actual_address, parent[], regional_offices[]`.
- `id` — **UUID-рядок**, не число.
- `parent` — **масив**; `regional_offices` — масив вкладених осередків. Ієрархія «центр ↔ осередок»
  вбудована в об'єкт партії → замінює старий merge по `politPartyUnitId`.

### `GET /party/{id}` → облікова картка партії (та сама модель, що рядок у /parties).

### `POST /party/{id}/reports` → список звітів партії
Row keys (факт): `id (UUID), schema_version, report_type ("main"), year, quarter, party_id,
is_party_office (bool), signed_date, created_date, signatory_id, special_status, public_summary`.
- ⚠️ Полів `office_type/status/signed/deleted` (як у Swagger) **немає**. Натомість:
  - `is_party_office` (bool) — заміна старому `officeType == "Центральний офіс"` (True = осередок; центр = False — уточнити напрям).
  - `signed_date` — дата підпису (кандидат на стару `date` для `unify_party_main_name` та дедуплікації).
  - `special_status`, `report_status` (на рівні рядків секцій) — нові поля статусу.
- `year` + `quarter` замість старих `year` + `period`.

### `GET /party/report/{id}` → повна деталізація звіту (ключовий ендпоінт)
Top keys: `id, schema_version, report_type, year, quarter, party_id, is_party_office,
signed_date, created_date, signatory_id, special_status, public_summary, head_info,
employees_by_civil_contract, employees_by_employment_contract, organizations, regional_offices,
properties{...}, payment_info{incoming{...}, outgoing{...}}, obligations, conclusion`.

## 3. Мапінг вкладених секцій → стара таблиця (STOP-гейт РОЗВ'ЯЗАНО)

| Вузол у `GET /party/report/{id}` | Окремий POST-ендпоінт | Стара таблиця |
|---|---|---|
| `regional_offices` (`code, name`) | — | **2.1** local_orgs_info (був tablets1) |
| `organizations` | — | **2.2** other_party_orgs_info (був tablets2) |
| `properties.property_object` | `POST .../realty` | 3.1 property_objects |
| `properties.property_movable` | `POST .../movable` | 3.2 movable_property |
| `properties.property_transport` | `POST .../transport` | 3.3 vehicles |
| `properties.property_paper` | `POST .../paper` | 3.4 securities |
| `properties.property_intangible_asset` | `POST .../intangible` | 3.5 intangible_assets |
| `properties.property_moneys` | `POST .../money` | 4 bank_accounts |
| `payment_info.incoming.monetary_contributions` | `POST .../payments/monetary_contributions` | 5 private_contributions |
| `payment_info.incoming.other_contributions` | `.../payments/other_contributions` | 6 in_kind_donations |
| `payment_info.incoming.state_funding` | `.../payments/state_funding` | 7 state_funding_transactions |
| `payment_info.incoming.other_incomes` | `.../payments/other_incomes` | 8 other_income |
| `payment_info.outgoing.budget_expenses` | `.../payments/budget_expenses` | 9.1 expenditures_public_funding |
| `payment_info.outgoing.outgoing_expenses` | `.../payments/outgoing_expenses` | 9.2 expenditures_private_funds |
| `payment_info.outgoing.return_expenses` | `.../payments/return_expenses` | 9.3 / 9.4 (false donations info/returning) |
| `payment_info.outgoing.transfer_expenses` | `.../payments/transfer_expenses` | 9.5 false_in_kind_donations_info |
| `obligations` | `POST .../obligations` | 10 liabilities |
| `head_info`, `employees_*`, метадані | — | 1 legal_entity_report_info |
| `public_summary` | — | «0_» агрегати + валідація |

## 4. Реальні row-схеми секцій (факт, з `exploration/samples/00_all_schemas.json`)

Майнові/зобов'язальні секції — кожна має власний набір іменованих полів:

- **money (табл. 4):** `id, report_status, account_type, account_number, account_holder,
  account_holder_code, begin_period_balance, end_period_balance, report_period_income,
  report_period_used_funds, created_at`.
- **realty / property_object (табл. 3.1):** `id, report_status, object_type, object_number, owning_date,
  owning_cost, owner_code, owner_name, total_area, object_address, object_rights, substraction_date, created_at`.
- **movable (табл. 3.2):** `id, report_status, movable_type, owning_date, owning_cost, description,
  manufacturer_name, trade_mark, movable_rights, substraction_date, created_at`.
- **transport (табл. 3.3):** `id, party_id, office_id, party_report_id, report_status, transport_type_id,
  transport_type, owning_subject_id, owning_date, owning_cost, object_number, transport_brand,
  transport_model, production_year, object_rights_id, object_rights, substraction_date, created_at`.
- **intangible (табл. 3.5):** `id, report_status, asset_type, asset_count, asset_description, asset_rights,
  owning_date, owning_cost, substraction_date, created_at`.
- **obligations (табл. 10):** `id, report_status, object_type_id, object_type, person_type, person_name,
  person_code, person_addr, owning_cost, owning_date, owning_reason, owning_subject_id,
  end_period_remains_cost, created_at`.
- **paper / property_paper (табл. 3.4):** ⚠️ не трапилась у перших 321 партії (цінні папери рідкісні).
  Схему добрати під час першого реального завантаження; за конвенцією очікуються поля виду
  `id, report_status, paper_type, owning_date, owning_cost, ... issuer ..., created_at`.

**ВАЖЛИВО — усі 8 платіжних типів мають ІДЕНТИЧНУ 41-польну схему** (розрізняються лише ендпоінтом +
`group_code`, а НЕ набором полів):
`id, report_id, group_code, payment_type, payment_code, payment_number, payment_amount, payment_currency,
payment_reason, payment_purpose, payment_operation_date, payment_instruction_date, payment_description,
refund_date, refund_amount, refund_budget_amount, refund_reason, refund_purpose, refund_description,
payer_{type,name,code,birthday,address,account_type,account_iban,bank_code,bank_name,bank_address},
receiver_{type,name,code,birthday,address,account_type,account_iban,bank_code,bank_name,bank_address},
created_at, updated_at`.
- Для внесків (5,6,7,8) джерело коштів = `payer_*`; для витрат (9.1,9.2) отримувач = `receiver_*`.
- `group_code` (напр. `"4_2"`) розрізняє підтипи всередині ендпоінта — може знадобитись для 9.3/9.4/9.5.
- Кожен `build_*()` для платіжних таблиць вибирає релевантну підмножину цих 41 полів під контракт
  відповідної старої таблиці (renamer_10..renamer_20).

## 4a. Мапінг «поле v2 → стара чиста колонка» (ключові/нетривіальні)

**Табл. 1 (legal_entity):** зі звіту `party_id`→(join до /parties для name/edrpou/адрес), `is_party_office`→officeType,
`signed_date`→report_submition_date, `report_type`→report_type, `year`→report_year, `quarter`→report_period,
`head_info.{name,surname...}`→legal_entity_head_*, `employees_by_employment_contract`→number_of_employees_contract,
`employees_by_civil_contract`→number_of_employees_civil_agreement. Адреси — з /parties `register_address`/`actual_address`.
(number_of_employees_volunteers — уточнити, чи є 3-й показник у v2.)

**Табл. 2.1 (regional_offices):** `code`→local_org_EDRPOU, `name`→local_org_name (+ метадані звіту).
**Табл. 2.2 (organizations):** `code`→other_party_org_EDRPOU, `name`→other_party_org_name (+ метадані).

**Табл. 4 (money):** account_type→account_type, account_number→account_number, account_holder→bank_name,
account_holder_code→bank_edrpou, begin/end_period_balance→balance_for_first/last_day_of_period,
report_period_income→income_during_reporting_period, report_period_used_funds→spent_during_reporting_period.

**Табл. 5/6/7/8 (внески, payer=джерело):** payer_name→donor_name, payer_code→donor_edrpou,
payer_type→donor_type, payer_birthday→donor_birth_date, payer_address→donor_location,
receiver_bank_name→bank_name, receiver_bank_code→bank_edrpou, receiver_account_iban→bank_account,
payment_operation_date→donation_date, payment_amount→donation_sum, refund_amount→donation_refund_sum.

**Табл. 9.1/9.2 (витрати, receiver=отримувач):** receiver_name→recipient_name, receiver_code→recipient_EDRPOU,
receiver_type→recipient_type, receiver_address→recipient_location, payer_bank_name→bank_name,
payer_bank_code→bank_EDRPOU, payer_account_iban→account_number, payment_operation_date→payment_date,
payment_purpose→payment_purpose, payment_amount→amount.

**Табл. 10 (obligations):** object_type→obligation_type, owning_reason→reason, owning_date→date_of_occurrence,
person_name→name, person_type→type, person_code→edrpou, person_addr→location, owning_cost→obligations_sum,
end_period_remains_cost→amount_not_yet_paid.

> Повний контракт колонок кожної таблиці фіксується в `config/schemas/` за golden-xlsx старого репо.

## 5. Відкриті питання, що лишились
1. Чи `GET /party/report/{id}` обрізає дуже великі секції (тисячі рядків витрат)? Якщо так — брати їх
   через пагінований `POST .../{section}`. Перевірити на партії з держфінансуванням.
2. `is_party_office`: True/False → яке значення = «Центральний офіс»? (для region='Україна' і party_main_*).
3. Формат сум: у зразках трапляються і рядки (`"35302.89"`), і числа (`100`) — привести типи як у golden.
4. Деперсоналізація: чи все ще `***`? (перевірити на приватних донорах — payer_code/birthday).
5. Точний зміст `public_summary` для «0_»-таблиць і як звіряти з рядковими сумами (валідація).
6. `report_status` (2, ...) та `special_status` — які значення означають «чинний/видалений/перепідписаний».

## 6. РОЗВ'ЯЗАННЯ відкритих питань (Фаза 2, емпірично на кеші 74k, 2026-07-13)

Джерело: `exploration/build_schemas_and_recon.py`, `exploration/samples/{golden_values,recon2,office_card}.json`.

1. **`is_party_office` → офіс.** `False` = **центральний офіс** (party_id у списку центральних партій),
   `True` = **регіональний осередок** (party_id серед offices). Перевірено на 4000 звітах, 0 розбіжностей.
   Мапінг у стару колонку `officeType`: `False→"Центральний офіс"`, `True→"Регіональний офіс"`
   (точні рядки з golden `1_legal_entity_report_info`: 2213 центр / 39868 регіон).
2. **`report_type`** = `"main"` (константа) → стара `"Основний"`.
3. **`quarter`** ∈ {1,2,3,4,5}; **`5` = річний звіт → `"рік"`**, 1–4 → `"N квартал"` (стара `report_period`).
   `year` (int) → `report_year`.
4. **Суми:** `money.*_balance/income/used_funds` — **рядки** (`"35302.89"`); `payment_amount` — mix int/float.
   Golden тримає баланси як float, `*_edrpou` як int. У build: числові суми → `pd.to_numeric`; звірка з golden по значеннях, не по dtype.
5. **Деперсоналізація:** у `payer_code/payer_birthday/receiver_*` **жодного `***`** на 4000 звітах →
   у v2 приховані дані просто відсутні (null), не масковані. `replace_stars` лишаємо як дешеву страховку.
6. **`special_status`** = null на всіх; **`report_status`** ∈ {2, null} (2 на money-рядках, null на платежах) —
   не інформативний фільтр. **Не фільтруємо** по статусах (як і старий пайплайн).
7. **`number_of_employees_volunteers`** — 3-го показника зайнятості у v2 **немає** (лише
   `employees_by_employment_contract`, `employees_by_civil_contract`) → колонка = None.
8. **`group_code` = 1:1 з ендпоінтом секції** (monetary=3_1, other_contributions=3_2, state_funding=3_3,
   other_incomes=3_4, budget_expenses=4_1, outgoing=4_2, return=4_3, transfer=4_4). Розділяти 9.3/9.5
   за group_code **не треба** — секція вже їх розрізняє. `return_expenses`→9.3, `transfer_expenses`→9.5.
9. **⚠️ АДРЕСИ НЕ В ЗВІТІ І НЕ В ДОВІДНИКУ.** `_parties.json` дає для осередків лише
   `{id, code, name, is_active}`; `GET /party/report/{id}` не містить адрес. **`GET /party/{id}`**
   (картка) повертає повні `register_address/actual_address/parent/head_info` і для осередків теж.
   → Потрібне **окреме одноразове завантаження карток** усіх id (321 центр + 9532 осередки) —
   `src/card_downloader.py` → `data/raw/_party_cards.json`. Таблиця 1 і колонка `legal_entity_region`
   майже всюди беруться з карток; `party_main_*` — з `card.parent` (для центру = сам).
   Мапінг адрес: `register_address.{country,post_index,region,district,city,street,building,
   building_part_num→korpus,apartments→apartment}` → `legal_entity_*`; `actual_address_same_register`→`is_actual_address`.
   Голова звіту: report-level `head_info.{surname→last,name→first,patronymic→middle}`.
10. **Money-секція (табл. 4) мапінг:** `account_holder→bank_name`, `account_holder_code→bank_edrpou`,
    `account_type→account_type`, `account_number→account_number`, `begin_period_balance→balance_for_first_day_of_period`,
    `report_period_income→income_during_reporting_period`, `report_period_used_funds→spent_during_reporting_period`,
    `end_period_balance→balance_for_last_day_of_period`.
11. **paper (3.4)** — схему добираємо фоновим сканом (рідкісна секція).
