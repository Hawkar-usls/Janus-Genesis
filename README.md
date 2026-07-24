# Janus Genesis — Golden Mirror MMO Foundation

Janus Genesis снова является игрой: бесконечной интерактивной песочницей, где история реагирует на решения игрока, сохраняет хронику и постепенно открывает общий мир совместного творчества.

Проект восстановлен из оригинальной линии Mirror Protocol, Trinity Engine, Black Box и Sleeping Overseer. Golden Mirror делает созидание главным способом развития: небезопасные действия не затрагивают других участников, а конструктивные решения открывают больше свободы и инструментов.

## Главный цикл

Reflection Instance → доверие и созидание → God Mode → Utopia Shard → совместное строительство.

Явный выход из игры всегда выполняется сразу — в том числе команды с обычной пунктуацией: `выйти!`, `exit.`.

## Возвращённые механики

- Trinity Engine: Архитектор, Творец и Трикстер меняют стиль повествования.
- Golden Mirror: локальная детерминированная проверка действий.
- Adaptive Psyche: свет, доверие, энтропия, глубина и архив эха.
- Instant Sync: атомарное сохранение после каждого хода.
- Genesis Chronicle: JSONL-хроника с SHA-256 цепочкой событий.
- Process-Safe Black Box: блокировки между несколькими MMO-воркерами.
- Dream Bridge: экспорт приключений в `dreams.json` для Janus Core.
- MMO Gateway: маршрутизация Reflection и Utopia.
- Offline First: игра работает без внешней модели; Gemini является необязательным рассказчиком.

## Запуск

Требуется Python 3.11 или новее.

Windows: запусти `START_JANUS_GENESIS.bat`.

Терминал:

```bash
python janus_genesis.py
```

Один ход с JSON-ответом:

```bash
python janus_genesis.py --action "Помочь построить мост"
```

Проверка всей хеш-цепочки хроники:

```bash
python janus_genesis.py --verify-chronicle
```

Для AI-нарратора значение `GEMINI_API_KEY` задаётся только через переменную окружения. Ключи не должны попадать в Git или игровые сохранения.

## Интеграция

```python
from janus_genesis import JanusWorld

world = JanusWorld(data_dir="./data")
reply = world.process_action("player-1", "Помочь построить мост")
print(reply.to_dict())
```

## Архив PLA-направления

Предыдущее PLA-состояние сохранено в ветке `archive/pla-genesis-before-game-restore`. Оно не уничтожено и может быть перенесено в отдельный репозиторий.

## Проверка

```bash
python -m unittest discover -s tests -v
```

Сейчас это восстановленная MMO foundation: локальная игра, память, Golden Mirror и маршрутизация работают. Сетевой transport, аккаунты, общая база мира, протокол взаимного согласия/party и Unreal-клиент ещё предстоит создать.

MIT © Hawkar-usls
