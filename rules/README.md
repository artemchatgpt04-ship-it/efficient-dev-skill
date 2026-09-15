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

Stage 2 will split rule groups only when there is executable behavior or validated guidance to attach to them.
