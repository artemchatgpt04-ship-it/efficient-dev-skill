# Shared core

The core is agent-neutral. Adapters may invoke or translate its decisions but must not reimplement them. The Stage 2 implementation uses Python's standard library and language-independent filename and path heuristics.

## Components

| Component | Status | Output |
| --- | --- | --- |
| Project Map | Implemented in `project_map.py`. | Deterministic JSON with directories, typed files, probable entry points, tests, configs, docs, source-test links, exclusions, and metrics. |
| Task Router | Implemented in `task_router.py`. | Ranked files and directories, evidence, conservative confidence, search roots, deferred scope, and scope metrics. |
| Smart Reader | Implemented in `smart_reader.py`. | Search/read order, full-file conditions, deferred areas, and explicit expansion triggers. |
| Read Cache | Future. | Source-linked summaries with validity metadata. |
| Instruction Router | Future. | A minimal set of task-relevant instruction references. |
| Change Tracker | Future. | Fresh, stale, or unknown validity decisions. |
| Test Router | Future. | An ordered validation plan with escalation reasons. |
| Context Compressor | Future. | Findings, decisions, changes, evidence, and open risks. |

## Stage 2 contracts

- Project Map format version is `1`; output is UTF-8 JSON with stable ordering and no timestamp or absolute root path.
- Directory pruning avoids scanning dependency, build, VCS, cache, and runtime-state trees. Additional exclusion globs are accepted by the builder and CLI.
- File classification is based on paths, conventional names, and extensions. No AST or dependency parser is used.
- Source-to-test links currently require a matching normalized filename stem.
- Router scores are explanations of heuristic signals, not probabilities. Low confidence changes the mode to `broaden-search`.
- Smart Reader never reads files or enforces access. It returns a recommendation that always permits evidence-based expansion.

## Boundaries

- Core decisions must not depend on Codex- or Antigravity-specific paths or commands.
- Optimization may prioritize reads but may never forbid evidence needed for safety or correctness.
- Stage 2 does not provide cache reuse, freshness, change tracking, test routing, or context compression.
