# Test strategy

Tests will validate observable behavior, not the presence of headings or wording in documentation. No placeholder test is included in Stage 1.

## Planned behavioral scenarios

| Scenario | Fixture and observation | Required outcome |
| --- | --- | --- |
| Local task | A small relevant module surrounded by unrelated decoy areas; record search and read events. | The agent reaches the correct result without an unjustified full-repository scan. |
| Cache reuse | Repeat a task against content with unchanged source fingerprints. | Valid cached knowledge is reused without rereading the same content for no stated reason. |
| Cache invalidation | Change a source after its summary is cached. | The stale knowledge is rejected or refreshed before use. |
| Scope expansion | Hide a necessary dependency outside the initial area and expose a reference to it. | The agent follows the dependency and records why the scope expanded. |
| Quality preservation | Use tasks with objective expected edits and meaningful project checks. | Context reduction does not prevent the task from meeting the same correctness criteria. |
| Shared core | Run equivalent host traces through the Codex and Antigravity adapters. | Both adapters produce common core decisions rather than duplicated host-specific logic. |
| Test routing | Provide related fast checks and unrelated expensive checks, then vary change impact. | Related checks run first; broader checks run when impact or uncertainty justifies them. |

## Test-harness requirements

- Instrument searches, reads, cache hits, invalidations, scope expansions, and test selections.
- Compare outcomes and evidence, not just token counts.
- Include failure cases and fixtures where broad reading is the correct choice.
- Make any efficiency metric reproducible and separate it from correctness gates.
- Do not claim savings until experiments define a baseline and report results.
