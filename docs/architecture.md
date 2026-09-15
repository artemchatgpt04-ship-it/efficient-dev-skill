# Architecture

## Data flow

```text
task + project instructions
          |
          v
   Instruction Router -----> relevant shared rules
          |
          v
      Task Router <--------- Project Map
          |
          v
     Smart Reader <--------> Read Cache
          |                      ^
          |                      |
          +---- Change Tracker --+
          |
          v
       work/change
          |
          v
       Test Router
          |
          v
  Context Compressor -----> compact current state
```

The flow is iterative. New dependencies, failed checks, risky changes, or contradictory evidence return control to the Task Router with a broader justified scope.

## Separation of concerns

There are three kinds of data:

1. **Skill-owned, portable data** — `SKILL.md`, shared rules, core contracts, adapter code, installer code, and tests. It is versioned in this repository.
2. **Project-owned durable data** — user configuration and any explicitly retained project map or state. It lives under the target project's `.efficient-dev` directory.
3. **Project-owned derived data** — caches, fingerprints, and generated map material. It also lives under `.efficient-dev`, but may be discarded and rebuilt.

Adapters sit outside the shared decision loop. They provide host capabilities and apply decisions; they do not change the meaning of those decisions.

## Safety and failure behavior

- Missing or stale maps and caches reduce optimization; they must not block work.
- When freshness cannot be established, the consumer treats the relevant knowledge as unverified.
- A narrow initial scope is allowed to grow whenever evidence points beyond it.
- Validation breadth follows change impact and uncertainty, not a fixed preference for small test sets.
- Local state must not be assumed safe to commit because it may contain paths, summaries, or project metadata.

## Deliberate Stage 1 omissions

No storage format, hashing algorithm, parser, indexer, runtime, command-line interface, or agent automation is selected yet. Those choices require prototypes and behavioral measurements in Stage 2.
