from __future__ import annotations

import argparse
import importlib.util
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

VECTOR_SCHEMA = "SLANG-CLAIMS-VECTORS-1"
EXPECTED_CORE_FILENAME = "slang_claims_v0_2_1.py"
EXPECTED_VECTOR_FILENAME = "SLANG_Claims_Vectors_v0_2_1.json"
VECTOR_SET_ID_PREFIX = "slang_claims_vector_set_sha256:"
VECTOR_FILE_MAX_BYTES = 4 * 1024 * 1024


def load_vector_file(path: Path) -> Any:
    data = path.read_bytes()
    if len(data) > VECTOR_FILE_MAX_BYTES:
        raise ValueError("VECTOR_FILE_TOO_LARGE")
    text = data.decode("utf-8")

    def pairs_hook(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("DUPLICATE_VECTOR_KEY:" + key)
            result[key] = value
        return result

    return json.loads(
        text,
        object_pairs_hook=pairs_hook,
        parse_constant=lambda x: (_ for _ in ()).throw(ValueError("NON_FINITE_VECTOR_NUMBER")),
    )

def vector_hash(value: Any) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_core(path: Path):
    spec = importlib.util.spec_from_file_location("slang_claims_reference", str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError("CORE_IMPORT_FAILED")
    module = importlib.util.module_from_spec(spec)
    sys.modules["slang_claims_reference"] = module
    spec.loader.exec_module(module)
    return module


def mutate(source: Any, fn: Callable[[Any], None]) -> Any:
    value = json.loads(json.dumps(source, ensure_ascii=False))
    fn(value)
    return value


def refresh(sc, value: Dict[str, Any]) -> Dict[str, Any]:
    return sc.refresh_declared_ids(value)


def reordered_object(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: reordered_object(value[k]) for k in reversed(list(value.keys()))}
    if isinstance(value, list):
        return [reordered_object(x) for x in value]
    return value


def semantic_inputs(sc) -> List[Tuple[str, Any]]:
    base = sc.build_reference_input(False, True)
    multi = sc.build_reference_input(True, True)
    cases: List[Tuple[str, Any]] = [("reference_single_payable", base), ("reference_multi_payable", multi), ("reference_hidden", sc.build_reference_input(False, False))]

    def add(name: str, value: Any, do_refresh: bool = False) -> None:
        cases.append((name, refresh(sc, value) if do_refresh else value))

    for field, replacement in [
        ("coverage_result", sc.COVERAGE_NOT_COVERED),
        ("occurrence_result", sc.OCCURRENCE_NOT_ESTABLISHED),
        ("exclusion_result", sc.BLOCKED),
        ("control_result", sc.BLOCKED),
    ]:
        add("negative_" + field, mutate(base, lambda x, f=field, r=replacement: x["claim_evidence"][0].__setitem__(f, r)), True)

    add("below_deductible", mutate(base, lambda x: (x["context"].__setitem__("claim_amount_minor", 50000), x["claim_evidence"][0].__setitem__("assessed_loss_minor", 50000))), True)
    add("equal_deductible", mutate(base, lambda x: (x["context"].__setitem__("claim_amount_minor", 100000), x["claim_evidence"][0].__setitem__("assessed_loss_minor", 100000))), True)
    add("zero_deductible", mutate(base, lambda x: x["context"].__setitem__("deductible_minor", 0)), True)
    add("zero_remaining_limit", mutate(base, lambda x: x["context"].__setitem__("remaining_limit_minor", 0)), True)
    add("limit_cap", mutate(base, lambda x: x["context"].__setitem__("remaining_limit_minor", 200000)), True)
    add("assessed_loss_cap", mutate(base, lambda x: x["claim_evidence"][0].__setitem__("assessed_loss_minor", 300000)), True)
    add("assessed_loss_zero", mutate(base, lambda x: x["claim_evidence"][0].__setitem__("assessed_loss_minor", 0)), True)
    add("claim_zero", mutate(base, lambda x: x["context"].__setitem__("claim_amount_minor", 0)), True)
    add("claim_one_minor", mutate(base, lambda x: x["context"].__setitem__("claim_amount_minor", 1)), True)
    add("double_block", mutate(base, lambda x: (x["claim_evidence"][0].__setitem__("coverage_result", sc.COVERAGE_NOT_COVERED), x["claim_evidence"][0].__setitem__("control_result", sc.BLOCKED))), True)

    for field in ["evaluation_id", "claim_ref", "policy_ref", "claimant_ref", "loss_event_ref", "currency"]:
        replacement = "OTHER" if field != "currency" else "EUR"
        add("binding_mismatch_" + field, mutate(base, lambda x, f=field, r=replacement: x["claim_evidence"][0].__setitem__(f, r)), True)

    for field in ["evaluation_id", "claim_ref", "policy_ref", "claimant_ref", "loss_event_ref", "currency", "claim_amount_minor", "deductible_minor", "remaining_limit_minor", "evaluation_authorized", "reference_visibility_authorized", "evidence_mode", "expected_authority_ids"]:
        add("missing_context_" + field, mutate(base, lambda x, f=field: x["context"].pop(f, None)))

    for field in ["schema", "evidence_id", "authority_id", "evaluation_id", "claim_ref", "policy_ref", "claimant_ref", "loss_event_ref", "currency", "coverage_result", "occurrence_result", "exclusion_result", "control_result", "assessed_loss_minor", "evidence_commitment"]:
        add("missing_evidence_" + field, mutate(base, lambda x, f=field: x["claim_evidence"][0].pop(f, None)))

    add("missing_evidence_list", mutate(base, lambda x: x.pop("claim_evidence", None)))
    add("empty_evidence_list", mutate(base, lambda x: x.__setitem__("claim_evidence", [])))
    add("evaluation_not_authorized", mutate(base, lambda x: x["context"].__setitem__("evaluation_authorized", False)), True)
    add("forbidden_password", mutate(base, lambda x: x["context"].__setitem__("password", "x")))
    add("forbidden_access_token", mutate(base, lambda x: x.__setitem__("access_token", "x")))
    add("forbidden_address", mutate(base, lambda x: x["claim_evidence"][0].__setitem__("address", "x")))
    for field_name in ["bankAccount", "bankaccount", "bank-account", "BANK_ACCOUNT", "cardNumber", "dateOfBirth", "payableAmountMinor"]:
        add("forbidden_variant_" + field_name, mutate(base, lambda x, f=field_name: x["context"].__setitem__(f, "x")))
    add("unknown_top_field", mutate(base, lambda x: x.__setitem__("other", True)))
    add("unknown_context_field", mutate(base, lambda x: x["context"].__setitem__("other", True)))
    add("unknown_evidence_field", mutate(base, lambda x: x["claim_evidence"][0].__setitem__("other", True)))
    add("unsupported_input_schema", mutate(base, lambda x: x.__setitem__("schema", "OTHER")))
    add("unsupported_profile", mutate(base, lambda x: x.__setitem__("profile_id", "OTHER")))
    add("unsupported_ruleset", mutate(base, lambda x: x.__setitem__("ruleset_id", "OTHER")))
    add("unsupported_evidence_schema", mutate(base, lambda x: x["claim_evidence"][0].__setitem__("schema", "OTHER")))
    add("invalid_currency", mutate(base, lambda x: x["context"].__setitem__("currency", "US")))
    add("invalid_commitment", mutate(base, lambda x: x["claim_evidence"][0].__setitem__("evidence_commitment", "sha256:123")))
    add("negative_money", mutate(base, lambda x: x["context"].__setitem__("deductible_minor", -1)))
    add("declared_context_mismatch", mutate(base, lambda x: x.__setitem__("declared_context_id", sc.CONTEXT_ID_PREFIX + "0" * 64)))
    add("declared_evidence_mismatch", mutate(base, lambda x: x.__setitem__("declared_evidence_set_id", sc.EVIDENCE_SET_ID_PREFIX + "0" * 64)))
    add("duplicate_expected_authority", mutate(multi, lambda x: x["context"].__setitem__("expected_authority_ids", ["CLAIM-AUTHORITY-A", "CLAIM-AUTHORITY-A"])))
    add("missing_expected_authority", refresh(sc, mutate(multi, lambda x: x.__setitem__("claim_evidence", x["claim_evidence"][:1]))))
    add("unexpected_authority", refresh(sc, mutate(multi, lambda x: (x["claim_evidence"][1].__setitem__("authority_id", "CLAIM-AUTHORITY-X"), x["claim_evidence"][1].__setitem__("evidence_id", "EVIDENCE-X")))))
    add("duplicate_evidence_id", refresh(sc, mutate(multi, lambda x: x["claim_evidence"][1].__setitem__("evidence_id", x["claim_evidence"][0]["evidence_id"]))))
    add("duplicate_authority_id", refresh(sc, mutate(multi, lambda x: x["claim_evidence"][1].__setitem__("authority_id", x["claim_evidence"][0]["authority_id"]))))

    for field, replacement in [
        ("coverage_result", sc.COVERAGE_NOT_COVERED),
        ("occurrence_result", sc.OCCURRENCE_NOT_ESTABLISHED),
        ("exclusion_result", sc.BLOCKED),
        ("control_result", sc.BLOCKED),
        ("assessed_loss_minor", 440000),
    ]:
        add("multi_disagreement_" + field, refresh(sc, mutate(multi, lambda x, f=field, r=replacement: x["claim_evidence"][1].__setitem__(f, r))))

    add("single_mode_two_evidence", refresh(sc, mutate(multi, lambda x: x["context"].__setitem__("evidence_mode", sc.EVIDENCE_SINGLE))))
    add("multi_mode_one_authority", refresh(sc, mutate(base, lambda x: x["context"].__setitem__("evidence_mode", sc.EVIDENCE_MULTI))))
    return cases


def semantic_vectors(sc) -> List[Dict[str, Any]]:
    output = []
    for name, value in semantic_inputs(sc):
        output.append({"name": name, "input": value, "expected_result": sc.resolve_claims(value), "expected_summary": sc.make_summary(value)})
    return output


def parser_vectors(sc) -> List[Dict[str, Any]]:
    valid = sc.canonical_json(sc.build_reference_input(False, True))
    deep_text = '{"x":' * (sc.MAX_JSON_DEPTH + 2) + '0' + '}' * (sc.MAX_JSON_DEPTH + 2)
    entries = [
        ("canonical_valid", valid, True),
        ("duplicate_key", '{"a":1,"a":2}', False),
        ("float", '{"x":1.5}', False),
        ("nan", '{"x":NaN}', False),
        ("trailing", '{"x":1} x', False),
        ("array_root", '[1,2,3]', True),
        ("null_root", 'null', True),
        ("boolean_root", 'true', True),
        ("integer_root", '1', True),
        ("unsafe_integer", '{"x":9007199254740992}', False),
        ("deep_nesting", deep_text, False),
    ]
    result = []
    for name, text, should_pass in entries:
        result.append({"name": name, "text": text, "should_parse": should_pass})
    return result


def relation_vectors(sc) -> List[Dict[str, Any]]:
    base = sc.build_reference_input(False, True)
    multi = sc.build_reference_input(True, True)
    relations: List[Dict[str, Any]] = []

    a = sc.resolve_claims(base)
    b = sc.resolve_claims(reordered_object(base))
    relations.append({"name": "object_key_order_invariance", "left": base, "right": reordered_object(base), "predicate": "canonical_input_id_equal", "expected": a["canonical_input_id"] == b["canonical_input_id"]})

    rev = mutate(multi, lambda x: x.__setitem__("claim_evidence", list(reversed(x["claim_evidence"]))))
    relations.append({"name": "evidence_order_invariance", "left": multi, "right": rev, "predicate": "canonical_input_id_equal", "expected": sc.resolve_claims(multi)["canonical_input_id"] == sc.resolve_claims(rev)["canonical_input_id"]})

    auth_rev = refresh(sc, mutate(multi, lambda x: x["context"].__setitem__("expected_authority_ids", list(reversed(x["context"]["expected_authority_ids"])))))
    relations.append({"name": "authority_order_invariance", "left": multi, "right": auth_rev, "predicate": "context_id_equal", "expected": sc.resolve_claims(multi)["context_id"] == sc.resolve_claims(auth_rev)["context_id"]})

    case_norm = refresh(sc, mutate(base, lambda x: (x["context"].__setitem__("claim_ref", "  claim-alpha  "), x["claim_evidence"][0].__setitem__("claim_ref", "claim-alpha"))))
    relations.append({"name": "ascii_identifier_normalization", "left": base, "right": case_norm, "predicate": "outcome_equal", "expected": sc.resolve_claims(base)["claim_outcome"] == sc.resolve_claims(case_norm)["claim_outcome"]})

    hidden = sc.build_reference_input(False, False)
    relations.append({"name": "visibility_noninterference", "left": base, "right": hidden, "predicate": "payability_equal", "expected": sc.resolve_claims(base)["payable_amount_minor"] == sc.resolve_claims(hidden)["payable_amount_minor"]})
    hidden_negative = refresh(sc, mutate(hidden, lambda x: x["claim_evidence"][0].__setitem__("coverage_result", sc.COVERAGE_NOT_COVERED)))
    relations.append({"name": "withheld_outcome_noninterference", "left": hidden, "right": hidden_negative, "predicate": "summary_equal", "expected": sc.make_summary(hidden) == sc.make_summary(hidden_negative)})
    forbidden_a = sc.clone(base)
    forbidden_a["context"]["password"] = "secret-a"
    forbidden_b = sc.clone(base)
    forbidden_b["context"]["password"] = "secret-b"
    relations.append({"name": "forbidden_value_redaction_noncommitment", "left": forbidden_a, "right": forbidden_b, "predicate": "submission_id_equal", "expected": sc.resolve_claims(forbidden_a)["submission_id"] == sc.resolve_claims(forbidden_b)["submission_id"]})

    changed_commit = refresh(sc, mutate(base, lambda x: x["claim_evidence"][0].__setitem__("evidence_commitment", sc.commitment("changed-provenance"))))
    relations.append({"name": "provenance_changes_identity_not_quantum", "left": base, "right": changed_commit, "predicate": "same_quantum_different_evidence_id", "expected": sc.resolve_claims(base)["payable_amount_minor"] == sc.resolve_claims(changed_commit)["payable_amount_minor"] and sc.resolve_claims(base)["evidence_set_id"] != sc.resolve_claims(changed_commit)["evidence_set_id"]})

    high_claim = refresh(sc, mutate(base, lambda x: x["context"].__setitem__("claim_amount_minor", 700000)))
    relations.append({"name": "claim_amount_monotone_within_profile", "left": base, "right": high_claim, "predicate": "right_payable_gte_left", "expected": sc.resolve_claims(high_claim)["payable_amount_minor"] >= sc.resolve_claims(base)["payable_amount_minor"]})

    high_limit = refresh(sc, mutate(base, lambda x: x["context"].__setitem__("remaining_limit_minor", 2000000)))
    relations.append({"name": "remaining_limit_monotone_within_profile", "left": base, "right": high_limit, "predicate": "right_payable_gte_left", "expected": sc.resolve_claims(high_limit)["payable_amount_minor"] >= sc.resolve_claims(base)["payable_amount_minor"]})

    high_deductible = refresh(sc, mutate(base, lambda x: x["context"].__setitem__("deductible_minor", 200000)))
    relations.append({"name": "deductible_antitone_within_profile", "left": base, "right": high_deductible, "predicate": "right_payable_lte_left", "expected": sc.resolve_claims(high_deductible)["payable_amount_minor"] <= sc.resolve_claims(base)["payable_amount_minor"]})

    lower_assessment = refresh(sc, mutate(base, lambda x: x["claim_evidence"][0].__setitem__("assessed_loss_minor", 300000)))
    relations.append({"name": "assessed_loss_bound_within_profile", "left": base, "right": lower_assessment, "predicate": "right_payable_lte_left", "expected": sc.resolve_claims(lower_assessment)["payable_amount_minor"] <= sc.resolve_claims(base)["payable_amount_minor"]})

    repeat1 = sc.resolve_claims(base)
    repeat2 = sc.resolve_claims(json.loads(json.dumps(base)))
    relations.append({"name": "exact_replay", "left": base, "right": base, "predicate": "full_result_equal", "expected": repeat1 == repeat2})
    return relations


def artifact_vectors(sc) -> List[Dict[str, Any]]:
    base = sc.build_reference_input(False, True)
    bundle = sc.build_bundle(base)
    receipt = sc.make_receipt(bundle)
    vectors: List[Dict[str, Any]] = []
    vectors.append({"name": "bundle_valid", "kind": "bundle", "artifact": bundle, "expected_pass": True})
    bad = json.loads(json.dumps(bundle)); bad["result"]["payable_amount_minor"] += 1
    vectors.append({"name": "bundle_result_tamper", "kind": "bundle", "artifact": bad, "expected_pass": False})
    bad2 = json.loads(json.dumps(bundle)); bad2["submitted_input"]["context"]["claim_amount_minor"] += 1
    vectors.append({"name": "bundle_input_tamper", "kind": "bundle", "artifact": bad2, "expected_pass": False})
    bad3 = json.loads(json.dumps(bundle)); bad3["bundle_id"] = sc.BUNDLE_ID_PREFIX + "0" * 64
    vectors.append({"name": "bundle_id_tamper", "kind": "bundle", "artifact": bad3, "expected_pass": False})

    vectors.append({"name": "receipt_integrity_valid", "kind": "receipt_integrity", "artifact": receipt, "expected_pass": True})
    badr = json.loads(json.dumps(receipt)); badr["payable_amount_minor"] += 1
    vectors.append({"name": "receipt_amount_tamper", "kind": "receipt_integrity", "artifact": badr, "expected_pass": False})
    badr2 = json.loads(json.dumps(receipt)); badr2["receipt_id"] = sc.RECEIPT_ID_PREFIX + "0" * 64
    vectors.append({"name": "receipt_id_tamper", "kind": "receipt_integrity", "artifact": badr2, "expected_pass": False})

    forged_amount = json.loads(json.dumps(receipt))
    forged_amount["payable_amount_minor"] = 999999999
    forged_amount.pop("receipt_id")
    forged_amount["receipt_id"] = sc.identity(sc.RECEIPT_ID_PREFIX, forged_amount)
    vectors.append({"name": "receipt_self_consistent_amount_forgery", "kind": "receipt_integrity", "artifact": forged_amount, "expected_pass": False})

    forged_authority = json.loads(json.dumps(receipt))
    forged_authority["payment_authority"] = "GRANTED"
    forged_authority.pop("receipt_id")
    forged_authority["receipt_id"] = sc.identity(sc.RECEIPT_ID_PREFIX, forged_authority)
    vectors.append({"name": "receipt_self_consistent_authority_forgery", "kind": "receipt_integrity", "artifact": forged_authority, "expected_pass": False})

    forged_profile = json.loads(json.dumps(receipt))
    forged_profile["profile_id"] = "OTHER"
    forged_profile.pop("receipt_id")
    forged_profile["receipt_id"] = sc.identity(sc.RECEIPT_ID_PREFIX, forged_profile)
    vectors.append({"name": "receipt_self_consistent_profile_forgery", "kind": "receipt_integrity", "artifact": forged_profile, "expected_pass": False})

    vectors.append({"name": "receipt_against_bundle_valid", "kind": "receipt_bundle", "receipt": receipt, "bundle": bundle, "expected_pass": True})
    other_bundle = sc.build_bundle(refresh(sc, mutate(base, lambda x: x["context"].__setitem__("claim_amount_minor", 600000))))
    vectors.append({"name": "receipt_against_other_bundle", "kind": "receipt_bundle", "receipt": receipt, "bundle": other_bundle, "expected_pass": False})

    hidden = sc.build_reference_input(False, False)
    vectors.append({"name": "hidden_summary_withholds", "kind": "summary", "input": hidden, "expected": sc.make_summary(hidden)})
    vectors.append({"name": "visible_summary_resolves", "kind": "summary", "input": base, "expected": sc.make_summary(base)})
    hidden_negative = refresh(sc, mutate(hidden, lambda x: x["claim_evidence"][0].__setitem__("coverage_result", sc.COVERAGE_NOT_COVERED)))
    vectors.append({"name": "hidden_summary_noninterference", "kind": "summary_pair", "left": hidden, "right": hidden_negative, "expected_pass": True})

    unauthorized = refresh(sc, mutate(base, lambda x: x["context"].__setitem__("evaluation_authorized", False)))
    conflict = refresh(sc, mutate(base, lambda x: x["claim_evidence"][0].__setitem__("policy_ref", "POLICY-OTHER")))
    incomplete = mutate(base, lambda x: x["context"].pop("policy_ref", None))
    forbidden = mutate(base, lambda x: x["context"].__setitem__("bankAccount", "x"))
    unsupported = mutate(base, lambda x: x.__setitem__("other", True))
    attestation_cases = [
        ("resolved", base),
        ("abstain", unauthorized),
        ("conflict", conflict),
        ("incomplete", incomplete),
        ("forbidden", forbidden),
        ("unsupported", unsupported),
    ]
    for name, input_value in attestation_cases:
        attestation = sc.make_attestation(input_value)
        vectors.append({"name": "attestation_" + name + "_integrity", "kind": "attestation_integrity", "artifact": attestation, "expected_pass": True})
        vectors.append({"name": "attestation_" + name + "_correspondence", "kind": "attestation_input", "artifact": attestation, "input": input_value, "expected_pass": True})

    abstain_attestation = sc.make_attestation(unauthorized)
    tampered_attestation = json.loads(json.dumps(abstain_attestation))
    tampered_attestation["state"] = sc.STATE_RESOLVED
    vectors.append({"name": "attestation_tamper", "kind": "attestation_integrity", "artifact": tampered_attestation, "expected_pass": False})
    vectors.append({"name": "attestation_wrong_input", "kind": "attestation_input", "artifact": abstain_attestation, "input": base, "expected_pass": False})

    vectors.append({"name": "contract_manifest", "kind": "contract", "artifact": sc.contract_manifest(), "expected_pass": True})
    return vectors


def serialization_vectors(sc) -> List[Dict[str, Any]]:
    example = sc.build_reference_input(False, True)
    bundle = sc.build_bundle(example)
    receipt = sc.make_receipt(bundle)
    abstain_input = refresh(sc, mutate(example, lambda x: x["context"].__setitem__("evaluation_authorized", False)))
    attestation = sc.make_attestation(abstain_input)
    contract = sc.contract_manifest()
    return [
        {"name": "example_input", "sha256": sc.sha256_hex(example), "canonical": sc.canonical_json(example)},
        {"name": "bundle", "sha256": sc.sha256_hex(bundle), "canonical": sc.canonical_json(bundle)},
        {"name": "receipt", "sha256": sc.sha256_hex(receipt), "canonical": sc.canonical_json(receipt)},
        {"name": "attestation", "sha256": sc.sha256_hex(attestation), "canonical": sc.canonical_json(attestation)},
        {"name": "contract", "sha256": sc.sha256_hex(contract), "canonical": sc.canonical_json(contract)},
    ]


def build_document(sc) -> Dict[str, Any]:
    example = sc.build_reference_input(False, True)
    bundle = sc.build_bundle(example)
    receipt = sc.make_receipt(bundle)
    abstain_input = refresh(sc, mutate(example, lambda x: x["context"].__setitem__("evaluation_authorized", False)))
    attestation = sc.make_attestation(abstain_input)
    contract = sc.contract_manifest()
    document = {
        "schema": VECTOR_SCHEMA,
        "version": sc.VERSION,
        "core_version": sc.CORE_VERSION,
        "profile_id": sc.PROFILE_ID,
        "ruleset_id": sc.RULESET_ID,
        "canonicalization_id": sc.CANONICALIZATION_ID,
        "identity_domain_id": sc.identity_domain_id(),
        "semantic_vectors": semantic_vectors(sc),
        "parser_vectors": parser_vectors(sc),
        "relations": relation_vectors(sc),
        "artifact_vectors": artifact_vectors(sc),
        "serialization_vectors": serialization_vectors(sc),
        "reference_evidence": {
            "example_input": example,
            "bundle": bundle,
            "receipt": receipt,
            "abstain_input": abstain_input,
            "attestation": attestation,
            "contract": contract,
        },
    }
    document["vector_set_id"] = VECTOR_SET_ID_PREFIX + vector_hash(document)
    return document


def verify_document(sc, document: Any) -> Tuple[Dict[str, Tuple[int, int]], List[str]]:
    report: Dict[str, Tuple[int, int]] = {}
    failures: List[str] = []
    if not isinstance(document, dict):
        return report, ["DOCUMENT_OBJECT_REQUIRED"]
    header_ok = (
        document.get("schema") == VECTOR_SCHEMA
        and document.get("version") == sc.VERSION
        and document.get("core_version") == sc.CORE_VERSION
        and document.get("profile_id") == sc.PROFILE_ID
        and document.get("ruleset_id") == sc.RULESET_ID
        and document.get("canonicalization_id") == sc.CANONICALIZATION_ID
        and document.get("identity_domain_id") == sc.identity_domain_id()
    )
    material = json.loads(json.dumps(document, ensure_ascii=False))
    vector_set_id = material.pop("vector_set_id", None)
    id_ok = vector_set_id == VECTOR_SET_ID_PREFIX + vector_hash(material)
    report["header"] = (int(header_ok and id_ok), 1)
    if not header_ok:
        failures.append("header")
    if not id_ok:
        failures.append("vector_set_id")

    semantic_pass = 0
    semantic_total = 0
    for vector in document.get("semantic_vectors", []):
        semantic_total += 1
        actual_result = sc.resolve_claims(vector.get("input"))
        actual_summary = sc.make_summary(vector.get("input"))
        ok = actual_result == vector.get("expected_result") and actual_summary == vector.get("expected_summary")
        semantic_pass += int(ok)
        if not ok:
            failures.append("semantic:" + str(vector.get("name")))
    report["semantic"] = (semantic_pass, semantic_total)

    parser_pass = 0
    parser_total = 0
    for vector in document.get("parser_vectors", []):
        parser_total += 1
        try:
            sc.strict_json_load_text(vector.get("text", ""))
            parsed = True
        except Exception:
            parsed = False
        ok = parsed == bool(vector.get("should_parse"))
        parser_pass += int(ok)
        if not ok:
            failures.append("parser:" + str(vector.get("name")))
    report["parser"] = (parser_pass, parser_total)

    relation_pass = 0
    relation_total = 0
    for vector in document.get("relations", []):
        relation_total += 1
        left = sc.resolve_claims(vector.get("left"))
        right = sc.resolve_claims(vector.get("right"))
        predicate = vector.get("predicate")
        if predicate == "canonical_input_id_equal":
            actual = left["canonical_input_id"] == right["canonical_input_id"]
        elif predicate == "context_id_equal":
            actual = left["context_id"] == right["context_id"]
        elif predicate == "outcome_equal":
            actual = left["claim_outcome"] == right["claim_outcome"]
        elif predicate == "payability_equal":
            actual = left["payable_amount_minor"] == right["payable_amount_minor"] and left["claim_outcome"] == right["claim_outcome"]
        elif predicate == "same_quantum_different_evidence_id":
            actual = left["payable_amount_minor"] == right["payable_amount_minor"] and left["evidence_set_id"] != right["evidence_set_id"]
        elif predicate == "right_payable_gte_left":
            actual = right["payable_amount_minor"] >= left["payable_amount_minor"]
        elif predicate == "right_payable_lte_left":
            actual = right["payable_amount_minor"] <= left["payable_amount_minor"]
        elif predicate == "full_result_equal":
            actual = left == right
        elif predicate == "summary_equal":
            actual = sc.make_summary(vector.get("left")) == sc.make_summary(vector.get("right"))
        elif predicate == "submission_id_equal":
            actual = left["submission_id"] == right["submission_id"]
        else:
            actual = False
        ok = actual == bool(vector.get("expected"))
        relation_pass += int(ok)
        if not ok:
            failures.append("relation:" + str(vector.get("name")))
    report["relations"] = (relation_pass, relation_total)

    artifact_pass = 0
    artifact_total = 0
    for vector in document.get("artifact_vectors", []):
        artifact_total += 1
        kind = vector.get("kind")
        if kind == "bundle":
            actual = sc.verify_bundle(vector.get("artifact"))[0]
            ok = actual == bool(vector.get("expected_pass"))
        elif kind == "receipt_integrity":
            actual = sc.check_receipt_integrity(vector.get("artifact"))[0]
            ok = actual == bool(vector.get("expected_pass"))
        elif kind == "receipt_bundle":
            actual = sc.verify_receipt_against_bundle(vector.get("receipt"), vector.get("bundle"))[0]
            ok = actual == bool(vector.get("expected_pass"))
        elif kind == "summary":
            ok = sc.make_summary(vector.get("input")) == vector.get("expected")
        elif kind == "summary_pair":
            actual = sc.make_summary(vector.get("left")) == sc.make_summary(vector.get("right"))
            ok = actual == bool(vector.get("expected_pass"))
        elif kind == "attestation_integrity":
            actual = sc.check_attestation_integrity(vector.get("artifact"))[0]
            ok = actual == bool(vector.get("expected_pass"))
        elif kind == "attestation_input":
            actual = sc.verify_attestation_against_input(vector.get("artifact"), vector.get("input"))[0]
            ok = actual == bool(vector.get("expected_pass"))
        elif kind == "contract":
            actual = vector.get("artifact") == sc.contract_manifest()
            ok = actual == bool(vector.get("expected_pass"))
        else:
            ok = False
        artifact_pass += int(ok)
        if not ok:
            failures.append("artifact:" + str(vector.get("name")))
    report["artifacts"] = (artifact_pass, artifact_total)

    serialization_pass = 0
    serialization_total = 0
    for vector in document.get("serialization_vectors", []):
        serialization_total += 1
        try:
            value = sc.strict_json_load_text(vector.get("canonical", ""))
            ok = sc.sha256_hex(value) == vector.get("sha256") and sc.canonical_json(value) == vector.get("canonical")
        except Exception:
            ok = False
        serialization_pass += int(ok)
        if not ok:
            failures.append("serialization:" + str(vector.get("name")))
    report["serialization"] = (serialization_pass, serialization_total)

    reference = document.get("reference_evidence", {})
    reference_input = sc.build_reference_input(False, True)
    reference_bundle = sc.build_bundle(reference_input)
    reference_receipt = sc.make_receipt(reference_bundle)
    reference_abstain_input = refresh(sc, mutate(reference_input, lambda x: x["context"].__setitem__("evaluation_authorized", False)))
    reference_checks = [
        reference.get("example_input") == reference_input,
        reference.get("bundle") == reference_bundle,
        reference.get("receipt") == reference_receipt,
        reference.get("abstain_input") == reference_abstain_input,
        reference.get("attestation") == sc.make_attestation(reference_abstain_input),
        reference.get("contract") == sc.contract_manifest(),
    ]
    report["reference_evidence"] = (sum(int(x) for x in reference_checks), len(reference_checks))
    if not all(reference_checks):
        failures.append("reference_evidence")
    return report, failures


def print_report(report: Dict[str, Tuple[int, int]], failures: List[str]) -> int:
    total_pass = 0
    total = 0
    for key in ["header", "semantic", "parser", "relations", "artifacts", "serialization", "reference_evidence"]:
        passed, count = report.get(key, (0, 0))
        total_pass += passed
        total += count
        print(key + ": " + str(passed) + "/" + str(count) + " reproduced")
    print("TOTAL: " + str(total_pass) + "/" + str(total) + " PASS")
    if failures:
        for failure in failures:
            print("FAIL " + failure)
        print("VERIFY: FAIL")
        return 1
    print("VERIFY: PASS")
    return 0


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="slang_claims_vectors_v0_2_1.py")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", metavar="PATH")
    group.add_argument("--verify", metavar="PATH")
    parser.add_argument("--core", default=EXPECTED_CORE_FILENAME)
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    core_path = Path(args.core)
    if not core_path.is_absolute():
        core_path = Path(__file__).resolve().parent / core_path
    sc = load_core(core_path)
    if args.write:
        document = build_document(sc)
        Path(args.write).write_text(json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        report, failures = verify_document(sc, document)
        return print_report(report, failures)
    document = load_vector_file(Path(args.verify))
    report, failures = verify_document(sc, document)
    return print_report(report, failures)


if __name__ == "__main__":
    raise SystemExit(main())
