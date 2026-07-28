#!/usr/bin/env python3
"""
SLANG-ResetPassword frozen conformance-vector generator and verifier.

Python 3.9+
Standard library only
"""

import argparse
import copy
import hashlib
import importlib.util
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple


VECTOR_SCHEMA = "SLANG-RESET-PASSWORD-VECTORS-1"
EXPECTED_CORE_FILENAME = "slang_reset_password_v0_1_0.py"
EXPECTED_VECTOR_FILENAME = "SLANG_ResetPassword_Vectors_v0_1_0.json"
VECTOR_SET_ID_PREFIX = "slang_reset_password_vector_set_sha256:"


def load_reference(path: Path):
    spec = importlib.util.spec_from_file_location("slang_reset_password_reference", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load reference implementation")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def mutate(source: Any, fn: Callable[[Any], None]) -> Any:
    value = copy.deepcopy(source)
    fn(value)
    return value


def without_declared_identities(value: Dict[str, Any]) -> Dict[str, Any]:
    candidate = copy.deepcopy(value)
    candidate.pop("declared_context_id", None)
    candidate.pop("declared_evidence_set_id", None)
    return candidate


def refresh(se, value: Dict[str, Any]) -> Dict[str, Any]:
    return se.attach_declared_identities(without_declared_identities(value))


def reordered_object(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: reordered_object(value[key]) for key in reversed(list(value.keys()))}
    if isinstance(value, list):
        return [reordered_object(item) for item in value]
    return copy.deepcopy(value)


def build_disagreement(se) -> Dict[str, Any]:
    value = se.build_multi_authorizer_input()
    value["authorization_evidence"][1]["authorization_result"] = se.OUTCOME_RESET_NOT_AUTHORIZED
    value["authorization_evidence"][1]["evidence_commitment"] = se.commitment("VECTOR-DISAGREEMENT")
    return refresh(se, value)


def build_missing_authorizer(se) -> Dict[str, Any]:
    value = se.build_multi_authorizer_input()
    value["authorization_evidence"] = value["authorization_evidence"][:1]
    return refresh(se, value)


def build_unexpected_authorizer(se) -> Dict[str, Any]:
    value = se.build_reference_input()
    context = value["context"]
    value["authorization_evidence"].append(
        se.build_evidence_record("AUTHORIZER-B", "RESET-EVIDENCE-002", se.OUTCOME_RESET_AUTHORIZED, context)
    )
    return refresh(se, value)


def build_duplicate_evidence_id(se) -> Dict[str, Any]:
    value = se.build_multi_authorizer_input()
    value["authorization_evidence"][1]["evidence_id"] = value["authorization_evidence"][0]["evidence_id"]
    return refresh(se, value)


def build_duplicate_authorizer_id(se) -> Dict[str, Any]:
    value = se.build_multi_authorizer_input()
    value["authorization_evidence"][1]["authorizer_id"] = value["authorization_evidence"][0]["authorizer_id"]
    return refresh(se, value)


def build_binding_mismatch(se, field: str, replacement: str) -> Dict[str, Any]:
    value = se.build_reference_input()
    value["authorization_evidence"][0][field] = replacement
    return refresh(se, value)


def build_changed_context(se, field: str, replacement: str) -> Dict[str, Any]:
    value = se.build_reference_input()
    value["context"][field] = replacement
    value["authorization_evidence"][0][field] = replacement
    return refresh(se, value)


def build_changed_commitment(se) -> Dict[str, Any]:
    value = se.build_reference_input()
    value["authorization_evidence"][0]["evidence_commitment"] = se.commitment("VECTOR-DIFFERENT-EVIDENCE")
    return refresh(se, value)


def build_oversized_evidence(se) -> Dict[str, Any]:
    value = se.build_reference_input()
    context = value["context"]
    value["authorization_evidence"] = [
        se.build_evidence_record(
            "AUTHORIZER-" + str(index),
            "EVIDENCE-" + str(index),
            se.OUTCOME_RESET_AUTHORIZED,
            context,
        )
        for index in range(se.MAX_EVIDENCE_RECORDS + 1)
    ]
    return without_declared_identities(value)



def build_reference_value_input(se) -> Dict[str, Any]:
    value = se.build_reference_input()
    value["context"]["subject_ref"] = "HUNTER2"
    value["authorization_evidence"][0]["subject_ref"] = "HUNTER2"
    return refresh(se, value)


def build_ascii_trimmed_identifier_input(se) -> Dict[str, Any]:
    value = se.build_reference_input()
    value["context"]["subject_ref"] = "\t subject-alpha \r\n"
    value["authorization_evidence"][0]["subject_ref"] = " subject-alpha\t"
    return refresh(se, value)


def build_ascii_trimmed_commitment_input(se) -> Dict[str, Any]:
    value = se.build_reference_input()
    current = value["authorization_evidence"][0]["evidence_commitment"]
    value["authorization_evidence"][0]["evidence_commitment"] = " \t" + current.upper() + "\r\n"
    return refresh(se, value)


def materialize_parser_text(se, vector: Dict[str, Any]) -> str:
    if "raw_json" in vector:
        raw_json = vector.get("raw_json")
        return raw_json if isinstance(raw_json, str) else ""
    generator = vector.get("generator")
    if generator == "BYTE_LIMIT_STRUCTURALLY_VALID":
        groups = int(vector.get("groups", 0))
        items = int(vector.get("items", 0))
        item_value = vector.get("item_value", "REFERENCE-VALUE-0001")
        inner = "[" + ",".join(se.canonical_json(item_value) for _ in range(items)) + "]"
        return "[" + ",".join(inner for _ in range(groups)) + "]"
    if generator == "NESTED_ARRAY":
        depth = int(vector.get("depth", 0))
        return ("[" * depth) + "0" + ("]" * depth)
    if generator == "NODE_LIMIT_TREE":
        groups = int(vector.get("groups", 0))
        items = int(vector.get("items", 0))
        inner = "[" + ",".join("0" for _ in range(items)) + "]"
        return "[" + ",".join(inner for _ in range(groups)) + "]"
    raise ValueError("unsupported parser vector generator")

def build_semantic_inputs(se) -> List[Tuple[str, Any]]:
    reference = se.build_reference_input()
    not_authorized = se.build_reference_input(se.OUTCOME_RESET_NOT_AUTHORIZED)
    hidden = se.build_reference_input(visible=False)
    multi_authorized = se.build_multi_authorizer_input(se.OUTCOME_RESET_AUTHORIZED)
    multi_not_authorized = se.build_multi_authorizer_input(se.OUTCOME_RESET_NOT_AUTHORIZED)

    unauthorized = se.build_reference_input()
    unauthorized["context"]["evaluation_authorized"] = False
    unauthorized = refresh(se, unauthorized)

    normalized = se.build_reference_input()
    normalized["context"]["subject_ref"] = "\t subject-alpha \r\n"
    normalized["authorization_evidence"][0]["subject_ref"] = " subject-alpha\t"
    normalized = refresh(se, normalized)

    unsupported_profile = without_declared_identities(
        mutate(reference, lambda value: value.__setitem__("profile_id", "OTHER-PROFILE"))
    )
    unsupported_ruleset = without_declared_identities(
        mutate(reference, lambda value: value.__setitem__("ruleset_id", "OTHER-RULESET"))
    )
    unsupported_schema = without_declared_identities(
        mutate(reference, lambda value: value.__setitem__("schema", "OTHER-SCHEMA"))
    )
    unsupported_mode = without_declared_identities(
        mutate(reference, lambda value: value["context"].__setitem__("evidence_mode", "MAJORITY"))
    )
    unsupported_authorizer_profile = without_declared_identities(
        mutate(
            reference,
            lambda value: value["authorization_evidence"][0].__setitem__(
                "authorizer_profile_id", "OTHER-AUTHORIZER-PROFILE"
            ),
        )
    )

    vectors: List[Tuple[str, Any]] = [
        ("reference_reset_authorized_visible", reference),
        ("reference_reset_not_authorized_visible", not_authorized),
        ("reference_reset_authorized_withheld", hidden),
        ("multi_authorizer_reset_authorized", multi_authorized),
        ("multi_authorizer_reset_not_authorized", multi_not_authorized),
        ("evaluation_not_authorized", unauthorized),
        ("identifier_normalization", normalized),
        ("missing_context", mutate(reference, lambda value: value.pop("context"))),
        ("missing_authorization_evidence", mutate(reference, lambda value: value.pop("authorization_evidence"))),
        ("empty_authorization_evidence", mutate(reference, lambda value: value.__setitem__("authorization_evidence", []))),
        ("missing_declared_context_id", mutate(reference, lambda value: value.pop("declared_context_id"))),
        ("missing_declared_evidence_set_id", mutate(reference, lambda value: value.pop("declared_evidence_set_id"))),
        ("missing_context_replacement_request_ref", mutate(reference, lambda value: value["context"].pop("replacement_request_ref"))),
        ("missing_context_evaluation_authorized", mutate(reference, lambda value: value["context"].pop("evaluation_authorized"))),
        ("missing_context_visibility_authorized", mutate(reference, lambda value: value["context"].pop("reference_visibility_authorized"))),
        ("missing_evidence_recovery_case_ref", mutate(reference, lambda value: value["authorization_evidence"][0].pop("recovery_case_ref"))),
        ("missing_evidence_authorization_result", mutate(reference, lambda value: value["authorization_evidence"][0].pop("authorization_result"))),
        ("missing_profile_id", mutate(reference, lambda value: value.pop("profile_id"))),
        ("missing_ruleset_id", mutate(reference, lambda value: value.pop("ruleset_id"))),
        ("missing_schema", mutate(reference, lambda value: value.pop("schema"))),
        ("subject_binding_mismatch", build_binding_mismatch(se, "subject_ref", "SUBJECT-OTHER")),
        ("credential_binding_mismatch", build_binding_mismatch(se, "credential_ref", "CREDENTIAL-OTHER")),
        ("credential_version_before_mismatch", build_binding_mismatch(se, "credential_version_before", "CREDENTIAL-VERSION-999")),
        ("replacement_request_binding_mismatch", build_binding_mismatch(se, "replacement_request_ref", "REPLACEMENT-REQUEST-999")),
        ("relying_party_binding_mismatch", build_binding_mismatch(se, "relying_party_ref", "RELYING-PARTY-OTHER")),
        ("recovery_case_binding_mismatch", build_binding_mismatch(se, "recovery_case_ref", "RECOVERY-CASE-999")),
        ("multi_authorizer_result_disagreement", build_disagreement(se)),
        ("multi_authorizer_missing_expected_authorizer", build_missing_authorizer(se)),
        ("single_authorizer_unexpected_authorizer", build_unexpected_authorizer(se)),
        ("duplicate_evidence_id", build_duplicate_evidence_id(se)),
        ("duplicate_authorizer_id", build_duplicate_authorizer_id(se)),
        ("declared_context_id_mismatch", mutate(reference, lambda value: value.__setitem__("declared_context_id", se.CONTEXT_ID_PREFIX + ("0" * 64)))),
        ("declared_evidence_set_id_mismatch", mutate(reference, lambda value: value.__setitem__("declared_evidence_set_id", se.EVIDENCE_SET_ID_PREFIX + ("0" * 64)))),
        ("unsupported_profile", unsupported_profile),
        ("unsupported_ruleset", unsupported_ruleset),
        ("unsupported_schema", unsupported_schema),
        ("unsupported_evidence_mode", unsupported_mode),
        ("unsupported_authorizer_profile", unsupported_authorizer_profile),
        ("top_level_array", [1, 2, 3]),
        ("top_level_null", None),
        ("unknown_top_level_field", mutate(reference, lambda value: value.__setitem__("unexpected", "VALUE"))),
        ("unknown_context_field", without_declared_identities(mutate(reference, lambda value: value["context"].__setitem__("unexpected", "VALUE")))),
        ("unknown_evidence_field", without_declared_identities(mutate(reference, lambda value: value["authorization_evidence"][0].__setitem__("unexpected", "VALUE")))),
        ("raw_password_forbidden", mutate(reference, lambda value: value.__setitem__("password", "VECTOR-RAW-PASSWORD"))),
        ("new_password_forbidden", mutate(reference, lambda value: value.__setitem__("new_password", "VECTOR-NEW-PASSWORD"))),
        ("reset_token_forbidden", mutate(reference, lambda value: value.__setitem__("reset_token", "VECTOR-RESET-TOKEN"))),
        ("otp_forbidden", mutate(reference, lambda value: value.__setitem__("otp", "123456"))),
        ("recovery_code_forbidden", mutate(reference, lambda value: value.__setitem__("recovery_code", "VECTOR-RECOVERY-CODE"))),
        ("password_hash_forbidden", mutate(reference, lambda value: value.__setitem__("password_hash", "VECTOR-HASH"))),
        ("caller_authenticated_forbidden", mutate(reference, lambda value: value.__setitem__("authenticated", True))),
        ("caller_access_forbidden", mutate(reference, lambda value: value.__setitem__("access", "GRANTED"))),
        ("caller_reset_authorized_forbidden", mutate(reference, lambda value: value.__setitem__("reset_authorized", True))),
        ("caller_credential_replaced_forbidden", mutate(reference, lambda value: value.__setitem__("credential_replaced", True))),
        ("caller_reset_authority_forbidden", mutate(reference, lambda value: value.__setitem__("reset_authority", "GRANTED"))),
        ("caller_resolution_state_forbidden", mutate(reference, lambda value: value.__setitem__("resolution_state", "RESOLVED"))),
        ("caller_bundle_id_forbidden", mutate(reference, lambda value: value.__setitem__("bundle_id", se.BUNDLE_ID_PREFIX + ("0" * 64)))),
        ("caller_public_summary_id_forbidden", mutate(reference, lambda value: value.__setitem__("public_summary_id", se.PUBLIC_SUMMARY_ID_PREFIX + ("0" * 64)))),
        ("nested_secret_forbidden", mutate(reference, lambda value: value.__setitem__("container", {"secret": "VECTOR-NESTED-SECRET"}))),
        ("invalid_context_identifier", without_declared_identities(mutate(reference, lambda value: value["context"].__setitem__("subject_ref", "INVALID SPACE")))),
        ("invalid_evidence_identifier", without_declared_identities(mutate(reference, lambda value: value["authorization_evidence"][0].__setitem__("evidence_id", "INVALID SPACE")))),
        ("invalid_evidence_commitment", without_declared_identities(mutate(reference, lambda value: value["authorization_evidence"][0].__setitem__("evidence_commitment", "sha256:1234")))),
        ("invalid_authorization_result", without_declared_identities(mutate(reference, lambda value: value["authorization_evidence"][0].__setitem__("authorization_result", "UNKNOWN")))),
        ("invalid_evaluation_authorized_type", without_declared_identities(mutate(reference, lambda value: value["context"].__setitem__("evaluation_authorized", "true")))),
        ("invalid_visibility_authorized_type", without_declared_identities(mutate(reference, lambda value: value["context"].__setitem__("reference_visibility_authorized", 1)))),
        ("authorization_evidence_not_array", without_declared_identities(mutate(reference, lambda value: value.__setitem__("authorization_evidence", {})))),
        ("context_not_object", without_declared_identities(mutate(reference, lambda value: value.__setitem__("context", [])))),
        ("evidence_record_not_object", without_declared_identities(mutate(reference, lambda value: value.__setitem__("authorization_evidence", ["EVIDENCE"])))),
        ("evidence_record_limit", build_oversized_evidence(se)),
        ("identifier_length_limit", without_declared_identities(mutate(reference, lambda value: value["context"].__setitem__("subject_ref", "A" * (se.MAX_IDENTIFIER_LENGTH + 1))))),
        ("single_mode_multiple_expected_authorizers", without_declared_identities(mutate(reference, lambda value: value["context"].__setitem__("expected_authorizer_ids", ["AUTHORIZER-A", "AUTHORIZER-B"])))),
        ("multi_mode_one_expected_authorizer", without_declared_identities(mutate(multi_authorized, lambda value: value["context"].__setitem__("expected_authorizer_ids", ["AUTHORIZER-A"])))),
        ("empty_expected_authorizer_ids", without_declared_identities(mutate(reference, lambda value: value["context"].__setitem__("expected_authorizer_ids", [])))),
        ("duplicate_expected_authorizer_ids", without_declared_identities(mutate(multi_authorized, lambda value: value["context"].__setitem__("expected_authorizer_ids", ["AUTHORIZER-A", "AUTHORIZER-A"])))),
        ("forbidden_precedence_over_incomplete", mutate(reference, lambda value: (value.__setitem__("password", "VECTOR-SECRET"), value.pop("context")))),
        ("forbidden_precedence_over_conflict", mutate(reference, lambda value: (value.__setitem__("password", "VECTOR-SECRET"), value.__setitem__("declared_context_id", se.CONTEXT_ID_PREFIX + ("0" * 64))))),
        ("unsupported_precedence_over_incomplete", without_declared_identities(mutate(reference, lambda value: (value.__setitem__("profile_id", "OTHER-PROFILE"), value.pop("context"))))),
        ("conflict_precedence_over_unsupported", mutate(reference, lambda value: (value["authorization_evidence"][0].__setitem__("subject_ref", "SUBJECT-OTHER"), value.__setitem__("profile_id", "OTHER-PROFILE")))),
        ("incomplete_precedence_over_abstain", mutate(unauthorized, lambda value: value.pop("declared_context_id"))),
        ("allowed_reference_value_not_content_classified", build_reference_value_input(se)),
        ("ascii_trimmed_identifier_normalization", build_ascii_trimmed_identifier_input(se)),
        ("identifier_trailing_nel_unsupported", mutate(reference, lambda value: value["context"].__setitem__("subject_ref", "SUBJECT-ALPHA\u0085"))),
        ("identifier_trailing_nbsp_unsupported", mutate(reference, lambda value: value["context"].__setitem__("subject_ref", "SUBJECT-ALPHA\u00a0"))),
        ("identifier_leading_em_space_unsupported", mutate(reference, lambda value: value["context"].__setitem__("subject_ref", "\u2003SUBJECT-ALPHA"))),
        ("identifier_sharp_s_unsupported", mutate(reference, lambda value: value["context"].__setitem__("subject_ref", "ßprint"))),
        ("identifier_ligature_fi_unsupported", mutate(reference, lambda value: value["context"].__setitem__("subject_ref", "ﬁle"))),
        ("identifier_fullwidth_unsupported", mutate(reference, lambda value: value["context"].__setitem__("subject_ref", "ＳUBJECT-ALPHA"))),
        ("ascii_trimmed_commitment_normalization", build_ascii_trimmed_commitment_input(se)),
        ("commitment_trailing_nel_unsupported", without_declared_identities(mutate(reference, lambda value: value["authorization_evidence"][0].__setitem__("evidence_commitment", value["authorization_evidence"][0]["evidence_commitment"] + "\u0085")))),
        ("commitment_trailing_nbsp_unsupported", without_declared_identities(mutate(reference, lambda value: value["authorization_evidence"][0].__setitem__("evidence_commitment", value["authorization_evidence"][0]["evidence_commitment"] + "\u00a0")))),
        ("commitment_non_ascii_character_unsupported", without_declared_identities(mutate(reference, lambda value: value["authorization_evidence"][0].__setitem__("evidence_commitment", "sha256:" + ("a" * 63) + "ａ")))),
        ("ascii_padded_forbidden_field", mutate(reference, lambda value: value.__setitem__(" PASSWORD ", "VECTOR-PADDED-SECRET"))),
        ("nested_mixed_case_forbidden_field", mutate(reference, lambda value: value.__setitem__("container", {"Password": "VECTOR-NESTED-CASE-SECRET"}))),
        ("non_ascii_suffixed_forbidden_name_unsupported", mutate(reference, lambda value: value.__setitem__("password\u0085", "VECTOR-NONASCII-NAME"))),
        ("non_ascii_lookalike_forbidden_name_unsupported", mutate(reference, lambda value: value.__setitem__("ｐassword", "VECTOR-LOOKALIKE-NAME"))),
    ]
    return vectors


def build_semantic_vectors(se) -> List[Dict[str, Any]]:
    return [
        {
            "name": name,
            "input": value,
            "expected": se.resolve_reset_password(value),
        }
        for name, value in build_semantic_inputs(se)
    ]


def build_presentation_vectors(se) -> List[Dict[str, Any]]:
    values = [
        ("visible_reset_authorized", se.build_reference_input()),
        ("visible_reset_not_authorized", se.build_reference_input(se.OUTCOME_RESET_NOT_AUTHORIZED)),
        ("withheld_reset_authorized", se.build_reference_input(visible=False)),
        ("withheld_reset_not_authorized", se.build_reference_input(se.OUTCOME_RESET_NOT_AUTHORIZED, visible=False)),
        ("incomplete_result", mutate(se.build_reference_input(), lambda value: value.pop("context"))),
        ("forbidden_result", mutate(se.build_reference_input(), lambda value: value.__setitem__("password", "VECTOR-RAW-PASSWORD"))),
    ]
    return [
        {
            "name": name,
            "input": value,
            "expected": se.public_summary(se.build_bundle(value)),
        }
        for name, value in values
    ]


def build_parser_vectors(se) -> List[Dict[str, Any]]:
    return [
        {"name": "duplicate_object_key", "raw_json": '{"schema":"A","schema":"B"}', "expected": "REJECT"},
        {"name": "floating_point", "raw_json": '{"value":1.5}', "expected": "REJECT"},
        {"name": "nan", "raw_json": '{"value":NaN}', "expected": "REJECT"},
        {"name": "positive_infinity", "raw_json": '{"value":Infinity}', "expected": "REJECT"},
        {"name": "negative_infinity", "raw_json": '{"value":-Infinity}', "expected": "REJECT"},
        {"name": "portable_integer_overflow", "raw_json": '{"value":9007199254740992}', "expected": "REJECT"},
        {"name": "lone_unicode_surrogate", "raw_json": '"\\ud800"', "expected": "REJECT"},
        {"name": "portable_integer_limit", "raw_json": '{"value":9007199254740991}', "expected": "ACCEPT"},
        {"name": "ordinary_object", "raw_json": '{"value":"ok"}', "expected": "ACCEPT"},
        {"name": "top_level_array", "raw_json": '[1,2,3]', "expected": "ACCEPT"},
        {
            "name": "json_input_byte_limit",
            "generator": "BYTE_LIMIT_STRUCTURALLY_VALID",
            "groups": 256,
            "items": 194,
            "item_value": "REFERENCE-VALUE-0001",
            "expected": "REJECT",
        },
        {
            "name": "json_depth_limit",
            "generator": "NESTED_ARRAY",
            "depth": se.MAX_JSON_DEPTH + 1,
            "expected": "REJECT",
        },
        {
            "name": "json_node_limit",
            "generator": "NODE_LIMIT_TREE",
            "groups": 256,
            "items": 195,
            "expected": "REJECT",
        },
    ]


def build_relations(se) -> List[Dict[str, Any]]:
    reference = se.build_reference_input()
    not_authorized = se.build_reference_input(se.OUTCOME_RESET_NOT_AUTHORIZED)
    hidden = se.build_reference_input(visible=False)
    multi = se.build_multi_authorizer_input()
    reordered_multi = copy.deepcopy(multi)
    reordered_multi["authorization_evidence"] = list(reversed(reordered_multi["authorization_evidence"]))

    normalized = copy.deepcopy(reference)
    normalized["context"]["subject_ref"] = " subject-alpha "
    normalized["authorization_evidence"][0]["subject_ref"] = "subject-alpha"
    normalized = refresh(se, normalized)

    return [
        {
            "name": "top_level_key_order_invariance",
            "left_input": reference,
            "right_input": reordered_object(reference),
            "equal_fields": ["canonical_input_id", "context_id", "evidence_set_id", "result_id", "state"],
            "different_fields": [],
        },
        {
            "name": "context_key_order_invariance",
            "left_input": reference,
            "right_input": mutate(reference, lambda value: value.__setitem__("context", reordered_object(value["context"]))),
            "equal_fields": ["canonical_input_id", "context_id", "result_id"],
            "different_fields": [],
        },
        {
            "name": "evidence_key_order_invariance",
            "left_input": reference,
            "right_input": mutate(reference, lambda value: value["authorization_evidence"].__setitem__(0, reordered_object(value["authorization_evidence"][0]))),
            "equal_fields": ["canonical_input_id", "evidence_set_id", "result_id"],
            "different_fields": [],
        },
        {
            "name": "multi_authorizer_record_order_invariance",
            "left_input": multi,
            "right_input": reordered_multi,
            "equal_fields": ["canonical_input_id", "evidence_set_id", "evidence_agreement_id", "result_id"],
            "different_fields": [],
        },
        {
            "name": "identifier_normalization",
            "left_input": reference,
            "right_input": normalized,
            "equal_fields": ["canonical_input_id", "context_id", "evidence_set_id", "result_id"],
            "different_fields": ["submission_id"],
        },
        {
            "name": "visibility_separation",
            "left_input": reference,
            "right_input": hidden,
            "equal_fields": ["state", "authorization_outcome", "admission_state", "evidence_set_id"],
            "different_fields": ["visibility_state", "outcome_visible", "outcome_id", "result_id"],
        },
        {
            "name": "reset_authorized_not_authorized_distinction",
            "left_input": reference,
            "right_input": not_authorized,
            "equal_fields": ["state", "context_id", "authorizer_manifest_id", "rule_profile_id"],
            "different_fields": ["authorization_outcome", "admission_state", "evidence_set_id", "outcome_id", "result_id"],
        },
        {
            "name": "replacement_request_identity_change",
            "left_input": reference,
            "right_input": build_changed_context(se, "replacement_request_ref", "REPLACEMENT-REQUEST-NEW"),
            "equal_fields": ["state", "authorization_outcome", "admission_state"],
            "different_fields": ["context_id", "canonical_input_id", "outcome_id", "result_id"],
        },
        {
            "name": "credential_version_before_identity_change",
            "left_input": reference,
            "right_input": build_changed_context(se, "credential_version_before", "CREDENTIAL-VERSION-004"),
            "equal_fields": ["state", "authorization_outcome", "admission_state"],
            "different_fields": ["context_id", "canonical_input_id", "outcome_id", "result_id"],
        },
        {
            "name": "evidence_commitment_identity_change",
            "left_input": reference,
            "right_input": build_changed_commitment(se),
            "equal_fields": ["state", "authorization_outcome", "admission_state", "context_id"],
            "different_fields": ["evidence_set_id", "evidence_agreement_id", "canonical_input_id", "result_id"],
        },
        {
            "name": "forbidden_reset_secret_changes_state",
            "left_input": reference,
            "right_input": mutate(reference, lambda value: value.__setitem__("password", "VECTOR-RAW-PASSWORD")),
            "equal_fields": ["execution_authority", "reset_authority", "credential_mutation_authority", "authentication_authority", "access_authority", "session_authority"],
            "different_fields": ["state", "admission_state", "submission_id", "result_id"],
        },
        {
            "name": "declared_context_identity_required",
            "left_input": reference,
            "right_input": mutate(reference, lambda value: value.pop("declared_context_id")),
            "equal_fields": ["execution_authority", "reset_authority", "credential_mutation_authority", "authentication_authority", "access_authority", "session_authority"],
            "different_fields": ["state", "result_id"],
        },
    ]


def build_artifact_vectors(se) -> List[Dict[str, Any]]:
    reference_input = se.build_reference_input()
    reference_bundle = se.build_bundle(reference_input)
    reference_receipt = se.make_receipt(reference_bundle)
    reference_summary = se.public_summary(reference_bundle)

    hidden_authorized_bundle = se.build_bundle(se.build_reference_input(visible=False))
    hidden_not_authorized_bundle = se.build_bundle(
        se.build_reference_input(se.OUTCOME_RESET_NOT_AUTHORIZED, visible=False)
    )
    hidden_authorized_summary = se.public_summary(hidden_authorized_bundle)
    hidden_not_authorized_summary = se.public_summary(hidden_not_authorized_bundle)

    tampered_bundle = copy.deepcopy(reference_bundle)
    tampered_bundle["result"]["admission_state"] = se.ADMISSION_DENY

    tampered_bundle_id = copy.deepcopy(reference_bundle)
    tampered_bundle_id["bundle_id"] = se.BUNDLE_ID_PREFIX + ("0" * 64)

    tampered_receipt = copy.deepcopy(reference_receipt)
    tampered_receipt["state"] = se.STATE_CONFLICT

    reset_authority_receipt = copy.deepcopy(reference_receipt)
    reset_authority_receipt["reset_authority"] = "GRANTED"
    reset_authority_receipt["receipt_id"] = se.identity(
        se.RECEIPT_ID_PREFIX,
        {key: value for key, value in reset_authority_receipt.items() if key != "receipt_id"},
    )

    mutation_authority_receipt = copy.deepcopy(reference_receipt)
    mutation_authority_receipt["credential_mutation_authority"] = "GRANTED"
    mutation_authority_receipt["receipt_id"] = se.identity(
        se.RECEIPT_ID_PREFIX,
        {key: value for key, value in mutation_authority_receipt.items() if key != "receipt_id"},
    )

    unrelated_receipt = se.make_receipt(se.build_bundle(se.build_reference_input(se.OUTCOME_RESET_NOT_AUTHORIZED)))

    secret_input = mutate(reference_input, lambda value: value.__setitem__("password", "VECTOR-PRIVATE-MARKER"))
    secret_bundle = se.build_bundle(secret_input)
    secret_receipt = se.make_receipt(secret_bundle)

    reference_value_bundle = se.build_bundle(build_reference_value_input(se))
    reference_value_receipt = se.make_receipt(reference_value_bundle)

    unsupported_value_input = mutate(reference_input, lambda value: value.__setitem__("api_key", "VECTOR-UNSUPPORTED-PRIVATE-MARKER"))
    unsupported_value_bundle = se.build_bundle(unsupported_value_input)
    unsupported_value_receipt = se.make_receipt(unsupported_value_bundle)

    tampered_hidden_outcome = copy.deepcopy(hidden_authorized_summary)
    tampered_hidden_outcome["authorization_outcome"] = se.OUTCOME_RESET_AUTHORIZED
    tampered_hidden_outcome["public_summary_id"] = se.identity(
        se.PUBLIC_SUMMARY_ID_PREFIX,
        {
            key: value
            for key, value in tampered_hidden_outcome.items()
            if key != "public_summary_id"
        },
    )

    tampered_hidden_reason = copy.deepcopy(hidden_authorized_summary)
    tampered_hidden_reason["reason_codes"] = ["RESET_AUTHORIZATION_EVIDENCE_ADMITTED"]
    tampered_hidden_reason["public_summary_id"] = se.identity(
        se.PUBLIC_SUMMARY_ID_PREFIX,
        {
            key: value
            for key, value in tampered_hidden_reason.items()
            if key != "public_summary_id"
        },
    )

    tampered_hidden_result_id = copy.deepcopy(hidden_authorized_summary)
    tampered_hidden_result_id["result_id"] = hidden_authorized_bundle["result"]["result_id"]
    tampered_hidden_result_id["public_summary_id"] = se.identity(
        se.PUBLIC_SUMMARY_ID_PREFIX,
        {
            key: value
            for key, value in tampered_hidden_result_id.items()
            if key != "public_summary_id"
        },
    )

    tampered_hidden_bundle_id = copy.deepcopy(hidden_authorized_summary)
    tampered_hidden_bundle_id["bundle_id"] = hidden_authorized_bundle["bundle_id"]
    tampered_hidden_bundle_id["public_summary_id"] = se.identity(
        se.PUBLIC_SUMMARY_ID_PREFIX,
        {
            key: value
            for key, value in tampered_hidden_bundle_id.items()
            if key != "public_summary_id"
        },
    )

    return [
        {"name": "reference_bundle_verifies", "operation": "VERIFY_BUNDLE", "bundle": reference_bundle, "expected_ok": True, "expected_reason": "PASS"},
        {"name": "reference_receipt_verifies", "operation": "VERIFY_RECEIPT", "receipt": reference_receipt, "expected_ok": True, "expected_reason": "PASS"},
        {"name": "reference_receipt_bundle_binding", "operation": "VERIFY_BINDING", "receipt": reference_receipt, "bundle": reference_bundle, "expected_ok": True, "expected_reason": "PASS"},
        {"name": "reference_public_summary_verifies", "operation": "VERIFY_PUBLIC_SUMMARY", "summary": reference_summary, "expected_ok": True, "expected_reason": "PASS"},
        {"name": "reference_public_summary_bundle_projection", "operation": "VERIFY_PUBLIC_SUMMARY_BINDING", "summary": reference_summary, "bundle": reference_bundle, "expected_ok": True, "expected_reason": "PASS"},
        {"name": "withheld_public_summary_verifies", "operation": "VERIFY_PUBLIC_SUMMARY", "summary": hidden_authorized_summary, "expected_ok": True, "expected_reason": "PASS"},
        {"name": "withheld_outcome_noninterference", "operation": "WITHHELD_NONINTERFERENCE", "left_summary": hidden_authorized_summary, "right_summary": hidden_not_authorized_summary, "expected_ok": True, "expected_reason": "PASS"},
        {"name": "withheld_public_summary_no_direction", "operation": "WITHHELD_NO_DIRECTION", "summary": hidden_authorized_summary, "expected_ok": True, "expected_reason": "PASS"},
        {"name": "tampered_hidden_outcome_rejected", "operation": "VERIFY_PUBLIC_SUMMARY", "summary": tampered_hidden_outcome, "expected_ok": False, "expected_reason": "PUBLIC_SUMMARY_OUTCOME_NOT_REDACTED"},
        {"name": "tampered_hidden_reason_rejected", "operation": "VERIFY_PUBLIC_SUMMARY", "summary": tampered_hidden_reason, "expected_ok": False, "expected_reason": "PUBLIC_SUMMARY_REASON_CODE_LEAK"},
        {"name": "tampered_hidden_result_id_rejected", "operation": "VERIFY_PUBLIC_SUMMARY", "summary": tampered_hidden_result_id, "expected_ok": False, "expected_reason": "PUBLIC_SUMMARY_RESULT_ID_NOT_REDACTED"},
        {"name": "tampered_hidden_bundle_id_rejected", "operation": "VERIFY_PUBLIC_SUMMARY", "summary": tampered_hidden_bundle_id, "expected_ok": False, "expected_reason": "PUBLIC_SUMMARY_BUNDLE_ID_NOT_REDACTED"},
        {"name": "direct_object_byte_ceiling", "operation": "DIRECT_INPUT_BYTE_LIMIT", "groups": 256, "items": 194, "item_value": "REFERENCE-VALUE-0001", "expected_ok": True, "expected_reason": "PASS"},
        {"name": "tampered_bundle_rejected", "operation": "VERIFY_BUNDLE", "bundle": tampered_bundle, "expected_ok": False, "expected_reason": "BUNDLE_RECONSTRUCTION_MISMATCH"},
        {"name": "tampered_bundle_id_rejected", "operation": "VERIFY_BUNDLE", "bundle": tampered_bundle_id, "expected_ok": False, "expected_reason": "BUNDLE_RECONSTRUCTION_MISMATCH"},
        {"name": "tampered_receipt_rejected", "operation": "VERIFY_RECEIPT", "receipt": tampered_receipt, "expected_ok": False, "expected_reason": "RECEIPT_IDENTITY_MISMATCH"},
        {"name": "reset_authority_receipt_rejected", "operation": "VERIFY_RECEIPT", "receipt": reset_authority_receipt, "expected_ok": False, "expected_reason": "RESET_AUTHORITY_MISMATCH"},
        {"name": "credential_mutation_authority_receipt_rejected", "operation": "VERIFY_RECEIPT", "receipt": mutation_authority_receipt, "expected_ok": False, "expected_reason": "CREDENTIAL_MUTATION_AUTHORITY_MISMATCH"},
        {"name": "unrelated_receipt_binding_rejected", "operation": "VERIFY_BINDING", "receipt": unrelated_receipt, "bundle": reference_bundle, "expected_ok": False, "expected_reason": "RECEIPT_BUNDLE_BINDING_MISMATCH"},
        {"name": "forbidden_value_redaction", "operation": "PRIVACY", "bundle": secret_bundle, "receipt": secret_receipt, "forbidden_marker": "VECTOR-PRIVATE-MARKER", "expected_ok": True, "expected_reason": "PASS"},
        {"name": "allowed_reference_value_preserved", "operation": "REFERENCE_VALUE_PRESERVATION", "bundle": reference_value_bundle, "receipt": reference_value_receipt, "reference_marker": "HUNTER2", "expected_ok": True, "expected_reason": "PASS"},
        {"name": "unsupported_field_value_preserved_in_bundle", "operation": "UNSUPPORTED_VALUE_PRESERVATION", "bundle": unsupported_value_bundle, "receipt": unsupported_value_receipt, "reference_marker": "VECTOR-UNSUPPORTED-PRIVATE-MARKER", "expected_ok": True, "expected_reason": "PASS"},
    ]


def serialization_record(se, name: str, value: Any) -> Dict[str, Any]:
    data = se.json_file_bytes(value)
    return {
        "name": name,
        "value": value,
        "expected_byte_length": len(data),
        "expected_sha256": hashlib.sha256(data).hexdigest(),
    }


def build_document(se) -> Dict[str, Any]:
    reference_input = se.build_reference_input()
    reference_bundle = se.build_bundle(reference_input)
    reference_receipt = se.make_receipt(reference_bundle)
    reference_summary = se.public_summary(reference_bundle)
    document: Dict[str, Any] = {
        "schema": VECTOR_SCHEMA,
        "version": se.VERSION,
        "core_version": se.CORE_VERSION,
        "profile_id": se.PROFILE_ID,
        "ruleset_id": se.RULESET_ID,
        "canonicalization_id": se.CANONICALIZATION_ID,
        "identity_domain_id": se.identity_domain_id(),
        "public_summary_schema": se.PUBLIC_SUMMARY_SCHEMA,
        "semantic_vectors": build_semantic_vectors(se),
        "presentation_vectors": build_presentation_vectors(se),
        "parser_vectors": build_parser_vectors(se),
        "artifact_vectors": build_artifact_vectors(se),
        "serialization_vectors": [
            serialization_record(se, "reference_bundle_bytes", reference_bundle),
            serialization_record(se, "reference_receipt_bytes", reference_receipt),
            serialization_record(se, "reference_public_summary_bytes", reference_summary),
        ],
        "relations": build_relations(se),
        "reference_evidence": {
            "example_input": reference_input,
            "bundle": reference_bundle,
            "receipt": reference_receipt,
        },
    }
    document["vector_set_id"] = se.identity(VECTOR_SET_ID_PREFIX, document)
    return document


def verify_header(se, document: Dict[str, Any]) -> List[str]:
    clean = dict(document)
    clean.pop("__source_bytes_canonical__", None)
    failures: List[str] = []
    expected = {
        "schema": VECTOR_SCHEMA,
        "version": se.VERSION,
        "core_version": se.CORE_VERSION,
        "profile_id": se.PROFILE_ID,
        "ruleset_id": se.RULESET_ID,
        "canonicalization_id": se.CANONICALIZATION_ID,
        "identity_domain_id": se.identity_domain_id(),
        "public_summary_schema": se.PUBLIC_SUMMARY_SCHEMA,
    }
    for key, value in expected.items():
        if clean.get(key) != value:
            failures.append("header " + key)
    vector_set_id = clean.get("vector_set_id")
    material = dict(clean)
    material.pop("vector_set_id", None)
    if vector_set_id != se.identity(VECTOR_SET_ID_PREFIX, material):
        failures.append("vector_set_id")
    return failures


def verify_document(se, document: Dict[str, Any]) -> Tuple[Dict[str, Tuple[int, int]], List[str]]:
    source_bytes_canonical = document.get("__source_bytes_canonical__") is True
    clean = dict(document)
    clean.pop("__source_bytes_canonical__", None)
    failures = verify_header(se, clean)
    report: Dict[str, Tuple[int, int]] = {}

    semantic_pass = 0
    semantic_vectors = clean.get("semantic_vectors", [])
    if not isinstance(semantic_vectors, list):
        failures.append("semantic_vectors type")
        semantic_vectors = []
    for vector in semantic_vectors:
        name = vector.get("name", "unnamed") if isinstance(vector, dict) else "unnamed"
        if not isinstance(vector, dict):
            failures.append("semantic vector type")
            continue
        actual = se.resolve_reset_password(vector.get("input"))
        if se.canonical_json(actual) == se.canonical_json(vector.get("expected")):
            semantic_pass += 1
        else:
            failures.append("semantic vector " + name)
    report["semantic vectors"] = (semantic_pass, len(semantic_vectors))

    presentation_pass = 0
    presentation_vectors = clean.get("presentation_vectors", [])
    if not isinstance(presentation_vectors, list):
        failures.append("presentation_vectors type")
        presentation_vectors = []
    for vector in presentation_vectors:
        name = vector.get("name", "unnamed") if isinstance(vector, dict) else "unnamed"
        if not isinstance(vector, dict):
            failures.append("presentation vector type")
            continue
        actual = se.public_summary(se.build_bundle(vector.get("input")))
        if se.canonical_json(actual) == se.canonical_json(vector.get("expected")):
            presentation_pass += 1
        else:
            failures.append("presentation vector " + name)
    report["presentation vectors"] = (presentation_pass, len(presentation_vectors))

    parser_pass = 0
    parser_vectors = clean.get("parser_vectors", [])
    if not isinstance(parser_vectors, list):
        failures.append("parser_vectors type")
        parser_vectors = []
    for vector in parser_vectors:
        name = vector.get("name", "unnamed") if isinstance(vector, dict) else "unnamed"
        try:
            raw_json = materialize_parser_text(se, vector)
            se.loads_strict(raw_json)
            actual = "ACCEPT"
        except (TypeError, ValueError, se.DuplicateKeyError, se.PortableJSONError):
            actual = "REJECT"
        if actual == vector.get("expected"):
            parser_pass += 1
        else:
            failures.append("parser vector " + name)
    report["parser vectors"] = (parser_pass, len(parser_vectors))

    artifact_pass = 0
    artifact_vectors = clean.get("artifact_vectors", [])
    if not isinstance(artifact_vectors, list):
        failures.append("artifact_vectors type")
        artifact_vectors = []
    for vector in artifact_vectors:
        name = vector.get("name", "unnamed") if isinstance(vector, dict) else "unnamed"
        if not isinstance(vector, dict):
            failures.append("artifact vector type")
            continue
        operation = vector.get("operation")
        if operation == "VERIFY_BUNDLE":
            actual_ok, actual_reason = se.verify_bundle(vector.get("bundle"))
        elif operation == "VERIFY_RECEIPT":
            actual_ok, actual_reason = se.verify_receipt(vector.get("receipt"))
        elif operation == "VERIFY_BINDING":
            actual_ok, actual_reason = se.verify_receipt_against_bundle(
                vector.get("receipt"), vector.get("bundle")
            )
        elif operation == "VERIFY_PUBLIC_SUMMARY":
            actual_ok, actual_reason = se.verify_public_summary(vector.get("summary"))
        elif operation == "VERIFY_PUBLIC_SUMMARY_BINDING":
            actual_ok, actual_reason = se.verify_public_summary_against_bundle(
                vector.get("summary"), vector.get("bundle")
            )
        elif operation == "WITHHELD_NONINTERFERENCE":
            left = vector.get("left_summary")
            right = vector.get("right_summary")
            actual_ok = se.canonical_json(left) == se.canonical_json(right)
            actual_reason = "PASS" if actual_ok else "WITHHELD_NONINTERFERENCE_FAILURE"
        elif operation == "WITHHELD_NO_DIRECTION":
            summary = vector.get("summary")
            serialized = se.canonical_json(summary)
            forbidden_tokens = (
                se.OUTCOME_RESET_AUTHORIZED,
                se.OUTCOME_RESET_NOT_AUTHORIZED,
                se.RESULT_ID_PREFIX,
                se.BUNDLE_ID_PREFIX,
            )
            actual_ok = (
                isinstance(summary, dict)
                and summary.get("authorization_outcome") is None
                and summary.get("admission_state") is None
                and summary.get("result_id") is None
                and summary.get("bundle_id") is None
                and summary.get("reason_codes") == [se.REASON_CODE_OUTCOME_WITHHELD]
                and all(token not in serialized for token in forbidden_tokens)
            )
            actual_reason = "PASS" if actual_ok else "WITHHELD_DIRECTION_LEAK"
        elif operation == "DIRECT_INPUT_BYTE_LIMIT":
            groups = int(vector.get("groups", 0))
            items = int(vector.get("items", 0))
            item_value = vector.get("item_value", "REFERENCE-VALUE-0001")
            value = [[item_value for _ in range(items)] for _ in range(groups)]
            resolver_rejected = False
            bundle_rejected = False
            try:
                se.resolve_reset_password(value)
            except se.PortableJSONError:
                resolver_rejected = True
            try:
                se.build_bundle(value)
            except se.PortableJSONError:
                bundle_rejected = True
            actual_ok = resolver_rejected and bundle_rejected
            actual_reason = "PASS" if actual_ok else "DIRECT_INPUT_BYTE_LIMIT_FAILURE"
        elif operation == "PRIVACY":
            marker = vector.get("forbidden_marker", "")
            serialized = se.canonical_json(
                {"bundle": vector.get("bundle"), "receipt": vector.get("receipt")}
            )
            actual_ok = marker not in serialized and "<FORBIDDEN_VALUE_REDACTED>" in serialized
            actual_reason = "PASS" if actual_ok else "PRIVACY_FAILURE"
        elif operation == "REFERENCE_VALUE_PRESERVATION":
            marker = vector.get("reference_marker", "")
            bundle = vector.get("bundle")
            receipt = vector.get("receipt")
            serialized = se.canonical_json({"bundle": bundle, "receipt": receipt})
            actual_ok = (
                isinstance(bundle, dict)
                and isinstance(receipt, dict)
                and marker in serialized
                and "<FORBIDDEN_VALUE_REDACTED>" not in serialized
                and bundle.get("result", {}).get("state") == se.STATE_RESOLVED
                and bundle.get("result", {}).get("subject_ref") == marker
            )
            actual_reason = "PASS" if actual_ok else "REFERENCE_VALUE_PRESERVATION_FAILURE"
        elif operation == "UNSUPPORTED_VALUE_PRESERVATION":
            marker = vector.get("reference_marker", "")
            bundle = vector.get("bundle")
            receipt = vector.get("receipt")
            bundle_serialized = se.canonical_json(bundle)
            receipt_serialized = se.canonical_json(receipt)
            actual_ok = (
                isinstance(bundle, dict)
                and isinstance(receipt, dict)
                and marker in bundle_serialized
                and marker not in receipt_serialized
                and bundle.get("result", {}).get("state") == se.STATE_UNSUPPORTED
                and bundle.get("submitted_input", {}).get("api_key") == marker
                and "api_key" not in bundle.get("normalized_projection", {})
            )
            actual_reason = "PASS" if actual_ok else "UNSUPPORTED_VALUE_PRESERVATION_FAILURE"
        else:
            actual_ok, actual_reason = False, "UNKNOWN_OPERATION"
        if actual_ok == vector.get("expected_ok") and actual_reason == vector.get("expected_reason"):
            artifact_pass += 1
        else:
            failures.append("artifact vector " + name)
    report["artifact vectors"] = (artifact_pass, len(artifact_vectors))

    evidence_pass = 0
    evidence_total = 3
    evidence = clean.get("reference_evidence", {})
    if isinstance(evidence, dict):
        expected_bundle = se.build_bundle(evidence.get("example_input"))
        expected_receipt = se.make_receipt(expected_bundle)
        if se.canonical_json(expected_bundle) == se.canonical_json(evidence.get("bundle")):
            evidence_pass += 1
        else:
            failures.append("reference bundle reproduction")
        if se.canonical_json(expected_receipt) == se.canonical_json(evidence.get("receipt")):
            evidence_pass += 1
        else:
            failures.append("reference receipt reproduction")
        ok, _ = se.verify_receipt_against_bundle(evidence.get("receipt"), evidence.get("bundle"))
        if ok:
            evidence_pass += 1
        else:
            failures.append("reference receipt binding")
    else:
        failures.append("reference evidence type")
    report["reference evidence"] = (evidence_pass, evidence_total)

    serialization_pass = 1 if source_bytes_canonical else 0
    serialization_total = 1
    if not source_bytes_canonical:
        failures.append("vector source bytes")
    serialization_vectors = clean.get("serialization_vectors", [])
    if not isinstance(serialization_vectors, list):
        failures.append("serialization_vectors type")
        serialization_vectors = []
    for vector in serialization_vectors:
        serialization_total += 1
        name = vector.get("name", "unnamed") if isinstance(vector, dict) else "unnamed"
        if not isinstance(vector, dict):
            failures.append("serialization vector type")
            continue
        data = se.json_file_bytes(vector.get("value"))
        actual_hash = hashlib.sha256(data).hexdigest()
        valid = (
            len(data) == vector.get("expected_byte_length")
            and actual_hash == vector.get("expected_sha256")
            and data.endswith(b"\n")
            and not data.endswith(b"\n\n")
            and b"\r" not in data
        )
        if valid:
            serialization_pass += 1
        else:
            failures.append("serialization vector " + name)
    report["serialization bytes"] = (serialization_pass, serialization_total)

    relation_pass = 0
    relations = clean.get("relations", [])
    if not isinstance(relations, list):
        failures.append("relations type")
        relations = []
    for relation in relations:
        name = relation.get("name", "unnamed") if isinstance(relation, dict) else "unnamed"
        if not isinstance(relation, dict):
            failures.append("relation type")
            continue
        left = se.resolve_reset_password(relation.get("left_input"))
        right = se.resolve_reset_password(relation.get("right_input"))
        equal_ok = all(
            se.canonical_json(left.get(field)) == se.canonical_json(right.get(field))
            for field in relation.get("equal_fields", [])
        )
        different_ok = all(
            se.canonical_json(left.get(field)) != se.canonical_json(right.get(field))
            for field in relation.get("different_fields", [])
        )
        if equal_ok and different_ok:
            relation_pass += 1
        else:
            failures.append("relation " + name)
    report["relations"] = (relation_pass, len(relations))

    return report, failures


def print_report(report: Dict[str, Tuple[int, int]], failures: List[str]) -> int:
    for label in (
        "semantic vectors",
        "presentation vectors",
        "parser vectors",
        "artifact vectors",
        "reference evidence",
        "serialization bytes",
        "relations",
    ):
        passed, total = report.get(label, (0, 0))
        print(f"{label}: {passed}/{total} reproduced")
    if failures:
        print("VERIFY: FAIL")
        for failure in failures:
            print("FAIL: " + failure)
        return 1
    print("VERIFY: PASS")
    return 0


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SLANG-ResetPassword frozen conformance vectors")
    parser.add_argument("--core", type=Path, default=Path(__file__).with_name(EXPECTED_CORE_FILENAME))
    parser.add_argument("--write", type=Path, help="write a frozen vector document")
    parser.add_argument("--verify", type=Path, help="verify a frozen vector document")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    if sys.version_info < (3, 9):
        print("ERROR: SLANG-ResetPassword v0.1.0 requires Python 3.9 or later", file=sys.stderr)
        return 2
    args = parse_args(argv)
    try:
        se = load_reference(args.core)
        if args.write:
            document = build_document(se)
            se.write_json(args.write, document)
            print("WROTE: " + str(args.write))
            print("vector_set_id: " + document["vector_set_id"])
            return 0
        verify_path = args.verify or Path(__file__).with_name(EXPECTED_VECTOR_FILENAME)
        document = se.load_json(verify_path)
        document["__source_bytes_canonical__"] = (
            verify_path.read_bytes()
            == se.json_file_bytes(
                {
                    key: value
                    for key, value in document.items()
                    if key != "__source_bytes_canonical__"
                }
            )
        )
        report, failures = verify_document(se, document)
        return print_report(report, failures)
    except (OSError, TypeError, ValueError, RuntimeError, MemoryError, RecursionError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
