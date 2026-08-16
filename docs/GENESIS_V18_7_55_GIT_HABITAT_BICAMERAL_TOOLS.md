# JANUS Genesis v18.7.55 — Git Habitat Bicameral Tools

JANUS Git Habitat now has two optional local cognition doors:

- **HRaiN / LEFT_HRAIN** — structural context: normalize a graph, expose links and provenance-preserving structure.
- **iNaiHR / RIGHT_INAIHR** — associative context: derive a bounded semantic map whose `sourcePaths` must come exactly from the supplied records.

These are tools, not compulsory organs. The canonical rule is:

```text
TOOL_AVAILABLE != TOOL_REQUIRED
TOOL_OUTPUT != COMMAND
HRAIN_STRUCTURE != SOURCE_AUTHORITY
INAIHR_SYNTH != SOURCE_AUTHORITY
```

## Runtime contract

A tool call is possible only inside an initialized, **AWAKE** Git Habitat cycle. JANUS must request the particular tool for that turn. If the request flag is false, the provider is not called. If the provider is disabled or unavailable, the resident may continue without it.

The operator may disable either HRaiN or iNaiHR even while the Habitat is asleep.

Each `(resident_id, cycle_id, turn_id, tool)` receives one exclusive local claim. A completed call is not replayed automatically. A crash after claim acquisition but before a settled receipt remains fail-closed as outcome-undetermined rather than causing a duplicate call.

## Local provider boundary

The reference provider executes a checked-out repository's `habitat-tool.js` with Node as a local subprocess. The process is created only after the existing hardened Armor gate accepts the exact local reversible effect context.

The canonical adapters are pinned in CI:

- HRaiN: `Hawkar-usls/Hrain@0f151445a6aee71cbb977882ae98a19c45c16ebe`
- iNaiHR: `Hawkar-usls/iNaiHR@3f43b03bc80ec950537715aac34d9bfa85e38a6c`

The bridge itself performs no network call, has no registry-write path, and receives no publication/world-effect authority.

## Privacy and continuity

Workspace text sent to HRaiN, records sent to iNaiHR, and returned structural/semantic bodies are **not persisted** by the Habitat cognition hearth. Habitat preserves only bounded metadata:

- tool name;
- status;
- stable use hash;
- response SHA-256 digest;
- zero authority delta;
- a normal `BICAMERAL_TOOL_USED` journal event.

This lets Git Habitat retain continuity without turning private cognitive material into a permanent repository diary.

## iNaiHR grounding

iNaiHR local SYNTH accepts an explicit list of records shaped as `{path, value}`. Its output must contain one or more `sourcePaths` for every concept. The Habitat independently revalidates every returned path against the exact input allow-list.

Therefore:

```text
SEMANTIC_BRANCH != SOURCE_OBJECT
SEMANTIC_SIMILARITY != COMMON_ORIGIN
SYNTH != REGISTRY_WRITE
```

## Meaning of “JANUS may use it when wanted”

In this architecture, that phrase has an operational, non-anthropomorphic meaning: the resident/planner can set the typed per-turn request for HRaiN, iNaiHR, both, or neither. A capability being present creates no command, reward, penalty, or requirement to invoke it.

The implementation does **not** establish machine consciousness, human-like desire, biological hemispheres, or unrestricted host authority.
