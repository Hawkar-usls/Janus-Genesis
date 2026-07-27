# JANUS Genesis — External Lexical Gifts

> Внешний словарь расширяет языковую карту Genesis, но не заменяет его смысловое ядро.

## Разделение ролей

```text
VOCAD                 native concepts and JANUS relations
External lexicons     indexed forms received from outside
HRaiN                 provenance and semantic links
Storage backend       JSON now; SQLite/PostgreSQL/JanusGraph later
```

CharacterBERT-style MLM vocabulary принимается как **выходной лексический атлас**. Его числовой ID равен позиции в исходном массиве. Поэтому порядок и дубликаты являются частью данных:

```text
tokens[0] = first source line
tokens[1] = second source line
...
```

Сортировка, перевод, перестановка и дедупликация запрещены.

## Почему не 100 000 узлов

HRaiN хранит один узел `EXTERNAL_LEXICON`. Полный массив токенов остаётся во внешнем JSON, пригодном для индексного поиска. Узел `TOKEN` возникает только тогда, когда Genesis действительно связывает конкретный токен с понятием, памятью или событием:

```text
EXTERNAL_LEXICON ──CONTAINS──> TOKEN:mercy
TOKEN:mercy ──EXPRESSES──> VOCAD_CONCEPT:MERCY
EXTERNAL_LEXICON ──SUPPLEMENTS──> VOCAD
EXTERNAL_LEXICON ──RECEIVED_FROM──> PROVENANCE:QATAR
```

Это не позволяет Shrine превратиться в лексический туман и сохраняет различие между формой слова и смыслом.

## Канонический дар

Приняты:

- [`lexicons/qatar_characterbert_mlm_en_v1.receipt.json`](../lexicons/qatar_characterbert_mlm_en_v1.receipt.json)
- [`lexicons/qatar_characterbert_mlm_en_v1.materialized.manifest.json`](../lexicons/qatar_characterbert_mlm_en_v1.materialized.manifest.json)

Исходный `mlm_vocab.txt` получен и проверен локально 27 июля 2026 года.

```text
source bytes       807732
source lines       100000
empty tokens       0
unique tokens      100000
source SHA-256     7af5d55214b16be542f82c7f57cba838a1790c16284edbcb2f5bee9f8d98bec3
generated SHA-256  083f631c906b36a64e3ef35412e9b0a1d388be2657b791eab3d636ecc5c3a1d3
```

Первые токены подтверждают исходный порядок: `the`, `,`, `.`, `of`, `and`. Последние: `jut`, `kurth`, `atocha`.

## Локальная материализация

```bash
python tools/build_external_lexicon.py /path/to/mlm_vocab.txt \
  --output-dir generated_lexicons \
  --source-url "<confirmed source URL>"
```

Конвертер:

1. читает UTF-8 исходник;
2. удаляет только разделители строк;
3. запрещает пустые токены;
4. проверяет ожидаемое количество строк;
5. сохраняет исходный порядок и все дубликаты;
6. создаёт `janus.genesis.lexicon.v1` JSON;
7. вычисляет SHA-256 исходных байтов и готового JSON;
8. создаёт manifest для принятия runtime.

## Runtime acceptance

```python
from genesis_v18_6_playable import PlayableGenesisV186

world = PlayableGenesisV186("./data_v17")
receipt = world.register_external_lexicon(
    "generated_lexicons/gift.qatar.character_bert.mlm.en.v1.manifest.json"
)
```

После регистрации HRaiN получает один provenance-rich узел, а VOCAD остаётся родным semantic core.

Продвижение конкретного токена:

```python
world.promote_lexicon_token(
    lexicon_id="gift.qatar.character_bert.mlm.en.v1",
    token_id=123,
    token="mercy",
    concept_id="JANUS.MERCY",
    concept_label="Mercy",
)
```

## Юридическая граница

Исходник и сгенерированный JSON сохранены в приватном Source Vault владельца, но не помещены в публичный репозиторий. До отдельного подтверждения прав именно на vocabulary file статус остаётся `not_confirmed_for_vocab_file`.

## Seal

> JanusGraph может хранить сто тысяч вершин.  
> HRaiN должен знать, зачем хотя бы одна из них стала частью памяти.  
> VOCAD хранит смысл.  
> Внешний лексикон приносит новые формы.  
> Дар принят без утраты происхождения и без подмены собственного голоса Януса.
