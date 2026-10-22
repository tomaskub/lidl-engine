from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

PRODUCER = Path(__file__).resolve().parents[1] / "evidence.py"


class WorkflowAttempt:
    def __init__(self, directory: Path) -> None:
        self.repo = directory / "repo"
        self.repo.mkdir()
        self.artifacts = directory / "evidence"
        self.artifacts.mkdir()
        self.env = {
            **os.environ,
            "GIT_AUTHOR_NAME": "CI test",
            "GIT_AUTHOR_EMAIL": "ci@example.test",
            "GIT_COMMITTER_NAME": "CI test",
            "GIT_COMMITTER_EMAIL": "ci@example.test",
        }
        self.git("init", "-b", "base")
        self.commit("common.txt")
        self.git("checkout", "-b", "feature")
        self.head = self.commit("feature.txt")
        self.git("checkout", "base")
        self.base = self.commit("base.txt")
        self.git("merge", "--no-ff", "feature", "-m", "Synthetic merge")
        self.tested = self.git("rev-parse", "HEAD")
        self.event = directory / "event.json"
        self.event.write_text(
            json.dumps(
                {
                    "number": 12,
                    "pull_request": {
                        "head": {"sha": self.head},
                        "base": {"sha": self.base},
                    },
                }
            )
        )
        self.steps = {
            name: {"outcome": "success", "conclusion": "success"}
            for name in (
                "checkout",
                "python",
                "dependencies",
                "tests",
                "typecheck",
                "lint",
                "format",
            )
        }
        self.env.update(
            GITHUB_EVENT_PATH=str(self.event),
            GITHUB_EVENT_NAME="pull_request",
            GITHUB_SERVER_URL="https://github.com",
            GITHUB_REPOSITORY="tomaskub/lidl-engine",
            GITHUB_SHA=self.tested,
            GITHUB_WORKFLOW="CI evidence",
            GITHUB_WORKFLOW_REF="tomaskub/lidl-engine/.github/workflows/ci-evidence.yml@refs/pull/12/merge",
            GITHUB_WORKFLOW_SHA=self.tested,
            GITHUB_RUN_ID="1234",
            GITHUB_RUN_ATTEMPT="2",
            GITHUB_JOB="verify",
        )

    def git(self, *arguments: str) -> str:
        return subprocess.check_output(
            ["git", *arguments],
            cwd=self.repo,
            env=self.env,
            text=True,
            stderr=subprocess.PIPE,
        ).strip()

    def commit(self, filename: str) -> str:
        (self.repo / filename).write_text(filename)
        self.git("add", filename)
        self.git("commit", "-m", filename)
        return self.git("rev-parse", "HEAD")

    def invoke(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(PRODUCER),
                *arguments,
                "--directory",
                str(self.artifacts),
            ],
            check=False,
            cwd=self.repo,
            env={**self.env, "CI_STEPS_JSON": json.dumps(self.steps)},
            text=True,
            capture_output=True,
        )

    def collect(self) -> dict[str, Any]:
        result = self.invoke("collect")
        assert result.returncode == 0, result.stderr
        return self.manifest()

    def manifest(self) -> dict[str, Any]:
        result: dict[str, Any] = json.loads(
            (self.artifacts / "evidence.json").read_text()
        )
        return result

    def report(
        self,
        cases: str = '<testcase classname="contract" name="passes" time="0.125"/>',
        *,
        attributes: str = 'tests="1" failures="0" errors="0" skipped="0"',
    ) -> None:
        (self.artifacts / "junit.xml").write_text(
            f"<testsuites><testsuite {attributes}>{cases}</testsuite></testsuites>"
        )


@pytest.fixture
def attempt(tmp_path: Path) -> WorkflowAttempt:
    return WorkflowAttempt(tmp_path)


def test_finalization_rejects_a_different_checked_out_revision(
    attempt: WorkflowAttempt,
) -> None:
    attempt.report()
    attempt.collect()
    attempt.git("checkout", "feature")
    result = attempt.invoke("finalize", "--job-outcome", "success")
    assert result.returncode != 0
    assert attempt.manifest()["job"]["outcome"] is None


def test_successful_command_cannot_claim_a_report_with_failed_cases(
    attempt: WorkflowAttempt,
) -> None:
    attempt.report(
        '<testcase name="broken" time="0.2"><failure message="assertion">traceback</failure></testcase>',
        attributes='tests="1" failures="1" errors="0" skipped="0"',
    )
    tests = attempt.collect()["checks"]["tests"]
    assert tests["execution"] == "incomplete"
    assert tests["report_problem"]


def test_pr_artifact_binds_synthetic_merge_and_actual_failed_job(
    attempt: WorkflowAttempt,
) -> None:
    attempt.report()
    raw = attempt.collect()
    assert raw["job"]["outcome"] is None
    result = attempt.invoke("finalize", "--job-outcome", "failure")
    assert result.returncode == 0, result.stderr
    evidence = attempt.manifest()
    assert evidence["schema_version"] == 1
    assert evidence["context"] == "pr_validation"
    assert evidence["pr"] == {
        "number": 12,
        "head_sha": attempt.head,
        "base_sha": attempt.base,
    }
    assert evidence["revision"] == {
        "event_sha": attempt.tested,
        "tested_sha": attempt.tested,
        "parents": [attempt.base, attempt.head],
    }
    assert attempt.tested != attempt.head
    assert evidence["workflow"]["run_id"] == 1234
    assert evidence["workflow"]["run_attempt"] == 2
    assert (
        evidence["workflow"]["attempt_url"]
        == "https://github.com/tomaskub/lidl-engine/actions/runs/1234/attempts/2"
    )
    assert evidence["job"] == {"id": "verify", "outcome": "failure"}
    assert evidence["publication"]["artifact_name"] == "ci-evidence-1234-2"
    assert evidence["checks"]["tests"]["cases"][0]["duration_seconds"] == 0.125
    assert evidence["verification_scope"]["application_tests_absent"]


def test_individual_failures_errors_skips_and_durations_survive(
    attempt: WorkflowAttempt,
) -> None:
    attempt.steps["tests"] = {"outcome": "failure", "conclusion": "failure"}
    attempt.report(
        '<testcase classname="contract" name="pass" time="0.1"/>'
        '<testcase classname="contract" name="fail" time="0.2"><failure message="expected 1">assert 2 == 1</failure></testcase>'
        '<testcase classname="contract" name="error" time="0.3"><error message="fixture">setup traceback</error></testcase>'
        '<testcase classname="contract" name="skip" time="0"><skipped message="browser absent">skip reason</skipped></testcase>',
        attributes='tests="4" failures="1" errors="1" skipped="1"',
    )
    evidence = attempt.collect()
    tests = evidence["checks"]["tests"]
    assert tests["execution"] == "completed"
    assert tests["outcome"] == "failure"
    assert tests["report"] == "junit.xml"
    assert [case["outcome"] for case in tests["cases"]] == [
        "passed",
        "failed",
        "error",
        "skipped",
    ]
    assert [case["duration_seconds"] for case in tests["cases"]] == [0.1, 0.2, 0.3, 0]
    assert tests["cases"][1]["details"] == "assert 2 == 1"
    assert tests["cases"][3]["message"] == "browser absent"
    assert evidence["checks"]["typecheck"]["outcome"] == "success"
    assert evidence["checks"]["lint"]["outcome"] == "success"
    assert evidence["checks"]["format"]["outcome"] == "success"


def test_setup_failure_records_unexecuted_checks_without_creating_report(
    attempt: WorkflowAttempt,
) -> None:
    attempt.steps["dependencies"] = {"outcome": "failure", "conclusion": "failure"}
    for name in ("tests", "typecheck", "lint", "format"):
        attempt.steps[name] = {"outcome": "skipped", "conclusion": "skipped"}
    evidence = attempt.collect()
    assert evidence["setup"]["dependencies"] == "failure"
    for check in evidence["checks"].values():
        assert check["execution"] == "unexecuted"
    assert evidence["checks"]["tests"]["report"] is None
    assert evidence["checks"]["tests"]["cases"] == []
    assert not (attempt.artifacts / "junit.xml").exists()


@pytest.mark.parametrize("event_name", ["push", "workflow_dispatch"])
def test_non_pr_execution_cannot_be_mistaken_for_pr_validation(
    attempt: WorkflowAttempt, event_name: str
) -> None:
    attempt.env["GITHUB_EVENT_NAME"] = event_name
    attempt.report()
    evidence = attempt.collect()
    assert evidence["context"] == event_name
    assert evidence["pr"] is None
    assert evidence["revision"]["tested_sha"] == attempt.tested


@pytest.mark.parametrize(
    "field,value",
    [
        ("GITHUB_RUN_ID", "1235"),
        ("GITHUB_RUN_ATTEMPT", "3"),
        ("GITHUB_REPOSITORY", "other/repo"),
    ],
)
def test_finalization_rejects_foreign_attempts(
    attempt: WorkflowAttempt, field: str, value: str
) -> None:
    attempt.report()
    attempt.collect()
    attempt.env[field] = value
    result = attempt.invoke("finalize", "--job-outcome", "success")
    assert result.returncode != 0
    assert attempt.manifest()["job"]["outcome"] is None


@pytest.mark.parametrize(
    "report",
    [
        None,
        "<testsuites>",
        '<testsuites><testsuite tests="0"/></testsuites>',
        '<testsuites><testsuite tests="2"><testcase name="partial" time="0.1"/></testsuite></testsuites>',
        '<testsuites><testsuite tests="1"><testcase name="bad duration" time="NaN"/></testsuite></testsuites>',
    ],
)
def test_unusable_report_cannot_claim_complete_execution(
    attempt: WorkflowAttempt, report: str | None
) -> None:
    if report is not None:
        (attempt.artifacts / "junit.xml").write_text(report)
    tests = attempt.collect()["checks"]["tests"]
    assert tests["execution"] == "incomplete"
    assert tests["report_problem"]


def test_diagnostic_and_screenshot_paths_point_to_retained_files(
    attempt: WorkflowAttempt,
) -> None:
    attempt.report()
    (attempt.artifacts / "diagnostics").mkdir()
    (attempt.artifacts / "diagnostics/tests.log").write_text("failure traceback")
    (attempt.artifacts / "screenshots/browser").mkdir(parents=True)
    (attempt.artifacts / "screenshots/browser/failure.png").write_bytes(
        b"browser diagnostic fixture"
    )
    evidence = attempt.collect()
    assert evidence["checks"]["tests"]["diagnostic"] == "diagnostics/tests.log"
    assert evidence["diagnostics"] == ["diagnostics/tests.log"]
    assert evidence["screenshots"] == ["screenshots/browser/failure.png"]
    assert (attempt.artifacts / evidence["screenshots"][0]).is_file()


def test_cancelled_execution_preserves_available_cases_but_is_incomplete(
    attempt: WorkflowAttempt,
) -> None:
    attempt.report()
    attempt.steps["tests"] = {"outcome": "cancelled", "conclusion": "cancelled"}
    tests = attempt.collect()["checks"]["tests"]
    assert tests["execution"] == "incomplete"
    assert tests["cases"][0]["name"] == "passes"


def test_skipped_command_cannot_claim_a_leftover_report(
    attempt: WorkflowAttempt,
) -> None:
    attempt.report()
    attempt.steps["tests"] = {"outcome": "skipped", "conclusion": "skipped"}
    tests = attempt.collect()["checks"]["tests"]
    assert tests["execution"] == "unexecuted"
    assert tests["report"] is None
    assert tests["cases"] == []
