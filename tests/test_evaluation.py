from lidl_engine.evaluation import score


def test_omitted_printed_facts_and_extra_assertions_reduce_separate_scores():
    reference = {
        "offers": [
            {
                "id": "one",
                "prices": {"amount": "3.99", "unit": "szt."},
                "dates": {"start": "2026-10-12"},
                "conditions": {"coupon": True},
                "categories": ["seafood"],
            }
        ]
    }
    predicted = {
        "offers": [
            {
                "reference_id": "one",
                "prices": {"amount": "3.99"},
                "dates": {"start": "2026-10-12", "end": "2026-10-17"},
                "conditions": {"coupon": None},
                "categories": ["seafood"],
            }
        ]
    }
    result = score(reference, predicted)
    assert result["scores"] == {
        "recall": 1,
        "prices": 0.5,
        "dates": 0.5,
        "conditions": 0,
        "categories": 1,
    }
    assert not result["passed"]


def test_wholly_missed_offers_reduce_recall_not_captured_fact_accuracy():
    reference = {
        "offers": [
            {
                "id": "one",
                "prices": {"amount": "3.99"},
                "dates": {"start": None},
                "conditions": {"coupon": None},
                "categories": [],
            }
        ]
    }
    predicted = {"offers": [{**reference["offers"][0], "reference_id": "one"}]}
    reference["offers"].append({**reference["offers"][0], "id": "two"})
    result = score(reference, predicted)
    assert result["scores"]["recall"] == 0.5
    assert all(
        result["scores"][key] == 1 for key in ["prices", "dates", "conditions", "categories"]
    )
    assert result["missed_offers"] == ["two"]


def test_unknown_extra_values_are_not_unsupported_assertions():
    reference = {
        "offers": [
            {
                "id": "one",
                "prices": {"amount": "3.99"},
                "dates": {"start": None},
                "conditions": {"coupon": None},
                "categories": [],
            }
        ]
    }
    predicted = {
        "offers": [
            {
                **reference["offers"][0],
                "reference_id": "one",
                "prices": {"amount": "3.99", "regular": None},
            }
        ]
    }
    assert score(reference, predicted)["passed"]
