"""Publish revision-bound execution evidence. See ci/README.md for v1."""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

CHECKS = {
    "tests": "diagnostics/tests.log",
    "typecheck": "diagnostics/typecheck.log",
    "lint": "diagnostics/lint.log",
    "format": "diagnostics/format.log",
}
APPLICATION_TESTS_ABSENT = [
    "offer collection and extraction",
    "offer validity and filtering",
    "database and migrations",
    "desktop browser and screenshots",
    "backup and recovery",
    "launch-quality evaluation",
]


def read_report(path: Path) -> list[dict[str, Any]]:
    """Read pytest's JUnit without dropping skipped or unsuccessful cases."""
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    if root.tag not in {"testsuite", "testsuites"} or not suites:
        raise ValueError("Expected JUnit testsuite or testsuites")
    cases: list[dict[str, Any]] = []
    for suite in suites:
        suite_cases = list(suite.findall("testcase"))
        if int(suite.attrib["tests"]) != len(suite_cases):
            raise ValueError("JUnit case count does not match suite total")
        counts = {"failed": 0, "error": 0, "skipped": 0}
        for case in suite_cases:
            duration = float(case.attrib["time"])
            if not math.isfinite(duration) or duration < 0:
                raise ValueError("Invalid JUnit case duration")
            details = [
                child for child in case if child.tag in {"failure", "error", "skipped"}
            ]
            if len(details) > 1:
                raise ValueError("Conflicting JUnit case outcomes")
            detail = details[0] if details else None
            outcome = (
                {"failure": "failed", "error": "error", "skipped": "skipped"}[
                    detail.tag
                ]
                if detail is not None
                else "passed"
            )
            if outcome != "passed":
                counts[outcome] += 1
            cases.append(
                {
                    "classname": case.get("classname", ""),
                    "name": case.attrib["name"],
                    "duration_seconds": duration,
                    "outcome": outcome,
                    "message": detail.get("message", "")
                    if detail is not None
                    else None,
                    "details": detail.text if detail is not None else None,
                }
            )
        for attribute, outcome in [
            ("failures", "failed"),
            ("errors", "error"),
            ("skipped", "skipped"),
        ]:
            if int(suite.get(attribute, "0")) != counts[outcome]:
                raise ValueError(f"JUnit {attribute} count does not match cases")
    if not cases:
        raise ValueError("JUnit report contains no test cases")
    return cases


def collect(directory: Path) -> None:
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
    steps = json.loads(os.environ["CI_STEPS_JSON"])
    event_name = os.environ["GITHUB_EVENT_NAME"]
    pr = event.get("pull_request") if event_name == "pull_request" else None
    run_url = (
        f"{os.environ['GITHUB_SERVER_URL']}/{os.environ['GITHUB_REPOSITORY']}"
        f"/actions/runs/{os.environ['GITHUB_RUN_ID']}"
    )
    checks: dict[str, dict[str, Any]] = {}
    for name, diagnostic in CHECKS.items():
        step = steps.get(name, {})
        outcome = step.get("outcome", "skipped")
        checks[name] = {
            "required": True,
            "execution": "unexecuted" if outcome == "skipped" else "completed",
            "outcome": outcome,
            "step_conclusion": step.get("conclusion", "skipped"),
            "diagnostic": diagnostic if (directory / diagnostic).is_file() else None,
        }
    tests = checks["tests"]
    tests.update(report=None, cases=[], report_problem=None)
    if tests["execution"] != "unexecuted":
        try:
            tests["cases"] = read_report(directory / "junit.xml")
            tests["report"] = "junit.xml"
            if tests["outcome"] == "success" and any(
                case["outcome"] in {"failed", "error"} for case in tests["cases"]
            ):
                raise ValueError(
                    "Successful test step disagrees with failed JUnit cases"
                )
            if tests["outcome"] == "cancelled":
                tests["execution"] = "incomplete"
        except (OSError, ET.ParseError, ValueError, KeyError) as error:
            tests["execution"] = "incomplete"
            tests["report_problem"] = str(error)

    revision = (
        subprocess.check_output(
            ["git", "show", "-s", "--format=%H %P", "HEAD"], text=True
        )
        .strip()
        .split()
    )
    manifest = {
        "schema_version": 1,
        "repository": os.environ["GITHUB_REPOSITORY"],
        "context": "pr_validation" if pr else event_name,
        "event_name": event_name,
        "pr": (
            {
                "number": event["number"],
                "head_sha": pr["head"]["sha"],
                "base_sha": pr["base"]["sha"],
            }
            if pr
            else None
        ),
        "revision": {
            "event_sha": os.environ["GITHUB_SHA"],
            "tested_sha": revision[0],
            "parents": revision[1:],
        },
        "workflow": {
            "name": os.environ["GITHUB_WORKFLOW"],
            "ref": os.environ["GITHUB_WORKFLOW_REF"],
            "sha": os.environ["GITHUB_WORKFLOW_SHA"],
            "run_id": int(os.environ["GITHUB_RUN_ID"]),
            "run_attempt": int(os.environ["GITHUB_RUN_ATTEMPT"]),
            "run_url": run_url,
            "attempt_url": f"{run_url}/attempts/{os.environ['GITHUB_RUN_ATTEMPT']}",
        },
        "job": {"id": os.environ["GITHUB_JOB"], "outcome": None},
        "setup": {
            name: steps.get(name, {}).get("outcome", "skipped")
            for name in ("checkout", "python", "dependencies")
        },
        "verification_scope": {
            "executed_suite": "ci/tests, evidence producer contract only",
            "application_tests_absent": APPLICATION_TESTS_ABSENT,
        },
        "checks": checks,
        "diagnostics": [
            str(path.relative_to(directory))
            for path in sorted((directory / "diagnostics").rglob("*"))
            if path.is_file()
        ],
        "screenshots": [
            str(path.relative_to(directory))
            for path in sorted((directory / "screenshots").rglob("*"))
            if path.is_file()
        ],
    }
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "evidence.json").write_text(json.dumps(manifest, indent=2) + "\n")


def finalize(directory: Path, job_outcome: str) -> None:
    path = directory / "evidence.json"
    manifest = json.loads(path.read_text())
    if (
        manifest["workflow"]["run_id"] != int(os.environ["GITHUB_RUN_ID"])
        or manifest["workflow"]["run_attempt"] != int(os.environ["GITHUB_RUN_ATTEMPT"])
        or manifest["repository"] != os.environ["GITHUB_REPOSITORY"]
        or manifest["revision"]["tested_sha"]
        != subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    ):
        raise ValueError(
            "Cannot finalize evidence from a different run, attempt, or revision"
        )
    manifest["job"]["outcome"] = job_outcome
    manifest["publication"] = {
        "artifact_name": (
            f"ci-evidence-{manifest['workflow']['run_id']}-"
            f"{manifest['workflow']['run_attempt']}"
        ),
        "retention_days": 30,
    }
    path.write_text(json.dumps(manifest, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("collect", "finalize"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--directory", type=Path, required=True)
        if command == "finalize":
            subparser.add_argument(
                "--job-outcome",
                choices=("success", "failure", "cancelled", "skipped"),
                required=True,
            )
    args = parser.parse_args()
    if args.command == "collect":
        collect(args.directory)
    else:
        finalize(args.directory, args.job_outcome)


if __name__ == "__main__":
    main()
