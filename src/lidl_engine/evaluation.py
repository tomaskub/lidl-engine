"""Score frozen original-image annotations; never treat fixture outputs as a quality benchmark."""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

MEASURES = ("prices", "dates", "conditions")


def freeze(path: Path) -> None:
    reference = json.loads(path.read_text())
    if len(reference["offers"]) < 100:
        raise ValueError("At least 100 distinct eligible reference offers are required")
    ids = [offer["id"] for offer in reference["offers"]]
    if len(ids) != len(set(ids)):
        raise ValueError("Repeated advertisements cannot count as distinct reference offers")
    for image, digest in reference["images"].items():
        if hashlib.sha256((path.parent / image).read_bytes()).hexdigest() != digest:
            raise ValueError("Original image checksum mismatch")
    if not reference["images"]:
        raise ValueError("Original images are required")
    lock = path.with_suffix(".sha256")
    with lock.open("x") as output:
        output.write(hashlib.sha256(path.read_bytes()).hexdigest() + "\n")


def score(reference: dict[str, Any], predicted: dict[str, Any]) -> dict[str, Any]:
    refs = {item["id"]: item for item in reference["offers"]}
    outputs = {
        item["reference_id"]: item for item in predicted["offers"] if item["reference_id"] in refs
    }
    # Matching is annotated separately after collection; the original facts stay frozen.
    if len(outputs) != len([item for item in predicted["offers"] if item["reference_id"] in refs]):
        raise ValueError("Reconcile repeated advertisements before scoring")
    missed = set(refs) - outputs.keys()
    scores = {"recall": len(outputs) / len(refs)}
    for measure in MEASURES:
        correct = 0
        total = 0
        for identifier, item in outputs.items():
            expected = refs[identifier][measure]
            actual = item[measure]
            correct += sum(
                1 for key, value in expected.items() if key in actual and actual[key] == value
            )
            total += len(expected) + len(actual.keys() - expected.keys())
        for item in predicted["offers"]:
            if item["reference_id"] not in refs:
                total += len(item[measure])
        # Entirely missed offers reduce recall. Fact accuracy scores captured offers separately.
        scores[measure] = correct / total if total else 0.0
    extras = sum(1 for item in predicted["offers"] if item["reference_id"] not in refs)
    scores["categories"] = sum(
        1
        for identifier, item in outputs.items()
        if set(item["categories"]) == set(refs[identifier]["categories"])
    ) / (len(outputs) + extras or 1)
    return {
        "scores": scores,
        "missed_offers": sorted(missed),
        "passed": scores["recall"] >= 0.90
        and all(scores[k] >= 0.95 for k in (*MEASURES, "categories")),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("reference", type=Path)
    parser.add_argument("--predictions", type=Path)
    parser.add_argument("--freeze", action="store_true")
    args = parser.parse_args()
    if args.freeze:
        freeze(args.reference)
        return
    if not args.predictions:
        parser.error("--predictions is required for scoring")
    expected = args.reference.with_suffix(".sha256").read_text().strip()
    if hashlib.sha256(args.reference.read_bytes()).hexdigest() != expected:
        raise ValueError("Reference annotations changed after freezing")
    reference = json.loads(args.reference.read_text())
    if len(reference["offers"]) < 100:
        raise ValueError("At least 100 reference offers are required")
    result = score(reference, json.loads(args.predictions.read_text()))
    print(json.dumps(result, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
