# Scripts

`efficient_dev.py` is a dependency-free wrapper around the shared core:

```text
python scripts/efficient_dev.py map [ROOT] [--output FILE] [--exclude GLOB] [--json]
python scripts/efficient_dev.py route "TASK" [--root ROOT | --map FILE] [--alias A=B] [--json]
python scripts/efficient_dev.py plan "TASK" [--root ROOT | --map FILE] [--alias A=B] [--json]
python scripts/efficient_dev.py instructions "TASK" [--root ROOT | --map FILE] [--alias A=B] [--json]
python scripts/efficient_dev.py cache status [--root ROOT] [--json]
python scripts/efficient_dev.py cache inspect FILE [--root ROOT] [--exact] [--json]
python scripts/efficient_dev.py cache record FILE --summary TEXT [--root ROOT] [--symbol NAME] [--relationship PATH] [--exclude GLOB]
python scripts/efficient_dev.py cache invalidate FILE [--root ROOT] [--json]
python scripts/efficient_dev.py changes [--root ROOT] [--update] [--json]
python scripts/efficient_dev.py tests [--root ROOT] [--task "TASK"] [--map FILE] [--json]
python scripts/efficient_dev.py context show [--root ROOT] [--json]
python scripts/efficient_dev.py context update [--root ROOT] [--task TASK] [--scope ITEM] [--inspected FILE] [--changed FILE] [--finding TEXT] [--decision TEXT] [--test RESULT] [--issue TEXT] [--next-action TEXT] [--json]
```

- `map` creates a portable Project Map. Its default destination is `ROOT/.efficient-dev/project-map.json`.
- `route` builds a map in memory unless `--map` supplies an existing one, then reports candidates and reasons.
- `plan` adds recommended search/read order, deferred scope, full-file conditions, and expansion triggers.
- `instructions` returns only selected `rules/*.md` references and explains each selection. Base safety is always selected; low confidence expands conservatively.
- `cache record` replaces the one current knowledge entry for a file; `status` and `inspect` verify fingerprints before reporting validity.
- `cache inspect --exact` preserves a valid orientation hit but still requires direct reading.
- `cache invalidate` prevents reuse until current knowledge is recorded again.
- `changes` compares current eligible files with the stored baseline, reconciles Read Cache, and reports Project Map refresh areas. `--update` accepts current fingerprints as the next baseline.
- `tests` reads the current change baseline and map relationships. It selects linked tests for local changes and recommends all mapped tests when risk is broad or unclear; it does not execute tests.
- `context update` replaces only the supplied session fields after normalization, deduplication, and bounding. `context show` reads `.efficient-dev/state/session.json`; neither command generates facts.

Repeat `--exclude` and `--alias` as needed. `--alias` is directional: `TASK_TERM=PATH_TERM`. Scripts added later must have a clear caller, bounded scope, safe failure behavior, and meaningful tests.
