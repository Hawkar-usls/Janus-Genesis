# PLA Janus Genesis

> **Не моделируй заново. Дай Янусу существующую модель — и позволь ему искать её более сильную, лёгкую и печатаемую форму.**

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Project status](https://img.shields.io/badge/status-foundation-orange)](docs/ROADMAP.md)

**PLA Janus Genesis** — открытая physics-first лаборатория преобразования существующих 3D-моделей для FDM-печати. Пользователь кладёт STL/OBJ/PLY в папку `workspace/inbox`, задаёт принтер, PLA, защищённые зоны и нагрузки, а Janus строит и сравнивает улучшенные варианты.

Цель проекта — минимальный расход филамента при заданной прочности, печатаемости и сохранении обязательной геометрии.

## Главный принцип

Janus не должен «рисовать убедительную форму» и объявлять её прочной. Каждый кандидат проходит измеримые стадии:

```text
existing model
    -> mesh validation and repair
    -> protected geometry contract
    -> print orientation search
    -> load cases and FEA
    -> topology/lattice transformation
    -> manufacturability filters
    -> slicing estimates
    -> Pareto selection
    -> physical validation
```

## Текущий статус

Репозиторий содержит **Foundation MVP**:

- пакетная загрузка моделей из папки;
- STL, OBJ и PLY;
- проверка и консервативный ремонт сетки;
- поиск базовой ориентации печати по эвристике нависаний;
- сравнение исходной и преобразованной модели;
- экспорт кандидата и JSON-отчёта;
- конфигурация Bambu Lab A1 + PLA;
- контракт будущих protected regions и load cases.

**Важно:** текущая foundation-версия ещё не выполняет FEA и топологическую оптимизацию, поэтому не заявляет доказанное увеличение прочности. Она создаёт безопасный и воспроизводимый входной слой для следующих этапов.

## Быстрый запуск на Windows

```powershell
git clone https://github.com/Hawkar-usls/Janus_Genesis.git
cd Janus_Genesis
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
janus-genesis init-workspace
```

Положи модель в:

```text
workspace/inbox/my_model.stl
```

Запусти преобразование:

```powershell
janus-genesis run
```

Результаты появятся здесь:

```text
workspace/outbox/my_model__janus_candidate.stl
workspace/reports/my_model__janus_report.json
```

Анализ одной модели без пакетного режима:

```powershell
janus-genesis analyze path\to\model.stl
```

## Структура проекта

```text
src/janus_genesis/     код конвейера
workspace/inbox/       входные модели
workspace/outbox/      преобразованные кандидаты
workspace/reports/     измерения и отчёты
examples/              пример контракта модели
schemas/               JSON Schema
scripts/               удобный запуск на Windows
docs/                  архитектура, roadmap и правила проверки
```

## Контракт модели

Рядом с `my_model.stl` можно разместить `my_model.janus.json`. В будущих этапах он будет определять:

- поверхности и отверстия, которые нельзя менять;
- зоны приложения сил;
- закрепления;
- направления нагрузок;
- допустимую деформацию;
- минимальную толщину;
- запрет поддержек;
- целевой запас прочности.

Пример находится в [`examples/bracket.janus.json`](examples/bracket.janus.json).

## Что означает «лучшая модель»

Одной абсолютно лучшей формы не существует. Janus будет искать Pareto-набор:

- минимальная масса;
- максимальная жёсткость;
- необходимый safety factor;
- минимум поддержек;
- минимальное время печати;
- устойчивость к нескольким сценариям нагрузки.

## Дорожная карта

1. **Foundation** — импорт, ремонт, ориентация, отчёт. `ACTIVE`
2. **Printability** — стенки, нависания, мосты, сопло, слои.
3. **Physics** — Gmsh + CalculiX/FEniCSx, несколько load cases.
4. **Transformation** — topology optimization и stress-aware lattice.
5. **Evolution** — популяция кандидатов и Pareto-отбор.
6. **Calibration** — обучение на реально напечатанных образцах.

Подробно: [`docs/ROADMAP.md`](docs/ROADMAP.md).

## Инженерная честность

Симуляция не является сертификатом. PLA анизотропен, ползёт под длительной нагрузкой и зависит от температуры, влажности, ориентации слоёв и профиля печати. Критические детали должны проходить реальные испытания. См. [`docs/VALIDATION.md`](docs/VALIDATION.md).

## Лицензия

MIT © 2026 Hawkar-usls
