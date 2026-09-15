# Efficient Development Skill

Efficient Development Skill is a portable set of instructions and small supporting tools for coding agents. It aims to reduce repository reading that does not contribute to a task while preserving the context needed for correct and safe work.

The project is at **Stage 4: working instruction, repository-scope, reading, cache, change, test, and context routing**. It uses transparent deterministic mechanisms and does not claim measured token savings.

## Principle

The default discovery path is:

```text
search -> candidate files -> relevant sections -> full files when justified
```

This is a prioritization rule, not a reading quota. An agent starts in the smallest reasonable scope and expands it when it discovers dependencies, risks, or insufficient context.

## Architecture

```text
SKILL.md               compact behavior entry point
    |
    +-- rules/         selectively loaded instruction groups
    +-- core/          agent-neutral routing, cache, tracking, and compression
    +-- adapters/      Codex and Antigravity integration only
    +-- installer/     future safe installation and update flow
    +-- scripts/       lightweight deterministic CLI
    +-- tests/         behavioral tests and fixtures
    `-- docs/          architecture and project-state documentation
```

The common core implements selective instruction references, repository mapping, initial scope selection, a non-binding reading plan, compact cached knowledge, SHA-256 validity checks, file-change comparison, risk-aware test selection, and bounded session facts. Adapters translate host capabilities and must not duplicate core decisions, so Codex and Antigravity can share the same behavior.

See [docs/architecture.md](docs/architecture.md) for component boundaries and [docs/project-state.md](docs/project-state.md) for the proposed `.efficient-dev` state model.

## Planned installation

The repository will be installable into another project through a small installer that:

1. detects or accepts the target agent;
2. connects the shared Skill through the matching adapter;
3. initializes project-local `.efficient-dev` state without overwriting existing data;
4. reports every file or configuration change.

The installer remains intentionally unimplemented. Current adapter notes document integration responsibilities without pretending that an unverified cross-agent installation flow exists.

## Try the core locally

Python 3.10 or newer is sufficient; the core has no third-party runtime dependencies.

```text
python scripts/efficient_dev.py map PATH_TO_PROJECT
python scripts/efficient_dev.py route "Fix history rendering" --root PATH_TO_PROJECT
python scripts/efficient_dev.py plan "Fix history rendering" --root PATH_TO_PROJECT
python scripts/efficient_dev.py instructions "Fix React history component" --root PATH_TO_PROJECT
python scripts/efficient_dev.py changes --root PATH_TO_PROJECT --update
python scripts/efficient_dev.py cache record src/file.py --root PATH_TO_PROJECT --summary "Short current knowledge"
python scripts/efficient_dev.py cache inspect src/file.py --root PATH_TO_PROJECT
python scripts/efficient_dev.py changes --root PATH_TO_PROJECT
python scripts/efficient_dev.py tests --root PATH_TO_PROJECT --task "Fix history rendering"
python scripts/efficient_dev.py context update --root PATH_TO_PROJECT --task "Fix history rendering" --changed src/file.py
python scripts/efficient_dev.py context show --root PATH_TO_PROJECT
```

`map` writes human-readable JSON to `PATH_TO_PROJECT/.efficient-dev/project-map.json` by default. `route` ranks files and directories using names, paths, task terms, file roles, and probable source-to-test links. `plan` turns that evidence into a search and reading order plus explicit reasons to expand the scope.

`cache record` stores one bounded current summary per eligible file. `cache inspect` hashes current bytes before returning knowledge; a mismatch returns no cached summary and requires rereading. `changes --update` records a baseline, while later `changes` calls report `added`, `modified`, `deleted`, and `unchanged` paths, invalidate only affected cache entries, and flag Project Map refresh areas.

`instructions` returns only relevant `rules/*.md` references and reasons, keeping mandatory base safety while deferring unrelated groups. `tests` starts with mapped tests for local changes and recommends the full suite for configuration, shared/public code, deletions, missing relationships, or uncertain routing. `context update` replaces supplied fields in bounded project-local session state; it normalizes and deduplicates caller facts without generating content.

Use repeatable `--exclude` patterns to extend the default noise rules. Use `--alias TASK_TERM=PATH_TERM` when the task and repository use different vocabulary; aliases are explicit because the router does not guess translations or domain meaning.

## Metrics

The commands report scope, cache, and change metrics plus instruction selection (`available_instruction_groups`, `selected_instruction_groups`), test planning (`candidate_tests`, `selected_tests`, `full_suite_recommended`), and session state (`context_items`, `context_size`, `deduplicated_items`). Counters describe one operation; they are not measurements of token savings or development quality.

## Repository layout

- `SKILL.md` — short entry point and safe default workflow.
- `core/` — shared implementation and contracts.
- `rules/` — detailed policies loaded only when relevant.
- `adapters/` — thin host-specific integration layers.
- `installer/` — installation and update design boundary.
- `scripts/` — lightweight CLI wrapper.
- `tests/` — executable behavioral tests and portable fixtures.
- `docs/` — architecture and local-state design.

## Status

Stage 4 adds only Instruction Router, separately routed rule groups, Test Router, Context Compressor, bounded session JSON, CLI inspection, and tests. Adapters, a full installer, automatic installation, servers, databases, embeddings, vector search, AST graphs, and LLM calls are not implemented.
