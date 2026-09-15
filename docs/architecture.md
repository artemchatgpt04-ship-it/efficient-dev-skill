# Architecture

## Stage 4 data flow

```text
task ----------------> Instruction Router ------> selected rules/*.md
                           |
repository -----> Project Map (JSON v1)
                       |
task ----------------> Task Router
                       |
                       v
                  Smart Reader
                       |
                       v
               Read Cache check <------ SHA-256 fingerprint
                 |          |
           cache hit     miss/stale/exact code needed
                 |          |
                 |       targeted source read
                 |          |
                 +----> cache record

repository -----> Change Tracker -----> cache invalidation
                       |
                       +---------------> Project Map refresh areas
                       |
                       `---------------> Test Router ------> focused/full validation plan

structured current facts -----------------------> Context Compressor
                                                        |
                                                        `--> state/session.json
```

The flow is deterministic for the same project bytes, exclusions, map, aliases, task, cache, and baseline. New dependencies, failed checks, risky changes, or contradictory evidence require the caller to expand the scope and repeat search or routing. Smart Reader and Read Cache recommend reuse or reading; neither enforces file access.

Instruction Router selects relative rule references from task terms and Task Router scope without loading their contents. Project Map prunes known noisy directories before traversal, inspects bounded file metadata, classifies conventional file roles, and links source/test files with matching normalized stems. Task Router ranks explicit lexical and relationship signals. Smart Reader orders search and section reads while preserving full-file and scope expansion escape hatches. Test Router turns current Change Tracker results and mapped links into a validation recommendation. Context Compressor stores only normalized caller-supplied facts.

## Separation of concerns

There are three kinds of data:

1. **Skill-owned, portable data** — `SKILL.md`, shared rules, core contracts, adapter code, installer code, and tests. It is versioned in this repository.
2. **Project-owned durable data** — future user configuration and explicitly retained state under the target project's `.efficient-dev` directory.
3. **Project-owned derived data** — `project-map.json`, `cache/read-cache.json`, `state/tracked-files.json`, and bounded `state/session.json`. Derived data may be discarded and rebuilt from current files and facts, although rebuilding cached knowledge requires rereading sources.

Adapters sit outside the shared decision loop. They provide host capabilities and apply decisions; they do not change the meaning of those decisions.

## Safety and failure behavior

- A missing map can be rebuilt or replaced by direct repository discovery; it must not block work.
- Change Tracker reports paths and directories that can make Project Map stale; map rebuilding remains explicit.
- Cached knowledge is returned only after a matching content fingerprint. Stale knowledge is withheld until current source is read and recorded again.
- Exact code or line-level work still requires reading source even when compact cached knowledge is valid.
- A narrow initial scope is allowed to grow whenever evidence points beyond it.
- Validation breadth follows change impact and uncertainty, not a fixed preference for small test sets.
- Instruction groups are references selected with reasons; low confidence expands safely instead of hiding potentially important guidance.
- Test Router never forbids the full suite and explicitly recommends it for shared, critical, deleted, or insufficiently mapped changes.
- Context Compressor cannot create facts and does not retain full command logs or source copies.
- Local state must not be assumed safe to commit because it may contain paths, summaries, or project metadata.

## Deliberate Stage 4 omissions

Adapter execution, a full installer, automatic installation, servers, databases, embeddings, vector search, LLM calls, rename inference, background watching, exact token accounting, and multi-language AST analysis remain outside the implementation.
