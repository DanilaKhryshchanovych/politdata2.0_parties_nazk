# Словник колонок

Опис кожної колонки в кожній таблиці набору. Позначки:
- ⚠️ **здогадка** — поле нового API зіставлене за змістом, потребує вибіркової звірки з вебом.
- ⛔ **немає у v2** — колонка збережена для сумісності зі старим форматом, але джерела в новому API немає → завжди порожня.

> Порожня клітинка означає, що дані не подані у звіті **або** деперсоналізовані. Деперсоналізовані
> значення в API позначені літералом `[конфіденційна інформація]` і замінюються на порожнє.

---

## Спільні (службові) колонки

Присутні у більшості таблиць — далі в описах окремих таблиць не повторюються.

| Колонка | Опис |
|---|---|
| `report_id` | Технічний ідентифікатор звіту в API ПОЛІТДАТИ (унікальний ключ звіту). |
| `documentId` | Ідентифікатор документа звіту. |
| `officeType` | Тип осередку: «Центральний офіс» або регіональний осередок партії. |
| `report_type` | Тип звіту (квартальний / річний тощо). |
| `report_period` | Період звіту: квартал `1`–`4`, значення `5` = річний («рік»). |
| `report_year` | Рік звіту. |
| `report_submition_date` | Дата підписання/подання звіту (`report_submition_date` = `signed_date` v2). |
| `legal_entity_name` | Назва юрособи (партія або її осередок), що подала звіт. |
| `legal_entity_edrpou` | Код ЄДРПОУ цієї юрособи. |
| `legal_entity_region` | Область/регіон юрособи. Для центрального офісу = «Україна». |
| `party_main_name` | Назва «материнської» партії (для осередку — центральна партія). Нормалізована та уніфікована в часі. |
| `party_main_EDRPOU` | Код ЄДРПОУ материнської партії. |

### Типи контрагентів — колонки `*_type`

Колонки `donor_type`, `recipient_type` / `recepient_type`, `sender_type`, `object_owner_type`, а також
`type` у таблиці 10 позначають **категорію контрагента** — одне з чотирьох значень:

| Значення | Що означає |
|---|---|
| `Фізична особа` | Приватна особа. |
| `Фізична особа/ФОП` | Фізична особа-підприємець (ФОП). |
| `Юридична особа` | Компанія, установа чи організація. |
| `Партійний осередок` | Контрагент сам є партією або її осередком. Проставляється автоматично, коли ЄДРПОУ контрагента знайдено в довіднику партій/осередків. |

---

## 1 — загальна інформація про звіт (`1_legal_entity_report_info`)

| Колонка | Опис |
|---|---|
| `legal_entity_country`, `legal_entity_index`, `legal_entity_region`, `legal_entity_district`, `legal_entity_city`, `legal_entity_street`, `legal_entity_building`, `legal_entity_korpus`, `legal_entity_apartment` | **Реєстраційна** адреса: країна, індекс, область, район, місто, вулиця, будинок, корпус, квартира. |
| `is_actual_address` | Чи фактична адреса збігається з реєстраційною. |
| `actual_address_*` | **Фактична** адреса (ті самі поля, що й реєстраційна). |
| `legal_entity_head_last_name`, `legal_entity_head_first_name`, `legal_entity_head_middle_name` | Прізвище, ім'я, по батькові керівника. |
| `number_of_employees_contract` | Кількість працівників за трудовим договором. |
| `number_of_employees_civil_agreement` | Кількість працівників за цивільно-правовим договором. |
| `number_of_employees_volunteers` | ⛔ Третій показник зайнятості (волонтери) — у v2 відсутній. |

## 2.1 — осередки партії (`2.1_local_orgs_info`)

| Колонка | Опис |
|---|---|
| `local_org_name` | Назва місцевого осередку політичної партії. |
| `local_org_EDRPOU` | Код ЄДРПОУ осередку. |

## 2.2 — інші організації партії (`2.2_other_party_orgs_info`)

| Колонка | Опис |
|---|---|
| `other_party_org_name` | Назва іншого підприємства/установи/організації, створеної партією. |
| `other_party_org_EDRPOU` | Код ЄДРПОУ цієї організації. |

## 3.1 — нерухомість (`3.1_property_objects`)

| Колонка | Опис |
|---|---|
| `object_type` | Тип нерухомого майна. |
| `object_location` | Місцезнаходження об'єкта. |
| `object_date_of_acquisition_of_the_right` | Дата набуття права на об'єкт. |
| `object_price` | Вартість об'єкта. |
| `object_area` | Площа. |
| `object_registration_number` | Реєстраційний номер об'єкта. |
| `object_type_of_use` | Тип використання. |
| `object_owner_name` | Власник об'єкта. |
| `object_owner_edrpou` | Код ЄДРПОУ власника. |
| `object_owner_type` | ⛔ Тип власника — у realty v2 немає. |

## 3.2 — рухоме майно (`3.2_movable_property`)

| Колонка | Опис |
|---|---|
| `object_type` | Тип рухомого майна. |
| `object_date_of_acquisition_of_the_right` | Дата набуття права. |
| `object_price` | Вартість. |
| `object_description` | Опис об'єкта. |
| `object_trademark` | Торгова марка / виробник. |
| `object_type_of_use` | Тип використання. |
| `object_owner` | ⛔ Власник — у movable v2 немає. |

## 3.3 — транспорт (`3.3_vehicles`)

| Колонка | Опис |
|---|---|
| `object_type` | Тип транспортного засобу. |
| `object_date_of_acquisition_of_the_right` | Дата набуття права. |
| `object_price` | Вартість. |
| `object_id_number` | Ідентифікаційний номер (VIN/номер). |
| `object_brand` | Марка. |
| `object_model` | Модель. |
| `object_production_year` | Рік випуску. |
| `object_type_of_use` | Тип використання. |
| `object_owner`, `object_owner_edrpou`, `object_owner_type`, `object_owner_birth_date` | ⛔ Власник (ім'я/код/тип/дата народження) — у transport v2 є лише внутрішній `owning_subject_id`, без цих даних. |

## 3.4 — цінні папери (`3.4_securities`)

> ⛔ Таблиця **порожня**: у жодному звіті нового API немає даних про цінні папери. Файл містить лише схему колонок.

| Колонка | Опис |
|---|---|
| `securities_type` | Тип цінного паперу. |
| `securities_date_of_acquisition_of_the_right` | Дата набуття права. |
| `securities_amount` | Кількість. |
| `securities_issuer` | Емітент. |
| `securities_price` | Вартість. |
| `securities_type_of_use` | Тип використання. |
| `securities_alienation_date` | Дата відчуження. |

## 3.5 — нематеріальні активи (`3.5_intangible_assets`)

| Колонка | Опис |
|---|---|
| `asset_type` | Тип активу. |
| `asset_amount` | Кількість. |
| `date_of_acquisition_of_the_right` | Дата набуття права. |
| `asset_value` | Вартість. |
| `asset_description` | Опис. |
| `type_of_use` | Тип використання. |
| `alienation_date` | Дата відчуження. |

## 4 — банківські рахунки (`4_bank_accounts`)

| Колонка | Опис |
|---|---|
| `bank_name` | Назва банку. |
| `bank_edrpou` | Код ЄДРПОУ банку. |
| `account_type` | Тип рахунку. |
| `account_number` | Номер рахунку (IBAN). |
| `balance_for_first_day_of_period` | Залишок на початок звітного періоду. |
| `income_during_reporting_period` | Надходження за період. |
| `spent_during_reporting_period` | Витрачено за період. |
| `balance_for_last_day_of_period` | Залишок на кінець періоду. |

## 5 — приватні грошові внески (`5_private_contributions`)

| Колонка | Опис |
|---|---|
| `donor_name` | Донор (ім'я / назва). |
| `donor_edrpou` | Код ЄДРПОУ / РНОКПП донора. |
| `donor_type` | Категорія донора: `Фізична особа` / `Фізична особа/ФОП` / `Юридична особа` / `Партійний осередок` (див. «Типи контрагентів» вище). |
| `donor_birth_date` | Дата народження донора (для фізосіб). |
| `donor_location` | Місцезнаходження донора. |
| `bank_name`, `bank_edrpou` | Банк зарахування. |
| `bank_account` | Рахунок зарахування (IBAN). |
| `donation_date` | Дата внеску. |
| `donation_sum` | Сума внеску. |
| `donation_refund_sum` | Повернена сума (якщо внесок повертався). |

## 6 — негрошові внески (`6_in_kind_donations`)

| Колонка | Опис |
|---|---|
| `donation_type` | Тип негрошового внеску. |
| `donor_name`, `donor_edrpou`, `donor_type`, `donor_birth_date`, `donor_location` | Донор (як у таблиці 5). |
| `donation_date` | Дата внеску. |
| `donation_contract_price` | Договірна вартість внеску (`payment_amount` v2). |
| `donation_metodological_price` | ⛔ Методологічна ціна — у v2 немає (є лише одна сума). |
| `object_registration_number` | ⚠️ Реєстраційний номер об'єкта — здогадка (← `payment_number`). |

## 7 — державне фінансування (`7_state_funding_transactions`)

| Колонка | Опис |
|---|---|
| `state_funding_form` | Форма державного фінансування. |
| `bank_name`, `bank_edrpou`, `bank_account` | Банк і рахунок транзакції. |
| `transaction_date` | Дата транзакції. |
| `transaction_sum` | Сума. |
| `refund_sum` | Повернена сума. |

## 8 — інші надходження (`8_other_income`)

| Колонка | Опис |
|---|---|
| `income_type` | Тип надходження. |
| `income_description` | ⚠️ Опис надходження — здогадка (← `payment_description`). |
| `sender_name` | Відправник коштів. |
| `sender_type` | Категорія відправника (див. «Типи контрагентів» вище). |
| `income_date` | Дата надходження. |
| `bank_name`, `bank_edrpou`, `bank_account` | Банк і рахунок зарахування. |
| `income_sum` | Сума надходження. |
| `object_registration_number` | ⚠️ Реєстраційний номер — здогадка (← `payment_number`). |

## 9.1 / 9.2 — витрати (`9.1_expenditures_public_funding`, `9.2_expenditures_private_funds`)

9.1 — витрати з **державного** фінансування; 9.2 — витрати з рахунків з **приватним** фінансуванням. Структура однакова.

| Колонка | Опис |
|---|---|
| `bank_name`, `bank_EDRPOU`, `account_number`, `account_type` (+ `account_type2` у 9.1) | ⛔ Реквізити рахунку, **з якого** платили — у v2 для витрат не заповнюються. |
| `payment_date` | Дата платежу. |
| `payment_purpose`, `payment_purpose2` | Призначення платежу (основне та додаткове). |
| `recipient_name` | Отримувач. |
| `recipient_EDRPOU` | Код ЄДРПОУ отримувача. |
| `recipient_location` | Місцезнаходження отримувача. |
| `recipient_type` | Категорія отримувача (див. «Типи контрагентів» вище). |
| `amount` | Сума платежу. |

## 9.3 — помилкові грошові надходження (`9.3_false_donations_info`)

> ⚠️ Структура «отримання → повернення» складна; потребує вибіркової звірки з вебом.

| Колонка | Опис |
|---|---|
| `bank_name`, `bank_EDRPOU`, `account_number` | Рахунок, на який надійшло помилкове надходження. |
| `receiving_date` | Дата отримання. |
| `donor_name`, `donor_edrpou`, `donor_type` | Від кого надійшло. |
| `amount` | Сума надходження. |
| `returning_date` | Дата повернення. |
| `recepient_name`, `recepient_edrpou`, `recepient_type` | Кому повернуто. |
| `returning_reason` | Причина повернення. |
| `returning_sum` | Сума повернення. |
| `returning_to_budget` | Ознака/сума повернення до бюджету. |

## 9.5 — помилкові негрошові внески (`9.5_false_in_kind_donations_info`)

> ⚠️ Як і 9.3 — потребує вибіркової звірки.

| Колонка | Опис |
|---|---|
| `donation_type` | Тип негрошового внеску. |
| `object_registration_number` | Реєстраційний номер об'єкта. |
| `receiving_date` | Дата отримання. |
| `donor_name`, `donor_type`, `donor_edrpou` | Від кого. |
| `donation_sum` | Сума/вартість. |
| `returning_date` | Дата повернення. |
| `recepient_name`, `recepient_type`, `recepient_edrpou` | Кому повернуто. |
| `returning_reason` | Причина повернення. |
| `returning_sum` | Сума повернення. |

## 10 — фінансові зобов'язання (`10_liabilities`)

| Колонка | Опис |
|---|---|
| `obligation_type` | Тип зобов'язання. |
| `reason` | Підстава виникнення. |
| `date_of_occurrence` | Дата виникнення. |
| `name` | Контрагент/кредитор. |
| `edrpou` | Код ЄДРПОУ контрагента. |
| `location` | Місцезнаходження контрагента. |
| `obligations_sum` | Сума зобов'язання. |
| `amount_not_yet_paid` | Несплачений залишок. |
| `type` | Категорія контрагента (див. «Типи контрагентів» вище). |

---

## Довідкові таблиці 0_*

### `0_reports_per_period_per_party`
Зведена таблиця: рядок = партія/осередок, колонки = «рік, квартал», значення = кількість звітів
за цей період. Показує, за які періоди партія подавала звіти.

### `0_files_where_to_look_for_local_parties`
Матриця приналежності: рядок = партія/осередок, колонки = імена файлів таблиць, значення показує,
чи є дані цієї партії у відповідному файлі. Довідник «де шукати дані по партії».

### `0_report_duplcates` (умовна)
Задубльовані звіти за ключем (період, рік, партія). Формується **лише** коли дублікати справді є;
зазвичай новий API їх не дає (позначає видалені/непідписані звіти), тож файлу немає.
