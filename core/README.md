# Shared core

The core is agent-neutral. Adapters may invoke or translate its decisions but must not reimplement them. The implementation uses Python's standard library, language-independent path heuristics, and content hashes.

## Components

| Component | Status | Output |
| --- | --- | --- |
| Project Map | Implemented in `project_map.py`. | Deterministic JSON with directories, typed files, probable entry points, tests, configs, docs, source-test links, exclusions, and metrics. |
| Task Router | Implemented in `task_router.py`. | Ranked files and directories, evidence, conservative confidence, search roots, deferred scope, and scope metrics. |
| Smart Reader | Implemented in `smart_reader.py`. | Search/read order, full-file conditions, deferred areas, and explicit expansion triggers. |
| Read Cache | Implemented in `read_cache.py`. | One bounded current knowledge entry per path, validated before reuse and removed when its source is deleted. |
| Instruction Router | Implemented in `instruction_router.py`. | Selected and deferred rule references, explicit reasons, conservative fallback, and selection metrics. |
| Change Tracker | Implemented in `change_tracker.py`. | Added, modified, deleted, and unchanged paths; cache invalidations; Project Map refresh areas. |
| Test Router | Implemented in `test_router.py`. | Linked or full-suite test selections, related test areas, risk reasons, and escalation conditions. |
| Context Compressor | Implemented in `context_compressor.py`. | Bounded current task, scope, files, findings, decisions, checks, risks, and next action. |

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
- Instruction Router always selects `base`, uses task and routed file/path signals, and returns references rather than loading rule contents.
- Low-confidence instruction routing keeps testing guidance and, when no domain is known, security guidance available.
- Test Router starts with mapped source-test relationships and recommends the full suite for unknown baselines, configuration, shared/public code, deletions, missing test links, or low-confidence scope.
- Context Compressor accepts structured caller facts only. Supplied fields replace their previous values; facts are whitespace-normalized, deduplicated, and bounded before deterministic JSON is stored.
- Stage 3 and Stage 4 JSON files have stable ordering and no timestamps, so equivalent state remains deterministic.

## Boundaries

- Core decisions must not depend on Codex- or Antigravity-specific paths or commands.
- Optimization may prioritize reads but may never forbid evidence needed for safety or correctness.
- The shared core does not depend on adapter paths or installer lifecycle code. Stage 5
  provides those outside `core/`; automatic background tracking, AST analysis, LLM calls,
  and direct test execution remain out of scope.
