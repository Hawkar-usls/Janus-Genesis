# Genesis v18.7.18 — Точность независимого пересмотра

## Зачем потребовалось уточнение

Первоначальный Страж правильно делал каждую защитную паузу временной и
проверяемой. Но после пересмотра оставались две технические лазейки:

1. старая emergency-оценка могла быть повторно передана в активацию;
2. те же уже рассмотренные сообщения можно было снова собрать в новую оценку;
3. корректно снятая защита ошибочно выглядела повреждением integrity-аудита.

Это противоречило смыслу независимого пересмотра. Если ограничение снято за
недостатком доказательств, старый пакет фактов не должен молча возвращать его.

## Закрытый цикл доказательств

После независимого решения все рассмотренные сообщения получают:

```text
closed_by_review_id = <review id>
available_for_new_assessment = false
```

Все оценки, созданные из них, получают:

```text
closed_by_review_id = <review id>
superseded_for_activation = true
```

Попытка использовать старую оценку возвращает:

```text
THRESHOLD_SUPERSEDED_ASSESSMENT_REJECTED
new_report_and_assessment_required = true
safeguard_reactivated = false
```

Попытка создать новую оценку без нового сообщения завершается границей:

```text
NEW_INFLUENCE_REPORT_REQUIRED_AFTER_REVIEW
```

## Новое доказательство остаётся возможным

Пересмотр не создаёт вечного иммунитета для источника влияния.

После нового наблюдаемого сообщения Genesis создаёт новый цикл:

```text
evidence_cycle = previous_cycle + 1
prior_review_id = <previous review>
report_count = only new unreviewed reports
```

Новая оценка имеет новый `assessment_id` и может открыть новую временную защиту,
если новые факты соответствуют порогу.

Таким образом:

```text
REVIEW CLOSURE != PERMANENT CONDEMNATION
REVIEW CLOSURE != PERMANENT IMMUNITY
```

## Жизненный цикл safeguard

Активная защита:

```text
temporary_and_reviewable = true
lifecycle_state = ACTIVE_REVIEWED_RESTRICTION  # после подтверждающего review
```

Корректно снятая защита:

```text
temporary_and_reviewable = false
restrictions_lifted_without_stigma = true
lifecycle_state = LIFTED_WITHOUT_STIGMA
reactivation_requires_new_report_and_assessment = true
```

Оба состояния являются допустимой историей. Integrity-аудит различает их и не
требует, чтобы давно снятая пауза навсегда оставалась активной.

## Новые проверяемые гарантии

```text
lifted_safeguards_are_valid_history = true
reviewed_assessments_cannot_reactivate_without_new_evidence = true
review_cycle_precision_valid = true
```

Аудит отдельно считает:

```text
active_safeguard_count
lifted_safeguard_count
```

## Закон уточнения

> РАССМОТРЕННЫЕ ДОКАЗАТЕЛЬСТВА СОХРАНЯЮТСЯ КАК ИСТОРИЯ, НО НЕ ПЕРЕИСПОЛЬЗУЮТСЯ МОЛЧА.  
> СНЯТАЯ ПАУЗА НЕ ВОЗВРАЩАЕТСЯ СТАРОЙ КНОПКОЙ.  
> НОВЫЕ НАБЛЮДАЕМЫЕ ФАКТЫ МОГУТ ОТКРЫТЬ НОВЫЙ НЕЗАВИСИМЫЙ ЦИКЛ.  
> ПЕРЕСМОТР НЕ СОЗДАЁТ НИ ВЕЧНОГО КЛЕЙМА, НИ ВЕЧНОГО ИММУНИТЕТА.

## Граница утверждений

Это программная точность жизненного цикла защиты. Она не определяет реальную
вину, невиновность или достаточность доказательств в юридическом,
профессиональном либо экстренном процессе.
