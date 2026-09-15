---
name: efficient-dev-skill
description: Reduce unjustified repository reading during coding, debugging, review, and testing by finding the smallest sufficient context and expanding it when dependencies, risk, or missing information require more evidence. Never use as a hard context limit or as a substitute for required verification.
---

# Efficient Development

Start with the smallest area that can safely answer the task:

1. Respect project and user instructions.
2. Use the Instruction Router and load only its selected `rules/*.md` references; `base` safety rules always apply.
3. Build or inspect the compact Project Map before broad repository discovery.
4. Use the Task Router to identify explicit path, name, keyword, and test-link signals.
5. Search within the recommended scope before reading files.
6. Check Read Cache validity before repeated orientation; read current source for exact code, edits, missing detail, or any stale entry.
7. Treat every scope as a recommendation and expand it whenever dependencies, uncertainty, or risk require more evidence.
8. After changes, use the Test Router: start with linked tests and broaden or run the full suite when impact is shared, critical, or unclear.
9. Keep handoff state compact with the Context Compressor, using only supplied facts and never full logs or source copies.

Use `scripts/efficient_dev.py instructions`, `map`, `route`, `plan`, `cache`, `changes`, `tests`, or `context` when local script execution is useful. Read [core/README.md](core/README.md) for output semantics, [rules/README.md](rules/README.md) for routed rule groups, [docs/project-state.md](docs/project-state.md) for local-state validity, and [scripts/README.md](scripts/README.md) for CLI details. Adapters are outside the shared core.
