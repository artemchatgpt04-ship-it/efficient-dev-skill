# Efficient Development Skill

Efficient Development Skill is a portable set of instructions and small supporting tools for coding agents. It aims to reduce repository reading that does not contribute to a task while preserving the context needed for correct and safe work.

The project is at **Stage 1: architecture and scaffold**. It does not yet analyze repositories, manage a working cache, or claim measured token savings.

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

The common core owns scope selection, reading strategy, cache validity, change awareness, test selection, and context compression. Adapters translate those decisions into the configuration, paths, and invocation mechanisms of a particular coding agent. Keeping this boundary prevents Codex and Antigravity from developing separate versions of the same optimization logic.

See [docs/architecture.md](docs/architecture.md) for component boundaries and [docs/project-state.md](docs/project-state.md) for the proposed `.efficient-dev` state model.

## Planned installation

The repository will be installable into another project through a small installer that:

1. detects or accepts the target agent;
2. connects the shared Skill through the matching adapter;
3. initializes project-local `.efficient-dev` state without overwriting existing data;
4. reports every file or configuration change.

The installer is intentionally not implemented in Stage 1. Current adapter notes document integration responsibilities without pretending that an unverified cross-agent installation flow exists.

## Repository layout

- `SKILL.md` — short entry point and safe default workflow.
- `core/` — contracts for shared future modules.
- `rules/` — detailed policies loaded only when relevant.
- `adapters/` — thin host-specific integration layers.
- `installer/` — installation and update design boundary.
- `scripts/` — reserved for justified deterministic helpers.
- `tests/` — behavioral test strategy; no placeholder passing tests.
- `docs/` — architecture and local-state design.

## Status

Stage 1 defines the boundaries, safety rule, persistent-state model, and future test obligations. Stage 2 may implement behavior only after formats, instrumentation, and success metrics are chosen and validated.
