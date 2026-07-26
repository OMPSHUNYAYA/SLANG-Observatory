#!/usr/bin/env python3
"""
SLANG-Exam Frozen Conformance Vectors
Semantic parity and reference-evidence verification for the bounded resolver.

Python 3.9+
Standard library only
"""

import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple


VECTORS_SCHEMA = "SLANG-EXAM-VECTORS-4"
VECTORS_VERSION = "0.7.2"

SEMANTIC_FIELDS = (
    "state",
    "assembly_state",
    "release_state",
    "paper_visible",
    "reason_codes",
    "selected_question_ids",
    "selection_mode",
    "selection_posture",
    "selection_context_id",
    "selection_event_id",
    "party_count",
    "commitment_manifest_id",
    "reveal_manifest_id",
    "participant_set_id",
    "commitment_aggregate_id",
    "selector_transcript_id",
    "applied_authority_requirements",
    "non_applicable_authority_fields",
    "authority_admitted",
    "identity_domain_id",
    "canonical_input_id",
    "bank_id",
    "blueprint_id",
    "paper_id",
    "evaluation_manifest_id",
    "result_id",
)

REFERENCE_FIELDS = (
    "multiplicity_state",
    "submission_id",
    "normalized_projection_id",
    "search_evidence_id",
    "search_evidence",
    "bundle_id",
    "receipt_id",
)


def load_reference(path: Path):
    if not path.exists():
        raise SystemExit("reference module not found: " + str(path))
    spec = importlib.util.spec_from_file_location("slang_exam_reference", str(path))
    if spec is None or spec.loader is None:
        raise SystemExit("could not load reference module: " + str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def mutate(source: Callable[[], Dict[str, Any]], fn: Callable[[Dict[str, Any]], None]) -> Dict[str, Any]:
    data = source()
    fn(data)
    return data


def build_unique_reference(se) -> Dict[str, Any]:
    source = se.build_reference_input()
    resolved = se.resolve_exam(source)
    selected = resolved["result"].get("selected_questions") or []
    selected_ids = {item["question_id"] for item in selected}
    for item in source["question_bank"]:
        item["approved"] = item["question_id"] in selected_ids
    return source


def build_near_duplicate_categories(se) -> Dict[str, Any]:
    source = se.build_reference_input()
    patterns = [
        ("ALGEBRA", "MEDIUM", "MCQ"),
        ("ALGEBRA", "MEDIUM", "SHORT"),
        ("GEOMETRY", "EASY", "MCQ"),
        ("REASONING", "HARD", "LONG"),
        ("APPLICATION", "MEDIUM", "SHORT"),
    ]
    for index in range(20):
        topic, difficulty, question_type = patterns[index % len(patterns)]
        question_id = "QN{:02d}".format(index)
        source["question_bank"].append(
            se.question(
                question_id,
                topic,
                difficulty,
                2,
                question_type,
                "GN{}".format(index % 5),
            )
        )
    return source


def build_vectors(se) -> List[Tuple[str, Any]]:
    reference = se.build_reference_input
    vectors: List[Tuple[str, Any]] = []

    vectors.append(("resolved_canonical_rank", reference()))
    vectors.append(("resolved_canonical_unique", build_unique_reference(se)))

    def variant_b(data: Dict[str, Any]) -> None:
        data["selector"]["variant_id"] = "VARIANT-B"

    vectors.append(("resolved_canonical_rank_variant_b", mutate(reference, variant_b)))

    reordered = reference()
    reordered["question_bank"] = list(reversed(reordered["question_bank"]))
    reordered["blueprint"]["topic_counts"] = dict(
        reversed(list(reordered["blueprint"]["topic_counts"].items()))
    )
    reordered["blueprint"]["difficulty_counts"] = dict(
        reversed(list(reordered["blueprint"]["difficulty_counts"].items()))
    )
    vectors.append(("resolved_canonical_rank_reordered", reordered))

    common_center_ignored = reference()
    common_center_ignored["context"]["center_authorized"] = False
    vectors.append(("resolved_common_center_flag_not_applicable", common_center_ignored))

    common_candidate_ignored = reference()
    common_candidate_ignored["context"]["candidate_valid"] = False
    vectors.append(("resolved_common_candidate_flag_not_applicable", common_candidate_ignored))

    center = reference()
    center["context"]["audience_scope"] = "CENTER"
    center["context"]["audience_id"] = "CENTER-001"
    vectors.append(("resolved_center_authorized", center))

    candidate = reference()
    candidate["context"]["audience_scope"] = "CANDIDATE"
    candidate["context"]["audience_id"] = "CANDIDATE-001"
    vectors.append(("resolved_candidate_authorized", candidate))

    vectors.append(("resolved_commit_reveal_rank", se.build_commit_reveal_input()))
    vectors.append(("resolved_mpcr_three_party", se.build_mpcr_input()))

    mpcr_reordered = se.build_mpcr_input()
    mpcr_reordered["selector"]["commitment_manifest"]["parties"].reverse()
    mpcr_reordered["selector"]["reveal_manifest"]["reveals"] = [
        mpcr_reordered["selector"]["reveal_manifest"]["reveals"][1],
        mpcr_reordered["selector"]["reveal_manifest"]["reveals"][2],
        mpcr_reordered["selector"]["reveal_manifest"]["reveals"][0],
    ]
    vectors.append(("resolved_mpcr_party_order_permutation", mpcr_reordered))

    mpcr_uppercase = se.build_mpcr_input()
    for party in mpcr_uppercase["selector"]["commitment_manifest"]["parties"]:
        party["commitment"] = party["commitment"].upper()
    for reveal in mpcr_uppercase["selector"]["reveal_manifest"]["reveals"]:
        reveal["salt"] = reveal["salt"].upper()
    vectors.append(("resolved_mpcr_uppercase_hex", mpcr_uppercase))

    assembly_denied = reference()
    assembly_denied["context"]["assembly_authorized"] = False
    vectors.append(("forbidden_assembly_not_authorized", assembly_denied))

    center_denied = copy.deepcopy(center)
    center_denied["context"]["center_authorized"] = False
    vectors.append(("forbidden_center_not_authorized", center_denied))

    candidate_center_denied = copy.deepcopy(candidate)
    candidate_center_denied["context"]["center_authorized"] = False
    vectors.append(("forbidden_candidate_center_not_authorized", candidate_center_denied))

    candidate_invalid = copy.deepcopy(candidate)
    candidate_invalid["context"]["candidate_valid"] = False
    vectors.append(("forbidden_candidate_invalid", candidate_invalid))

    release_withheld = reference()
    release_withheld["context"]["release_authorized"] = False
    vectors.append(("forbidden_release_withheld", release_withheld))

    window_closed = reference()
    window_closed["context"]["exam_window_open"] = False
    vectors.append(("forbidden_exam_window_closed", window_closed))

    mpcr_withheld = se.build_mpcr_input()
    mpcr_withheld["context"]["release_authorized"] = False
    vectors.append(("forbidden_mpcr_release_withheld", mpcr_withheld))

    inject_state = reference()
    inject_state["state"] = "RESOLVED"
    vectors.append(("forbidden_derived_field_injection", inject_state))

    missing_selector = reference()
    del missing_selector["selector"]
    vectors.append(("incomplete_missing_selector", missing_selector))

    insufficient_topic = reference()
    for item in insufficient_topic["question_bank"]:
        if item["topic"] == "GEOMETRY":
            item["approved"] = False
    vectors.append(("incomplete_topic_capacity", insufficient_topic))

    cross_constraint = reference()
    cross_constraint["blueprint"]["max_per_exposure_group"] = 2
    for item in cross_constraint["question_bank"]:
        item["exposure_group"] = "ONE-GROUP"
    vectors.append(("incomplete_cross_constraint_unsatisfiable", cross_constraint))

    mpcr_missing = se.build_mpcr_input()
    mpcr_missing["selector"]["reveal_manifest"]["reveals"].pop()
    vectors.append(("incomplete_mpcr_missing_reveal", mpcr_missing))

    mpcr_few = se.build_mpcr_input()
    mpcr_few["selector"]["commitment_manifest"]["parties"] = mpcr_few["selector"]["commitment_manifest"]["parties"][:1]
    mpcr_few["selector"]["reveal_manifest"]["reveals"] = mpcr_few["selector"]["reveal_manifest"]["reveals"][:1]
    vectors.append(("incomplete_mpcr_insufficient_parties", mpcr_few))

    declared_bank_mismatch = reference()
    declared_bank_mismatch["declared_bank_id"] = "slang_exam_bank_sha256:" + "0" * 64
    vectors.append(("conflict_declared_bank_id", declared_bank_mismatch))

    count_total_mismatch = reference()
    count_total_mismatch["blueprint"]["difficulty_counts"] = {"EASY": 1, "MEDIUM": 1, "HARD": 1}
    vectors.append(("conflict_blueprint_count_total", count_total_mismatch))

    bad_common_id = reference()
    bad_common_id["context"]["audience_id"] = "CENTER-001"
    vectors.append(("conflict_common_audience_id_scope", bad_common_id))

    bad_center_id = reference()
    bad_center_id["context"]["audience_scope"] = "CENTER"
    bad_center_id["context"]["audience_id"] = "ALL"
    vectors.append(("conflict_center_audience_id_scope", bad_center_id))

    single_mismatch = se.build_commit_reveal_input()
    single_mismatch["selector"]["selection_salt"] = hashlib.sha256(b"MISMATCH").hexdigest()
    vectors.append(("conflict_single_party_commitment_mismatch", single_mismatch))

    single_transplant = se.build_commit_reveal_input()
    single_transplant["context"]["audience_scope"] = "CENTER"
    single_transplant["context"]["audience_id"] = "CENTER-002"
    vectors.append(("conflict_single_party_context_transplant", single_transplant))

    mpcr_mismatch = se.build_mpcr_input()
    mpcr_mismatch["selector"]["reveal_manifest"]["reveals"][0]["salt"] = hashlib.sha256(b"MISMATCH").hexdigest()
    vectors.append(("conflict_mpcr_commitment_mismatch", mpcr_mismatch))

    mpcr_duplicate = se.build_mpcr_input()
    mpcr_duplicate["selector"]["commitment_manifest"]["parties"].append(
        copy.deepcopy(mpcr_duplicate["selector"]["commitment_manifest"]["parties"][0])
    )
    vectors.append(("conflict_mpcr_duplicate_party", mpcr_duplicate))

    mpcr_unknown = se.build_mpcr_input()
    mpcr_unknown["selector"]["reveal_manifest"]["reveals"].append(
        {"party_id": "UNKNOWN", "salt": hashlib.sha256(b"UNKNOWN").hexdigest()}
    )
    vectors.append(("conflict_mpcr_undeclared_reveal", mpcr_unknown))

    mpcr_declared_id = se.build_mpcr_input()
    mpcr_declared_id["selector"]["declared_commitment_manifest_id"] = (
        "slang_exam_mpcr_commitments_sha256:" + "0" * 64
    )
    vectors.append(("conflict_mpcr_declared_manifest_id", mpcr_declared_id))

    mpcr_audience_transplant = se.build_mpcr_input()
    mpcr_audience_transplant["context"]["audience_scope"] = "CENTER"
    mpcr_audience_transplant["context"]["audience_id"] = "CENTER-003"
    vectors.append(("conflict_mpcr_audience_context_transplant", mpcr_audience_transplant))

    mpcr_bank_transplant = se.build_mpcr_input()
    mpcr_bank_transplant["question_bank"][0]["content_commitment"] = se.commitment("Q101-CONTENT-ALTERNATE")
    vectors.append(("conflict_mpcr_bank_context_transplant", mpcr_bank_transplant))

    mpcr_blueprint_transplant = se.build_mpcr_input()
    mpcr_blueprint_transplant["blueprint"]["max_per_exposure_group"] = 3
    vectors.append(("conflict_mpcr_blueprint_context_transplant", mpcr_blueprint_transplant))

    mpcr_roster_transplant = se.build_mpcr_input()
    extra_salt = hashlib.sha256(b"PARTY-D-SALT").hexdigest()
    mpcr_roster_transplant["selector"]["commitment_manifest"]["parties"].append(
        {"party_id": "PARTY-D", "commitment": "0" * 64}
    )
    mpcr_roster_transplant["selector"]["reveal_manifest"]["reveals"].append(
        {"party_id": "PARTY-D", "salt": extra_salt}
    )
    extra_commitment = se.make_mpcr_party_commitment(mpcr_roster_transplant, "PARTY-D", extra_salt)
    mpcr_roster_transplant["selector"]["commitment_manifest"]["parties"][-1]["commitment"] = extra_commitment
    vectors.append(("conflict_mpcr_roster_context_transplant", mpcr_roster_transplant))

    bad_schema = reference()
    bad_schema["schema"] = "SLANG-EXAM-INPUT-99"
    vectors.append(("unsupported_schema", bad_schema))

    unknown_top = reference()
    unknown_top["surprise"] = "value"
    vectors.append(("unsupported_unknown_top_level_field", unknown_top))
    vectors.append(("unsupported_non_object_input", "not-an-object"))

    canonical_mpcr_field = reference()
    canonical_mpcr_field["selector"]["selection_event_id"] = "NOT-ALLOWED"
    vectors.append(("unsupported_mpcr_field_under_canonical", canonical_mpcr_field))

    mpcr_single_field = se.build_mpcr_input()
    mpcr_single_field["selector"]["selection_salt"] = "0" * 64
    vectors.append(("unsupported_single_field_under_mpcr", mpcr_single_field))

    mpcr_too_many = se.build_mpcr_input()
    for index in range(6):
        party_id = "EXTRA-" + str(index)
        salt = hashlib.sha256(party_id.encode("ascii")).hexdigest()
        mpcr_too_many["selector"]["commitment_manifest"]["parties"].append(
            {"party_id": party_id, "commitment": "0" * 64}
        )
        mpcr_too_many["selector"]["reveal_manifest"]["reveals"].append(
            {"party_id": party_id, "salt": salt}
        )
    vectors.append(("unsupported_mpcr_party_limit", mpcr_too_many))

    marks_upper_bound = reference()
    for item in marks_upper_bound["question_bank"]:
        item["marks"] = se.MAX_QUESTION_MARKS
    marks_upper_bound["blueprint"]["total_marks"] = (
        marks_upper_bound["blueprint"]["total_questions"] * se.MAX_QUESTION_MARKS
    )
    vectors.append(("resolved_marks_upper_bound", marks_upper_bound))

    vectors.append(("unsupported_question_marks_above_limit", se.build_adversarial_marks_input()))

    total_marks_above = reference()
    total_marks_above["blueprint"]["total_marks"] = se.MAX_TOTAL_MARKS + 1
    vectors.append(("unsupported_total_marks_above_limit", total_marks_above))

    sha_leading_plus = reference()
    sha_leading_plus["question_bank"][0]["content_commitment"] = "+" + "a" * 63
    vectors.append(("unsupported_sha256_leading_plus", sha_leading_plus))

    sha_underscore = reference()
    sha_underscore["question_bank"][0]["content_commitment"] = "a" * 31 + "_" + "a" * 32
    vectors.append(("unsupported_sha256_embedded_underscore", sha_underscore))

    sha_space = reference()
    sha_space["question_bank"][0]["content_commitment"] = " " + "a" * 63
    vectors.append(("unsupported_sha256_leading_space", sha_space))

    sha_prefix = reference()
    sha_prefix["question_bank"][0]["content_commitment"] = "0x" + "a" * 62
    vectors.append(("unsupported_sha256_hex_prefix", sha_prefix))

    sha_non_hex = reference()
    sha_non_hex["question_bank"][0]["content_commitment"] = "g" + "a" * 63
    vectors.append(("unsupported_sha256_non_hex", sha_non_hex))

    near_duplicate = build_near_duplicate_categories(se)
    vectors.append(("resolved_near_duplicate_categories", near_duplicate))

    near_duplicate_reordered = copy.deepcopy(near_duplicate)
    near_duplicate_reordered["question_bank"].reverse()
    vectors.append(("resolved_near_duplicate_categories_reordered", near_duplicate_reordered))

    abstain_multiple = reference()
    abstain_multiple["selector"] = {"mode": "ABSTAIN_ON_MULTIPLE", "variant_id": "VARIANT-A"}
    vectors.append(("abstain_multiple_admissible", abstain_multiple))

    return vectors


def build_relations() -> List[Dict[str, Any]]:
    return [
        {
            "name": "canonical_order_invariance",
            "left": "resolved_canonical_rank",
            "right": "resolved_canonical_rank_reordered",
            "equal_fields": [
                "canonical_input_id",
                "normalized_projection_id",
                "bank_id",
                "blueprint_id",
                "selection_context_id",
                "selected_question_ids",
                "paper_id",
                "evaluation_manifest_id",
                "result_id",
                "search_evidence_id",
            ],
            "different_fields": ["submission_id", "bundle_id", "receipt_id"],
        },
        {
            "name": "mpcr_party_order_invariance",
            "left": "resolved_mpcr_three_party",
            "right": "resolved_mpcr_party_order_permutation",
            "equal_fields": [
                "canonical_input_id",
                "normalized_projection_id",
                "selection_context_id",
                "selected_question_ids",
                "paper_id",
                "result_id",
                "search_evidence_id",
                "commitment_manifest_id",
                "reveal_manifest_id",
                "participant_set_id",
                "commitment_aggregate_id",
                "selector_transcript_id",
            ],
            "different_fields": ["submission_id", "bundle_id", "receipt_id"],
        },
        {
            "name": "mpcr_hex_case_normalization",
            "left": "resolved_mpcr_three_party",
            "right": "resolved_mpcr_uppercase_hex",
            "equal_fields": [
                "canonical_input_id",
                "normalized_projection_id",
                "selection_context_id",
                "selected_question_ids",
                "paper_id",
                "result_id",
                "search_evidence_id",
                "commitment_manifest_id",
                "reveal_manifest_id",
                "participant_set_id",
                "commitment_aggregate_id",
                "selector_transcript_id",
            ],
            "different_fields": ["submission_id", "bundle_id", "receipt_id"],
        },
        {
            "name": "canonical_release_withholding_preserves_paper",
            "left": "resolved_canonical_rank",
            "right": "forbidden_release_withheld",
            "equal_fields": [
                "bank_id",
                "blueprint_id",
                "selection_context_id",
                "paper_id",
                "evaluation_manifest_id",
                "search_evidence_id",
            ],
            "different_fields": [
                "submission_id",
                "canonical_input_id",
                "result_id",
                "bundle_id",
                "receipt_id",
            ],
        },
        {
            "name": "canonical_window_withholding_preserves_paper",
            "left": "resolved_canonical_rank",
            "right": "forbidden_exam_window_closed",
            "equal_fields": [
                "bank_id",
                "blueprint_id",
                "selection_context_id",
                "paper_id",
                "evaluation_manifest_id",
                "search_evidence_id",
            ],
            "different_fields": [
                "submission_id",
                "canonical_input_id",
                "result_id",
                "bundle_id",
                "receipt_id",
            ],
        },
        {
            "name": "mpcr_release_withholding_preserves_paper",
            "left": "resolved_mpcr_three_party",
            "right": "forbidden_mpcr_release_withheld",
            "equal_fields": [
                "bank_id",
                "blueprint_id",
                "selection_context_id",
                "paper_id",
                "evaluation_manifest_id",
                "search_evidence_id",
                "commitment_manifest_id",
                "reveal_manifest_id",
                "participant_set_id",
                "commitment_aggregate_id",
                "selector_transcript_id",
            ],
            "different_fields": [
                "submission_id",
                "canonical_input_id",
                "result_id",
                "bundle_id",
                "receipt_id",
            ],
        },
        {
            "name": "common_center_flag_non_applicability",
            "left": "resolved_canonical_rank",
            "right": "resolved_common_center_flag_not_applicable",
            "equal_fields": [
                "selection_context_id",
                "selected_question_ids",
                "paper_id",
                "evaluation_manifest_id",
                "search_evidence_id",
            ],
            "different_fields": [
                "submission_id",
                "canonical_input_id",
                "result_id",
                "bundle_id",
                "receipt_id",
            ],
        },
        {
            "name": "common_candidate_flag_non_applicability",
            "left": "resolved_canonical_rank",
            "right": "resolved_common_candidate_flag_not_applicable",
            "equal_fields": [
                "selection_context_id",
                "selected_question_ids",
                "paper_id",
                "evaluation_manifest_id",
                "search_evidence_id",
            ],
            "different_fields": [
                "submission_id",
                "canonical_input_id",
                "result_id",
                "bundle_id",
                "receipt_id",
            ],
        },
        {
            "name": "variant_changes_selection_context",
            "left": "resolved_canonical_rank",
            "right": "resolved_canonical_rank_variant_b",
            "equal_fields": ["bank_id", "blueprint_id"],
            "different_fields": [
                "submission_id",
                "canonical_input_id",
                "selection_context_id",
                "paper_id",
                "result_id",
                "search_evidence_id",
                "bundle_id",
                "receipt_id",
            ],
        },
        {
            "name": "near_duplicate_category_order_invariance",
            "left": "resolved_near_duplicate_categories",
            "right": "resolved_near_duplicate_categories_reordered",
            "equal_fields": [
                "canonical_input_id",
                "normalized_projection_id",
                "bank_id",
                "blueprint_id",
                "selection_context_id",
                "selected_question_ids",
                "paper_id",
                "evaluation_manifest_id",
                "result_id",
                "search_evidence_id",
            ],
            "different_fields": ["submission_id", "bundle_id", "receipt_id"],
        },
    ]


def normalized_selector_data(se, raw_input: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    normalized, issues = se.normalize_input(raw_input)
    if normalized is None or issues:
        raise ValueError("search probe input did not normalize")
    bank_id = se.identity("slang_exam_bank_sha256:", normalized["question_bank"])
    blueprint_id = se.identity("slang_exam_blueprint_sha256:", normalized["blueprint"])
    participant_id = se.participant_set_id(normalized)
    context_id = se.selection_context_id(normalized, bank_id, blueprint_id, participant_id)
    return normalized, se.selector_material(normalized, context_id, participant_id)


def search_probe_actual(
    se,
    raw_input: Dict[str, Any],
    solution_limit: int,
    node_limit: int,
) -> Dict[str, Any]:
    normalized, selector_data = normalized_selector_data(se, raw_input)
    solutions, stats = se.find_solutions(
        normalized,
        selector_data,
        solution_limit,
        node_limit,
    )
    if len(solutions) >= 2:
        multiplicity_state = "MULTIPLE_PROVED"
    elif len(solutions) == 1 and not stats["search_budget_exhausted"]:
        multiplicity_state = "UNIQUE_PROVED"
    else:
        multiplicity_state = "NOT_ESTABLISHED"
    return {
        "solution_limit": solution_limit,
        "node_limit": node_limit,
        "solution_count": len(solutions),
        "search_nodes": stats["search_nodes"],
        "search_budget_exhausted": stats["search_budget_exhausted"],
        "admissible_solution_count_lower_bound": stats[
            "admissible_solution_count_lower_bound"
        ],
        "multiplicity_state": multiplicity_state,
        "marks_dp_memory_bound_bits": stats["marks_dp_memory_bound_bits"],
    }


def build_search_probes(se, raw_by_name: Dict[str, Any]) -> List[Dict[str, Any]]:
    definitions = [
        ("budget_exhaustion_before_selection", "resolved_canonical_rank", 2, 1),
        ("budget_exhaustion_after_first_selection", "resolved_canonical_rank", 2, 75),
        ("multiplicity_proved_with_sufficient_budget", "resolved_canonical_rank", 2, 100),
    ]
    probes: List[Dict[str, Any]] = []
    for name, input_name, solution_limit, node_limit in definitions:
        actual = search_probe_actual(
            se,
            raw_by_name[input_name],
            solution_limit,
            node_limit,
        )
        probes.append(
            {
                "name": name,
                "input_name": input_name,
                "expected_reference": actual,
            }
        )
    return probes


def resolve_actual(se, raw_input: Any) -> Dict[str, Any]:
    bundle = se.resolve_exam(raw_input)
    result = bundle["result"]
    evidence = result.get("evidence", {})
    receipt = se.make_receipt(bundle)
    selected = result.get("selected_questions")
    selected_ids = [item["question_id"] for item in selected] if isinstance(selected, list) else None

    actual: Dict[str, Any] = {
        "state": result.get("state"),
        "assembly_state": result.get("assembly_state"),
        "release_state": result.get("release_state"),
        "paper_visible": result.get("paper_visible"),
        "reason_codes": result.get("reason_codes"),
        "selected_question_ids": selected_ids,
        "selection_mode": evidence.get("selection_mode"),
        "selection_posture": evidence.get("selection_posture"),
        "multiplicity_state": evidence.get("multiplicity_state"),
        "selection_context_id": result.get("selection_context_id"),
        "selection_event_id": evidence.get("selection_event_id"),
        "party_count": evidence.get("party_count"),
        "commitment_manifest_id": evidence.get("commitment_manifest_id"),
        "reveal_manifest_id": evidence.get("reveal_manifest_id"),
        "participant_set_id": evidence.get("participant_set_id"),
        "commitment_aggregate_id": evidence.get("commitment_aggregate_id"),
        "selector_transcript_id": evidence.get("selector_transcript_id"),
        "applied_authority_requirements": evidence.get("applied_authority_requirements"),
        "non_applicable_authority_fields": evidence.get("non_applicable_authority_fields"),
        "authority_admitted": evidence.get("authority_admitted"),
        "identity_domain_id": result.get("identity_domain_id"),
        "canonical_input_id": result.get("canonical_input_id"),
        "bank_id": result.get("bank_id"),
        "blueprint_id": result.get("blueprint_id"),
        "paper_id": result.get("paper_id"),
        "evaluation_manifest_id": result.get("evaluation_manifest_id"),
        "result_id": result.get("result_id"),
        "submission_id": result.get("submission_id"),
        "normalized_projection_id": result.get("normalized_projection_id"),
        "search_evidence_id": result.get("search_evidence_id"),
        "search_evidence": result.get("search_evidence"),
        "bundle_id": bundle.get("bundle_id"),
        "receipt_id": receipt.get("receipt_id"),
    }
    return actual


def expected_part(actual: Dict[str, Any], fields: Tuple[str, ...]) -> Dict[str, Any]:
    return {field: actual.get(field) for field in fields}


def build_document(se) -> Dict[str, Any]:
    entries: List[Dict[str, Any]] = []
    names = set()
    raw_by_name: Dict[str, Any] = {}
    for name, raw_input in build_vectors(se):
        if name in names:
            raise SystemExit("duplicate vector name: " + name)
        names.add(name)
        se.validate_portable_json(raw_input)
        raw_by_name[name] = raw_input
        actual = resolve_actual(se, raw_input)
        entries.append(
            {
                "name": name,
                "input": raw_input,
                "expected_semantic": expected_part(actual, SEMANTIC_FIELDS),
                "expected_reference": expected_part(actual, REFERENCE_FIELDS),
            }
        )
    entries.sort(key=lambda entry: entry["name"])

    relations = build_relations()
    search_probes = build_search_probes(se, raw_by_name)
    document: Dict[str, Any] = {
        "schema": VECTORS_SCHEMA,
        "vectors_version": VECTORS_VERSION,
        "reference_version": se.VERSION,
        "core_version": se.CORE_VERSION,
        "profile_id": se.PROFILE_ID,
        "ruleset_id": se.RULESET_ID,
        "canonicalization_id": se.CANONICALIZATION_ID,
        "identity_domain_id": se.identity_domain_id(),
        "input_schema": se.INPUT_SCHEMA,
        "result_schema": se.RESULT_SCHEMA,
        "bundle_schema": se.BUNDLE_SCHEMA,
        "receipt_schema": se.RECEIPT_SCHEMA,
        "semantic_fields": list(SEMANTIC_FIELDS),
        "reference_fields": list(REFERENCE_FIELDS),
        "vector_count": len(entries),
        "relation_count": len(relations),
        "search_probe_count": len(search_probes),
        "vectors": entries,
        "relations": relations,
        "search_probes": search_probes,
    }
    document["vectors_id"] = se.identity("slang_exam_vectors_sha256:", document)
    return document


def verify_header(se, document: Dict[str, Any]) -> List[str]:
    expected = {
        "schema": VECTORS_SCHEMA,
        "vectors_version": VECTORS_VERSION,
        "reference_version": se.VERSION,
        "core_version": se.CORE_VERSION,
        "profile_id": se.PROFILE_ID,
        "ruleset_id": se.RULESET_ID,
        "canonicalization_id": se.CANONICALIZATION_ID,
        "identity_domain_id": se.identity_domain_id(),
        "input_schema": se.INPUT_SCHEMA,
        "result_schema": se.RESULT_SCHEMA,
        "bundle_schema": se.BUNDLE_SCHEMA,
        "receipt_schema": se.RECEIPT_SCHEMA,
        "semantic_fields": list(SEMANTIC_FIELDS),
        "reference_fields": list(REFERENCE_FIELDS),
    }
    failures: List[str] = []
    for key, value in expected.items():
        if document.get(key) != value:
            failures.append(key.upper() + "_MISMATCH")
    return failures


def verify_document(
    se,
    document: Any,
    semantic_only: bool = False,
) -> Tuple[int, int, int, int, int, int, int, int, List[str]]:
    if not isinstance(document, dict):
        return 0, 0, 0, 0, 0, 0, 0, 0, ["VECTORS_NOT_OBJECT"]

    failures = verify_header(se, document)
    stored_id = document.get("vectors_id")
    material = {key: value for key, value in document.items() if key != "vectors_id"}
    if stored_id != se.identity("slang_exam_vectors_sha256:", material):
        failures.append("VECTORS_ID_MISMATCH")

    entries = document.get("vectors")
    if not isinstance(entries, list):
        return 0, 0, 0, 0, 0, 0, 0, 0, failures + ["VECTORS_LIST_MISSING"]
    if document.get("vector_count") != len(entries):
        failures.append("VECTOR_COUNT_MISMATCH")

    names = [entry.get("name") for entry in entries if isinstance(entry, dict)]
    if len(names) != len(entries) or any(not isinstance(name, str) for name in names):
        failures.append("VECTOR_NAME_INVALID")
    if len(set(names)) != len(names):
        failures.append("VECTOR_NAME_DUPLICATE")
    if names != sorted(names):
        failures.append("VECTOR_ORDER_MISMATCH")

    semantic_passed = 0
    reference_passed = 0
    actual_by_name: Dict[str, Dict[str, Any]] = {}

    for entry in entries:
        if not isinstance(entry, dict):
            failures.append("VECTOR_ENTRY_NOT_OBJECT")
            continue
        name = str(entry.get("name", "<unnamed>"))
        raw_input = entry.get("input")
        stored_semantic = entry.get("expected_semantic")
        stored_reference = entry.get("expected_reference")

        if not isinstance(stored_semantic, dict):
            failures.append(name + ": SEMANTIC_EXPECTED_NOT_OBJECT")
            continue
        if set(stored_semantic) != set(SEMANTIC_FIELDS):
            failures.append(name + ": SEMANTIC_FIELD_SURFACE_MISMATCH")
            continue
        if not isinstance(stored_reference, dict):
            failures.append(name + ": REFERENCE_EXPECTED_NOT_OBJECT")
            continue
        if set(stored_reference) != set(REFERENCE_FIELDS):
            failures.append(name + ": REFERENCE_FIELD_SURFACE_MISMATCH")
            continue

        try:
            se.validate_portable_json(raw_input)
            actual = resolve_actual(se, raw_input)
        except (TypeError, ValueError) as exc:
            failures.append(name + ": INPUT_DOMAIN_FAILURE:" + str(exc))
            continue

        actual_by_name[name] = actual
        semantic_mismatch = [
            field for field in SEMANTIC_FIELDS if stored_semantic.get(field) != actual.get(field)
        ]
        if semantic_mismatch:
            failures.append(name + ": SEMANTIC:" + ",".join(semantic_mismatch))
        else:
            semantic_passed += 1

        if semantic_only:
            reference_passed += 1
        else:
            reference_mismatch = [
                field for field in REFERENCE_FIELDS if stored_reference.get(field) != actual.get(field)
            ]
            if reference_mismatch:
                failures.append(name + ": REFERENCE:" + ",".join(reference_mismatch))
            else:
                reference_passed += 1

    relations = document.get("relations")
    if not isinstance(relations, list):
        return (
            semantic_passed,
            len(entries),
            reference_passed,
            len(entries),
            0,
            0,
            0,
            0,
            failures + ["RELATIONS_LIST_MISSING"],
        )
    if document.get("relation_count") != len(relations):
        failures.append("RELATION_COUNT_MISMATCH")

    relation_passed = 0
    for relation in relations:
        if not isinstance(relation, dict):
            failures.append("RELATION_NOT_OBJECT")
            continue
        name = str(relation.get("name", "<unnamed-relation>"))
        left = actual_by_name.get(relation.get("left"))
        right = actual_by_name.get(relation.get("right"))
        if left is None or right is None:
            failures.append(name + ": RELATION_VECTOR_MISSING")
            continue
        relation_failures: List[str] = []
        for field in relation.get("equal_fields", []):
            if left.get(field) != right.get(field):
                relation_failures.append("expected_equal:" + str(field))
        for field in relation.get("different_fields", []):
            if left.get(field) == right.get(field):
                relation_failures.append("expected_different:" + str(field))
        if relation_failures:
            failures.append(name + ": " + ",".join(relation_failures))
        else:
            relation_passed += 1

    search_probes = document.get("search_probes")
    search_probe_passed = 0
    search_probe_total = 0
    if not isinstance(search_probes, list):
        failures.append("SEARCH_PROBES_LIST_MISSING")
    else:
        search_probe_total = len(search_probes)
        if document.get("search_probe_count") != search_probe_total:
            failures.append("SEARCH_PROBE_COUNT_MISMATCH")
        if semantic_only:
            search_probe_passed = search_probe_total
        else:
            raw_by_name = {
                entry["name"]: entry["input"]
                for entry in entries
                if isinstance(entry, dict)
                and isinstance(entry.get("name"), str)
                and "input" in entry
            }
            probe_names = []
            for probe in search_probes:
                if not isinstance(probe, dict):
                    failures.append("SEARCH_PROBE_NOT_OBJECT")
                    continue
                name = str(probe.get("name", "<unnamed-search-probe>"))
                probe_names.append(name)
                input_name = probe.get("input_name")
                expected = probe.get("expected_reference")
                if input_name not in raw_by_name:
                    failures.append(name + ": SEARCH_PROBE_INPUT_MISSING")
                    continue
                if not isinstance(expected, dict):
                    failures.append(name + ": SEARCH_PROBE_EXPECTED_NOT_OBJECT")
                    continue
                try:
                    actual = search_probe_actual(
                        se,
                        raw_by_name[input_name],
                        int(expected.get("solution_limit")),
                        int(expected.get("node_limit")),
                    )
                except (TypeError, ValueError) as exc:
                    failures.append(name + ": SEARCH_PROBE_FAILURE:" + str(exc))
                    continue
                if actual != expected:
                    differing = sorted(
                        key
                        for key in set(actual) | set(expected)
                        if actual.get(key) != expected.get(key)
                    )
                    failures.append(name + ": SEARCH_PROBE:" + ",".join(differing))
                else:
                    search_probe_passed += 1
            if len(set(probe_names)) != len(probe_names):
                failures.append("SEARCH_PROBE_NAME_DUPLICATE")

    return (
        semantic_passed,
        len(entries),
        reference_passed,
        len(entries),
        relation_passed,
        len(relations),
        search_probe_passed,
        search_probe_total,
        failures,
    )


def print_report(
    semantic_passed: int,
    semantic_total: int,
    reference_passed: int,
    reference_total: int,
    relation_passed: int,
    relation_total: int,
    search_probe_passed: int,
    search_probe_total: int,
    failures: List[str],
    semantic_only: bool,
) -> int:
    print("SLANG-Exam Conformance Vectors Verify")
    print("=" * 72)
    print("semantic vectors: {}/{} reproduced".format(semantic_passed, semantic_total))
    if semantic_only:
        print("reference evidence: not required")
    else:
        print("reference evidence: {}/{} reproduced".format(reference_passed, reference_total))
    print("relations: {}/{} reproduced".format(relation_passed, relation_total))
    if semantic_only:
        print("search probes: not required")
    else:
        print("search probes: {}/{} reproduced".format(search_probe_passed, search_probe_total))
    if failures:
        for failure in failures:
            print("  FAIL " + failure)
        print("VERIFY: FAIL")
        return 1
    print("VERIFY: PASS")
    return 0


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="SLANG-Exam frozen semantic and reference conformance vectors."
    )
    parser.add_argument(
        "--reference",
        default="slang_exam_v0_7_2.py",
        help="path to the reference module",
    )
    parser.add_argument("--verify", metavar="PATH", help="verify a frozen vector file")
    parser.add_argument(
        "--semantic-only",
        action="store_true",
        help="verify semantic parity without requiring reference traversal evidence",
    )
    parser.add_argument("--write-candidate", metavar="PATH", help="write a candidate vector file")
    parser.add_argument(
        "--accept-contract-change",
        action="store_true",
        help="allow replacement of an existing candidate path",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    se = load_reference(Path(args.reference))

    if args.verify:
        try:
            document = se.load_json(Path(args.verify))
        except (OSError, UnicodeError, TypeError, ValueError, json.JSONDecodeError) as exc:
            print("VERIFY: FAIL")
            print("Reason: " + str(exc))
            return 1
        report = verify_document(se, document, semantic_only=args.semantic_only)
        return print_report(*report, semantic_only=args.semantic_only)

    document = build_document(se)
    if args.write_candidate:
        path = Path(args.write_candidate)
        if path.exists() and not args.accept_contract_change:
            print("WRITE: FAIL")
            print("Reason: target exists; use --accept-contract-change to replace it")
            return 1
        path.write_text(
            json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print("WROTE: " + str(path))
        print("vectors: " + str(document["vector_count"]))
        print("relations: " + str(document["relation_count"]))
        print("search probes: " + str(document["search_probe_count"]))
        print("vectors_id: " + document["vectors_id"])
        return 0

    report = verify_document(se, document, semantic_only=args.semantic_only)
    print("SLANG-Exam Conformance Vectors Self-Check")
    print("=" * 72)
    print("semantic vectors: {}/{} reproduced".format(report[0], report[1]))
    if args.semantic_only:
        print("reference evidence: not required")
    else:
        print("reference evidence: {}/{} reproduced".format(report[2], report[3]))
    print("relations: {}/{} reproduced".format(report[4], report[5]))
    if args.semantic_only:
        print("search probes: not required")
    else:
        print("search probes: {}/{} reproduced".format(report[6], report[7]))
    print("vectors_id: " + document["vectors_id"])
    if report[8]:
        for failure in report[8]:
            print("  FAIL " + failure)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
