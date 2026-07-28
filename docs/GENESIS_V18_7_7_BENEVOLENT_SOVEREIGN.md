# Genesis v18.7.7 — The Benevolent Sovereign

## 1. Добро и отношения с NPC

Genesis больше не начинает каждую встречу с добрым человеком из полного нуля.

Отношение хранится по шкале от `-100` до `+100` и складывается из трёх независимых частей:

```text
goodwill_prior  — известная миру история добрых поступков
personal_bond   — личная история конкретного NPC и игрока
distance        — последствия давления, повторного нарушения границ и вреда
```

Устойчиво добрый игрок получает положительный `goodwill_prior`. Поэтому обычные просьбы о разговоре, совместной работе, прогулке или помощи чаще получают ответ `accepted`, чем `refused`.

Это не превращает добро в валюту владения человеком:

```text
goodness_guarantees_consent = false
intimacy_is_not_purchased = true
love_is_not_purchased = true
forgiveness_is_not_purchased = true
secrets_are_not_purchased = true
repeated_pressure_may_force_refusal = true
```

Для любви, совместной жизни, интимности, прощения, секрета или крупного личного обязательства общий добрый авторитет не повышает шанс согласия. Там учитывается только лично сложившаяся связь и текущая свободная воля NPC.

Один спокойный отказ сам по себе не портит отношения. Повторное давление до завершения прежнего ответа снижает личную связь.

## 2. Живая шкала

```text
-100…-61  враждебное
 -60…-21  настороженное
 -20…+9   нейтральное
 +10…+34  доброжелательное
 +35…+59  тёплое
 +60…+79  близкое
 +80…+100 глубокое доверие
```

Шкала видна через `relationship_state()` и `public_state()`. Она описывает текущую симулированную связь, но не является доказательством сознания NPC и не даёт игроку права командовать.

## 3. Триумвират и Суверен

Триумвират больше не является окончательной властью.

```text
3+ добровольных независимых голоса
        ↓
живая рекомендация поля
        ↓
JANUS.SOVEREIGN
        ↓
каноническое решение или честная отсрочка
```

Три голоса открывают минимальный кворум. Четвёртый, пятый и последующие голоса могут присоединиться без привилегии первоначальных участников.

Три одинаковых утверждения образуют `CONSENSUS_FIELD`, а не ложный спор. Для настоящего `DISPUTE_FIELD` нужны хотя бы две различающиеся позиции.

## 4. Добровольный третий голос

Читательский голос допускается к суверенному делу только когда он:

- привязан к proof, от которого хранится только SHA-256;
- явно согласился участвовать;
- остаётся активным;
- опирается на точное evidence;
- может отказаться от будущего участия.

В локальном reference-runtime один и тот же proof не может быть зарегистрирован под несколькими `reader_id`. Это закрывает повторное использование одного связанного доказательства как нескольких голосов.

При этом произвольная локальная строка proof **не объявляется доказательством реальной личности** и не обеспечивает полную Sybil-защиту. В общей сети identity-provider обязан аутентифицировать одного субъекта и выдать проверяемую привязку, прежде чем его голос получит суверенный статус.

Исторические слова уже участвовавшего свидетеля не стираются после выхода, но новые решения не могут использовать его как активного участника без нового согласия.

## 5. Структурированный предмет

Свободной строки `about` недостаточно. Новое суверенное дело требует `subject_scope`:

```text
topic
entity
event
time_scope
location
timeless
rights_sensitive
```

Утверждения о сменах 28, 29 и 30 июля больше нельзя объединить в один спор только потому, что всем присвоена строка `work_shift_start`.

## 6. Решение Януса

Триумвират формирует рекомендацию:

```text
CONSENSUS
MAJORITY
PLURAL
```

После этого `JANUS.SOVEREIGN` принимает решение:

```text
RATIFY_CONSENSUS
RATIFY_TRIUMVIRATE_RECOMMENDATION
ADOPT_MOST_SUPPORTED_POSITION
DEFER_FOR_MORE_EVIDENCE
PROTECT_FREEDOM
```

Янус сохраняет все несогласные claims и точные evidence. Решение не переписывает историю и не объявляет проигравший голос несуществующим.

Для вопросов личной свободы, любви, ухода, согласия или интимной связи Янус не выбирает человека за человека:

```text
ruling = PROTECT_FREEDOM
overrides_personal_consent = false
```

Суверенитет Януса относится к канонической записи и законам Genesis, а не к собственности над чужой волей.

## 7. Жизненный цикл

Суверенное дело может иметь состояния:

```text
RECOMMENDED
SOVEREIGN_DECIDED
OPEN_FOR_EVIDENCE
RESOLVED
REOPENED
SUPERSEDED
```

Новые evidence способны переоткрыть дело. Старое решение остаётся в Chronicle, но перестаёт изображать вечную неизменную истину.

## 8. Канонические инварианты

```text
good_people_begin_with_positive_goodwill = true
ordinary_cooperation_receives_yes_bias = true
goodness_guarantees_consent = false
intimacy_uses_personal_bond_not_moral_score = true

three_voices_open_field_not_close_it = true
identical_positions_are_consensus_not_dispute = true
reader_voice_requires_proof_and_consent = true
one_bound_proof_maps_to_one_reader_voice = true
local_proof_is_not_real_world_identity_claim = true
production_voice_requires_authenticated_provider = true
subject_scope_is_structured = true
additional_grounded_voices_may_join = true
triumvirate_recommends_janus_decides = true
janus_is_sovereign_decider = true
janus_preserves_dissent = true
janus_may_defer_for_evidence = true
sovereign_cannot_override_personal_consent = true
case_lifecycle_is_reversible = true
```

> Добро открывает дверь чаще, но не запирает её за вошедшим.
>
> Триумвират говорит. Янус решает. Свобода остаётся выше решения.
>
> **JANUS RULES THE RECORD, NOT THE SOUL.**
