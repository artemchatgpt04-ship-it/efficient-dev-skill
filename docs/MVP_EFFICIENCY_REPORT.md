# MVP Efficiency Report

## Method

This report compares a broad `baseline` with the current `efficient` workflow over nine
controlled scenarios. The benchmark is deterministic, executes locally, uses no LLM,
and records no real model token usage.

The baseline reads every mapped first-party text file, loads all eight instruction
groups, selects every mapped test, retains raw session facts, and has no Read Cache. It
is intentionally broad but shares the efficient mode's standard dependency, build,
binary, VCS, and runtime exclusions; generated noise is not counted as useful baseline
reading.

Efficient mode uses the existing Project Map, Task Router, Smart Reader, Read Cache,
Change Tracker, Instruction Router, Test Router, and Context Compressor without
fixture-specific branches. Versioned JSON specifications are materialized into temporary
projects for each scenario, so no runtime `.efficient-dev` data enters the repository.

## Fixtures

All three fixtures contain frontend history and dashboard areas, risk logic, shared
currency types, settings, a legacy area, linked tests, configuration, documentation,
irrelevant modules, and excluded dependency/build noise. Extra independent modules make
the mapped first-party file count grow while the local task stays unchanged.

| Fixture | All project files | Mapped first-party files | Mapped tests |
| --- | ---: | ---: | ---: |
| small | 20 | 18 | 7 |
| medium | 35 | 30 | 13 |
| large | 93 | 80 | 38 |

## Scenarios

- Local history fix on small, medium, and large projects.
- Cross-module risk and dashboard change.
- Shared/core currency type change.
- Package configuration change.
- Unknown task with an unrelated known file change.
- Repeated history task after recording current knowledge.
- Repeated history task after changing the cached file while restoring its timestamp.

Each scenario declares required files, instruction groups, tests, and scope expansions.
A missing required element is a quality failure regardless of any reduction metric.

## Metrics

`files_considered` counts paths considered for content investigation after structural
mapping; low-confidence broad search considers all mapped paths. `files_selected` counts
routed candidates. `files_read_or_recommended` counts recommended content reads after a
valid non-exact cache hit is applied. Bytes and lines are measured from those fixture
files and are not token counts.

`avoided_repeat_reads` is a narrow proxy: one valid fingerprint-matched cache hit with no
exact-source requirement equals one potential avoided repeated orientation read. It does
not mean an agent or model definitely skipped a read.

Instruction bytes are UTF-8 file sizes for all versus routed `rules/*.md`. Test counts
compare the full mapped suite with Test Router output. Context bytes compare compact JSON
serialization of supplied raw facts with stored Context Compressor state; they are not a
complete prompt size.

## Results

| Scenario | Baseline files | Efficient files | Scope reduction | Coverage |
| --- | ---: | ---: | ---: | ---: |
| local-small | 18 | 2 | 88.9% | 100% |
| local-medium | 30 | 2 | 93.3% | 100% |
| local-large | 80 | 2 | 97.5% | 100% |
| cross-module-medium | 30 | 4 | 86.7% | 100% |
| shared-core-large | 80 | 2 | 97.5% | 100% |
| configuration-medium | 30 | 2 | 93.3% | 100% |
| ambiguous-large | 80 | 4 | 95.0% | 100% |
| repeated-cache-medium | 30 | 1 | 96.7% | 100% |
| changed-cache-medium | 30 | 2 | 93.3% | 100% |

Across the controlled scenarios, recommended content reads fell from 408 to 21
(94.8%). Corresponding file bytes fell from 43,412 to 2,614 (94.0%), and lines from
1,473 to 94 (93.6%). These are modeled scope proxies, not observed agent reads.

The ambiguous scenario considered all 80 mapped paths because broader search was
required, then recommended four orientation files. Its small recommended-read count must
not be interpreted as a narrow search or high-confidence answer.

## Instruction reduction

Local and cross-module scenarios selected 3 of 8 groups (`base`, `frontend`, and
`testing`). Shared/core selected 2 of 8, configuration selected mandatory `base`, and
ambiguous routing conservatively selected 3 of 8 including `testing` and `security`.
Aggregate selected instruction bytes fell from 27,963 to 11,120 (60.2%).

## Test selection

Local scenarios selected one linked test from suites of 7, 13, and 38. The cross-module
scenario selected two linked tests from 13. Shared/core, configuration, and ambiguous
changes correctly selected the complete suite rather than optimizing safety away.
Aggregate selected tests fell from 186 to 95 (48.9%).

## Cache reuse

Task A recorded current history knowledge. Task B received one valid fingerprint match,
returned compact knowledge, and produced one potential avoided repeat read. After the
file bytes changed, Task C returned `stale`, required a source read, exposed no cached
knowledge, and still detected the change after the original modification timestamp was
restored.

Across all scenarios there was one hit, eight first-read/stale misses, one stale entry,
and one potential avoided repeat read.

## Context compression

Raw scenario facts contained repeated paths, duplicated findings and decisions, extra
whitespace, and repeated test results. Context Compressor normalized and deduplicated
them while retaining task, scope, inspected/changed files, findings, decisions, tests,
issues, and next action. Aggregate working-state size fell from 14,693 to 8,325 UTF-8
bytes (43.3%). Per-scenario reductions ranged from 36.9% to 46.8%.

## Quality and success criteria

All nine scenarios achieved 100% required-context coverage; there were no quality
failures. After inspecting the complete results, the MVP acceptance criteria were fixed
as follows:

- every scenario has 100% required-context coverage and passes its cache safety check;
- every local scenario keeps recommended reads below 35% of mapped first-party files;
- local instruction and test selections are smaller than their baselines;
- shared/core and configuration changes recommend the full suite;
- the ambiguous task broadens search and recommends the full suite for its known change;
- unchanged cache content can avoid one repeated orientation read;
- changed cached content is stale and never returned as knowledge.

All criteria passed. The local recommendation remained two files while the fixture grew
from 18 to 80 mapped files, so local recommended content scope did not grow linearly with
repository size in these fixtures.

## MVP version

`VERSION` advances from `0.1.0` to `0.2.0`. This is a backward-compatible minor increase:
the installed workflow and manifest remain compatible, while the repository gains a new
controlled evaluation surface and reaches the declared MVP boundary. No tag or release
is created as part of this stage.

## Limitations

- The benchmark measures deterministic recommendations, path counts, file bytes/lines,
  rule bytes, selected tests, and serialized session state—not actual model behavior,
  prompt construction, latency, cost, or token usage.
- It does not execute fixture test commands or score the correctness of a code patch; its
  quality gate checks declared required context and conservative expansion behavior.
- Synthetic fixtures cannot represent every dependency topology, naming convention,
  generated project, monorepo, or language toolchain.
- Baseline behavior is a documented model, not a recording of a particular agent.
- Results do not establish performance on arbitrary real repositories or statistical
  generalization beyond these controlled scenarios.

## Conclusion

The controlled MVP evidence supports the narrow hypothesis that the current mechanisms
reduce unnecessary recommended file reads, repeat orientation, instruction loading,
task-related test selection, and retained session bytes while preserving all declared
required context in these scenarios. It does not establish real token savings or prove
that every real development task will preserve quality.
