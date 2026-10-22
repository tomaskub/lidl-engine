import pytest


def test_intentional_ci_skip() -> None:
    pytest.skip('PER-45 live skip evidence probe')
