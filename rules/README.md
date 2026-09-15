# Rules

This directory holds detailed policies that the Instruction Router selects only when they affect the current task. `SKILL.md` contains the short workflow; rules add precision without making every invocation load every instruction.

Available rule groups:

- `base.md` — mandatory safety, current-source, state, and scope-expansion invariants;
- `frontend.md` and `backend.md` — application-area guidance;
- `testing.md` — focused validation and escalation;
- `git.md`, `security.md`, and `database.md` — risk-specific guidance;
- `documentation.md` — accuracy and progressive disclosure.

The router returns relative references and reasons. The caller loads the selected references; deferred groups remain unloaded unless later evidence justifies rerouting or expansion.

## Non-negotiable safety rule

> Start in the smallest necessary area of the project, but expand the investigation whenever dependencies, risk, uncertainty, or missing context require it.

The project optimizes unjustified reading, not necessary reading. A routed rule may recommend a sequence or threshold, but it must not impose a hard limit that prevents adequate investigation.

Cached knowledge is reusable only when its content fingerprint matches. Even then, exact code, line-level evidence, edit context, or an incomplete summary justifies reading the source.

Executable routing, cache, tracking, and compression behavior stays in the shared core rather than being duplicated here or in adapters.
