#!/usr/bin/env python3
"""
SLANG-Voting frozen conformance-vector generator and verifier.

Python 3.9+
Standard library only
"""

import argparse
import copy
import importlib.util
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple


VECTOR_SCHEMA = "SLANG-VOTING-VECTORS-2"
EXPECTED_CORE_FILENAME = "slang_voting_v0_1_2.py"
EXPECTED_VECTOR_FILENAME = "SLANG_Voting_Vectors_v0_1_2.json"
EXPECTED_FIELDS = (
    "state",
    "resolution_state",
    "visibility_state",
    "outcome_visible",
    "selected_candidate_ids",
    "leading_candidate_ids",
    "candidate_record_totals",
    "candidate_resolution_totals",
    "total_non_candidate_records",
    "total_records",
    "reason_codes",
    "missing_dependencies",
    "conflicts",
    "prohibitions",
    "unsupported_features",
    "execution_authority",
    "certification_authority",
    "official_result_authority",
    "evidence",
    "submission_id",
    "canonical_input_id",
    "candidate_set_id",
    "reporting_boundary_id",
    "source_manifest_id",
    "source_agreement_id",
    "report_set_id",
    "rule_profile_id",
    "outcome_id",
    "evaluation_evidence_id",
    "result_id",
)


def load_reference(path: Path):
    spec = importlib.util.spec_from_file_location("slang_voting_reference", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load reference implementation")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def mutate(source: Dict[str, Any], fn: Callable[[Dict[str, Any]], None]) -> Dict[str, Any]:
    value = copy.deepcopy(source)
    fn(value)
    return value


def refresh(se, value: Dict[str, Any]) -> Dict[str, Any]:
    return se.attach_declared_identities(value)


def expected_part(result: Dict[str, Any]) -> Dict[str, Any]:
    return {field: result.get(field) for field in EXPECTED_FIELDS}


def build_tie_input(se) -> Dict[str, Any]:
    value = se.build_single_source_input()
    replacements = [
        ("100", "100", "40"),
        ("90", "90", "20"),
        ("80", "80", "20"),
        ("90", "90", "10"),
    ]
    for report, counts in zip(value["sources"][0]["reports"], replacements):
        report["candidate_counts"] = {
            "CANDIDATE-A": counts[0],
            "CANDIDATE-B": counts[1],
            "CANDIDATE-C": counts[2],
        }
        report["total_records"] = str(sum(int(item) for item in counts) + int(report["non_candidate_count"]))
    return refresh(se, value)


def build_zero_input(se) -> Dict[str, Any]:
    value = se.build_single_source_input()
    for report in value["sources"][0]["reports"]:
        report["candidate_counts"] = {candidate: "0" for candidate in value["contest"]["candidate_ids"]}
        report["total_records"] = report["non_candidate_count"]
    return refresh(se, value)


def build_majority_yes(se) -> Dict[str, Any]:
    value = se.build_absolute_majority_input()
    for report in value["sources"][0]["reports"]:
        report["candidate_counts"]["CANDIDATE-A"] = str(int(report["candidate_counts"]["CANDIDATE-A"]) + 200)
        report["total_records"] = str(
            sum(int(item) for item in report["candidate_counts"].values())
            + int(report["non_candidate_count"])
        )
    return refresh(se, value)


def build_top_k_boundary_tie(se) -> Dict[str, Any]:
    value = se.build_top_k_input()
    for report in value["sources"][0]["reports"]:
        report["candidate_counts"]["CANDIDATE-C"] = report["candidate_counts"]["CANDIDATE-B"]
        report["total_records"] = str(
            sum(int(item) for item in report["candidate_counts"].values())
            + int(report["non_candidate_count"])
        )
    return refresh(se, value)


def build_weight_local_tie(se) -> Dict[str, Any]:
    value = se.build_unit_weight_input()
    report = value["sources"][0]["reports"][0]
    report["candidate_counts"] = {
        "CANDIDATE-A": "100",
        "CANDIDATE-B": "100",
        "CANDIDATE-C": "40",
    }
    report["total_records"] = "245"
    return refresh(se, value)


def build_source_disagreement(se) -> Dict[str, Any]:
    value = se.build_reference_input()
    report = value["sources"][1]["reports"][0]
    report["candidate_counts"]["CANDIDATE-B"] = "91"
    report["total_records"] = "246"
    value["sources"][1]["declared_report_set_id"] = se.make_report_set_id_for_input(
        value,
        value["sources"][1]["reports"],
    )
    return value


def build_vectors(se) -> List[Tuple[str, Any]]:
    base = se.build_reference_input()
    single = se.build_single_source_input()
    vectors: List[Tuple[str, Any]] = [
        ("reference_multi_source_unique_max", base),
        ("single_source_unique_max", single),
        ("absolute_majority_not_reached", se.build_absolute_majority_input()),
        ("absolute_majority_reached", build_majority_yes(se)),
        ("top_k_unambiguous", se.build_top_k_input()),
        ("top_k_boundary_tie", build_top_k_boundary_tie(se)),
        ("unit_winner_weight", se.build_unit_weight_input()),
        ("unit_winner_weight_local_tie", build_weight_local_tie(se)),
        ("unique_max_tie", build_tie_input(se)),
        ("zero_resolution_total", build_zero_input(se)),
        (
            "reference_visibility_withheld",
            mutate(base, lambda value: value["context"].__setitem__("reference_visibility_authorized", False)),
        ),
        (
            "evaluation_not_authorized",
            mutate(base, lambda value: value["context"].__setitem__("evaluation_authorized", False)),
        ),
        (
            "open_reporting_boundary",
            refresh(se, mutate(base, lambda value: value["context"].__setitem__("reporting_boundary_sealed", False))),
        ),
        (
            "missing_source",
            mutate(base, lambda value: value["sources"].pop()),
        ),
        (
            "extra_source",
            mutate(
                base,
                lambda value: value["sources"].append(
                    {
                        **copy.deepcopy(value["sources"][0]),
                        "source_id": "SOURCE-D",
                        "source_dataset_commitment": se.commitment("SOURCE-D"),
                    }
                ),
            ),
        ),
        (
            "duplicate_source",
            mutate(base, lambda value: value["sources"].append(copy.deepcopy(value["sources"][0]))),
        ),
        ("source_report_set_disagreement", build_source_disagreement(se)),
        (
            "declared_report_set_mismatch",
            mutate(
                base,
                lambda value: value["sources"][0].__setitem__(
                    "declared_report_set_id",
                    se.REPORT_SET_PREFIX + ("f" * 64),
                ),
            ),
        ),
        (
            "missing_reporting_unit",
            mutate(
                base,
                lambda value: [source["reports"].pop() for source in value["sources"]],
            ),
        ),
        (
            "duplicate_unit_report",
            mutate(
                base,
                lambda value: value["sources"][0]["reports"].append(
                    copy.deepcopy(value["sources"][0]["reports"][0])
                ),
            ),
        ),
        (
            "undeclared_reporting_unit",
            mutate(
                base,
                lambda value: value["sources"][0]["reports"].append(
                    {
                        "unit_id": "UNIT-X",
                        "candidate_counts": {
                            "CANDIDATE-A": "1",
                            "CANDIDATE-B": "0",
                            "CANDIDATE-C": "0",
                        },
                        "non_candidate_count": "0",
                        "total_records": "1",
                    }
                ),
            ),
        ),
        (
            "report_total_mismatch",
            mutate(
                base,
                lambda value: value["sources"][0]["reports"][0].__setitem__("total_records", "999"),
            ),
        ),
        (
            "missing_candidate_count",
            mutate(
                base,
                lambda value: value["sources"][0]["reports"][0]["candidate_counts"].pop("CANDIDATE-C"),
            ),
        ),
        (
            "undeclared_candidate_count",
            mutate(
                base,
                lambda value: value["sources"][0]["reports"][0]["candidate_counts"].__setitem__("CANDIDATE-X", "1"),
            ),
        ),
        (
            "boolean_candidate_count",
            mutate(
                base,
                lambda value: value["sources"][0]["reports"][0]["candidate_counts"].__setitem__("CANDIDATE-A", True),
            ),
        ),
        (
            "integer_candidate_count",
            mutate(
                base,
                lambda value: value["sources"][0]["reports"][0]["candidate_counts"].__setitem__("CANDIDATE-A", 120),
            ),
        ),
        (
            "negative_candidate_count",
            mutate(
                base,
                lambda value: value["sources"][0]["reports"][0]["candidate_counts"].__setitem__("CANDIDATE-A", "-1"),
            ),
        ),
        (
            "leading_zero_candidate_count",
            mutate(
                base,
                lambda value: value["sources"][0]["reports"][0]["candidate_counts"].__setitem__("CANDIDATE-A", "0120"),
            ),
        ),
        (
            "count_digit_limit",
            mutate(
                base,
                lambda value: value["sources"][0]["reports"][0]["candidate_counts"].__setitem__(
                    "CANDIDATE-A", "1" * (se.MAX_COUNT_DIGITS + 1)
                ),
            ),
        ),
        (
            "unsupported_aggregation_mode",
            mutate(base, lambda value: value["contest"].__setitem__("aggregation_mode", "RANKED_CHOICE")),
        ),
        (
            "unsupported_decision_rule",
            mutate(base, lambda value: value["contest"].__setitem__("decision_rule", {"mode": "RANKED_CHOICE"})),
        ),
        (
            "top_k_missing_seats",
            mutate(base, lambda value: value["contest"].__setitem__("decision_rule", {"mode": se.RULE_TOP_K})),
        ),
        (
            "top_k_boolean_seats",
            mutate(
                base,
                lambda value: value["contest"].__setitem__(
                    "decision_rule", {"mode": se.RULE_TOP_K, "seats_to_fill": True}
                ),
            ),
        ),
        (
            "derived_winner_injection",
            mutate(base, lambda value: value.__setitem__("winner", "CANDIDATE-A")),
        ),
        (
            "unknown_top_level_field",
            mutate(base, lambda value: value.__setitem__("unknown", True)),
        ),
        (
            "duplicate_candidate_identifier",
            mutate(base, lambda value: value["contest"]["candidate_ids"].append("candidate-a")),
        ),
        (
            "duplicate_expected_unit_identifier",
            mutate(base, lambda value: value["contest"]["expected_unit_ids"].append("unit-001")),
        ),
        (
            "invalid_source_commitment",
            mutate(base, lambda value: value["sources"][0].__setitem__("source_dataset_commitment", "abc")),
        ),
        (
            "unsupported_report_field",
            mutate(base, lambda value: value["sources"][0]["reports"][0].__setitem__("winner", "CANDIDATE-A")),
        ),
        (
            "unit_weight_not_applicable",
            mutate(base, lambda value: value["sources"][0]["reports"][0].__setitem__("unit_weight", "5")),
        ),
        (
            "candidate_set_declared_identity_mismatch",
            mutate(
                base,
                lambda value: value.__setitem__(
                    "declared_candidate_set_id",
                    "slang_voting_candidate_set_sha256:" + ("f" * 64),
                ),
            ),
        ),
        (
            "reporting_boundary_declared_identity_mismatch",
            mutate(
                base,
                lambda value: value.__setitem__(
                    "declared_reporting_boundary_id",
                    "slang_voting_reporting_boundary_sha256:" + ("f" * 64),
                ),
            ),
        ),
        (
            "forbidden_and_incomplete_precedence",
            mutate(
                base,
                lambda value: (
                    value["context"].__setitem__("evaluation_authorized", False),
                    [source["reports"].pop() for source in value["sources"]],
                ),
            ),
        ),
        (
            "conflict_and_unsupported_precedence",
            mutate(
                base,
                lambda value: (
                    value["contest"]["candidate_ids"].append("candidate-a"),
                    value["contest"].__setitem__("aggregation_mode", "RANKED_CHOICE"),
                ),
            ),
        ),
        (
            "unsupported_and_incomplete_precedence",
            mutate(
                base,
                lambda value: (
                    value["sources"][0].__setitem__("source_dataset_commitment", "abc"),
                    value["sources"].pop(),
                ),
            ),
        ),
        (
            "uppercase_declared_report_set_identity",
            mutate(
                base,
                lambda value: value["sources"][0].__setitem__(
                    "declared_report_set_id",
                    se.REPORT_SET_PREFIX
                    + value["sources"][0]["declared_report_set_id"][len(se.REPORT_SET_PREFIX):].upper(),
                ),
            ),
        ),
        (
            "uppercase_declared_candidate_set_identity",
            mutate(
                base,
                lambda value: value.__setitem__(
                    "declared_candidate_set_id",
                    "slang_voting_candidate_set_sha256:"
                    + value["declared_candidate_set_id"][len("slang_voting_candidate_set_sha256:"):].upper(),
                ),
            ),
        ),
        (
            "uppercase_declared_reporting_boundary_identity",
            mutate(
                base,
                lambda value: value.__setitem__(
                    "declared_reporting_boundary_id",
                    "slang_voting_reporting_boundary_sha256:"
                    + value["declared_reporting_boundary_id"][len("slang_voting_reporting_boundary_sha256:"):].upper(),
                ),
            ),
        ),
        (
            "uppercase_source_commitment",
            mutate(
                base,
                lambda value: value["sources"][0].__setitem__(
                    "source_dataset_commitment",
                    value["sources"][0]["source_dataset_commitment"].upper(),
                ),
            ),
        ),
    ]
    return vectors


def build_parser_vectors() -> List[Dict[str, str]]:
    return [
        {"name": "duplicate_object_key", "raw_json": '{"schema":"A","schema":"B"}', "expected": "REJECT"},
        {"name": "floating_point", "raw_json": '{"value":1.5}', "expected": "REJECT"},
        {"name": "nan", "raw_json": '{"value":NaN}', "expected": "REJECT"},
        {"name": "infinity", "raw_json": '{"value":Infinity}', "expected": "REJECT"},
        {"name": "portable_integer_overflow", "raw_json": '{"value":9007199254740992}', "expected": "REJECT"},
        {"name": "lone_unicode_surrogate", "raw_json": '"\\ud800"', "expected": "REJECT"},
        {"name": "portable_integer_limit", "raw_json": '{"value":9007199254740991}', "expected": "ACCEPT"},
        {"name": "ordinary_object", "raw_json": '{"value":"ok"}', "expected": "ACCEPT"},
    ]


def reorder_all(value: Dict[str, Any]) -> None:
    value["contest"]["candidate_ids"].reverse()
    value["contest"]["expected_unit_ids"].reverse()
    value["context"]["expected_source_ids"].reverse()
    value["sources"].reverse()
    for source in value["sources"]:
        source["reports"].reverse()
        for report in source["reports"]:
            report["candidate_counts"] = dict(reversed(list(report["candidate_counts"].items())))


def build_relations(se) -> List[Dict[str, Any]]:
    base = se.build_reference_input()
    reordered = mutate(base, reorder_all)
    single = se.build_single_source_input()
    withheld = mutate(base, lambda value: value["context"].__setitem__("reference_visibility_authorized", False))
    changed = se.build_single_source_input()
    for report in changed["sources"][0]["reports"]:
        report["candidate_counts"]["CANDIDATE-B"] = str(int(report["candidate_counts"]["CANDIDATE-B"]) + 200)
        report["total_records"] = str(
            sum(int(item) for item in report["candidate_counts"].values())
            + int(report["non_candidate_count"])
        )
    changed = refresh(se, changed)
    tie = build_tie_input(se)
    tie_reordered = mutate(tie, reorder_all)
    uppercase_commitment = mutate(
        base,
        lambda value: value["sources"][0].__setitem__(
            "source_dataset_commitment",
            value["sources"][0]["source_dataset_commitment"].upper(),
        ),
    )
    mixed = mutate(
        base,
        lambda value: (
            value["context"].__setitem__("evaluation_authorized", False),
            [source["reports"].pop() for source in value["sources"]],
        ),
    )
    mixed_reordered = mutate(mixed, reorder_all)
    return [
        {
            "name": "presentation_permutation_preserves_semantics",
            "left_input": base,
            "right_input": reordered,
            "equal_fields": ["canonical_input_id", "report_set_id", "source_agreement_id", "outcome_id", "result_id"],
            "different_fields": ["submission_id"],
        },
        {
            "name": "single_and_multi_source_preserve_outcome",
            "left_input": base,
            "right_input": single,
            "equal_fields": ["report_set_id", "outcome_id", "result_id", "selected_candidate_ids"],
            "different_fields": ["canonical_input_id", "source_manifest_id", "source_agreement_id", "evaluation_evidence_id"],
        },
        {
            "name": "visibility_policy_preserves_resolved_outcome",
            "left_input": base,
            "right_input": withheld,
            "equal_fields": ["outcome_id", "resolution_state", "selected_candidate_ids", "candidate_resolution_totals"],
            "different_fields": ["state", "visibility_state", "result_id", "evaluation_evidence_id"],
        },
        {
            "name": "material_count_change_changes_outcome",
            "left_input": single,
            "right_input": changed,
            "equal_fields": ["candidate_set_id", "reporting_boundary_id", "rule_profile_id"],
            "different_fields": ["report_set_id", "outcome_id", "result_id", "selected_candidate_ids"],
        },
        {
            "name": "tie_order_does_not_break_tie",
            "left_input": tie,
            "right_input": tie_reordered,
            "equal_fields": ["state", "reason_codes", "leading_candidate_ids", "outcome_id", "result_id"],
            "different_fields": ["submission_id"],
        },
        {
            "name": "repeat_resolution_is_identical",
            "left_input": base,
            "right_input": copy.deepcopy(base),
            "equal_fields": ["submission_id", "canonical_input_id", "outcome_id", "evaluation_evidence_id", "result_id"],
            "different_fields": [],
        },
        {
            "name": "source_commitment_hex_case_normalizes",
            "left_input": base,
            "right_input": uppercase_commitment,
            "equal_fields": ["canonical_input_id", "source_manifest_id", "source_agreement_id", "outcome_id", "result_id"],
            "different_fields": ["submission_id"],
        },
        {
            "name": "mixed_issue_diagnostics_are_order_invariant",
            "left_input": mixed,
            "right_input": mixed_reordered,
            "equal_fields": ["state", "resolution_state", "reason_codes", "missing_dependencies", "prohibitions", "result_id"],
            "different_fields": ["submission_id"],
        },
    ]


def resolve_actual(se, raw_input: Any) -> Dict[str, Any]:
    return se.build_bundle(raw_input)["result"]


def summary_actual(se, raw_input: Any) -> Dict[str, Any]:
    return se.public_summary(se.build_bundle(raw_input))


def build_presentation_vectors(se) -> List[Dict[str, Any]]:
    visible = se.build_reference_input()
    withheld = mutate(
        visible,
        lambda value: value["context"].__setitem__(
            "reference_visibility_authorized", False
        ),
    )
    tie = build_tie_input(se)
    incomplete = refresh(
        se,
        mutate(
            visible,
            lambda value: value["context"].__setitem__(
                "reporting_boundary_sealed", False
            ),
        ),
    )
    return [
        {
            "name": "visible_resolved_summary",
            "input": visible,
            "expected": summary_actual(se, visible),
        },
        {
            "name": "withheld_resolved_summary",
            "input": withheld,
            "expected": summary_actual(se, withheld),
        },
        {
            "name": "abstain_tie_summary",
            "input": tie,
            "expected": summary_actual(se, tie),
        },
        {
            "name": "incomplete_open_boundary_summary",
            "input": incomplete,
            "expected": summary_actual(se, incomplete),
        },
    ]


def build_document(se) -> Dict[str, Any]:
    semantic_vectors = []
    for name, raw_input in build_vectors(se):
        semantic_vectors.append(
            {
                "name": name,
                "input": raw_input,
                "expected": expected_part(resolve_actual(se, raw_input)),
            }
        )

    reference_input = se.build_reference_input()
    reference_bundle = se.build_bundle(reference_input)
    reference_receipt = se.make_receipt(reference_bundle)
    document: Dict[str, Any] = {
        "schema": VECTOR_SCHEMA,
        "version": se.VERSION,
        "core_version": se.CORE_VERSION,
        "profile_id": se.PROFILE_ID,
        "ruleset_id": se.RULESET_ID,
        "canonicalization_id": se.CANONICALIZATION_ID,
        "identity_domain_id": se.identity_domain_id(),
        "public_summary_schema": se.PUBLIC_SUMMARY_SCHEMA,
        "semantic_vectors": semantic_vectors,
        "presentation_vectors": build_presentation_vectors(se),
        "parser_vectors": build_parser_vectors(),
        "relations": build_relations(se),
        "reference_evidence": {
            "example_input": reference_input,
            "bundle": reference_bundle,
            "receipt": reference_receipt,
        },
    }
    document["vector_set_id"] = se.identity("slang_voting_vector_set_sha256:", document)
    return document


def verify_header(se, document: Dict[str, Any]) -> List[str]:
    document = dict(document)
    document.pop("__source_bytes_canonical__", None)
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
        if document.get(key) != value:
            failures.append("header " + key)
    vector_set_id = document.get("vector_set_id")
    material = dict(document)
    material.pop("vector_set_id", None)
    if vector_set_id != se.identity("slang_voting_vector_set_sha256:", material):
        failures.append("vector_set_id")
    return failures


def verify_document(se, document: Dict[str, Any]) -> Tuple[Dict[str, Tuple[int, int]], List[str]]:
    source_bytes_canonical = document.get("__source_bytes_canonical__") is True
    document = dict(document)
    document.pop("__source_bytes_canonical__", None)
    failures = verify_header(se, document)
    report: Dict[str, Tuple[int, int]] = {}

    semantic_pass = 0
    semantic_vectors = document.get("semantic_vectors", [])
    if not isinstance(semantic_vectors, list):
        failures.append("semantic_vectors type")
        semantic_vectors = []
    for vector in semantic_vectors:
        name = vector.get("name", "unnamed") if isinstance(vector, dict) else "unnamed"
        if not isinstance(vector, dict):
            failures.append("semantic vector type")
            continue
        actual = expected_part(resolve_actual(se, vector.get("input")))
        if se.canonical_json(actual) == se.canonical_json(vector.get("expected")):
            semantic_pass += 1
        else:
            failures.append("semantic vector " + name)
    report["semantic vectors"] = (semantic_pass, len(semantic_vectors))

    presentation_pass = 0
    presentation_vectors = document.get("presentation_vectors", [])
    if not isinstance(presentation_vectors, list):
        failures.append("presentation_vectors type")
        presentation_vectors = []
    for vector in presentation_vectors:
        name = vector.get("name", "unnamed") if isinstance(vector, dict) else "unnamed"
        if not isinstance(vector, dict):
            failures.append("presentation vector type")
            continue
        actual = summary_actual(se, vector.get("input"))
        if se.canonical_json(actual) == se.canonical_json(vector.get("expected")):
            presentation_pass += 1
        else:
            failures.append("presentation vector " + name)
    report["presentation vectors"] = (presentation_pass, len(presentation_vectors))

    parser_pass = 0
    parser_vectors = document.get("parser_vectors", [])
    if not isinstance(parser_vectors, list):
        failures.append("parser_vectors type")
        parser_vectors = []
    for vector in parser_vectors:
        name = vector.get("name", "unnamed") if isinstance(vector, dict) else "unnamed"
        try:
            se.loads_strict(vector.get("raw_json", ""))
            actual = "ACCEPT"
        except (TypeError, ValueError, se.DuplicateKeyError):
            actual = "REJECT"
        if actual == vector.get("expected"):
            parser_pass += 1
        else:
            failures.append("parser vector " + name)
    report["parser vectors"] = (parser_pass, len(parser_vectors))

    evidence_pass = 0
    evidence_total = 3
    evidence = document.get("reference_evidence", {})
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

    serialization_pass = 0
    serialization_total = 1
    if source_bytes_canonical:
        serialization_pass = 1
    else:
        failures.append("serialization bytes")
    report["serialization bytes"] = (serialization_pass, serialization_total)

    relation_pass = 0
    relations = document.get("relations", [])
    if not isinstance(relations, list):
        failures.append("relations type")
        relations = []
    for relation in relations:
        name = relation.get("name", "unnamed") if isinstance(relation, dict) else "unnamed"
        if not isinstance(relation, dict):
            failures.append("relation type")
            continue
        left = resolve_actual(se, relation.get("left_input"))
        right = resolve_actual(se, relation.get("right_input"))
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
    parser = argparse.ArgumentParser(description="SLANG-Voting frozen conformance vectors")
    parser.add_argument("--core", type=Path, default=Path(__file__).with_name(EXPECTED_CORE_FILENAME))
    parser.add_argument("--write", type=Path, help="write a frozen vector document")
    parser.add_argument("--verify", type=Path, help="verify a frozen vector document")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
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
            verify_path.read_bytes() == se.json_file_bytes({
                key: value for key, value in document.items()
                if key != "__source_bytes_canonical__"
            })
        )
        report, failures = verify_document(se, document)
        return print_report(report, failures)
    except (OSError, TypeError, ValueError, RuntimeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
