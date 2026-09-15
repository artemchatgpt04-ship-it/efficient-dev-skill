# Scripts

`efficient_dev.py` is a dependency-free wrapper around the shared core:

```text
python scripts/efficient_dev.py map [ROOT] [--output FILE] [--exclude GLOB] [--json]
python scripts/efficient_dev.py route "TASK" [--root ROOT | --map FILE] [--alias A=B] [--json]
python scripts/efficient_dev.py plan "TASK" [--root ROOT | --map FILE] [--alias A=B] [--json]
```

- `map` creates a portable Project Map. Its default destination is `ROOT/.efficient-dev/project-map.json`.
- `route` builds a map in memory unless `--map` supplies an existing one, then reports candidates and reasons.
- `plan` adds recommended search/read order, deferred scope, full-file conditions, and expansion triggers.

Repeat `--exclude` and `--alias` as needed. `--alias` is directional: `TASK_TERM=PATH_TERM`. Scripts added later must have a clear caller, bounded scope, safe failure behavior, and meaningful tests.
