# Test strategy

Tests validate observable behavior, not documentation wording.

Run all current tests with:

```text
python -B -m unittest discover -s tests -v
```

The committed `polyglot_project` fixture contains TypeScript, Python, Java, Go, and Rust paths plus configuration, documentation, and conventional tests.

## Stage 2 coverage

| Scenario | Observable assertion |
| --- | --- |
| Local task | History work selects the history source and its test without recommending every mapped file. |
| Related tests | Conventional TypeScript, Python, and Go test names link to matching source stems. |
| Unknown task | Missing terms produce low confidence and `broaden-search`, not invented precision. |
| Noise | VCS, dependency, build, coverage, and binary data are absent from mapped files. |
| Extensible exclusions | An additional exclusion pattern extends, rather than replaces, defaults. |
| Scope expansion | Every Smart Reader plan allows expansion and lists evidence-based triggers. |
| Determinism | Repeated maps, routes, plans, and JSON round trips are equivalent. |
| CLI | `map`, `route`, and `plan` execute against the committed fixture. |

## Stage 3 coverage

| Scenario | Observable assertion |
| --- | --- |
| Cache hit | Matching content returns compact knowledge without requiring repeated orientation. |
| Exact source | A valid cache hit still requires reading when exact code is requested. |
| Modified content | A changed SHA-256 fingerprint marks only that entry stale and withholds its knowledge. |
| Same timestamp | Changed bytes are detected after restoring the original modification timestamp. |
| Added/deleted | Change Tracker reports both; deleted cached knowledge is removed. |
| Unrelated modification | Changing module A leaves module B's cache valid. |
| Determinism | Repeated fingerprints and change scans over the same state are equal. |
| Noise | Dependency directories and `.efficient-dev` runtime data are not tracked or cached. |
| Cache bounds | Recording replaces one path entry and excluded files are rejected. |
| CLI | `cache` and `changes` cover baseline, hit, modification, and stale flows. |

## Stage 4 coverage

| Scenario | Observable assertion |
| --- | --- |
| Frontend instructions | Base, frontend, and linked testing guidance are selected without backend or database rules. |
| Security instructions | Security terms select security rules; base never disappears. |
| Ambiguous instructions | Low confidence safely adds testing and security guidance. |
| Local validation | One changed source selects its mapped test without unrelated module tests or the full suite. |
| Broad validation | Shared/core, configuration, deleted, and unlinked source changes recommend the full suite. |
| Context duplicates | Repeated facts are normalized and stored once. |
| Context replacement | New values replace supplied old fields while omitted current fields remain. |
| Context bounds | Large log-like facts are truncated and item counts are capped. |
| Critical context | Task, changes, decisions, checks, issues, and next action remain explicit fields. |
| Determinism | Equivalent inputs produce equivalent instruction, test, and session outputs. |
| CLI | `instructions`, `tests`, `context update`, and `context show` execute against an isolated fixture. |

## Test-harness requirements

- Measure mapped and candidate scope without treating it as token savings.
- Compare outcomes and evidence, not just token counts.
- Include failure cases and fixtures where broad reading is the correct choice.
- Make any efficiency metric reproducible and separate it from correctness gates.
- Do not claim savings until experiments define a baseline and report results.

Quality-preservation experiments, concurrent writers, adapter conformance, automatic installation, and routed test execution remain future test areas because those capabilities are outside Stage 4.
