# Efficient Development Skill

Efficient Development Skill is a portable set of instructions and small supporting tools for coding agents. It aims to reduce repository reading that does not contribute to a task while preserving the context needed for correct and safe work.

The project is at **Stage 5: portable installation for Codex and Antigravity plus the Stage 2–4 shared core**. It uses transparent deterministic mechanisms and does not claim measured token savings.

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
    +-- adapters/      Codex and Antigravity discovery documentation
    +-- installer/     safe bundle lifecycle and thin destination adapters
    +-- scripts/       lightweight deterministic CLI
    +-- tests/         behavioral tests and fixtures
    `-- docs/          architecture and project-state documentation
```

The common core implements selective instruction references, repository mapping, initial scope selection, a non-binding reading plan, compact cached knowledge, SHA-256 validity checks, file-change comparison, risk-aware test selection, and bounded session facts. Adapters translate host capabilities and must not duplicate core decisions, so Codex and Antigravity can share the same behavior.

See [docs/architecture.md](docs/architecture.md) for component boundaries,
[docs/installation.md](docs/installation.md) for installer safety and verified discovery
paths, and [docs/project-state.md](docs/project-state.md) for the `.efficient-dev` state
model.

## Install for Codex

Python 3.10 or newer is sufficient. From this source checkout, install into an existing
target project:

```text
python installer/efficient_dev_installer.py install codex PATH_TO_PROJECT
python installer/efficient_dev_installer.py status codex PATH_TO_PROJECT
```

The default destination is `PATH_TO_PROJECT/.agents/skills/efficient-dev`. Codex normally
discovers repository Skills automatically; restart it if discovery does not refresh.

## Install for Antigravity

```text
python installer/efficient_dev_installer.py install antigravity PATH_TO_PROJECT
python installer/efficient_dev_installer.py status antigravity PATH_TO_PROJECT
```

The default destination is also `PATH_TO_PROJECT/.agents/skills/efficient-dev`, matching
Antigravity workspace discovery. The installed bundle stays progressively disclosed:
short metadata, compact `SKILL.md`, then only the referenced rules or tools needed for a
task.

Use `update` or `uninstall` in place of `install` for lifecycle operations. Existing
destinations are never overwritten by `install`, and project-owned `.efficient-dev`
state survives both update and uninstall. Global and compatibility modes are always
explicit; see [installer usage](installer/README.md).

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
- `adapters/` — host-specific discovery guidance without shared-core duplication.
- `installer/` — standard-library bundle lifecycle, manifest, CLI, and thin adapters.
- `scripts/` — lightweight CLI wrapper.
- `tests/` — executable behavioral tests and portable fixtures.
- `docs/` — architecture and local-state design.

## Status

Stage 5 adds the bounded bundle, version and ownership manifest, safe lifecycle CLI,
Codex and Antigravity path adapters, portability tests, and project-state preservation.
Automatic internet updates, agent configuration edits, package registries, servers,
databases, embeddings, vector search, AST graphs, LLM calls, telemetry, and token-savings
experiments are not implemented.
