# Test strategy

Tests validate observable behavior, not documentation wording.

Run the Stage 2 suite with:

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

## Test-harness requirements

- Measure mapped and candidate scope without treating it as token savings.
- Compare outcomes and evidence, not just token counts.
- Include failure cases and fixtures where broad reading is the correct choice.
- Make any efficiency metric reproducible and separate it from correctness gates.
- Do not claim savings until experiments define a baseline and report results.

Quality-preservation experiments, cache reuse, invalidation, change tracking, adapter conformance, and routed test execution remain future test areas because their components are outside Stage 2.
