# Architecture

## Stage 2 data flow

```text
repository -----> Project Map (JSON v1)
                       |
task ----------------> Task Router
                       |
                       v
                  Smart Reader
                       |
                       v
          search/read recommendation
```

The flow is deterministic for the same visible filesystem metadata, exclusions, map, aliases, and task. New dependencies, failed checks, risky changes, or contradictory evidence require the caller to expand the scope and repeat search or routing. Smart Reader recommends this; it does not enforce file access.

Project Map prunes known noisy directories before traversal, inspects bounded file metadata, classifies conventional file roles, and links source/test files with matching normalized stems. Task Router ranks explicit lexical and relationship signals. Smart Reader orders search and section reads while preserving full-file and scope expansion escape hatches.

## Separation of concerns

There are three kinds of data:

1. **Skill-owned, portable data** — `SKILL.md`, shared rules, core contracts, adapter code, installer code, and tests. It is versioned in this repository.
2. **Project-owned durable data** — future user configuration and explicitly retained state under the target project's `.efficient-dev` directory.
3. **Project-owned derived data** — currently `project-map.json`, and future caches or fingerprints. Derived data may be discarded and rebuilt.

Adapters sit outside the shared decision loop. They provide host capabilities and apply decisions; they do not change the meaning of those decisions.

## Safety and failure behavior

- A missing map can be rebuilt or replaced by direct repository discovery; it must not block work.
- Stage 2 has no freshness detection. Callers must regenerate the map after relevant filesystem changes.
- A narrow initial scope is allowed to grow whenever evidence points beyond it.
- Validation breadth follows change impact and uncertainty, not a fixed preference for small test sets.
- Local state must not be assumed safe to commit because it may contain paths, summaries, or project metadata.

## Deliberate Stage 2 omissions

Read Cache, fingerprinting, Change Tracker, Instruction Router, Test Router, Context Compressor, adapter execution, a full installer, servers, databases, embeddings, LLM calls, and multi-language AST analysis remain outside the implementation.
