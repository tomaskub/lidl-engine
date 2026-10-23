# PER-45 live CI verification

Verified on 2026-10-22 UTC using draft
[PR #3](https://github.com/tomaskub/lidl-engine/pull/3) against main
`a889e803f6d49f2609b580044b9915cb29032670`. These are real `pull_request`
workflow attempts. The final artifacts were downloaded with `gh run download`
and their JSON, JUnit, and diagnostic files inspected locally.

| Scenario | Run, attempt 1 | Downloadable artifact | Verification job | Observed test execution |
| --- | --- | --- | --- | --- |
| Pass | [39872812030](https://github.com/tomaskub/lidl-engine/actions/runs/39872812030) | [ci-evidence-39872812030-1](https://github.com/tomaskub/lidl-engine/actions/runs/39872812030/artifacts/12466638370) | success | 18 passed |
| Failed test | [39873001033](https://github.com/tomaskub/lidl-engine/actions/runs/39873001033) | [ci-evidence-39873001033-1](https://github.com/tomaskub/lidl-engine/actions/runs/39873001033/artifacts/12466963286) | failure | 18 passed, 1 failed |
| Skip | [39873038685](https://github.com/tomaskub/lidl-engine/actions/runs/39873038685) | [ci-evidence-39873038685-1](https://github.com/tomaskub/lidl-engine/actions/runs/39873038685/artifacts/12466998037) | success | 18 passed, 1 skipped |
| Setup failure | [39873062022](https://github.com/tomaskub/lidl-engine/actions/runs/39873062022) | [ci-evidence-39873062022-1](https://github.com/tomaskub/lidl-engine/actions/runs/39873062022/artifacts/12467191782) | failure | unexecuted, no JUnit or invented cases |
| Restored baseline | [39873081586](https://github.com/tomaskub/lidl-engine/actions/runs/39873081586) | [ci-evidence-39873081586-1](https://github.com/tomaskub/lidl-engine/actions/runs/39873081586/artifacts/12467122046) | success | 18 passed |

Each publisher succeeded, including for the failed verification jobs. Artifacts
are retained for 30 days, until approximately 2026-11-21, and require repository
access. A later consumer must check expiration; this document does not extend it.

## Revision binding

All four scenario manifests have `context: pr_validation`, PR number 3, the
base above, workflow identity, run ID and attempt 1. Actual tested commits are
synthetic merges. Each has exactly the recorded base and PR head as parents.

| Scenario | PR head | Actual tested merge |
| --- | --- | --- |
| Pass | `4366b1ca50807ada54cb68bff5191a6e9006f78b` | `d8c2cb2c1034147fe6e57f2b5774cf1ad7aa5d35` |
| Failed test | `7c7944aebbb0b79ec0955504a599d4df4b944635` | `d9b95f538b81db8efa72ec25b60691e8f8494807` |
| Skip | `bdabe31b77617deeb87dc00cc31edebca753d914` | `0cdaff546d733b7055208a14f2532830820b6d37` |
| Setup failure | `d15a44639f7ba15c4da3242cfbacca6c6d3817f9` | `f3f276ce57e5bb6621d50ff4b69a2b97d6594fa1` |

## Diagnostic observations

The failed-test report preserves the testcase name, duration, assertion message,
and traceback. `diagnostics/tests.log` contains the same deliberate assertion.
GitHub's [verification job](https://github.com/tomaskub/lidl-engine/actions/runs/39873001033/job/120151713954)
and manifest independently show successful typecheck, lint, and formatting
steps after the failed test step. The publisher binds `job.outcome: failure`.

The skipped testcase preserves its reason and duration in JUnit and JSON.
The verification job succeeds because pytest accepts skips. A required skipped
testcase still cannot support a passing factory gate; consumers must inspect
individual outcomes rather than relying on the job's green summary.

The setup-failure revision temporarily passed an invalid option to pip. Its
[verification job](https://github.com/tomaskub/lidl-engine/actions/runs/39873062022/job/120151922306)
failed installation, skipped tests and dependent tools, and still collected and
uploaded diagnostics. `diagnostics/setup.log` retains the error. All required
checks are `unexecuted`; tests have `report: null` and no cases. No `junit.xml`
exists in that artifact.

An earlier exploratory failed-test attempt exposed Bash's default pipeline
behavior: `tee` hid the pytest exit status. Its contradictory report was marked
incomplete by the collector. The workflow now explicitly selects `shell: bash`,
which enables pipeline failure propagation. The failed-test and skip rows above
repeat verification after that fix. The temporary probe test and pip option
were removed in `84a38109c2c11f865fe33d70091ae4498c58a149`.

## Scope limits

The complete baseline suite tests the evidence producer through its CLI with
temporary real Git repositories and generated JSON/JUnit files. No PER-25
application is imported. Offer collection/extraction, validity/filtering,
database/migrations, desktop browser, backup/recovery, and launch evaluation
tests remain absent from main's baseline. No real browser screenshots exist;
the contract tests only verify retention references using a diagnostic fixture.

Push and manual contexts, malformed/missing reports, cancellation, and foreign
run/attempt/revision rejection have local contract coverage. The live rows here
establish PR execution and uploads, not a main push or application acceptance.

To inspect one artifact again before expiry:

```sh
gh run download 39873001033 --repo tomaskub/lidl-engine \
  --name ci-evidence-39873001033-1 --dir /tmp/per45-failed-evidence
```
