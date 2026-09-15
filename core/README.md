# Shared core

The core is agent-neutral. Adapters may invoke or translate its decisions but must not reimplement them. The implementation uses Python's standard library, language-independent path heuristics, and content hashes.

## Components

| Component | Status | Output |
| --- | --- | --- |
| Project Map | Implemented in `project_map.py`. | Deterministic JSON with directories, typed files, probable entry points, tests, configs, docs, source-test links, exclusions, and metrics. |
| Task Router | Implemented in `task_router.py`. | Ranked files and directories, evidence, conservative confidence, search roots, deferred scope, and scope metrics. |
| Smart Reader | Implemented in `smart_reader.py`. | Search/read order, full-file conditions, deferred areas, and explicit expansion triggers. |
| Read Cache | Implemented in `read_cache.py`. | One bounded current knowledge entry per path, validated before reuse and removed when its source is deleted. |
| Instruction Router | Future. | A minimal set of task-relevant instruction references. |
| Change Tracker | Implemented in `change_tracker.py`. | Added, modified, deleted, and unchanged paths; cache invalidations; Project Map refresh areas. |
| Test Router | Future. | An ordered validation plan with escalation reasons. |
| Context Compressor | Future. | Findings, decisions, changes, evidence, and open risks. |

## Current contracts

- Project Map format version is `1`; output is UTF-8 JSON with stable ordering and no timestamp or absolute root path.
- Directory pruning avoids scanning dependency, build, VCS, cache, and runtime-state trees. Additional exclusion globs are accepted by the builder and CLI.
- File classification is based on paths, conventional names, and extensions. No AST or dependency parser is used.
- Source-to-test links currently require a matching normalized filename stem.
- Router scores are explanations of heuristic signals, not probabilities. Low confidence changes the mode to `broaden-search`.
- Smart Reader never reads files or enforces access. It returns a recommendation that always permits evidence-based expansion.
- Fingerprints use SHA-256 over file bytes and never rely on modification time.
- Read Cache stores compact summaries, symbols, and relationships—not source text—and returns knowledge only when the current fingerprint matches.
- One cache entry replaces the previous entry for the same path; deleted entries are removed rather than accumulated.
- Change Tracker compares eligible mapped files with a project-local fingerprint baseline and invalidates only affected cached paths.
- Stage 3 JSON files have stable ordering and no timestamps, so equivalent state remains deterministic.

## Boundaries

- Core decisions must not depend on Codex- or Antigravity-specific paths or commands.
- Optimization may prioritize reads but may never forbid evidence needed for safety or correctness.
- Stage 3 does not provide Instruction Router, Test Router, Context Compressor, adapter execution, or automatic background tracking.
