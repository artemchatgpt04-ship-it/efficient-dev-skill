# Shared core

The core is agent-neutral. It describes decisions and data contracts; adapters may invoke or translate them but must not reimplement them.

## Planned components

| Component | Responsibility | Expected output |
| --- | --- | --- |
| Project Map | Maintain a compact view of important files, symbols, entry points, tests, and relationships. | A freshness-aware map, not a repository dump. |
| Task Router | Convert the task and available project knowledge into an initial investigation scope. | Ranked areas, search targets, and reasons. |
| Smart Reader | Progress from search results to files, then sections, then full files only when justified. | Read requests with an evidence-based scope. |
| Read Cache | Reuse concise knowledge derived from previously read content. | Source-linked summaries with validity metadata. |
| Instruction Router | Select only rules and detailed guidance relevant to the current task. | A minimal set of instruction references. |
| Change Tracker | Detect whether sources used by maps, summaries, or decisions have changed. | Fresh, stale, or unknown validity decisions. |
| Test Router | Select related checks first and broader checks when impact or uncertainty warrants them. | An ordered validation plan with escalation reasons. |
| Context Compressor | Replace accumulated working detail with a short current state. | Findings, decisions, changes, evidence, and open risks. |

## Boundaries

- Core decisions must not depend on Codex- or Antigravity-specific paths or commands.
- Every cached conclusion must remain traceable to source identity and freshness information.
- `unknown` freshness is not equivalent to `fresh`.
- Optimization may prioritize reads but may never forbid evidence needed for safety or correctness.
- Formats and executable interfaces remain deliberately unspecified until Stage 2 prototypes establish what is necessary.
