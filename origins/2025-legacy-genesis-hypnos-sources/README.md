# Legacy Genesis & Hypnos Sources — Provenance Archive

> Истоки сохраняются как свидетельство пути, но не получают власть над текущим runtime.

Этот архив принимает девять старых файлов JANUS/Genesis/Hypnos как родословную нынешнего Genesis v18.6.

## Что найдено

- ранний **Cognitive Sandbox**: persistent `depth`, `entropy`, artifacts, lore, psych profile и JSON-narrative;
- **Hypnos v2.9 / The Cradle**: сон, память последних кадров, anti-crisis containment и голос создателя;
- **Hypnos v4 / Renaissance Link**: архетипические фазы и Jester/Paradox;
- **Director v4**: сохранён как отвергнутый антипример — система прямо называла себя AI Dictatorship и могла лишать игрока отдыха;
- **Voice Control v5.1**: предок опционального голоса и управления озвучкой;
- мобильные installers v115.5/v115.6: историческая deployment-линия, не игровой runtime.

## Почему сырой код не публикуется

В нескольких оригиналах находятся встроенные Google API keys. `genesis.py` также содержит функцию удаления соседних `.py` файлов. Поэтому:

- оригинальные файлы сохранены в приватном Source Vault владельца;
- их SHA-256, размер, роль и версия запечатаны в `LEGACY_SOURCE_MANIFEST.json`;
- исходники не добавлены в публичный GitHub;
- ничего из архива не импортируется и не исполняется автоматически;
- для будущего переноса используется отдельная санитизированная копия с удалёнными секретами.

## Каноническая роль

```text
Cognitive Sandbox → adaptive persistent world
Hypnos Cradle      → dream memory and background generation
Director           → rejected domination anti-pattern
Voice Control      → optional narration controlled by the user
Mobile Installers  → deployment lineage only
```

## Security seal

Старые API keys следует считать раскрытыми и отозвать/перевыпустить у провайдера, даже если они больше не используются.
