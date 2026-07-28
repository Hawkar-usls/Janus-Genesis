# Genesis v18.7.8 — The Unbought Voice

## 1. Зачем появился этот слой

Genesis не должен путать общественное мнение с количеством публикаций.

```text
1000 аккаунтов ≠ 1000 независимых людей
1000 репостов ≠ 1000 независимых доказательств
большой охват ≠ истинность
реклама ≠ свидетельство
координация ≠ консенсус
```

`The Unbought Voice` защищает суверенные решения Януса от фейковых аккаунтов, SMM-сеток, скрытой рекламы, скрытой автоматизации, подмены личности и искусственного большинства.

Это не универсальный детектор лжи и не цензор. Слой проверяет происхождение, независимость и раскрытие интересов, а не объявляет неудобное мнение ложным.

## 2. Influence-sensitive scope

Обычные частные дела продолжают работать по прежним законам. Защитный контур включается для предметов, отмеченных:

```text
influence_sensitive = true
public_opinion = true
```

Такой предмет требует отдельной проверки каждого голоса до формирования кворума.

## 3. Учёт голоса

Для каждого участника сохраняются только хеши proof:

```text
identity_proof_sha256
controller_proof_sha256
evidence_family
message_fingerprint
campaign_cluster
```

Сырые proof не записываются.

Для суверенного веса нужны:

- активный аккаунт;
- аутентифицированный identity-provider;
- раскрытый оператор;
- точное grounded evidence;
- раскрытие спонсора, когда публикация оплачена;
- раскрытие автоматизации, когда действует бот;
- раскрытие кампании, когда сообщения координируются.

Локальная proof-строка не выдаётся за проверку реального человека. В производственной сети требуется настоящий аутентифицированный provider.

## 4. Защита от ферм аккаунтов

Несколько аккаунтов с одним `controller_proof` образуют один coordination-cluster.

```text
один оператор → один независимый вес
```

Остальные claims не удаляются. Они сохраняются как amplification, но не создают дополнительные голоса.

Один identity-proof также нельзя зарегистрировать как несколько разных reader-голосов.

## 5. SMM

Открытая SMM-кампания разрешена говорить, но не изображает органическое большинство.

```text
раскрытая кампания из 50 аккаунтов → один координированный источник
```

Нераскрытая кампания не получает суверенного веса до раскрытия происхождения.

Genesis не утверждает, что любая похожая формулировка является SMM. Совпадение exact-message и одного evidence-family учитывается как amplification, а не как приговор людям.

## 6. Скрытая реклама и боты

```text
sponsored = true + sponsor отсутствует
    → SPONSORSHIP_NOT_DISCLOSED

automation = true + automation_disclosed = false
    → AUTOMATION_NOT_DISCLOSED
```

Такие claims остаются в реестре, но не участвуют в формировании независимого кворума.

## 7. Обман и обвинение в обмане

Жалоба сама по себе не может заставить замолчать человека.

```text
record_manipulation_evidence(...)
    → PENDING_REVIEW
```

Пока evidence не проверено, голос не теряет вес.

Подтвердить манипуляцию может только:

```text
JANUS.SOVEREIGN
```

После проверки возможны категории:

```text
FAKE_IDENTITY
HIDDEN_SPONSORSHIP
SHARED_CONTROLLER
CONTENT_FABRICATION
AUTOMATION_CONCEALMENT
IMPERSONATION
```

Ложное или недостаточное обвинение может быть отклонено. Это защищает антифейковую механику от превращения в инструмент травли и цензуры.

## 8. Audit

`audit_influence_claims()` возвращает:

```text
submitted_claim_ids
eligible_claim_ids
quarantined_claim_ids
reasons_by_claim
independent_voice_count
controller_cluster_count
message_evidence_cluster_count
controller_collisions
mirrored_amplification
explicit_manipulation_evidence_count
risk_level
```

Каждый claim относится либо к eligible, либо к quarantined. Ни один claim не исчезает.

## 9. Янус и кворум

В influence-sensitive деле триумвират открывается только после трёх независимо допустимых голосов.

```text
искусственный кворум → не открывает суверенное большинство
```

Если уже открытое дело позднее теряет проверенный кворум, Янус принимает:

```text
DEFER_FOR_AUTHENTICITY_AUDIT
```

Это не означает, что quarantined claim ложен. Это означает, что его нельзя использовать как независимый голос до завершения проверки.

## 10. Несогласие защищено

Разные позиции не являются признаком манипуляции.

```text
dissent_is_not_manipulation = true
suspicion_is_not_a_truth_verdict = true
```

Подлинный участник с доказанным происхождением может выступать против большинства, против триумвирата и против прежнего решения Януса. Его dissent сохраняется.

## 11. Канонические инварианты

```text
reach_is_not_evidence = true
repetition_is_not_independent_support = true
same_controller_counts_as_one_voice = true
same_message_and_evidence_counts_as_amplification = true
paid_influence_requires_disclosure = true
automation_requires_disclosure = true
influence_sensitive_quorum_requires_authenticated_provider = true
suspicion_is_not_a_truth_verdict = true
dissent_is_not_manipulation = true
manipulation_accusation_requires_evidence = true
quarantined_claims_are_preserved_not_deleted = true
janus_may_defer_for_authenticity_audit = true
```

> Голос нельзя купить количеством его копий.
>
> Масса повторений не превращается в массу свидетельств.
>
> Янус защищает право говорить — и право мира знать, кто на самом деле говорит.
>
> **THE VOICE MAY BE LOUD. THE VOICE MUST STILL BE ITS OWN.**
