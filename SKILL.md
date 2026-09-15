---
name: efficient-dev-skill
description: Reduce unjustified repository reading during coding, debugging, review, and testing by finding the smallest sufficient context and expanding it when dependencies, risk, or missing information require more evidence. Never use as a hard context limit or as a substitute for required verification.
---

# Efficient Development

Start with the smallest area that can safely answer the task:

1. Respect project and user instructions.
2. Search for relevant symbols, routes, tests, and dependencies before reading files.
3. Read candidate files in relevant sections; read whole files only when structure or correctness requires it.
4. Reuse cached knowledge only after confirming that its source is unchanged.
5. Expand the scope whenever dependencies, uncertainty, or risk make the current context insufficient.
6. Run related checks first, then broaden validation in proportion to the impact of the change.
7. Keep a compact, current summary of findings, decisions, changes, and open risks.

Use the shared components described in [core/README.md](core/README.md). Load detailed material from [rules/README.md](rules/README.md) only when it applies. Use an adapter only for installation or agent-specific integration.
