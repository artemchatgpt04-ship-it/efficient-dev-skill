# Antigravity adapter

The Antigravity adapter resolves discovery locations; all decision behavior remains in
the shared core.

The primary workspace destination follows current Antigravity documentation:

```text
PROJECT/.agents/skills/efficient-dev/
```

The explicit `global` mode targets `HOME/.gemini/config/skills/efficient-dev` for the
Antigravity IDE. Current Google codelab material documents a different global location
for Antigravity CLI, so `cli-global` targets
`HOME/.gemini/antigravity-cli/skills/efficient-dev`. The modes are never mixed or
selected implicitly.

The copied directory keeps `SKILL.md` short and includes its relative `rules/`, `core/`,
and `scripts/` resources. Antigravity can therefore discover the description first,
load the main instructions on activation, and load detailed resources only when needed.

See [installer usage](../../installer/README.md) and
[installation architecture](../../docs/installation.md).
