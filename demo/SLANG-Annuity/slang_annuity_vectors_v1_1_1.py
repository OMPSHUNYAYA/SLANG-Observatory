import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import slang_annuity_v1_1_1 as core

VECTOR_SCHEMA = "SLANG-ANNUITY-VECTORS-1"


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(core.canonical_json(value).encode("utf-8")).hexdigest()


def semantic_cases() -> List[Tuple[str, Dict[str, Any]]]:
    base = core.build_reference_input(False, True, True)
    cases: List[Tuple[str, Dict[str, Any]]] = [("reference_payable", base)]
    for name, field, value in [
        ("inactive_contract", "contract_status", "INACTIVE"),
        ("suspended_contract", "contract_status", "SUSPENDED"),
        ("terminated_contract", "contract_status", "TERMINATED"),
        ("below_age", "attained_age_years", 60),
        ("age_exact_boundary", "attained_age_years", 65),
        ("insufficient_vesting", "credited_service_years", 9),
        ("vesting_exact_boundary", "credited_service_years", 10),
        ("insufficient_contribution", "total_contributed_minor", 14999999),
        ("contribution_exact_boundary", "total_contributed_minor", 15000000),
        ("not_elected", "payout_election", "NOT_ELECTED"),
        ("payee_invalid", "payee_status", "NOT_VALID"),
        ("zero_amount", "declared_periodic_payout_minor", 0),
        ("small_positive_amount", "declared_periodic_payout_minor", 1),
    ]:
        cases.append((name, core.with_evidence_override(base, 0, {field: value})))
    missing = core.clone(base)
    missing["annuity_evidence"][0].pop("attained_age_years")
    missing.pop("declared_evidence_set_id", None)
    cases.append(("missing_age", missing))
    forbidden = core.clone(base)
    forbidden["payout_amount_minor"] = 999
    cases.append(("forbidden_derived_injection", forbidden))
    unknown = core.clone(base)
    unknown["context"]["unversioned_extension"] = True
    cases.append(("unknown_context_field", unknown))
    cases.append(("evaluation_not_authorized", core.build_reference_input(False, True, False)))
    commitment = core.clone(base)
    commitment["annuity_evidence"][0]["evidence_commitment"] = core.EVIDENCE_COMMITMENT_PREFIX + "0" * 64
    commitment.pop("declared_evidence_set_id", None)
    cases.append(("commitment_mismatch", commitment))
    context = core.clone(base)
    context["annuity_evidence"][0]["case_id"] = "ANNUITY-OTHER"
    context["annuity_evidence"][0]["evidence_commitment"] = core.evidence_commitment_for_record(context["annuity_evidence"][0])
    context.pop("declared_evidence_set_id", None)
    cases.append(("context_binding_mismatch", context))
    declared_context = core.clone(base)
    declared_context["declared_context_id"] = core.CONTEXT_ID_PREFIX + "0" * 64
    cases.append(("declared_context_id_mismatch", declared_context))
    multi = core.build_reference_input(True, True, True)
    cases.append(("multi_authority_payable", multi))
    disagreement = core.clone(multi)
    disagreement["annuity_evidence"][1]["declared_periodic_payout_minor"] = 1300000
    disagreement["annuity_evidence"][1]["evidence_commitment"] = core.evidence_commitment_for_record(disagreement["annuity_evidence"][1])
    disagreement.pop("declared_evidence_set_id", None)
    cases.append(("multi_authority_disagreement", disagreement))
    missing_authority = core.clone(multi)
    missing_authority["annuity_evidence"] = missing_authority["annuity_evidence"][:1]
    missing_authority.pop("declared_evidence_set_id", None)
    cases.append(("missing_expected_authority", missing_authority))
    unexpected = core.clone(base)
    unexpected["annuity_evidence"][0]["authority_id"] = "AUTHORITY-X"
    unexpected["annuity_evidence"][0]["evidence_commitment"] = core.evidence_commitment_for_record(unexpected["annuity_evidence"][0])
    unexpected.pop("declared_evidence_set_id", None)
    cases.append(("unexpected_authority", unexpected))
    hidden = core.build_reference_input(False, False, True)
    cases.append(("hidden_payable", hidden))
    cases.append(("hidden_not_payable", core.with_evidence_override(hidden, 0, {"attained_age_years": 60})))
    return cases


def build_vectors() -> Dict[str, Any]:
    semantic = []
    for name, raw in semantic_cases():
        semantic.append({"name": name, "input": raw, "expected_result": core.resolve_annuity(raw), "expected_summary": core.make_summary(raw)})
    single = core.build_reference_input(False, True, True)
    multi = core.build_reference_input(True, True, True)
    reversed_multi = core.clone(multi)
    reversed_multi["annuity_evidence"].reverse()
    hidden_positive = core.build_reference_input(False, False, True)
    hidden_negative = core.with_evidence_override(hidden_positive, 0, {"attained_age_years": 60})
    relations = [
        {"name": "evidence_order_independence", "relation": "RESULT_EQUAL", "left": multi, "right": reversed_multi},
        {"name": "withheld_outcome_noninterference", "relation": "SUMMARY_EQUAL", "left": hidden_positive, "right": hidden_negative},
        {"name": "repeat_determinism", "relation": "RESULT_EQUAL", "left": single, "right": core.clone(single)},
        {"name": "single_multi_outcome_projection", "relation": "OUTCOME_PROJECTION_EQUAL", "left": single, "right": multi},
    ]
    parser = [
        {"name": "duplicate_key", "raw": '{"x":1,"x":2}', "expected_prefix": "DUPLICATE_JSON_KEY"},
        {"name": "float", "raw": '{"x":1.25}', "expected_prefix": "FLOAT_NOT_SUPPORTED"},
        {"name": "nan", "raw": '{"x":NaN}', "expected_prefix": "NONFINITE_NUMBER_NOT_SUPPORTED"},
        {"name": "bad_json", "raw": '{"x":', "expected_prefix": "JSONDecodeError"},
    ]
    bundle = core.build_bundle(single)
    receipt = core.make_receipt(bundle)
    abstain_input = core.build_reference_input(False, True, False)
    attestation = core.make_attestation(abstain_input)
    artifacts = {
        "bundle": bundle,
        "receipt": receipt,
        "attestation_input": abstain_input,
        "attestation": attestation,
        "bundle_hash": canonical_hash(bundle),
        "receipt_hash": canonical_hash(receipt),
        "attestation_hash": canonical_hash(attestation),
    }
    return {
        "schema": VECTOR_SCHEMA,
        "version": core.VERSION,
        "core_version": core.CORE_VERSION,
        "profile_id": core.PROFILE_ID,
        "ruleset_id": core.RULESET_ID,
        "canonicalization_id": core.CANONICALIZATION_ID,
        "contract_id": core.contract_id(),
        "identity_domain_id": core.identity_domain_id(),
        "semantic": semantic,
        "relations": relations,
        "parser": parser,
        "artifacts": artifacts,
    }


def verify_vectors(vectors: Any) -> Tuple[bool, List[str], Dict[str, Tuple[int, int]]]:
    failures: List[str] = []
    counts: Dict[str, Tuple[int, int]] = {}
    header_checks = [
        isinstance(vectors, dict),
        isinstance(vectors, dict) and vectors.get("schema") == VECTOR_SCHEMA,
        isinstance(vectors, dict) and vectors.get("version") == core.VERSION,
        isinstance(vectors, dict) and vectors.get("core_version") == core.CORE_VERSION,
        isinstance(vectors, dict) and vectors.get("profile_id") == core.PROFILE_ID,
        isinstance(vectors, dict) and vectors.get("ruleset_id") == core.RULESET_ID,
        isinstance(vectors, dict) and vectors.get("canonicalization_id") == core.CANONICALIZATION_ID,
        isinstance(vectors, dict) and vectors.get("contract_id") == core.contract_id(),
        isinstance(vectors, dict) and vectors.get("identity_domain_id") == core.identity_domain_id(),
    ]
    counts["header"] = (sum(1 for item in header_checks if item), len(header_checks))
    for index, passed in enumerate(header_checks):
        if not passed:
            failures.append("header:" + str(index))
    semantic_passed = 0
    semantic_total = 0
    for item in vectors.get("semantic", []) if isinstance(vectors, dict) else []:
        semantic_total += 2
        result_ok = core.resolve_annuity(item.get("input")) == item.get("expected_result")
        summary_ok = core.make_summary(item.get("input")) == item.get("expected_summary")
        semantic_passed += int(result_ok) + int(summary_ok)
        if not result_ok:
            failures.append("semantic_result:" + str(item.get("name")))
        if not summary_ok:
            failures.append("semantic_summary:" + str(item.get("name")))
    counts["semantic"] = (semantic_passed, semantic_total)
    relation_passed = 0
    relation_total = 0
    for item in vectors.get("relations", []) if isinstance(vectors, dict) else []:
        relation_total += 1
        relation = item.get("relation")
        if relation == "RESULT_EQUAL":
            passed = core.resolve_annuity(item.get("left")) == core.resolve_annuity(item.get("right"))
        elif relation == "SUMMARY_EQUAL":
            passed = core.make_summary(item.get("left")) == core.make_summary(item.get("right"))
        elif relation == "OUTCOME_PROJECTION_EQUAL":
            left = core.resolve_annuity(item.get("left"))
            right = core.resolve_annuity(item.get("right"))
            keys = ["state", "annuity_outcome", "currency", "payout_amount_minor", "reason_codes", "contract_condition", "age_condition", "vesting_condition", "contribution_condition", "election_condition", "payee_condition", "amount_condition"]
            passed = all(left.get(key) == right.get(key) for key in keys)
        else:
            passed = False
        relation_passed += int(passed)
        if not passed:
            failures.append("relation:" + str(item.get("name")))
    counts["relations"] = (relation_passed, relation_total)
    parser_passed = 0
    parser_total = 0
    for item in vectors.get("parser", []) if isinstance(vectors, dict) else []:
        parser_total += 1
        observed = "NONE"
        try:
            core.strict_json_load_text(item.get("raw", ""))
        except Exception as exc:
            observed = exc.__class__.__name__ if exc.__class__.__name__ == "JSONDecodeError" else str(exc).split(":", 1)[0]
        passed = observed == item.get("expected_prefix")
        parser_passed += int(passed)
        if not passed:
            failures.append("parser:" + str(item.get("name")) + ":" + observed)
    counts["parser"] = (parser_passed, parser_total)
    artifacts = vectors.get("artifacts", {}) if isinstance(vectors, dict) else {}
    artifact_checks = [
        core.verify_bundle(artifacts.get("bundle"))[0],
        core.check_receipt_integrity(artifacts.get("receipt"))[0],
        core.verify_receipt_against_bundle(artifacts.get("receipt"), artifacts.get("bundle"))[0],
        core.check_attestation_integrity(artifacts.get("attestation"))[0],
        core.verify_attestation_against_input(artifacts.get("attestation"), artifacts.get("attestation_input"))[0],
        canonical_hash(artifacts.get("bundle")) == artifacts.get("bundle_hash"),
        canonical_hash(artifacts.get("receipt")) == artifacts.get("receipt_hash"),
        canonical_hash(artifacts.get("attestation")) == artifacts.get("attestation_hash"),
    ]
    counts["artifacts"] = (sum(1 for item in artifact_checks if item), len(artifact_checks))
    for index, passed in enumerate(artifact_checks):
        if not passed:
            failures.append("artifact:" + str(index))
    return not failures, failures, counts


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="slang_annuity_vectors_v1_1_1.py")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--verify", metavar="VECTOR_JSON")
    group.add_argument("--write", metavar="VECTOR_JSON")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    if args.write:
        Path(args.write).write_text(json.dumps(build_vectors(), ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        print("WRITE: PASS")
        return 0
    try:
        vectors = core.load_json_file(Path(args.verify))
    except Exception as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        return 2
    ok, failures, counts = verify_vectors(vectors)
    for name in ["header", "semantic", "relations", "parser", "artifacts"]:
        passed, total = counts.get(name, (0, 0))
        print(name + ": " + str(passed) + "/" + str(total) + " reproduced")
    total_passed = sum(value[0] for value in counts.values())
    total = sum(value[1] for value in counts.values())
    print("TOTAL: " + str(total_passed) + "/" + str(total) + " PASS")
    if failures:
        for failure in failures:
            print("FAIL " + failure)
    print("VERIFY: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
