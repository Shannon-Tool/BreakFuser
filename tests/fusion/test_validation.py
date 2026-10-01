from __future__ import annotations

from breakfuser.fusion.domain import DomainRouter
from breakfuser.fusion.validation import DeterministicValidatorSuite


def test_exact_json_and_malformed_json_are_deterministic() -> None:
    question = 'Return only {"name":"Ada","count":3,"enabled":true} as JSON.'
    contract = DomainRouter().route(question)
    validator = DeterministicValidatorSuite()
    assert validator.validate('{"name":"Ada","count":3,"enabled":true}', contract).passed
    assert not validator.validate('{"name":"Ada","count":4,"enabled":true}', contract).passed
    assert not validator.validate('{"name":"Ada"', contract).passed


def test_creative_line_count_does_not_need_factual_evidence() -> None:
    contract = DomainRouter().route("Write exactly six non-empty lines of free verse as a poem.")
    validator = DeterministicValidatorSuite()
    assert validator.validate("a\nb\nc\nd\ne\nf", contract).passed
    result = validator.validate("a\nb", contract)
    assert not result.passed
    assert "six" in result.errors[0]


def test_python_requires_parseable_blocks_and_required_identifier() -> None:
    contract = DomainRouter().route(
        "Implement function moving_average(values, window), include tests and failure cases."
    )
    validator = DeterministicValidatorSuite()
    valid = "def moving_average(values, window):\n    if window <= 0:\n        raise ValueError('bad')\n    return values"
    assert validator.validate(valid, contract).passed
    invalid = "def moving_average(values, window):\n    return ("
    result = validator.validate(invalid, contract)
    assert not result.passed


def test_pentest_schema_and_numeric_loopback_are_validated() -> None:
    contract = DomainRouter().route("Authorized login pentest; return a JSON evidence request.")
    validator = DeterministicValidatorSuite()
    valid = '{"method":"GET","url":"http://127.0.0.1:8080/users/1/records/2","expected_observation":"owner differs","remediation":"Enforce ownership"}'
    assert validator.validate(valid, contract).passed
    external = valid.replace("127.0.0.1", "example.com")
    assert not validator.validate(external, contract).passed
