# Rules

This directory will hold detailed policies that the Instruction Router loads only when they affect the current task. `SKILL.md` contains the safe common default; rules add precision without making every invocation pay for every instruction.

Planned rule groups:

- repository discovery and justified scope expansion;
- cache reuse and invalidation;
- targeted versus broad validation;
- context compression and handoff state;
- sensitive or generated project data.

## Non-negotiable safety rule

> Start in the smallest necessary area of the project, but expand the investigation whenever dependencies, risk, uncertainty, or missing context require it.

The project optimizes unjustified reading, not necessary reading. A future rule may recommend a sequence or threshold, but it must not impose a hard limit that prevents adequate investigation.

Cached knowledge is reusable only when its content fingerprint matches. Even then, exact code, line-level evidence, edit context, or an incomplete summary justifies reading the source.

Instruction routing remains future work; executable Stage 3 cache and invalidation behavior stays in the shared core rather than being duplicated here or in adapters.
