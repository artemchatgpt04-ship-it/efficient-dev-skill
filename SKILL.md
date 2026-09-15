---
name: efficient-dev-skill
description: Reduce unjustified repository reading during coding, debugging, review, and testing by finding the smallest sufficient context and expanding it when dependencies, risk, or missing information require more evidence. Never use as a hard context limit or as a substitute for required verification.
---

# Efficient Development

Start with the smallest area that can safely answer the task:

1. Respect project and user instructions.
2. Build or inspect the compact Project Map before broad repository discovery.
3. Use the Task Router to identify explicit path, name, keyword, and test-link signals.
4. Search within the recommended scope before reading files.
5. Read relevant sections first; read whole files only when structure or correctness requires it.
6. Treat every scope as a recommendation and expand it whenever dependencies, uncertainty, or risk require more evidence.

Use `scripts/efficient_dev.py map`, `route`, or `plan` when local script execution is useful. Read [core/README.md](core/README.md) for output semantics and [scripts/README.md](scripts/README.md) for CLI details. Load [rules/README.md](rules/README.md) only when detailed scope guidance applies. Adapters are for installation or agent-specific integration, not routing logic.
