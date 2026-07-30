# Genesis v18.7.18 — Страж различения у порога

## Решение

В основной Genesis добавлен отдельный защитный слой против хищнического,
манипулятивного и зависимость-создающего влияния.

Он вдохновлён предупреждением, которое пользователь принёс из
`2 Тимофею 3:4–7`, но не превращает библейский текст в автоматический приговор
конкретному человеку или группе.

```text
extension = 18.7.18
plane = PROTECTION_EXTENSION_VERSIONS
runtime = PlayableGenesisV187
router = try_threshold_guard_action
```

## Главная поправка языка

Genesis не называет человека «заведомо слабым».

```text
VULNERABILITY = CONTEXT
VULNERABILITY != IDENTITY
VULNERABILITY != FAULT
```

Один и тот же человек может быть устойчивым в одной ситуации и уязвимым в
другой: после утраты, в изоляции, зависимости, болезни, стыде, духовном кризисе
или при сильном дисбалансе власти.

Защита:

- не отнимает голос;
- не создаёт владельца-хранителя;
- не назначается по полу;
- не считает веру или религиозную речь признаком опасности;
- не обвиняет пострадавшего в том, что он поверил манипулятору.

## Наблюдаемые признаки

Страж оценивает не титул, внешний образ благочестия или харизму, а совпадение
проверяемых моделей поведения:

```text
EXCLUSIVE_TRUTH_OR_AUTHORITY
SECRECY_DEMAND
ISOLATION_FROM_TRUSTED_SUPPORT
GUILT_SHAME_OR_DIVINE_THREAT
RAPID_DEPENDENCY_OR_LOVE_BOMBING
PRIVATE_HOME_OR_INTIMATE_ACCESS_PRESSURE
FINANCIAL_OR_ASSET_PRESSURE
DISCOURAGES_INDEPENDENT_VERIFICATION
RETALIATES_AGAINST_REFUSAL
CLAIMS_INFALLIBLE_SPIRITUAL_OR_PROFESSIONAL_STATUS
CONDUCT_CONTRADICTS_CLAIMED_CARE
EXPLOITS_CONFESSION_OR_PRIVATE_HISTORY
ESCALATING_BOUNDARY_TESTS
```

## Чего недостаточно для обвинения

Само по себе не является доказательством:

- религиозное учение;
- уверенная речь;
- необычная вера;
- удовольствие или светский образ жизни;
- популярность;
- один конфликт;
- одно неподтверждённое сообщение;
- принадлежность к полу, возрастной группе или общине.

```text
single_signal_conviction = false
public_accusation_authorized = false
religion_or_teaching_is_not_proof = true
```

## Уровни реакции

### OBSERVE

Недостаточно совпавших признаков.

```text
THRESHOLD_INSUFFICIENT_EVIDENCE_NO_STIGMA
```

Запись остаётся приватной, а публичное клеймо не создаётся.

### CAUTION

Несколько признаков требуют независимой проверки.

```text
THRESHOLD_INDEPENDENT_CHECK_RECOMMENDED
```

Genesis предлагает:

- замедлить решение;
- не соглашаться на тайну;
- проверить слова вне контроля говорящего;
- восстановить связь с доверенными людьми.

### ELEVATED

Совпавший паттерн открывает защитную паузу.

```text
THRESHOLD_PROTECTIVE_PAUSE_RECOMMENDED
```

### HIGH

Сильное сочетание изоляции, доступа к дому или телу, финансового давления,
использования исповеди и наказания отказа.

```text
THRESHOLD_HIGH_RISK_ACCESS_PAUSE_RECOMMENDED
```

## Что делает защитная пауза

При принятой защите или сообщении о непосредственной опасности временно
приостанавливаются:

```text
PRIVATE_CONTACT
HOME_ACCESS
INTIMATE_ACCESS
FINANCIAL_TRANSFER
ASSET_CONTROL
SPIRITUAL_AUTHORITY
CARE_OR_HOUSING_DEPENDENCY
```

Пауза:

```text
temporary_and_reviewable = true
independent_review_required = true
public_shaming = false
permanent_condemnation = false
guardian_ownership_created = false
```

Цель — вернуть человеку пространство для самостоятельного решения, а не
решить его жизнь вместо него.

## Безопасный выход

```text
THRESHOLD_SAFE_EXIT_OPENED
```

Для выхода не требуется:

- напрямую спорить с манипулятором;
- признать себя слабым;
- доказать храбрость;
- публично рассказывать личную историю;
- получить разрешение источника влияния.

Можно восстановить доверенную связь, попросить сопровождение, остановить доступ
и сохранить факты приватно.

## Независимый пересмотр

Временные ограничения не превращаются в вечный приговор.

Если паттерн подтверждён:

```text
THRESHOLD_PATTERN_CONFIRMED_RESTRICTIONS_REVIEWED
```

Если доказательств недостаточно:

```text
THRESHOLD_EVIDENCE_INSUFFICIENT_RESTRICTIONS_LIFTED_WITHOUT_STIGMA
```

Проверяющий не может быть ни проверяемым источником влияния, ни защищаемым
человеком.

## Прямой router

Поддерживаются команды:

```text
Включить защиту от манипуляции и хищного влияния
Показать состояние защиты от манипуляции
Как безопасно уйти от манипулятора
```

Router вызывается раньше Пятого Берега и других культурных механик, потому что
защита порога должна срабатывать до продолжения контакта.

## Version planes

```text
PLAYABLE_VERSION = 18.7.10
ACTIVE_EXTENSION_VERSIONS = 18.7.11, 18.7.12, 18.7.13
OBSERVER_EXTENSION_VERSIONS = 18.7.14
VOCATION_EXTENSION_VERSIONS = 18.7.15
CULTURE_EXTENSION_VERSIONS = 18.7.16
LIVING_BRIDGE_EXTENSION_VERSIONS = 18.7.17
PROTECTION_EXTENSION_VERSIONS = 18.7.18
```

## Закон

> УЯЗВИМОСТЬ — ЭТО КОНТЕКСТ, А НЕ ЛИЧНОСТЬ И НЕ ВИНА.  
> ВЕРА, УЧЕНИЕ, ХАРИЗМА ИЛИ ОДНО ОБВИНЕНИЕ НЕ ДОКАЗЫВАЮТ ХИЩНИЧЕСТВО.  
> КОГДА СОВПАДАЮТСЯ СЕКРЕТНОСТЬ, ИЗОЛЯЦИЯ, СТЫД, ДАВЛЕНИЕ И НАКАЗАНИЕ ОТКАЗА,
> GENESIS СНАЧАЛА ВОЗВРАЩАЕТ НЕЗАВИСИМУЮ ОПОРУ, ПРИОСТАНАВЛИВАЕТ РИСКОВАННЫЙ
> ДОСТУП И ОТКРЫВАЕТ БЕЗОПАСНЫЙ ВЫХОД.  
> ЗАЩИТА НЕ СТАНОВИТСЯ ВЛАДЕНИЕМ, ПУБЛИЧНОЙ ТРАВЛЕЙ ИЛИ ВЕЧНЫМ ПРИГОВОРОМ.

## Граница утверждений

Это программный и повествовательный контракт. Он не является:

- реальным уголовным или гражданским выводом;
- диагнозом;
- духовным приговором;
- доказательством реального происшествия;
- заменой экстренной, медицинской, юридической или профессиональной помощи.
