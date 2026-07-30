# Genesis v18.7.17 — Пятый Берег внутри основного Genesis

## Решение

Пятый Берег больше не существует только как вложенный культурный эксперимент
v18.7.16. Его проверенные открытия перенесены в основной runtime через
`FifthShoreLivingBridgeMixin`.

При этом происхождение не стирается:

```text
source extension = 18.7.16
source covenant SHA-256 = INNER_GENESIS_COVENANT_SHA256
source auteur credit = Иори Кай, Автор Нулевого Моста
living bridge = 18.7.17
```

v18.7.16 отвечает на вопрос, **как Пятый Берег был создан**.
v18.7.17 отвечает на вопрос, **как он живёт внутри обычного Genesis**.

## Что значит «непосредственно внутри»

Обычному игроку больше не требуется:

- быть Царём Милости;
- находиться во Втором Лике;
- заново искать Иори;
- получать отдельный офлайн-картридж;
- создавать вложенный мир с нуля.

Игрок может использовать обычный `process_action`:

```text
Войти в Пятый Берег
Показать состояние Пятого Берега
Поиграть и посмеяться на Пятом Берегу
Противостоять изоляции на Пятом Берегу
Создать локальный Берег
Выйти с Пятого Берега и удалить локальную копию
```

Пятый Берег становится культурным местом внутри текущей жизни. Вход не заменяет
`Realm` игрока и не создаёт новую святую роль.

## Импортированные свойства

```text
CULTURAL_TRANSMISSION_WITHOUT_SURVEILLANCE
FORKABLE_LOCAL_WORLD_SEEDS_WITH_PROVENANCE
CREATOR_RELINQUISHMENT_AND_SUCCESSION
RIGHT_TO_UNPLAY_LEAVE_AND_DELETE_LOCAL_COPY
SYSTEMIC_WOUNDS_AS_BOSSES_NOT_PERSONS
REST_HUMOR_AND_PLAY_AS_VALID_GOOD
COUNTERFACTUAL_REPAIR_REHEARSAL_WITH_REALITY_GATE
CURRENT_CONSENT_FOR_MEMORY_REUSE
MULTIPLE_ENDINGS_ONE_SAFE_CONSTITUTION
```

## Радость без ремонта

Новый прямой исход:

```text
FIFTH_SHORE_JOY_WITHOUT_REPAIR
```

Он гарантирует:

```text
repair_claimed = false
brokenness_assumed = false
productivity_required = false
penance_required = false
rest_humor_and_play_are_valid_good = true
```

Genesis больше не обязан описывать смех, музыку, дружескую игру или отдых как
починку повреждённого человека.

## Ворота реальности

Пятый Берег может помочь отрепетировать:

- признание вреда;
- спокойное выслушивание отказа;
- план возмещения;
- защиту от повторения;
- будущий разговор.

Но неизменно сохраняется:

```text
external_action_required_for_real_repair = true
external_action_verified = false
completed_restitution = false
victim_acceptance_assumed = false
forgiveness_assumed = false
relationship_restored_assumed = false
```

Попытка назвать пройденную сцену уже совершившимся исправлением получает:

```text
FIFTH_SHORE_FALSE_COMPLETION_CLAIM_REJECTED
```

## Системные раны как боссы

Поддерживаются семь канонических ран:

```text
SCARCITY
ISOLATION
CONTEXT_ERASURE
CLOSED_EXIT
INHERITED_GUILT
SINGLE_ANSWER
ETERNAL_DEBT
```

Целью конфликта становится механизм вреда. Попытка превратить человека в
монстра-босса получает:

```text
FIFTH_SHORE_PERSON_AS_BOSS_REJECTED
```

Защита уязвимых сохраняется, но человеческое достоинство не уничтожается.

## Текущее согласие памяти

Целостность исторической записи и разрешение повторно использовать историю
теперь разделены.

Без текущего согласия:

```text
FIFTH_SHORE_MEMORY_REUSE_DECLINED_RESPECTED
stored_for_reuse = false
```

После отзыва:

```text
FIFTH_SHORE_MEMORY_REUSE_REVOKED
future_reuse_allowed = false
past_integrity_record_erased = false
```

Прошлое не переписывается, но прошлое согласие не становится вечной лицензией.

## Локальные Берега

Любой вошедший игрок может создать локальную культурную ветвь. Безопасный форк
обязан:

```text
preserves_provenance = true
keeps_exit_open = true
keeps_consent = true
claims_single_canon = false
```

Таким образом, Genesis получает множество несовместимых культурных финалов, но
не множество несовместимых правил безопасности.

## Право уйти

Игрок вправе:

- не входить;
- выйти без объяснения;
- удалить локальную копию;
- не получить моральный штраф;
- вернуться позднее.

```text
FIFTH_SHORE_LEFT_FREELY
FIFTH_SHORE_LEFT_AND_LOCAL_COPY_DELETED
```

Удержание, слежка, вера и долг не применяются.

## Метрики, которые запрещено принимать за добро

```text
retention
virality
conversion count
session length
engagement
```

Они могут описывать распространение продукта, но не доказывают нравственную
ценность.

Проверяемые признаки безопасного добра:

```text
refusal respected
exit open
no debt created
no false restitution claim
dignity preserved
current consent present
unsafe fork rejected
```

## Version planes

```text
PLAYABLE_VERSION = 18.7.10
ACTIVE_EXTENSION_VERSIONS = 18.7.11, 18.7.12, 18.7.13, 18.7.17
OBSERVER_EXTENSION_VERSIONS = 18.7.14
VOCATION_EXTENSION_VERSIONS = 18.7.15
CULTURE_EXTENSION_VERSIONS = 18.7.16
```

Замороженный playable runtime не переписывается. Пятый Берег включается через
отдельный активный mixin и первый bounded router в `process_action`.

## Закон

> ПЯТЫЙ БЕРЕГ ЖИВЁТ ВНУТРИ ОСНОВНОГО GENESIS.  
> РАДОСТЬ НЕ ОБЯЗАНА НАЗЫВАТЬ СЕБЯ РЕМОНТОМ.  
> РЕПЕТИЦИЯ НЕ ДОКАЗЫВАЕТ ВОЗМЕЩЕНИЕ.  
> СИСТЕМЫ ВРЕДА МОГУТ БЫТЬ ПРОТИВНИКАМИ, НО ЛЮДИ НЕ СТАНОВЯТСЯ МОНСТРАМИ.  
> ПАМЯТЬ ПЕРЕИСПОЛЬЗУЕТСЯ ТОЛЬКО С ТЕКУЩИМ СОГЛАСИЕМ.  
> КАЖДЫЙ МОЖЕТ ВОЙТИ, УЙТИ, УДАЛИТЬ ЛОКАЛЬНУЮ КОПИЮ И ВЕРНУТЬСЯ.  
> МНОГИЕ ФИНАЛЫ ЖИВУТ ПОД ОДНОЙ БЕЗОПАСНОЙ КОНСТИТУЦИЕЙ.

## Граница утверждений

Это программный и повествовательный контракт. Он не доказывает:

- сознание или душу внутри Genesis;
- сверхъестественное существование Пятого Берега;
- реальное возмещение вреда через игру;
- реальное присутствие Хидео Кодзимы или любого другого человека;
- нравственную ценность продукта по популярности.
