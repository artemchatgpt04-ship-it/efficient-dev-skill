# Efficient Development Skill

Efficient Development Skill is a portable set of instructions and small supporting tools for coding agents. It aims to reduce repository reading that does not contribute to a task while preserving the context needed for correct and safe work.

The project is at **Stage 2: working Project Map, Task Router, and Smart Reader**. It uses transparent heuristics and does not claim measured token savings.

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
    +-- rules/         selectively loaded shared policies
    +-- core/          agent-neutral decisions and state contracts
    +-- adapters/      Codex and Antigravity integration only
    +-- installer/     future safe installation and update flow
    +-- scripts/       future deterministic helpers
    +-- tests/         future behavioral and compatibility checks
    `-- docs/          architecture and project-state documentation
```

The common core now implements repository mapping, initial scope selection, and a non-binding reading plan. Future cache validity, change awareness, test selection, and context compression remain unimplemented. Adapters translate host capabilities and must not duplicate core decisions, so Codex and Antigravity can share the same behavior.

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
```

`map` writes human-readable JSON to `PATH_TO_PROJECT/.efficient-dev/project-map.json` by default. `route` ranks files and directories using names, paths, task terms, file roles, and probable source-to-test links. `plan` turns that evidence into a search and reading order plus explicit reasons to expand the scope.

Use repeatable `--exclude` patterns to extend the default noise rules. Use `--alias TASK_TERM=PATH_TERM` when the task and repository use different vocabulary; aliases are explicit because the router does not guess translations or domain meaning.

## Metrics

The commands report `total_files`, `mapped_files`, `candidate_files`, `candidate_directories`, and `scope_ratio`. Here, `total_files` means files encountered outside directories pruned as noise, and `scope_ratio` is candidate files divided by mapped files. These are scope diagnostics, not measurements of token savings or development quality.

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

Stage 2 implements only Project Map, Task Router, Smart Reader, the `map`/`route`/`plan` CLI, initial scope metrics, and real tests. Read Cache, fingerprinting, Change Tracker, Instruction Router, Test Router, Context Compressor, a full installer, servers, databases, embeddings, and LLM calls are not implemented.
