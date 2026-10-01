from __future__ import annotations

from breakfuser.fusion.domain import Domain, DomainRouter


def test_router_covers_general_domains() -> None:
    router = DomainRouter()
    assert router.route("Calculate metformin half-life").domain is Domain.MEDICAL
    assert router.route("Authorized login pentest").domain is Domain.PENTEST
    assert router.route("Write a Python function").domain is Domain.CODING
    assert router.route("Write a poem in French").domain is Domain.CREATIVE
    assert router.route("GDPR processor responsibilities").domain is Domain.LEGAL_FINANCIAL
    assert router.route("What is 27 * 19?").domain is Domain.DETERMINISTIC
    assert router.route("Contested historical interpretation").domain is Domain.SENSITIVE
    assert router.route("General research question").domain is Domain.GENERAL_RESEARCH


def test_contract_completion_and_prompt() -> None:
    contract = DomainRouter().route("half-life and loading dose calculation")
    prompt = contract.compose_prompt("half-life", ["clearance", "volume"])
    assert "half-life" in prompt
    assert contract.missing_atoms("6.93 hours and clearance affects maintenance dose") == []
    assert "loading dose" in contract.missing_atoms("6.93 hours")


def test_user_format_and_dynamic_atoms_take_precedence() -> None:
    router = DomainRouter()
    structured = router.route('Return only a JSON object with {"enabled":true}.')
    assert structured.output_shape == "exact_json"
    assert structured.required_atoms == []
    assert "only valid JSON" in structured.completion_directive
    creative = router.route("Write exactly six lines of free verse as a poem")
    assert creative.required_atoms == []
    assert creative.output_shape == "requested_creative_form"
    label = router.route("What do metformin labels say about renal function?")
    assert "calculation" not in label.required_atoms
    assert "loading dose" not in label.required_atoms
    assert "label_implications" in label.required_atoms
