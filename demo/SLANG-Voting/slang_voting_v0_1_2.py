#!/usr/bin/env python3
"""
SLANG-Voting
Bounded deterministic election-result resolution from declared aggregate records.

Python 3.9+
Standard library only
"""

import argparse
import copy
import hashlib
import json
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple


VERSION = "0.1.2"
CORE_VERSION = "SLANG-CORE-1-D05"
PROFILE_ID = "SLANG-VOTING-PROFILE-1-D03"
RULESET_ID = "SLANG-VOTING-RULESET-1-D03"
CANONICALIZATION_ID = "SLANG-CANONICAL-JSON-1-D02"

INPUT_SCHEMA = "SLANG-VOTING-INPUT-1"
RESULT_SCHEMA = "SLANG-VOTING-RESULT-1"
BUNDLE_SCHEMA = "SLANG-VOTING-BUNDLE-1"
RECEIPT_SCHEMA = "SLANG-VOTING-RECEIPT-1"
PUBLIC_SUMMARY_SCHEMA = "SLANG-VOTING-PUBLIC-SUMMARY-1"

STATE_RESOLVED = "RESOLVED"
STATE_INCOMPLETE = "INCOMPLETE"
STATE_CONFLICT = "CONFLICT"
STATE_FORBIDDEN = "FORBIDDEN"
STATE_UNSUPPORTED = "UNSUPPORTED"
STATE_ABSTAIN = "ABSTAIN"

SUPPORTED_STATES = {
    STATE_RESOLVED,
    STATE_INCOMPLETE,
    STATE_CONFLICT,
    STATE_FORBIDDEN,
    STATE_UNSUPPORTED,
    STATE_ABSTAIN,
}

EVIDENCE_SINGLE_SOURCE = "SINGLE_SOURCE"
EVIDENCE_MULTI_SOURCE = "MULTI_SOURCE_EXACT_AGREEMENT"
SUPPORTED_EVIDENCE_MODES = {EVIDENCE_SINGLE_SOURCE, EVIDENCE_MULTI_SOURCE}

AGGREGATION_SUM_COUNTS = "SUM_COUNTS"
AGGREGATION_UNIT_WINNER_WEIGHT = "UNIT_WINNER_WEIGHT"
SUPPORTED_AGGREGATION_MODES = {
    AGGREGATION_SUM_COUNTS,
    AGGREGATION_UNIT_WINNER_WEIGHT,
}

RULE_UNIQUE_MAX = "UNIQUE_MAX"
RULE_ABSOLUTE_MAJORITY = "ABSOLUTE_MAJORITY"
RULE_TOP_K = "TOP_K"
SUPPORTED_DECISION_RULES = {RULE_UNIQUE_MAX, RULE_ABSOLUTE_MAJORITY, RULE_TOP_K}

TOP_LEVEL_KEYS = {
    "schema",
    "profile_id",
    "ruleset_id",
    "context",
    "contest",
    "sources",
    "declared_candidate_set_id",
    "declared_reporting_boundary_id",
}

DERIVED_TOP_LEVEL_KEYS = {
    "state",
    "resolution_state",
    "visibility_state",
    "outcome_visible",
    "winner",
    "winner_visible",
    "winner_identity",
    "structural_state",
    "selected_candidate_ids",
    "leading_candidate_ids",
    "candidate_record_totals",
    "candidate_resolution_totals",
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
    "bundle_id",
    "receipt_id",
    "result",
    "normalized_projection",
    "submitted_input",
    "evidence",
    "reason_codes",
    "missing_dependencies",
    "conflicts",
    "prohibitions",
    "unsupported_features",
}

CONTEXT_KEYS = {
    "evaluation_id",
    "jurisdiction_id",
    "evaluation_authorized",
    "reporting_boundary_sealed",
    "reference_visibility_authorized",
    "evidence_mode",
    "expected_source_ids",
}

CONTEST_KEYS = {
    "contest_id",
    "candidate_ids",
    "expected_unit_ids",
    "aggregation_mode",
    "decision_rule",
}

DECISION_RULE_KEYS = {"mode", "seats_to_fill"}
SOURCE_KEYS = {"source_id", "source_dataset_commitment", "declared_report_set_id", "reports"}
REPORT_BASE_KEYS = {"unit_id", "candidate_counts", "non_candidate_count", "total_records"}
REPORT_WEIGHT_KEYS = REPORT_BASE_KEYS | {"unit_weight"}

MAX_SAFE_INTEGER = (2 ** 53) - 1
MAX_JSON_DEPTH = 64
MAX_JSON_NODES = 500000
MAX_JSON_INPUT_BYTES = 16 * 1024 * 1024
MAX_IDENTIFIER_LENGTH = 64
MAX_CANDIDATES = 128
MAX_REPORTING_UNITS = 10000
MAX_SOURCES = 16
MAX_COUNT_DIGITS = 30
MAX_AGGREGATE_DIGITS = 40
MAX_REACHABLE_AGGREGATE = MAX_REPORTING_UNITS * ((10 ** MAX_COUNT_DIGITS) - 1)
MAX_REACHABLE_AGGREGATE_DIGITS = len(str(MAX_REACHABLE_AGGREGATE))
HEX_DIGITS = frozenset("0123456789abcdefABCDEF")
LOWER_HEX_DIGITS = frozenset("0123456789abcdef")
IDENTIFIER_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9._:-]{0,63}$")
DECIMAL_PATTERN = re.compile(r"^(0|[1-9][0-9]*)$")
REPORT_SET_PREFIX = "slang_voting_report_set_sha256:"

BUNDLE_KEYS = {
    "schema",
    "version",
    "core_version",
    "canonicalization_id",
    "identity_domain_id",
    "submitted_input",
    "normalized_projection",
    "result",
    "bundle_id",
}

RECEIPT_KEYS = {
    "schema",
    "version",
    "core_version",
    "canonicalization_id",
    "identity_domain_id",
    "profile_id",
    "ruleset_id",
    "evaluation_id",
    "contest_id",
    "state",
    "resolution_state",
    "visibility_state",
    "outcome_visible",
    "selected_candidate_ids",
    "leading_candidate_ids",
    "aggregation_mode",
    "decision_rule_mode",
    "evidence_mode",
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
    "reason_codes",
    "execution_authority",
    "certification_authority",
    "official_result_authority",
    "bundle_id",
    "receipt_id",
}


class PortableJSONError(ValueError):
    pass


class DuplicateKeyError(PortableJSONError):
    pass


@dataclass(frozen=True)
class ValidationIssue:
    state: str
    code: str
    detail: str


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def json_clone(value: Any) -> Any:
    return json.loads(canonical_json(value))


def sha256_hex(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def identity(prefix: str, value: Any) -> str:
    return prefix + sha256_hex(value)


def identity_domain_material() -> Dict[str, str]:
    return {
        "version": VERSION,
        "core_version": CORE_VERSION,
        "profile_id": PROFILE_ID,
        "ruleset_id": RULESET_ID,
        "canonicalization_id": CANONICALIZATION_ID,
        "input_schema": INPUT_SCHEMA,
        "result_schema": RESULT_SCHEMA,
        "bundle_schema": BUNDLE_SCHEMA,
        "receipt_schema": RECEIPT_SCHEMA,
        "public_summary_schema": PUBLIC_SUMMARY_SCHEMA,
    }


def identity_domain_id() -> str:
    return identity("slang_voting_identity_domain_sha256:", identity_domain_material())


def contains_lone_surrogate(value: str) -> bool:
    return any(0xD800 <= ord(char) <= 0xDFFF for char in value)


def validate_portable_json(value: Any, path: str = "$") -> None:
    stack: List[Tuple[Any, str, int]] = [(value, path, 0)]
    nodes = 0
    while stack:
        current, current_path, depth = stack.pop()
        nodes += 1
        if nodes > MAX_JSON_NODES:
            raise PortableJSONError("portable JSON node limit exceeded")
        if depth > MAX_JSON_DEPTH:
            raise PortableJSONError("portable JSON depth limit exceeded at " + current_path)
        if current is None or isinstance(current, bool):
            continue
        if isinstance(current, str):
            if contains_lone_surrogate(current):
                raise PortableJSONError("lone surrogate is not supported at " + current_path)
            continue
        if isinstance(current, int) and not isinstance(current, bool):
            if current < -MAX_SAFE_INTEGER or current > MAX_SAFE_INTEGER:
                raise PortableJSONError("integer outside portable range at " + current_path)
            continue
        if isinstance(current, float):
            raise PortableJSONError("floating-point values are not supported at " + current_path)
        if isinstance(current, list):
            for index in range(len(current) - 1, -1, -1):
                stack.append((current[index], current_path + "[" + str(index) + "]", depth + 1))
            continue
        if isinstance(current, dict):
            for key, item in reversed(list(current.items())):
                if not isinstance(key, str):
                    raise PortableJSONError("JSON object key is not a string at " + current_path)
                if contains_lone_surrogate(key):
                    raise PortableJSONError("lone surrogate object key is not supported at " + current_path)
                stack.append((item, current_path + "." + key, depth + 1))
            continue
        raise PortableJSONError(
            "unsupported JSON value at " + current_path + ": " + type(current).__name__
        )


def normalize_text(value: str) -> str:
    return value.strip()


def normalize_label(value: str) -> str:
    return normalize_text(value).upper()


def is_plain_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def normalize_identifier(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    text = normalize_label(value)
    if len(text) > MAX_IDENTIFIER_LENGTH or not IDENTIFIER_PATTERN.fullmatch(text):
        return None
    return text


def normalize_sha256(value: Any) -> Optional[str]:
    if not isinstance(value, str) or len(value) != 64:
        return None
    if any(character not in HEX_DIGITS for character in value):
        return None
    return value.lower()


def is_identity_with_prefix(value: Any, prefix: str) -> bool:
    if not isinstance(value, str) or not value.startswith(prefix):
        return False
    digest = value[len(prefix):]
    return len(digest) == 64 and all(character in LOWER_HEX_DIGITS for character in digest)


def parse_decimal_string(value: Any, field_name: str) -> Tuple[Optional[int], Optional[str]]:
    if not isinstance(value, str) or not DECIMAL_PATTERN.fullmatch(value):
        return None, "INVALID_" + field_name.upper() + "_DECIMAL"
    if len(value) > MAX_COUNT_DIGITS:
        return None, field_name.upper() + "_DIGIT_LIMIT_EXCEEDED"
    return int(value, 10), None


def decimal_string(value: int) -> str:
    return str(value)


VALIDATION_STATE_PRIORITY = {
    STATE_FORBIDDEN: 0,
    STATE_CONFLICT: 1,
    STATE_UNSUPPORTED: 2,
    STATE_INCOMPLETE: 3,
}


def issue_priority(state: str) -> int:
    return VALIDATION_STATE_PRIORITY.get(state, 99)


def choose_primary_issue(issues: Sequence[ValidationIssue]) -> ValidationIssue:
    if not issues:
        raise ValueError("primary issue selection requires at least one issue")
    if any(issue.state not in VALIDATION_STATE_PRIORITY for issue in issues):
        raise ValueError("validation issue has unsupported state")
    return sorted(issues, key=lambda item: (issue_priority(item.state), item.code, item.detail))[0]


def unique_sorted(values: Iterable[str]) -> List[str]:
    return sorted(set(values))


def normalize_identifier_list(
    value: Any,
    field_name: str,
    maximum: int,
) -> Tuple[Optional[List[str]], List[ValidationIssue]]:
    issues: List[ValidationIssue] = []
    if value is None:
        return None, [ValidationIssue(STATE_INCOMPLETE, "MISSING_" + field_name.upper(), field_name)]
    if not isinstance(value, list):
        return None, [ValidationIssue(STATE_UNSUPPORTED, "INVALID_" + field_name.upper() + "_TYPE", field_name)]
    if not value:
        issues.append(ValidationIssue(STATE_INCOMPLETE, "EMPTY_" + field_name.upper(), field_name))
    if len(value) > maximum:
        issues.append(ValidationIssue(STATE_UNSUPPORTED, field_name.upper() + "_LIMIT_EXCEEDED", str(len(value))))
    normalized: List[str] = []
    seen: Set[str] = set()
    for index, raw in enumerate(value):
        item = normalize_identifier(raw)
        if item is None:
            issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_" + field_name.upper() + "_ID", str(index)))
            continue
        if item in seen:
            issues.append(ValidationIssue(STATE_CONFLICT, "DUPLICATE_" + field_name.upper() + "_ID", item))
            continue
        seen.add(item)
        normalized.append(item)
    return sorted(normalized), issues


def normalize_context(value: Any) -> Tuple[Optional[Dict[str, Any]], List[ValidationIssue]]:
    issues: List[ValidationIssue] = []
    if value is None:
        return None, [ValidationIssue(STATE_INCOMPLETE, "MISSING_CONTEXT", "context")]
    if not isinstance(value, dict):
        return None, [ValidationIssue(STATE_UNSUPPORTED, "INVALID_CONTEXT_TYPE", "context")]
    for key in sorted(set(value) - CONTEXT_KEYS):
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "UNSUPPORTED_CONTEXT_FIELD", key))
    for key in sorted(CONTEXT_KEYS):
        if key not in value:
            issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_CONTEXT_FIELD", key))

    normalized: Dict[str, Any] = {}
    for key in ("evaluation_id", "jurisdiction_id"):
        if key in value:
            item = normalize_identifier(value.get(key))
            if item is None:
                issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_" + key.upper(), key))
            else:
                normalized[key] = item

    for key in (
        "evaluation_authorized",
        "reporting_boundary_sealed",
        "reference_visibility_authorized",
    ):
        if key in value:
            raw = value.get(key)
            if not isinstance(raw, bool):
                issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_" + key.upper(), key))
            else:
                normalized[key] = raw

    if "evidence_mode" in value:
        raw_mode = value.get("evidence_mode")
        if not isinstance(raw_mode, str) or normalize_label(raw_mode) not in SUPPORTED_EVIDENCE_MODES:
            issues.append(ValidationIssue(STATE_UNSUPPORTED, "UNSUPPORTED_EVIDENCE_MODE", repr(raw_mode)))
        else:
            normalized["evidence_mode"] = normalize_label(raw_mode)

    source_ids, source_issues = normalize_identifier_list(
        value.get("expected_source_ids"),
        "expected_source",
        MAX_SOURCES,
    )
    issues.extend(source_issues)
    if source_ids is not None:
        normalized["expected_source_ids"] = source_ids

    mode = normalized.get("evidence_mode")
    if source_ids is not None and mode == EVIDENCE_SINGLE_SOURCE and len(source_ids) != 1:
        issues.append(ValidationIssue(STATE_CONFLICT, "SINGLE_SOURCE_REQUIRES_ONE_SOURCE", str(len(source_ids))))
    if source_ids is not None and mode == EVIDENCE_MULTI_SOURCE and len(source_ids) < 2:
        issues.append(ValidationIssue(STATE_INCOMPLETE, "MULTI_SOURCE_REQUIRES_AT_LEAST_TWO_SOURCES", str(len(source_ids))))
    if normalized.get("reporting_boundary_sealed") is False:
        issues.append(ValidationIssue(STATE_INCOMPLETE, "REPORTING_BOUNDARY_OPEN", "reporting_boundary_sealed"))
    if normalized.get("evaluation_authorized") is False:
        issues.append(ValidationIssue(STATE_FORBIDDEN, "EVALUATION_NOT_AUTHORIZED", "evaluation_authorized"))

    return normalized, issues


def normalize_decision_rule(value: Any, candidate_count: Optional[int]) -> Tuple[Optional[Dict[str, Any]], List[ValidationIssue]]:
    issues: List[ValidationIssue] = []
    if value is None:
        return None, [ValidationIssue(STATE_INCOMPLETE, "MISSING_DECISION_RULE", "decision_rule")]
    if not isinstance(value, dict):
        return None, [ValidationIssue(STATE_UNSUPPORTED, "INVALID_DECISION_RULE_TYPE", "decision_rule")]
    for key in sorted(set(value) - DECISION_RULE_KEYS):
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "UNSUPPORTED_DECISION_RULE_FIELD", key))
    if "mode" not in value:
        issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_DECISION_RULE_MODE", "mode"))
        return None, issues

    normalized: Dict[str, Any] = {}
    raw_mode = value.get("mode")
    if not isinstance(raw_mode, str) or normalize_label(raw_mode) not in SUPPORTED_DECISION_RULES:
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "UNSUPPORTED_DECISION_RULE_MODE", repr(raw_mode)))
        return None, issues
    mode = normalize_label(raw_mode)
    normalized["mode"] = mode

    has_seats = "seats_to_fill" in value
    if mode == RULE_TOP_K:
        if not has_seats:
            issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_SEATS_TO_FILL", "seats_to_fill"))
        else:
            seats = value.get("seats_to_fill")
            if not is_plain_int(seats) or seats < 1:
                issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_SEATS_TO_FILL", repr(seats)))
            elif candidate_count is not None and seats >= candidate_count:
                issues.append(ValidationIssue(STATE_UNSUPPORTED, "SEATS_TO_FILL_MUST_BE_LESS_THAN_CANDIDATE_COUNT", str(seats)))
            else:
                normalized["seats_to_fill"] = seats
    elif has_seats:
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "SEATS_TO_FILL_NOT_APPLICABLE", mode))

    return normalized, issues


def normalize_contest(value: Any) -> Tuple[Optional[Dict[str, Any]], List[ValidationIssue]]:
    issues: List[ValidationIssue] = []
    if value is None:
        return None, [ValidationIssue(STATE_INCOMPLETE, "MISSING_CONTEST", "contest")]
    if not isinstance(value, dict):
        return None, [ValidationIssue(STATE_UNSUPPORTED, "INVALID_CONTEST_TYPE", "contest")]
    for key in sorted(set(value) - CONTEST_KEYS):
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "UNSUPPORTED_CONTEST_FIELD", key))
    for key in sorted(CONTEST_KEYS):
        if key not in value:
            issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_CONTEST_FIELD", key))

    normalized: Dict[str, Any] = {}
    if "contest_id" in value:
        contest_id = normalize_identifier(value.get("contest_id"))
        if contest_id is None:
            issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_CONTEST_ID", "contest_id"))
        else:
            normalized["contest_id"] = contest_id

    candidate_ids, candidate_issues = normalize_identifier_list(
        value.get("candidate_ids"),
        "candidate",
        MAX_CANDIDATES,
    )
    unit_ids, unit_issues = normalize_identifier_list(
        value.get("expected_unit_ids"),
        "reporting_unit",
        MAX_REPORTING_UNITS,
    )
    issues.extend(candidate_issues)
    issues.extend(unit_issues)
    if candidate_ids is not None:
        normalized["candidate_ids"] = candidate_ids
    if unit_ids is not None:
        normalized["expected_unit_ids"] = unit_ids

    if "aggregation_mode" in value:
        raw_mode = value.get("aggregation_mode")
        if not isinstance(raw_mode, str) or normalize_label(raw_mode) not in SUPPORTED_AGGREGATION_MODES:
            issues.append(ValidationIssue(STATE_UNSUPPORTED, "UNSUPPORTED_AGGREGATION_MODE", repr(raw_mode)))
        else:
            normalized["aggregation_mode"] = normalize_label(raw_mode)

    decision_rule, decision_issues = normalize_decision_rule(
        value.get("decision_rule"),
        len(candidate_ids) if candidate_ids is not None else None,
    )
    issues.extend(decision_issues)
    if decision_rule is not None:
        normalized["decision_rule"] = decision_rule

    return normalized, issues


def normalize_candidate_counts(
    value: Any,
    candidate_ids: Optional[List[str]],
    unit_id: str,
) -> Tuple[Optional[Dict[str, str]], Optional[Dict[str, int]], List[ValidationIssue]]:
    issues: List[ValidationIssue] = []
    if value is None:
        return None, None, [ValidationIssue(STATE_INCOMPLETE, "MISSING_CANDIDATE_COUNTS", unit_id)]
    if not isinstance(value, dict):
        return None, None, [ValidationIssue(STATE_UNSUPPORTED, "INVALID_CANDIDATE_COUNTS_TYPE", unit_id)]

    normalized_strings: Dict[str, str] = {}
    normalized_ints: Dict[str, int] = {}
    for raw_key, raw_value in value.items():
        candidate_id = normalize_identifier(raw_key)
        if candidate_id is None:
            issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_REPORT_CANDIDATE_ID", unit_id))
            continue
        if candidate_id in normalized_strings:
            issues.append(ValidationIssue(STATE_CONFLICT, "NORMALIZED_CANDIDATE_COUNT_COLLISION", unit_id + ":" + candidate_id))
            continue
        count, error = parse_decimal_string(raw_value, "candidate_count")
        if error is not None:
            issues.append(ValidationIssue(STATE_UNSUPPORTED, error, unit_id + ":" + candidate_id))
            continue
        normalized_strings[candidate_id] = decimal_string(count if count is not None else 0)
        normalized_ints[candidate_id] = count if count is not None else 0

    if candidate_ids is not None:
        expected = set(candidate_ids)
        present = set(normalized_strings)
        for missing in sorted(expected - present):
            issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_CANDIDATE_COUNT", unit_id + ":" + missing))
        for extra in sorted(present - expected):
            issues.append(ValidationIssue(STATE_CONFLICT, "UNDECLARED_CANDIDATE_COUNT", unit_id + ":" + extra))

    return dict(sorted(normalized_strings.items())), dict(sorted(normalized_ints.items())), issues


def normalize_report(
    value: Any,
    candidate_ids: Optional[List[str]],
    aggregation_mode: Optional[str],
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], List[ValidationIssue]]:
    issues: List[ValidationIssue] = []
    if not isinstance(value, dict):
        return None, None, [ValidationIssue(STATE_UNSUPPORTED, "INVALID_REPORT_TYPE", type(value).__name__)]

    expected_keys = REPORT_WEIGHT_KEYS if aggregation_mode == AGGREGATION_UNIT_WINNER_WEIGHT else REPORT_BASE_KEYS
    for key in sorted(set(value) - expected_keys):
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "UNSUPPORTED_REPORT_FIELD", key))
    for key in sorted(expected_keys):
        if key not in value:
            issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_REPORT_FIELD", key))

    unit_id = normalize_identifier(value.get("unit_id"))
    if unit_id is None:
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_UNIT_ID", repr(value.get("unit_id"))))
        unit_label = "UNKNOWN-UNIT"
    else:
        unit_label = unit_id

    count_strings, count_ints, count_issues = normalize_candidate_counts(
        value.get("candidate_counts"),
        candidate_ids,
        unit_label,
    )
    issues.extend(count_issues)

    normalized: Dict[str, Any] = {}
    computational: Dict[str, Any] = {}
    if unit_id is not None:
        normalized["unit_id"] = unit_id
        computational["unit_id"] = unit_id
    if count_strings is not None:
        normalized["candidate_counts"] = count_strings
    if count_ints is not None:
        computational["candidate_counts"] = count_ints

    for field in ("non_candidate_count", "total_records"):
        if field in value:
            count, error = parse_decimal_string(value.get(field), field)
            if error is not None:
                issues.append(ValidationIssue(STATE_UNSUPPORTED, error, unit_label))
            else:
                normalized[field] = decimal_string(count if count is not None else 0)
                computational[field] = count if count is not None else 0

    if aggregation_mode == AGGREGATION_UNIT_WINNER_WEIGHT and "unit_weight" in value:
        weight, error = parse_decimal_string(value.get("unit_weight"), "unit_weight")
        if error is not None:
            issues.append(ValidationIssue(STATE_UNSUPPORTED, error, unit_label))
        elif weight == 0:
            issues.append(ValidationIssue(STATE_UNSUPPORTED, "UNIT_WEIGHT_MUST_BE_POSITIVE", unit_label))
        else:
            normalized["unit_weight"] = decimal_string(weight)
            computational["unit_weight"] = weight

    if (
        count_ints is not None
        and not count_issues
        and "non_candidate_count" in computational
        and "total_records" in computational
    ):
        calculated = sum(count_ints.values()) + computational["non_candidate_count"]
        if calculated != computational["total_records"]:
            issues.append(ValidationIssue(STATE_CONFLICT, "REPORT_TOTAL_MISMATCH", unit_label))

    return normalized, computational, issues


def report_set_material(contest: Dict[str, Any], reports: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "domain": "SLANG-VOTING-REPORT-SET-1",
        "contest_id": contest.get("contest_id"),
        "candidate_ids": contest.get("candidate_ids"),
        "expected_unit_ids": contest.get("expected_unit_ids"),
        "aggregation_mode": contest.get("aggregation_mode"),
        "reports": list(reports),
    }


def report_set_identity(contest: Dict[str, Any], reports: Sequence[Dict[str, Any]]) -> str:
    return identity(REPORT_SET_PREFIX, report_set_material(contest, reports))


def normalize_source(
    value: Any,
    contest: Optional[Dict[str, Any]],
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], List[ValidationIssue]]:
    issues: List[ValidationIssue] = []
    if not isinstance(value, dict):
        return None, None, [ValidationIssue(STATE_UNSUPPORTED, "INVALID_SOURCE_TYPE", type(value).__name__)]
    for key in sorted(set(value) - SOURCE_KEYS):
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "UNSUPPORTED_SOURCE_FIELD", key))
    for key in sorted(SOURCE_KEYS):
        if key not in value:
            issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_SOURCE_FIELD", key))

    normalized: Dict[str, Any] = {}
    computational: Dict[str, Any] = {}
    source_id = normalize_identifier(value.get("source_id"))
    if source_id is None:
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_SOURCE_ID", repr(value.get("source_id"))))
        source_label = "UNKNOWN-SOURCE"
    else:
        source_label = source_id
        normalized["source_id"] = source_id
        computational["source_id"] = source_id

    commitment = normalize_sha256(value.get("source_dataset_commitment"))
    if commitment is None:
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_SOURCE_DATASET_COMMITMENT", source_label))
    else:
        normalized["source_dataset_commitment"] = commitment

    declared_report_set_id = value.get("declared_report_set_id")
    if not is_identity_with_prefix(declared_report_set_id, REPORT_SET_PREFIX):
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_DECLARED_REPORT_SET_ID", source_label))
    else:
        normalized["declared_report_set_id"] = declared_report_set_id

    reports_value = value.get("reports")
    normalized_reports: List[Dict[str, Any]] = []
    computational_reports: List[Dict[str, Any]] = []
    if not isinstance(reports_value, list):
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_REPORTS_TYPE", source_label))
    else:
        if len(reports_value) > MAX_REPORTING_UNITS:
            issues.append(ValidationIssue(STATE_UNSUPPORTED, "REPORT_LIMIT_EXCEEDED", source_label))
        seen_units: Set[str] = set()
        candidate_ids = contest.get("candidate_ids") if contest else None
        aggregation_mode = contest.get("aggregation_mode") if contest else None
        for raw_report in reports_value:
            normalized_report, computational_report, report_issues = normalize_report(
                raw_report,
                candidate_ids,
                aggregation_mode,
            )
            issues.extend(report_issues)
            if normalized_report is not None and "unit_id" in normalized_report:
                unit_id = normalized_report["unit_id"]
                if unit_id in seen_units:
                    issues.append(ValidationIssue(STATE_CONFLICT, "DUPLICATE_UNIT_REPORT", source_label + ":" + unit_id))
                else:
                    seen_units.add(unit_id)
                    normalized_reports.append(normalized_report)
                    if computational_report is not None:
                        computational_reports.append(computational_report)

        if contest is not None and contest.get("expected_unit_ids") is not None:
            expected = set(contest["expected_unit_ids"])
            present = set(seen_units)
            for missing in sorted(expected - present):
                issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_REPORTING_UNIT", source_label + ":" + missing))
            for extra in sorted(present - expected):
                issues.append(ValidationIssue(STATE_CONFLICT, "UNDECLARED_REPORTING_UNIT", source_label + ":" + extra))

    normalized_reports.sort(key=lambda item: item.get("unit_id", ""))
    computational_reports.sort(key=lambda item: item.get("unit_id", ""))
    normalized["reports"] = normalized_reports
    computational["reports"] = computational_reports

    contest_complete = (
        contest is not None
        and all(
            key in contest
            for key in ("contest_id", "candidate_ids", "expected_unit_ids", "aggregation_mode")
        )
    )
    report_identity_nonblocking_codes = {
        "INVALID_SOURCE_DATASET_COMMITMENT",
        "INVALID_DECLARED_REPORT_SET_ID",
    }
    report_blocking = any(
        issue.code not in report_identity_nonblocking_codes
        for issue in issues
    )
    if contest_complete and normalized_reports and not report_blocking:
        computed_report_set_id = report_set_identity(contest, normalized_reports)
        computational["report_set_id"] = computed_report_set_id
        normalized["computed_report_set_id"] = computed_report_set_id
        if (
            is_identity_with_prefix(declared_report_set_id, REPORT_SET_PREFIX)
            and declared_report_set_id != computed_report_set_id
        ):
            issues.append(ValidationIssue(STATE_CONFLICT, "DECLARED_REPORT_SET_ID_MISMATCH", source_label))

    return normalized, computational, issues


def candidate_set_material(contest: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "domain": "SLANG-VOTING-CANDIDATE-SET-1",
        "contest_id": contest.get("contest_id"),
        "candidate_ids": contest.get("candidate_ids"),
    }


def reporting_boundary_material(contest: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "domain": "SLANG-VOTING-REPORTING-BOUNDARY-1",
        "contest_id": contest.get("contest_id"),
        "expected_unit_ids": contest.get("expected_unit_ids"),
        "reporting_boundary_sealed": context.get("reporting_boundary_sealed"),
    }


def rule_profile_material(contest: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "domain": "SLANG-VOTING-RULE-PROFILE-1",
        "aggregation_mode": contest.get("aggregation_mode"),
        "decision_rule": contest.get("decision_rule"),
    }


def normalize_input(raw_input: Any) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], List[ValidationIssue]]:
    issues: List[ValidationIssue] = []
    if not isinstance(raw_input, dict):
        return None, None, [ValidationIssue(STATE_UNSUPPORTED, "INPUT_NOT_OBJECT", type(raw_input).__name__)]

    for key in sorted(set(raw_input) & DERIVED_TOP_LEVEL_KEYS):
        issues.append(ValidationIssue(STATE_FORBIDDEN, "DERIVED_FIELD_INJECTION", key))
    for key in sorted(set(raw_input) - TOP_LEVEL_KEYS - DERIVED_TOP_LEVEL_KEYS):
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "UNSUPPORTED_TOP_LEVEL_FIELD", key))
    for key in ("schema", "profile_id", "ruleset_id", "context", "contest", "sources"):
        if key not in raw_input:
            issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_TOP_LEVEL_FIELD", key))

    normalized: Dict[str, Any] = {}
    computational: Dict[str, Any] = {}

    for key, expected, code in (
        ("schema", INPUT_SCHEMA, "UNSUPPORTED_INPUT_SCHEMA"),
        ("profile_id", PROFILE_ID, "UNSUPPORTED_PROFILE_ID"),
        ("ruleset_id", RULESET_ID, "UNSUPPORTED_RULESET_ID"),
    ):
        if key in raw_input:
            if raw_input.get(key) != expected:
                issues.append(ValidationIssue(STATE_UNSUPPORTED, code, repr(raw_input.get(key))))
            else:
                normalized[key] = expected

    context, context_issues = normalize_context(raw_input.get("context"))
    contest, contest_issues = normalize_contest(raw_input.get("contest"))
    issues.extend(context_issues)
    issues.extend(contest_issues)
    if context is not None:
        normalized["context"] = context
        computational["context"] = context
    if contest is not None:
        normalized["contest"] = contest
        computational["contest"] = contest

    if contest is not None:
        candidate_identity_ready = all(
            key in contest for key in ("contest_id", "candidate_ids")
        )
        boundary_identity_ready = (
            all(key in contest for key in ("contest_id", "expected_unit_ids"))
            and context is not None
            and "reporting_boundary_sealed" in context
        )
        rule_identity_ready = all(
            key in contest for key in ("aggregation_mode", "decision_rule")
        )

        computed_candidate_set_id = None
        computed_boundary_id = None
        if candidate_identity_ready:
            computed_candidate_set_id = identity(
                "slang_voting_candidate_set_sha256:",
                candidate_set_material(contest),
            )
            normalized["computed_candidate_set_id"] = computed_candidate_set_id
            computational["candidate_set_id"] = computed_candidate_set_id
        if boundary_identity_ready:
            computed_boundary_id = identity(
                "slang_voting_reporting_boundary_sha256:",
                reporting_boundary_material(contest, context or {}),
            )
            normalized["computed_reporting_boundary_id"] = computed_boundary_id
            computational["reporting_boundary_id"] = computed_boundary_id
        if rule_identity_ready:
            computational["rule_profile_id"] = identity(
                "slang_voting_rule_profile_sha256:",
                rule_profile_material(contest),
            )

        declared_candidate_set_id = raw_input.get("declared_candidate_set_id")
        if declared_candidate_set_id is not None:
            if not is_identity_with_prefix(declared_candidate_set_id, "slang_voting_candidate_set_sha256:"):
                issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_DECLARED_CANDIDATE_SET_ID", "declared_candidate_set_id"))
            else:
                normalized["declared_candidate_set_id"] = declared_candidate_set_id
                if (
                    computed_candidate_set_id is not None
                    and declared_candidate_set_id != computed_candidate_set_id
                ):
                    issues.append(ValidationIssue(STATE_CONFLICT, "DECLARED_CANDIDATE_SET_ID_MISMATCH", "declared_candidate_set_id"))

        declared_boundary_id = raw_input.get("declared_reporting_boundary_id")
        if declared_boundary_id is not None:
            if not is_identity_with_prefix(declared_boundary_id, "slang_voting_reporting_boundary_sha256:"):
                issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_DECLARED_REPORTING_BOUNDARY_ID", "declared_reporting_boundary_id"))
            else:
                normalized["declared_reporting_boundary_id"] = declared_boundary_id
                if (
                    computed_boundary_id is not None
                    and declared_boundary_id != computed_boundary_id
                ):
                    issues.append(ValidationIssue(STATE_CONFLICT, "DECLARED_REPORTING_BOUNDARY_ID_MISMATCH", "declared_reporting_boundary_id"))

    sources_value = raw_input.get("sources")
    normalized_sources: List[Dict[str, Any]] = []
    computational_sources: List[Dict[str, Any]] = []
    if not isinstance(sources_value, list):
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_SOURCES_TYPE", "sources"))
    else:
        if len(sources_value) > MAX_SOURCES:
            issues.append(ValidationIssue(STATE_UNSUPPORTED, "SOURCE_LIMIT_EXCEEDED", str(len(sources_value))))
        seen_sources: Set[str] = set()
        for raw_source in sources_value:
            normalized_source, computational_source, source_issues = normalize_source(raw_source, contest)
            issues.extend(source_issues)
            if normalized_source is not None and "source_id" in normalized_source:
                source_id = normalized_source["source_id"]
                if source_id in seen_sources:
                    issues.append(ValidationIssue(STATE_CONFLICT, "DUPLICATE_SOURCE", source_id))
                else:
                    seen_sources.add(source_id)
                    normalized_sources.append(normalized_source)
                    if computational_source is not None:
                        computational_sources.append(computational_source)

        if context is not None and context.get("expected_source_ids") is not None:
            expected_sources = set(context["expected_source_ids"])
            present_sources = set(seen_sources)
            for missing in sorted(expected_sources - present_sources):
                issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_SOURCE", missing))
            for extra in sorted(present_sources - expected_sources):
                issues.append(ValidationIssue(STATE_CONFLICT, "UNDECLARED_SOURCE", extra))

    normalized_sources.sort(key=lambda item: item.get("source_id", ""))
    computational_sources.sort(key=lambda item: item.get("source_id", ""))
    normalized["sources"] = normalized_sources
    computational["sources"] = computational_sources

    report_set_ids = [source.get("report_set_id") for source in computational_sources if source.get("report_set_id")]
    if context is not None and context.get("evidence_mode") == EVIDENCE_MULTI_SOURCE and report_set_ids:
        if len(set(report_set_ids)) != 1:
            issues.append(ValidationIssue(STATE_CONFLICT, "SOURCE_REPORT_SETS_DISAGREE", ",".join(sorted(set(report_set_ids)))))
        elif len(report_set_ids) == len(computational_sources) and computational_sources:
            canonical_report_sets = {canonical_json(source.get("reports")) for source in computational_sources}
            if len(canonical_report_sets) != 1:
                issues.append(ValidationIssue(STATE_CONFLICT, "SOURCE_CANONICAL_REPORTS_DISAGREE", "sources"))
    if context is not None and context.get("evidence_mode") == EVIDENCE_SINGLE_SOURCE and len(computational_sources) != 1:
        issues.append(ValidationIssue(STATE_CONFLICT, "SINGLE_SOURCE_CARDINALITY_MISMATCH", str(len(computational_sources))))

    return normalized, computational, issues


def source_manifest_material(normalized_input: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "domain": "SLANG-VOTING-SOURCE-MANIFEST-1",
        "evidence_mode": normalized_input.get("context", {}).get("evidence_mode"),
        "expected_source_ids": normalized_input.get("context", {}).get("expected_source_ids"),
        "sources": [
            {
                "source_id": source.get("source_id"),
                "source_dataset_commitment": source.get("source_dataset_commitment"),
                "declared_report_set_id": source.get("declared_report_set_id"),
                "computed_report_set_id": source.get("computed_report_set_id"),
            }
            for source in normalized_input.get("sources", [])
        ],
    }


def source_agreement_material(computational: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "domain": "SLANG-VOTING-SOURCE-AGREEMENT-1",
        "evidence_mode": computational.get("context", {}).get("evidence_mode"),
        "expected_source_ids": computational.get("context", {}).get("expected_source_ids"),
        "source_report_sets": [
            {
                "source_id": source.get("source_id"),
                "report_set_id": source.get("report_set_id"),
            }
            for source in computational.get("sources", [])
        ],
    }


def safe_aggregate_add(current: int, value: int) -> int:
    result = current + value
    if len(str(result)) > MAX_AGGREGATE_DIGITS:
        raise ValueError("aggregate digit limit exceeded")
    return result


def common_reports(computational: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    sources = computational.get("sources", [])
    if not sources:
        return None
    report_set_ids = [source.get("report_set_id") for source in sources]
    if not report_set_ids or any(value is None for value in report_set_ids) or len(set(report_set_ids)) != 1:
        return None
    report_sets = [source.get("reports") for source in sources]
    if any(reports is None for reports in report_sets):
        return None
    canonical_report_sets = {canonical_json(reports) for reports in report_sets}
    if len(canonical_report_sets) != 1:
        return None
    return report_sets[0]


def calculate_totals(
    contest: Dict[str, Any],
    reports: Sequence[Dict[str, Any]],
) -> Tuple[Optional[Dict[str, int]], Optional[Dict[str, int]], int, int, List[str]]:
    candidate_ids = contest["candidate_ids"]
    record_totals = {candidate_id: 0 for candidate_id in candidate_ids}
    resolution_totals = {candidate_id: 0 for candidate_id in candidate_ids}
    non_candidate_total = 0
    total_records = 0
    local_tie_units: List[str] = []

    for report in reports:
        for candidate_id in candidate_ids:
            record_totals[candidate_id] = safe_aggregate_add(
                record_totals[candidate_id],
                report["candidate_counts"][candidate_id],
            )
        non_candidate_total = safe_aggregate_add(non_candidate_total, report["non_candidate_count"])
        total_records = safe_aggregate_add(total_records, report["total_records"])

        if contest["aggregation_mode"] == AGGREGATION_SUM_COUNTS:
            for candidate_id in candidate_ids:
                resolution_totals[candidate_id] = safe_aggregate_add(
                    resolution_totals[candidate_id],
                    report["candidate_counts"][candidate_id],
                )
        else:
            top_count = max(report["candidate_counts"].values())
            top_candidates = sorted(
                candidate_id
                for candidate_id, count in report["candidate_counts"].items()
                if count == top_count
            )
            if len(top_candidates) != 1:
                local_tie_units.append(report["unit_id"])
            else:
                winner = top_candidates[0]
                resolution_totals[winner] = safe_aggregate_add(
                    resolution_totals[winner],
                    report["unit_weight"],
                )

    return record_totals, resolution_totals, non_candidate_total, total_records, local_tie_units


def decision_from_totals(
    decision_rule: Dict[str, Any],
    totals: Dict[str, int],
) -> Tuple[str, List[str], List[str], Dict[str, Any]]:
    ranked = sorted(totals, key=lambda candidate_id: (-totals[candidate_id], candidate_id))
    top_value = totals[ranked[0]] if ranked else 0
    leading = sorted(candidate_id for candidate_id in ranked if totals[candidate_id] == top_value)
    total_resolution = sum(totals.values())
    mode = decision_rule["mode"]
    evidence = {
        "ranked_candidate_ids": ranked,
        "top_resolution_total": decimal_string(top_value),
        "total_resolution_quantity": decimal_string(total_resolution),
    }

    if total_resolution == 0:
        return STATE_ABSTAIN, [], leading, {**evidence, "decision_reason": "ZERO_RESOLUTION_TOTAL"}

    if mode == RULE_UNIQUE_MAX:
        if len(leading) == 1:
            return STATE_RESOLVED, leading, leading, {**evidence, "decision_reason": "UNIQUE_MAXIMUM"}
        return STATE_ABSTAIN, [], leading, {**evidence, "decision_reason": "TOP_TIE"}

    if mode == RULE_ABSOLUTE_MAJORITY:
        if len(leading) == 1 and top_value * 2 > total_resolution:
            return STATE_RESOLVED, leading, leading, {**evidence, "decision_reason": "ABSOLUTE_MAJORITY"}
        return STATE_ABSTAIN, [], leading, {**evidence, "decision_reason": "NO_ABSOLUTE_MAJORITY"}

    seats = decision_rule["seats_to_fill"]
    boundary_value = totals[ranked[seats - 1]]
    selected_above = [candidate_id for candidate_id in ranked if totals[candidate_id] > boundary_value]
    tied_at_boundary = [candidate_id for candidate_id in ranked if totals[candidate_id] == boundary_value]
    slots_remaining = seats - len(selected_above)
    evidence["selection_boundary_total"] = decimal_string(boundary_value)
    evidence["boundary_tied_candidate_ids"] = sorted(tied_at_boundary)
    if len(tied_at_boundary) > slots_remaining:
        return STATE_ABSTAIN, [], leading, {**evidence, "decision_reason": "TOP_K_BOUNDARY_TIE"}
    selected = selected_above + sorted(tied_at_boundary)[:slots_remaining]
    return STATE_RESOLVED, selected, leading, {**evidence, "decision_reason": "TOP_K_UNAMBIGUOUS"}


def make_base_result() -> Dict[str, Any]:
    return {
        "schema": RESULT_SCHEMA,
        "version": VERSION,
        "core_version": CORE_VERSION,
        "canonicalization_id": CANONICALIZATION_ID,
        "identity_domain_id": identity_domain_id(),
        "profile_id": PROFILE_ID,
        "ruleset_id": RULESET_ID,
        "state": STATE_UNSUPPORTED,
        "resolution_state": STATE_UNSUPPORTED,
        "visibility_state": "NOT_RESOLVED",
        "outcome_visible": False,
        "selected_candidate_ids": None,
        "leading_candidate_ids": None,
        "candidate_record_totals": None,
        "candidate_resolution_totals": None,
        "total_non_candidate_records": None,
        "total_records": None,
        "evaluation_id": None,
        "contest_id": None,
        "aggregation_mode": None,
        "decision_rule_mode": None,
        "evidence_mode": None,
        "submission_id": None,
        "canonical_input_id": None,
        "candidate_set_id": None,
        "reporting_boundary_id": None,
        "source_manifest_id": None,
        "source_agreement_id": None,
        "report_set_id": None,
        "rule_profile_id": None,
        "outcome_id": None,
        "evaluation_evidence_id": None,
        "result_id": None,
        "reason_codes": [],
        "missing_dependencies": [],
        "conflicts": [],
        "prohibitions": [],
        "unsupported_features": [],
        "execution_authority": "NONE",
        "certification_authority": "NONE",
        "official_result_authority": "NONE",
        "evidence": {},
    }


def issue_lists(issues: Sequence[ValidationIssue]) -> Tuple[List[str], List[str], List[str], List[str]]:
    missing = unique_sorted(issue.detail for issue in issues if issue.state == STATE_INCOMPLETE)
    conflicts = unique_sorted(issue.detail for issue in issues if issue.state == STATE_CONFLICT)
    prohibitions = unique_sorted(issue.detail for issue in issues if issue.state == STATE_FORBIDDEN)
    unsupported = unique_sorted(issue.detail for issue in issues if issue.state == STATE_UNSUPPORTED)
    return missing, conflicts, prohibitions, unsupported


def resolve_voting(raw_input: Any) -> Dict[str, Any]:
    result = make_base_result()
    try:
        validate_portable_json(raw_input)
        submitted = json_clone(raw_input)
        result["submission_id"] = identity("slang_voting_submission_sha256:", submitted)
    except (TypeError, ValueError, MemoryError, RecursionError) as exc:
        result["state"] = STATE_UNSUPPORTED
        result["resolution_state"] = STATE_UNSUPPORTED
        result["reason_codes"] = ["PORTABLE_JSON_BOUNDARY_FAILURE"]
        result["unsupported_features"] = [str(exc)]
        result["result_id"] = identity(
            "slang_voting_result_sha256:",
            {
                "identity_domain_id": identity_domain_id(),
                "state": result["state"],
                "reason_codes": result["reason_codes"],
            },
        )
        return {"submitted_input": None, "normalized_projection": None, "result": result}

    normalized, computational, issues = normalize_input(submitted)
    if normalized is not None:
        result["canonical_input_id"] = identity("slang_voting_canonical_input_sha256:", normalized)
    if computational is None:
        computational = {}

    context = computational.get("context", {})
    contest = computational.get("contest", {})
    result["evaluation_id"] = context.get("evaluation_id")
    result["contest_id"] = contest.get("contest_id")
    result["aggregation_mode"] = contest.get("aggregation_mode")
    result["decision_rule_mode"] = contest.get("decision_rule", {}).get("mode")
    result["evidence_mode"] = context.get("evidence_mode")
    result["candidate_set_id"] = computational.get("candidate_set_id")
    result["reporting_boundary_id"] = computational.get("reporting_boundary_id")
    result["rule_profile_id"] = computational.get("rule_profile_id")

    if normalized is not None:
        result["source_manifest_id"] = identity(
            "slang_voting_source_manifest_sha256:",
            source_manifest_material(normalized),
        )
    if computational.get("sources") is not None:
        result["source_agreement_id"] = identity(
            "slang_voting_source_agreement_sha256:",
            source_agreement_material(computational),
        )
        report_set_ids = [source.get("report_set_id") for source in computational.get("sources", []) if source.get("report_set_id")]
        if report_set_ids and len(set(report_set_ids)) == 1:
            result["report_set_id"] = report_set_ids[0]

    if issues:
        primary = choose_primary_issue(issues)
        result["state"] = primary.state
        result["resolution_state"] = primary.state
        if primary.state == STATE_FORBIDDEN:
            result["visibility_state"] = "WITHHOLD"
        missing, conflicts, prohibitions, unsupported = issue_lists(issues)
        result["reason_codes"] = unique_sorted(issue.code for issue in issues)
        result["missing_dependencies"] = missing
        result["conflicts"] = conflicts
        result["prohibitions"] = prohibitions
        result["unsupported_features"] = unsupported
    else:
        reports = common_reports(computational)
        if reports is None:
            result["state"] = STATE_CONFLICT
            result["resolution_state"] = STATE_CONFLICT
            result["reason_codes"] = ["NO_COMMON_REPORT_SET"]
            result["conflicts"] = ["sources"]
        else:
            try:
                record_totals, resolution_totals, non_candidate_total, total_records, local_ties = calculate_totals(contest, reports)
            except ValueError as exc:
                result["state"] = STATE_UNSUPPORTED
                result["resolution_state"] = STATE_UNSUPPORTED
                result["reason_codes"] = ["AGGREGATE_RESOURCE_LIMIT_EXCEEDED"]
                result["unsupported_features"] = [str(exc)]
            else:
                result["candidate_record_totals"] = {
                    key: decimal_string(value) for key, value in sorted((record_totals or {}).items())
                }
                result["candidate_resolution_totals"] = {
                    key: decimal_string(value) for key, value in sorted((resolution_totals or {}).items())
                }
                result["total_non_candidate_records"] = decimal_string(non_candidate_total)
                result["total_records"] = decimal_string(total_records)

                if local_ties:
                    result["state"] = STATE_ABSTAIN
                    result["resolution_state"] = STATE_ABSTAIN
                    result["reason_codes"] = ["UNIT_LOCAL_TIE"]
                    result["conflicts"] = []
                    result["evidence"] = {"local_tie_unit_ids": sorted(local_ties)}
                else:
                    resolution_state, selected, leading, decision_evidence = decision_from_totals(
                        contest["decision_rule"],
                        resolution_totals or {},
                    )
                    result["resolution_state"] = resolution_state
                    result["selected_candidate_ids"] = selected if resolution_state == STATE_RESOLVED else None
                    result["leading_candidate_ids"] = leading
                    result["reason_codes"] = [decision_evidence["decision_reason"]]
                    result["evidence"] = decision_evidence

                    if resolution_state == STATE_RESOLVED:
                        if context.get("reference_visibility_authorized") is True:
                            result["state"] = STATE_RESOLVED
                            result["visibility_state"] = "VISIBLE"
                            result["outcome_visible"] = True
                        else:
                            result["state"] = STATE_FORBIDDEN
                            result["visibility_state"] = "WITHHOLD"
                            result["outcome_visible"] = False
                            result["reason_codes"] = ["REFERENCE_VISIBILITY_WITHHELD"]
                            result["prohibitions"] = ["reference_visibility_authorized"]
                    else:
                        result["state"] = resolution_state
                        result["visibility_state"] = "NOT_RESOLVED"
                        result["outcome_visible"] = False

    outcome_material = {
        "domain": "SLANG-VOTING-OUTCOME-1",
        "identity_domain_id": identity_domain_id(),
        "candidate_set_id": result.get("candidate_set_id"),
        "reporting_boundary_id": result.get("reporting_boundary_id"),
        "report_set_id": result.get("report_set_id"),
        "rule_profile_id": result.get("rule_profile_id"),
        "resolution_state": result.get("resolution_state"),
        "selected_candidate_ids": result.get("selected_candidate_ids"),
        "leading_candidate_ids": result.get("leading_candidate_ids"),
        "candidate_resolution_totals": result.get("candidate_resolution_totals"),
    }
    result["outcome_id"] = identity("slang_voting_outcome_sha256:", outcome_material)

    evidence_material = {
        "domain": "SLANG-VOTING-EVALUATION-EVIDENCE-1",
        "source_manifest_id": result.get("source_manifest_id"),
        "source_agreement_id": result.get("source_agreement_id"),
        "outcome_id": result.get("outcome_id"),
        "state": result.get("state"),
        "visibility_state": result.get("visibility_state"),
        "outcome_visible": result.get("outcome_visible"),
        "evidence": result.get("evidence"),
    }
    result["evaluation_evidence_id"] = identity(
        "slang_voting_evaluation_evidence_sha256:",
        evidence_material,
    )

    result["result_id"] = identity(
        "slang_voting_result_sha256:",
        {
            "domain": "SLANG-VOTING-RESULT-IDENTITY-1",
            "identity_domain_id": identity_domain_id(),
            "outcome_id": result.get("outcome_id"),
            "state": result.get("state"),
            "visibility_state": result.get("visibility_state"),
            "outcome_visible": result.get("outcome_visible"),
        },
    )

    return {
        "submitted_input": submitted,
        "normalized_projection": normalized,
        "result": result,
    }


def build_bundle(raw_input: Any) -> Dict[str, Any]:
    resolved = resolve_voting(raw_input)
    bundle: Dict[str, Any] = {
        "schema": BUNDLE_SCHEMA,
        "version": VERSION,
        "core_version": CORE_VERSION,
        "canonicalization_id": CANONICALIZATION_ID,
        "identity_domain_id": identity_domain_id(),
        "submitted_input": resolved["submitted_input"],
        "normalized_projection": resolved["normalized_projection"],
        "result": resolved["result"],
    }
    bundle["bundle_id"] = identity("slang_voting_bundle_sha256:", bundle)
    return bundle


def verify_bundle(bundle: Any) -> Tuple[bool, str]:
    if not isinstance(bundle, dict):
        return False, "BUNDLE_NOT_OBJECT"
    try:
        validate_portable_json(bundle)
    except (TypeError, ValueError):
        return False, "BUNDLE_PORTABLE_JSON_MISMATCH"
    if set(bundle) != BUNDLE_KEYS:
        return False, "BUNDLE_FIELDS_MISMATCH"
    if bundle.get("schema") != BUNDLE_SCHEMA:
        return False, "BUNDLE_SCHEMA_MISMATCH"
    if bundle.get("version") != VERSION:
        return False, "BUNDLE_VERSION_MISMATCH"
    if bundle.get("core_version") != CORE_VERSION:
        return False, "BUNDLE_CORE_VERSION_MISMATCH"
    if bundle.get("canonicalization_id") != CANONICALIZATION_ID:
        return False, "CANONICALIZATION_ID_MISMATCH"
    if bundle.get("identity_domain_id") != identity_domain_id():
        return False, "IDENTITY_DOMAIN_ID_MISMATCH"
    bundle_id = bundle.get("bundle_id")
    if not isinstance(bundle_id, str):
        return False, "BUNDLE_ID_MISSING"
    material = dict(bundle)
    del material["bundle_id"]
    if bundle_id != identity("slang_voting_bundle_sha256:", material):
        return False, "BUNDLE_ID_MISMATCH"
    try:
        expected = build_bundle(bundle.get("submitted_input"))
        if canonical_json(bundle) != canonical_json(expected):
            return False, "BUNDLE_RECONSTRUCTION_MISMATCH"
    except (TypeError, ValueError, MemoryError, RecursionError):
        return False, "RESOURCE_LIMIT_EXCEEDED"
    return True, "PASS"


def make_receipt(bundle: Dict[str, Any]) -> Dict[str, Any]:
    result = bundle["result"]
    receipt: Dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "version": VERSION,
        "core_version": CORE_VERSION,
        "canonicalization_id": CANONICALIZATION_ID,
        "identity_domain_id": identity_domain_id(),
        "profile_id": result["profile_id"],
        "ruleset_id": result["ruleset_id"],
        "evaluation_id": result["evaluation_id"],
        "contest_id": result["contest_id"],
        "state": result["state"],
        "resolution_state": result["resolution_state"],
        "visibility_state": result["visibility_state"],
        "outcome_visible": result["outcome_visible"],
        "selected_candidate_ids": result["selected_candidate_ids"],
        "leading_candidate_ids": result["leading_candidate_ids"],
        "aggregation_mode": result["aggregation_mode"],
        "decision_rule_mode": result["decision_rule_mode"],
        "evidence_mode": result["evidence_mode"],
        "submission_id": result["submission_id"],
        "canonical_input_id": result["canonical_input_id"],
        "candidate_set_id": result["candidate_set_id"],
        "reporting_boundary_id": result["reporting_boundary_id"],
        "source_manifest_id": result["source_manifest_id"],
        "source_agreement_id": result["source_agreement_id"],
        "report_set_id": result["report_set_id"],
        "rule_profile_id": result["rule_profile_id"],
        "outcome_id": result["outcome_id"],
        "evaluation_evidence_id": result["evaluation_evidence_id"],
        "result_id": result["result_id"],
        "reason_codes": result["reason_codes"],
        "execution_authority": result["execution_authority"],
        "certification_authority": result["certification_authority"],
        "official_result_authority": result["official_result_authority"],
        "bundle_id": bundle["bundle_id"],
    }
    receipt["receipt_id"] = identity("slang_voting_receipt_sha256:", receipt)
    return receipt


def verify_receipt(receipt: Any) -> Tuple[bool, str]:
    if not isinstance(receipt, dict):
        return False, "RECEIPT_NOT_OBJECT"
    try:
        validate_portable_json(receipt)
    except (TypeError, ValueError):
        return False, "RECEIPT_PORTABLE_JSON_MISMATCH"
    if set(receipt) != RECEIPT_KEYS:
        return False, "RECEIPT_FIELDS_MISMATCH"
    if receipt.get("schema") != RECEIPT_SCHEMA:
        return False, "RECEIPT_SCHEMA_MISMATCH"
    if receipt.get("version") != VERSION:
        return False, "RECEIPT_VERSION_MISMATCH"
    if receipt.get("core_version") != CORE_VERSION:
        return False, "RECEIPT_CORE_VERSION_MISMATCH"
    if receipt.get("canonicalization_id") != CANONICALIZATION_ID:
        return False, "CANONICALIZATION_ID_MISMATCH"
    if receipt.get("identity_domain_id") != identity_domain_id():
        return False, "IDENTITY_DOMAIN_ID_MISMATCH"
    receipt_id = receipt.get("receipt_id")
    if not isinstance(receipt_id, str):
        return False, "RECEIPT_ID_MISSING"
    material = dict(receipt)
    del material["receipt_id"]
    if receipt_id != identity("slang_voting_receipt_sha256:", material):
        return False, "RECEIPT_ID_MISMATCH"
    return True, "PASS"


def verify_receipt_against_bundle(receipt: Any, bundle: Any) -> Tuple[bool, str]:
    bundle_ok, bundle_reason = verify_bundle(bundle)
    if not bundle_ok:
        return False, "BUNDLE_" + bundle_reason
    receipt_ok, receipt_reason = verify_receipt(receipt)
    if not receipt_ok:
        return False, receipt_reason
    expected = make_receipt(bundle)
    if canonical_json(receipt) != canonical_json(expected):
        return False, "RECEIPT_BUNDLE_BINDING_MISMATCH"
    return True, "PASS"


def commitment(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def make_report_set_id_for_input(raw_input: Dict[str, Any], reports: List[Dict[str, Any]]) -> str:
    normalized_contest, contest_issues = normalize_contest(raw_input["contest"])
    if contest_issues or normalized_contest is None:
        raise ValueError("contest is not valid")
    normalized_reports: List[Dict[str, Any]] = []
    for report in reports:
        normalized_report, _, report_issues = normalize_report(
            report,
            normalized_contest["candidate_ids"],
            normalized_contest["aggregation_mode"],
        )
        if report_issues or normalized_report is None:
            raise ValueError("report is not valid")
        normalized_reports.append(normalized_report)
    normalized_reports.sort(key=lambda item: item["unit_id"])
    return report_set_identity(normalized_contest, normalized_reports)


def attach_declared_identities(raw_input: Dict[str, Any]) -> Dict[str, Any]:
    value = copy.deepcopy(raw_input)
    normalized_context, context_issues = normalize_context(value["context"])
    normalized_contest, contest_issues = normalize_contest(value["contest"])
    blocking_context = [issue for issue in context_issues if issue.code != "REPORTING_BOUNDARY_OPEN"]
    if blocking_context or contest_issues or normalized_context is None or normalized_contest is None:
        raise ValueError("reference input is not structurally valid")
    value["declared_candidate_set_id"] = identity(
        "slang_voting_candidate_set_sha256:",
        candidate_set_material(normalized_contest),
    )
    value["declared_reporting_boundary_id"] = identity(
        "slang_voting_reporting_boundary_sha256:",
        reporting_boundary_material(normalized_contest, normalized_context),
    )
    for source in value["sources"]:
        source["declared_report_set_id"] = make_report_set_id_for_input(value, source["reports"])
    return value


def build_reference_reports() -> List[Dict[str, Any]]:
    return [
        {
            "unit_id": "UNIT-001",
            "candidate_counts": {"CANDIDATE-A": "120", "CANDIDATE-B": "90", "CANDIDATE-C": "30"},
            "non_candidate_count": "5",
            "total_records": "245",
        },
        {
            "unit_id": "UNIT-002",
            "candidate_counts": {"CANDIDATE-A": "80", "CANDIDATE-B": "100", "CANDIDATE-C": "20"},
            "non_candidate_count": "4",
            "total_records": "204",
        },
        {
            "unit_id": "UNIT-003",
            "candidate_counts": {"CANDIDATE-A": "75", "CANDIDATE-B": "65", "CANDIDATE-C": "40"},
            "non_candidate_count": "3",
            "total_records": "183",
        },
        {
            "unit_id": "UNIT-004",
            "candidate_counts": {"CANDIDATE-A": "95", "CANDIDATE-B": "70", "CANDIDATE-C": "25"},
            "non_candidate_count": "2",
            "total_records": "192",
        },
    ]


def build_reference_input() -> Dict[str, Any]:
    reports = build_reference_reports()
    raw = {
        "schema": INPUT_SCHEMA,
        "profile_id": PROFILE_ID,
        "ruleset_id": RULESET_ID,
        "context": {
            "evaluation_id": "EVALUATION-001",
            "jurisdiction_id": "JURISDICTION-REFERENCE",
            "evaluation_authorized": True,
            "reporting_boundary_sealed": True,
            "reference_visibility_authorized": True,
            "evidence_mode": EVIDENCE_MULTI_SOURCE,
            "expected_source_ids": ["SOURCE-A", "SOURCE-B", "SOURCE-C"],
        },
        "contest": {
            "contest_id": "CONTEST-001",
            "candidate_ids": ["CANDIDATE-A", "CANDIDATE-B", "CANDIDATE-C"],
            "expected_unit_ids": ["UNIT-001", "UNIT-002", "UNIT-003", "UNIT-004"],
            "aggregation_mode": AGGREGATION_SUM_COUNTS,
            "decision_rule": {"mode": RULE_UNIQUE_MAX},
        },
        "sources": [
            {
                "source_id": source_id,
                "source_dataset_commitment": commitment("SLANG-VOTING-REFERENCE-" + source_id),
                "declared_report_set_id": REPORT_SET_PREFIX + ("0" * 64),
                "reports": copy.deepcopy(reports),
            }
            for source_id in ("SOURCE-A", "SOURCE-B", "SOURCE-C")
        ],
    }
    return attach_declared_identities(raw)


def build_single_source_input() -> Dict[str, Any]:
    value = build_reference_input()
    value["context"]["evidence_mode"] = EVIDENCE_SINGLE_SOURCE
    value["context"]["expected_source_ids"] = ["SOURCE-A"]
    value["sources"] = [value["sources"][0]]
    return attach_declared_identities(value)


def build_absolute_majority_input() -> Dict[str, Any]:
    value = build_single_source_input()
    value["contest"]["decision_rule"] = {"mode": RULE_ABSOLUTE_MAJORITY}
    return attach_declared_identities(value)


def build_top_k_input() -> Dict[str, Any]:
    value = build_single_source_input()
    value["contest"]["decision_rule"] = {"mode": RULE_TOP_K, "seats_to_fill": 2}
    return attach_declared_identities(value)


def build_unit_weight_input() -> Dict[str, Any]:
    value = build_single_source_input()
    value["contest"]["aggregation_mode"] = AGGREGATION_UNIT_WINNER_WEIGHT
    weights = {"UNIT-001": "5", "UNIT-002": "7", "UNIT-003": "3", "UNIT-004": "4"}
    for report in value["sources"][0]["reports"]:
        report["unit_weight"] = weights[report["unit_id"]]
    return attach_declared_identities(value)


def strict_object_pairs(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError("duplicate JSON object key: " + key)
        result[key] = value
    return result


def reject_nonfinite_constant(value: str) -> None:
    raise PortableJSONError("non-finite JSON number: " + value)


def reject_float_number(value: str) -> None:
    raise PortableJSONError("floating-point JSON number is not supported: " + value)


def parse_safe_integer(value: str) -> int:
    parsed = int(value, 10)
    if parsed < -MAX_SAFE_INTEGER or parsed > MAX_SAFE_INTEGER:
        raise PortableJSONError("JSON integer outside portable range: " + value)
    return parsed


def loads_strict(text: str) -> Any:
    if not isinstance(text, str):
        raise PortableJSONError("JSON input must be text")
    try:
        encoded = text.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise PortableJSONError("JSON input contains invalid Unicode") from exc
    if len(encoded) > MAX_JSON_INPUT_BYTES:
        raise PortableJSONError("JSON input exceeds byte limit")
    try:
        value = json.loads(
            text,
            object_pairs_hook=strict_object_pairs,
            parse_constant=reject_nonfinite_constant,
            parse_float=reject_float_number,
            parse_int=parse_safe_integer,
        )
    except DuplicateKeyError:
        raise
    except PortableJSONError:
        raise
    except json.JSONDecodeError as exc:
        raise PortableJSONError(
            "invalid JSON at line " + str(exc.lineno) + ", column " + str(exc.colno)
        ) from exc
    except RecursionError as exc:
        raise PortableJSONError("JSON nesting exceeds parser limit") from exc
    validate_portable_json(value)
    return value


def load_json(path: Path) -> Any:
    if path.stat().st_size > MAX_JSON_INPUT_BYTES:
        raise PortableJSONError("JSON input exceeds byte limit")
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise PortableJSONError("JSON input is not valid UTF-8") from exc
    return loads_strict(text)


def json_file_bytes(value: Any) -> bytes:
    """Serialize one JSON artifact as UTF-8 with exactly one terminal LF.

    The byte contract is independent of the host operating system. It is used
    for generated vectors, bundles, and receipts.
    """
    text = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
    return (text.rstrip("\r\n") + "\n").encode("utf-8")


def write_json(path: Path, value: Any) -> None:
    path.write_bytes(json_file_bytes(value))


def mutate(source: Dict[str, Any], fn) -> Dict[str, Any]:
    value = copy.deepcopy(source)
    fn(value)
    return value


def run_self_test() -> int:
    groups: Dict[str, List[Tuple[str, bool]]] = {}

    def check(group: str, name: str, condition: bool) -> None:
        groups.setdefault(group, []).append((name, bool(condition)))

    base = build_reference_input()
    bundle = build_bundle(base)
    result = bundle["result"]
    receipt = make_receipt(bundle)

    check("REFERENCE", "reference resolves", result["state"] == STATE_RESOLVED)
    check("REFERENCE", "resolution state resolves", result["resolution_state"] == STATE_RESOLVED)
    check("REFERENCE", "outcome visible", result["outcome_visible"] is True)
    check("REFERENCE", "candidate A selected", result["selected_candidate_ids"] == ["CANDIDATE-A"])
    check("REFERENCE", "candidate A total", result["candidate_record_totals"].get("CANDIDATE-A") == "370")
    check("REFERENCE", "candidate B total", result["candidate_record_totals"].get("CANDIDATE-B") == "325")
    check("REFERENCE", "candidate C total", result["candidate_record_totals"].get("CANDIDATE-C") == "115")
    check("REFERENCE", "non-candidate total", result["total_non_candidate_records"] == "14")
    check("REFERENCE", "record total", result["total_records"] == "824")
    check("REFERENCE", "three source agreement", result["evidence_mode"] == EVIDENCE_MULTI_SOURCE)
    check("REFERENCE", "report set identity present", isinstance(result["report_set_id"], str))
    check("REFERENCE", "source manifest identity present", isinstance(result["source_manifest_id"], str))
    check("REFERENCE", "source agreement identity present", isinstance(result["source_agreement_id"], str))
    check("REFERENCE", "outcome identity present", isinstance(result["outcome_id"], str))
    check("REFERENCE", "evidence identity present", isinstance(result["evaluation_evidence_id"], str))
    check("REFERENCE", "execution authority none", result["execution_authority"] == "NONE")
    check("REFERENCE", "certification authority none", result["certification_authority"] == "NONE")
    check("REFERENCE", "official result authority none", result["official_result_authority"] == "NONE")

    reordered = copy.deepcopy(base)
    reordered["contest"]["candidate_ids"].reverse()
    reordered["contest"]["expected_unit_ids"].reverse()
    reordered["context"]["expected_source_ids"].reverse()
    reordered["sources"].reverse()
    for source in reordered["sources"]:
        source["reports"].reverse()
        for report in source["reports"]:
            report["candidate_counts"] = dict(reversed(list(report["candidate_counts"].items())))
    reordered_result = build_bundle(reordered)["result"]
    check("DETERMINISM", "reordered canonical input stable", result["canonical_input_id"] == reordered_result["canonical_input_id"])
    check("DETERMINISM", "reordered report set stable", result["report_set_id"] == reordered_result["report_set_id"])
    check("DETERMINISM", "reordered source agreement stable", result["source_agreement_id"] == reordered_result["source_agreement_id"])
    check("DETERMINISM", "reordered outcome stable", result["outcome_id"] == reordered_result["outcome_id"])
    check("DETERMINISM", "reordered result stable", result["result_id"] == reordered_result["result_id"])
    check("DETERMINISM", "submission identity records presentation", result["submission_id"] != reordered_result["submission_id"])
    repeat_result = build_bundle(base)["result"]
    check("DETERMINISM", "repeat canonical input stable", result["canonical_input_id"] == repeat_result["canonical_input_id"])
    check("DETERMINISM", "repeat outcome stable", result["outcome_id"] == repeat_result["outcome_id"])
    check("DETERMINISM", "repeat result stable", result["result_id"] == repeat_result["result_id"])

    withheld = copy.deepcopy(base)
    withheld["context"]["reference_visibility_authorized"] = False
    withheld_result = build_bundle(withheld)["result"]
    check("VISIBILITY", "withheld top state forbidden", withheld_result["state"] == STATE_FORBIDDEN)
    check("VISIBILITY", "withheld resolution remains resolved", withheld_result["resolution_state"] == STATE_RESOLVED)
    check("VISIBILITY", "withheld outcome hidden", withheld_result["outcome_visible"] is False)
    check("VISIBILITY", "withheld visibility state", withheld_result["visibility_state"] == "WITHHOLD")
    check("VISIBILITY", "withheld outcome identity stable", withheld_result["outcome_id"] == result["outcome_id"])
    check("VISIBILITY", "withheld result identity changes", withheld_result["result_id"] != result["result_id"])
    check("VISIBILITY", "withheld selected candidates retained", withheld_result["selected_candidate_ids"] == ["CANDIDATE-A"])
    check("VISIBILITY", "withheld totals retained", withheld_result["candidate_resolution_totals"] == result["candidate_resolution_totals"])
    check("VISIBILITY", "withheld reason exact", withheld_result["reason_codes"] == ["REFERENCE_VISIBILITY_WITHHELD"])

    unauthorized = copy.deepcopy(base)
    unauthorized["context"]["evaluation_authorized"] = False
    unauthorized_result = build_bundle(unauthorized)["result"]
    check("VISIBILITY", "evaluation forbidden", unauthorized_result["state"] == STATE_FORBIDDEN)
    check("VISIBILITY", "evaluation reason", "EVALUATION_NOT_AUTHORIZED" in unauthorized_result["reason_codes"])

    forbidden_incomplete = copy.deepcopy(base)
    forbidden_incomplete["context"]["evaluation_authorized"] = False
    for source in forbidden_incomplete["sources"]:
        source["reports"] = source["reports"][:-1]
    forbidden_incomplete_result = build_bundle(forbidden_incomplete)["result"]
    check("PRECEDENCE", "forbidden outranks incomplete", forbidden_incomplete_result["state"] == STATE_FORBIDDEN)
    check("PRECEDENCE", "forbidden and incomplete reasons retained", {"EVALUATION_NOT_AUTHORIZED", "MISSING_REPORTING_UNIT"}.issubset(set(forbidden_incomplete_result["reason_codes"])))
    check("PRECEDENCE", "forbidden reasons sorted", forbidden_incomplete_result["reason_codes"] == sorted(set(forbidden_incomplete_result["reason_codes"])))
    check("PRECEDENCE", "forbidden lower category retained", any("UNIT-004" in item for item in forbidden_incomplete_result["missing_dependencies"]))

    conflict_unsupported = copy.deepcopy(base)
    conflict_unsupported["contest"]["candidate_ids"].append("candidate-a")
    conflict_unsupported["contest"]["aggregation_mode"] = "RANKED_CHOICE"
    conflict_unsupported_result = build_bundle(conflict_unsupported)["result"]
    check("PRECEDENCE", "conflict outranks unsupported", conflict_unsupported_result["state"] == STATE_CONFLICT)
    check("PRECEDENCE", "conflict and unsupported reasons retained", {"DUPLICATE_CANDIDATE_ID", "UNSUPPORTED_AGGREGATION_MODE"}.issubset(set(conflict_unsupported_result["reason_codes"])))

    unsupported_incomplete = copy.deepcopy(base)
    unsupported_incomplete["sources"][0]["source_dataset_commitment"] = "abc"
    unsupported_incomplete["sources"] = unsupported_incomplete["sources"][:-1]
    unsupported_incomplete_result = build_bundle(unsupported_incomplete)["result"]
    check("PRECEDENCE", "unsupported outranks incomplete", unsupported_incomplete_result["state"] == STATE_UNSUPPORTED)
    check("PRECEDENCE", "unsupported and incomplete reasons retained", {"INVALID_SOURCE_DATASET_COMMITMENT", "MISSING_SOURCE"}.issubset(set(unsupported_incomplete_result["reason_codes"])))

    open_boundary = copy.deepcopy(base)
    open_boundary["context"]["reporting_boundary_sealed"] = False
    open_boundary = attach_declared_identities(open_boundary)
    open_result = build_bundle(open_boundary)["result"]
    check("STATES", "open boundary incomplete", open_result["state"] == STATE_INCOMPLETE)
    check("STATES", "open boundary reason", "REPORTING_BOUNDARY_OPEN" in open_result["reason_codes"])

    missing_unit = copy.deepcopy(base)
    for source in missing_unit["sources"]:
        source["reports"] = source["reports"][:-1]
        source["declared_report_set_id"] = make_report_set_id_for_input(missing_unit, source["reports"])
    missing_result = build_bundle(missing_unit)["result"]
    check("STATES", "missing unit incomplete", missing_result["state"] == STATE_INCOMPLETE)
    check("STATES", "missing unit reason", "MISSING_REPORTING_UNIT" in missing_result["reason_codes"])

    tie = build_single_source_input()
    tie["sources"][0]["reports"][0]["candidate_counts"] = {
        "CANDIDATE-A": "100", "CANDIDATE-B": "100", "CANDIDATE-C": "40"
    }
    tie["sources"][0]["reports"][0]["total_records"] = "245"
    tie["sources"][0]["reports"][1]["candidate_counts"] = {
        "CANDIDATE-A": "90", "CANDIDATE-B": "90", "CANDIDATE-C": "20"
    }
    tie["sources"][0]["reports"][1]["total_records"] = "204"
    tie["sources"][0]["reports"][2]["candidate_counts"] = {
        "CANDIDATE-A": "80", "CANDIDATE-B": "80", "CANDIDATE-C": "20"
    }
    tie["sources"][0]["reports"][2]["total_records"] = "183"
    tie["sources"][0]["reports"][3]["candidate_counts"] = {
        "CANDIDATE-A": "90", "CANDIDATE-B": "90", "CANDIDATE-C": "10"
    }
    tie["sources"][0]["reports"][3]["total_records"] = "192"
    tie = attach_declared_identities(tie)
    tie_result = build_bundle(tie)["result"]
    check("STATES", "tie abstains", tie_result["state"] == STATE_ABSTAIN)
    check("STATES", "tie reason", tie_result["reason_codes"] == ["TOP_TIE"])
    check("STATES", "tie does not select", tie_result["selected_candidate_ids"] is None)
    check("STATES", "tie leading set complete", tie_result["leading_candidate_ids"] == ["CANDIDATE-A", "CANDIDATE-B"])

    visible_summary = public_summary(bundle)
    withheld_bundle = build_bundle(withheld)
    withheld_summary = public_summary(withheld_bundle)
    tie_bundle = build_bundle(tie)
    tie_summary = public_summary(tie_bundle)
    open_bundle = build_bundle(open_boundary)
    open_summary = public_summary(open_bundle)

    check("PRESENTATION", "summary schema", visible_summary["summary_schema"] == PUBLIC_SUMMARY_SCHEMA)
    check("PRESENTATION", "visible summary not redacted", visible_summary["outcome_fields_redacted"] is False)
    check("PRESENTATION", "visible summary selected candidates", visible_summary["selected_candidate_ids"] == ["CANDIDATE-A"])
    check("PRESENTATION", "visible summary leading candidates", visible_summary["leading_candidate_ids"] == ["CANDIDATE-A"])
    check("PRESENTATION", "visible summary totals", visible_summary["candidate_resolution_totals"] == result["candidate_resolution_totals"])
    check("PRESENTATION", "withheld summary redacted", withheld_summary["outcome_fields_redacted"] is True)
    check("PRESENTATION", "withheld summary selected hidden", withheld_summary["selected_candidate_ids"] is None)
    check("PRESENTATION", "withheld summary leaders hidden", withheld_summary["leading_candidate_ids"] is None)
    check("PRESENTATION", "withheld summary totals hidden", withheld_summary["candidate_resolution_totals"] is None)
    check("PRESENTATION", "withheld full result selected retained", withheld_result["selected_candidate_ids"] == ["CANDIDATE-A"])
    check("PRESENTATION", "withheld full result totals retained", withheld_result["candidate_resolution_totals"] == result["candidate_resolution_totals"])
    check("PRESENTATION", "tie summary redacted", tie_summary["outcome_fields_redacted"] is True)
    check("PRESENTATION", "tie summary leaders hidden", tie_summary["leading_candidate_ids"] is None)
    check("PRESENTATION", "tie summary totals hidden", tie_summary["candidate_resolution_totals"] is None)
    check("PRESENTATION", "incomplete summary redacted", open_summary["outcome_fields_redacted"] is True)
    check("PRESENTATION", "summary preserves result id", withheld_summary["result_id"] == withheld_result["result_id"])
    check("PRESENTATION", "summary preserves bundle id", withheld_summary["bundle_id"] == withheld_bundle["bundle_id"])
    check("CLI", "visible result strict exit zero", required_visible_result_exit_code(visible_summary) == 0)
    check("CLI", "withheld result strict exit three", required_visible_result_exit_code(withheld_summary) == 3)

    zero = build_single_source_input()
    for report in zero["sources"][0]["reports"]:
        report["candidate_counts"] = {candidate: "0" for candidate in zero["contest"]["candidate_ids"]}
        report["total_records"] = report["non_candidate_count"]
    zero = attach_declared_identities(zero)
    zero_result = build_bundle(zero)["result"]
    check("STATES", "zero total abstains", zero_result["state"] == STATE_ABSTAIN)
    check("STATES", "zero total reason", zero_result["reason_codes"] == ["ZERO_RESOLUTION_TOTAL"])

    majority = build_absolute_majority_input()
    majority_result = build_bundle(majority)["result"]
    check("DECISION_RULES", "reference lacks absolute majority", majority_result["state"] == STATE_ABSTAIN)
    check("DECISION_RULES", "majority reason", majority_result["reason_codes"] == ["NO_ABSOLUTE_MAJORITY"])
    majority_yes = copy.deepcopy(majority)
    for report in majority_yes["sources"][0]["reports"]:
        report["candidate_counts"]["CANDIDATE-A"] = str(int(report["candidate_counts"]["CANDIDATE-A"]) + 200)
        report["total_records"] = str(sum(int(v) for v in report["candidate_counts"].values()) + int(report["non_candidate_count"]))
    majority_yes = attach_declared_identities(majority_yes)
    majority_yes_result = build_bundle(majority_yes)["result"]
    check("DECISION_RULES", "absolute majority resolves", majority_yes_result["state"] == STATE_RESOLVED)
    check("DECISION_RULES", "absolute majority selects A", majority_yes_result["selected_candidate_ids"] == ["CANDIDATE-A"])

    top_k = build_top_k_input()
    top_k_result = build_bundle(top_k)["result"]
    check("DECISION_RULES", "top k resolves", top_k_result["state"] == STATE_RESOLVED)
    check("DECISION_RULES", "top k selects A and B", top_k_result["selected_candidate_ids"] == ["CANDIDATE-A", "CANDIDATE-B"])
    top_k_tie = copy.deepcopy(top_k)
    for report in top_k_tie["sources"][0]["reports"]:
        report["candidate_counts"]["CANDIDATE-C"] = report["candidate_counts"]["CANDIDATE-B"]
        report["total_records"] = str(sum(int(v) for v in report["candidate_counts"].values()) + int(report["non_candidate_count"]))
    top_k_tie = attach_declared_identities(top_k_tie)
    top_k_tie_result = build_bundle(top_k_tie)["result"]
    check("DECISION_RULES", "top k boundary tie abstains", top_k_tie_result["state"] == STATE_ABSTAIN)
    check("DECISION_RULES", "top k boundary reason", top_k_tie_result["reason_codes"] == ["TOP_K_BOUNDARY_TIE"])

    weighted = build_unit_weight_input()
    weighted_result = build_bundle(weighted)["result"]
    check("AGGREGATION", "weighted mode resolves", weighted_result["state"] == STATE_RESOLVED)
    check("AGGREGATION", "weighted selects A", weighted_result["selected_candidate_ids"] == ["CANDIDATE-A"])
    check("AGGREGATION", "weighted A total", weighted_result["candidate_resolution_totals"]["CANDIDATE-A"] == "12")
    check("AGGREGATION", "weighted B total", weighted_result["candidate_resolution_totals"]["CANDIDATE-B"] == "7")
    weighted_tie = copy.deepcopy(weighted)
    weighted_tie["sources"][0]["reports"][0]["candidate_counts"]["CANDIDATE-A"] = "100"
    weighted_tie["sources"][0]["reports"][0]["candidate_counts"]["CANDIDATE-B"] = "100"
    weighted_tie["sources"][0]["reports"][0]["candidate_counts"]["CANDIDATE-C"] = "40"
    weighted_tie["sources"][0]["reports"][0]["total_records"] = "245"
    weighted_tie = attach_declared_identities(weighted_tie)
    weighted_tie_result = build_bundle(weighted_tie)["result"]
    check("AGGREGATION", "local weighted tie abstains", weighted_tie_result["state"] == STATE_ABSTAIN)
    check("AGGREGATION", "local weighted tie reason", weighted_tie_result["reason_codes"] == ["UNIT_LOCAL_TIE"])
    check("AGGREGATION", "local tie voids whole selection", weighted_tie_result["selected_candidate_ids"] is None)
    check("AGGREGATION", "local tie unit recorded", weighted_tie_result["evidence"].get("local_tie_unit_ids") == ["UNIT-001"])

    source_disagree = copy.deepcopy(base)
    source_disagree["sources"][1]["reports"][0]["candidate_counts"]["CANDIDATE-B"] = "91"
    source_disagree["sources"][1]["reports"][0]["total_records"] = "246"
    source_disagree["sources"][1]["declared_report_set_id"] = make_report_set_id_for_input(source_disagree, source_disagree["sources"][1]["reports"])
    disagree_result = build_bundle(source_disagree)["result"]
    check("SOURCE_AGREEMENT", "source disagreement conflicts", disagree_result["state"] == STATE_CONFLICT)
    check("SOURCE_AGREEMENT", "source disagreement reason", "SOURCE_REPORT_SETS_DISAGREE" in disagree_result["reason_codes"])

    synthetic_common = {
        "sources": [
            {"report_set_id": "same", "reports": [{"unit_id": "U1", "candidate_counts": {"A": 1}}]},
            {"report_set_id": "same", "reports": [{"unit_id": "U1", "candidate_counts": {"A": 2}}]},
        ]
    }
    check("SOURCE_AGREEMENT", "digest equality alone does not establish common reports", common_reports(synthetic_common) is None)

    missing_source = copy.deepcopy(base)
    missing_source["sources"] = missing_source["sources"][:-1]
    missing_source_result = build_bundle(missing_source)["result"]
    check("SOURCE_AGREEMENT", "missing source incomplete", missing_source_result["state"] == STATE_INCOMPLETE)
    check("SOURCE_AGREEMENT", "missing source reason", "MISSING_SOURCE" in missing_source_result["reason_codes"])

    extra_source = copy.deepcopy(base)
    extra = copy.deepcopy(extra_source["sources"][0])
    extra["source_id"] = "SOURCE-D"
    extra["source_dataset_commitment"] = commitment("SOURCE-D")
    extra_source["sources"].append(extra)
    extra_source_result = build_bundle(extra_source)["result"]
    check("SOURCE_AGREEMENT", "extra source conflicts", extra_source_result["state"] == STATE_CONFLICT)
    check("SOURCE_AGREEMENT", "extra source reason", "UNDECLARED_SOURCE" in extra_source_result["reason_codes"])

    duplicate_source = copy.deepcopy(base)
    duplicate_source["sources"].append(copy.deepcopy(duplicate_source["sources"][0]))
    duplicate_source_result = build_bundle(duplicate_source)["result"]
    check("SOURCE_AGREEMENT", "duplicate source conflicts", duplicate_source_result["state"] == STATE_CONFLICT)
    check("SOURCE_AGREEMENT", "duplicate source reason", "DUPLICATE_SOURCE" in duplicate_source_result["reason_codes"])

    mismatch_declared = copy.deepcopy(base)
    mismatch_declared["sources"][0]["declared_report_set_id"] = REPORT_SET_PREFIX + ("f" * 64)
    mismatch_result = build_bundle(mismatch_declared)["result"]
    check("SOURCE_AGREEMENT", "declared report mismatch conflicts", mismatch_result["state"] == STATE_CONFLICT)
    check("SOURCE_AGREEMENT", "declared report mismatch reason", "DECLARED_REPORT_SET_ID_MISMATCH" in mismatch_result["reason_codes"])

    uppercase_report_id = copy.deepcopy(base)
    report_prefix = REPORT_SET_PREFIX
    uppercase_report_id["sources"][0]["declared_report_set_id"] = report_prefix + uppercase_report_id["sources"][0]["declared_report_set_id"][len(report_prefix):].upper()
    uppercase_report_result = build_bundle(uppercase_report_id)["result"]
    check("IDENTITY_SYNTAX", "uppercase declared report id unsupported", uppercase_report_result["state"] == STATE_UNSUPPORTED)
    check("IDENTITY_SYNTAX", "uppercase declared report id reason", "INVALID_DECLARED_REPORT_SET_ID" in uppercase_report_result["reason_codes"])
    check("IDENTITY_SYNTAX", "uppercase declared report id not conflict", "DECLARED_REPORT_SET_ID_MISMATCH" not in uppercase_report_result["reason_codes"])

    candidate_prefix = "slang_voting_candidate_set_sha256:"
    uppercase_candidate_id = copy.deepcopy(base)
    uppercase_candidate_id["declared_candidate_set_id"] = candidate_prefix + uppercase_candidate_id["declared_candidate_set_id"][len(candidate_prefix):].upper()
    uppercase_candidate_result = build_bundle(uppercase_candidate_id)["result"]
    check("IDENTITY_SYNTAX", "uppercase declared candidate id unsupported", uppercase_candidate_result["state"] == STATE_UNSUPPORTED)
    check("IDENTITY_SYNTAX", "uppercase declared candidate id reason", "INVALID_DECLARED_CANDIDATE_SET_ID" in uppercase_candidate_result["reason_codes"])

    boundary_prefix = "slang_voting_reporting_boundary_sha256:"
    uppercase_boundary_id = copy.deepcopy(base)
    uppercase_boundary_id["declared_reporting_boundary_id"] = boundary_prefix + uppercase_boundary_id["declared_reporting_boundary_id"][len(boundary_prefix):].upper()
    uppercase_boundary_result = build_bundle(uppercase_boundary_id)["result"]
    check("IDENTITY_SYNTAX", "uppercase declared boundary id unsupported", uppercase_boundary_result["state"] == STATE_UNSUPPORTED)
    check("IDENTITY_SYNTAX", "uppercase declared boundary id reason", "INVALID_DECLARED_REPORTING_BOUNDARY_ID" in uppercase_boundary_result["reason_codes"])

    uppercase_commitment = copy.deepcopy(base)
    uppercase_commitment["sources"][0]["source_dataset_commitment"] = uppercase_commitment["sources"][0]["source_dataset_commitment"].upper()
    uppercase_commitment_output = resolve_voting(uppercase_commitment)
    uppercase_commitment_result = uppercase_commitment_output["result"]
    check("IDENTITY_SYNTAX", "uppercase source commitment admitted", uppercase_commitment_result["state"] == STATE_RESOLVED)
    check("IDENTITY_SYNTAX", "uppercase source commitment canonicalized", uppercase_commitment_result["canonical_input_id"] == result["canonical_input_id"])
    check("IDENTITY_SYNTAX", "uppercase source commitment changes submission", uppercase_commitment_result["submission_id"] != result["submission_id"])

    invalid_binding = copy.deepcopy(base)
    invalid_binding["sources"][0]["source_dataset_commitment"] = "abc"
    invalid_binding["sources"][0]["declared_report_set_id"] = "abc"
    invalid_binding_output = resolve_voting(invalid_binding)
    first_normalized_source = invalid_binding_output["normalized_projection"]["sources"][0]
    check("REPORT_SET_ID", "report set computed despite binding syntax issues", isinstance(first_normalized_source.get("computed_report_set_id"), str))

    blocking_report = copy.deepcopy(base)
    blocking_report["sources"][0]["reports"][0]["total_records"] = "999"
    blocking_output = resolve_voting(blocking_report)
    blocking_source = blocking_output["normalized_projection"]["sources"][0]
    check("REPORT_SET_ID", "report set omitted after report-affecting issue", "computed_report_set_id" not in blocking_source)

    def state_of(value: Any) -> str:
        return build_bundle(value)["result"]["state"]

    validation_cases = [
        ("derived field injection", mutate(base, lambda v: v.__setitem__("winner", "CANDIDATE-A")), STATE_FORBIDDEN, "DERIVED_FIELD_INJECTION"),
        ("unknown top field", mutate(base, lambda v: v.__setitem__("unknown", True)), STATE_UNSUPPORTED, "UNSUPPORTED_TOP_LEVEL_FIELD"),
        ("unsupported schema", mutate(base, lambda v: v.__setitem__("schema", "OTHER")), STATE_UNSUPPORTED, "UNSUPPORTED_INPUT_SCHEMA"),
        ("unsupported profile", mutate(base, lambda v: v.__setitem__("profile_id", "OTHER")), STATE_UNSUPPORTED, "UNSUPPORTED_PROFILE_ID"),
        ("unsupported ruleset", mutate(base, lambda v: v.__setitem__("ruleset_id", "OTHER")), STATE_UNSUPPORTED, "UNSUPPORTED_RULESET_ID"),
        ("candidate duplicate", mutate(base, lambda v: v["contest"]["candidate_ids"].append("candidate-a")), STATE_CONFLICT, "DUPLICATE_CANDIDATE_ID"),
        ("unit duplicate", mutate(base, lambda v: v["contest"]["expected_unit_ids"].append("unit-001")), STATE_CONFLICT, "DUPLICATE_REPORTING_UNIT_ID"),
        ("source duplicate expected", mutate(base, lambda v: v["context"]["expected_source_ids"].append("source-a")), STATE_CONFLICT, "DUPLICATE_EXPECTED_SOURCE_ID"),
        ("unsupported aggregation", mutate(base, lambda v: v["contest"].__setitem__("aggregation_mode", "RANKED_CHOICE")), STATE_UNSUPPORTED, "UNSUPPORTED_AGGREGATION_MODE"),
        ("unsupported decision", mutate(base, lambda v: v["contest"].__setitem__("decision_rule", {"mode": "RANKED_CHOICE"})), STATE_UNSUPPORTED, "UNSUPPORTED_DECISION_RULE_MODE"),
        ("boolean count", mutate(base, lambda v: v["sources"][0]["reports"][0]["candidate_counts"].__setitem__("CANDIDATE-A", True)), STATE_UNSUPPORTED, "INVALID_CANDIDATE_COUNT_DECIMAL"),
        ("integer count", mutate(base, lambda v: v["sources"][0]["reports"][0]["candidate_counts"].__setitem__("CANDIDATE-A", 120)), STATE_UNSUPPORTED, "INVALID_CANDIDATE_COUNT_DECIMAL"),
        ("negative count", mutate(base, lambda v: v["sources"][0]["reports"][0]["candidate_counts"].__setitem__("CANDIDATE-A", "-1")), STATE_UNSUPPORTED, "INVALID_CANDIDATE_COUNT_DECIMAL"),
        ("leading zero count", mutate(base, lambda v: v["sources"][0]["reports"][0]["candidate_counts"].__setitem__("CANDIDATE-A", "0120")), STATE_UNSUPPORTED, "INVALID_CANDIDATE_COUNT_DECIMAL"),
        ("count digit limit", mutate(base, lambda v: v["sources"][0]["reports"][0]["candidate_counts"].__setitem__("CANDIDATE-A", "1" * (MAX_COUNT_DIGITS + 1))), STATE_UNSUPPORTED, "CANDIDATE_COUNT_DIGIT_LIMIT_EXCEEDED"),
        ("missing candidate count", mutate(base, lambda v: v["sources"][0]["reports"][0]["candidate_counts"].pop("CANDIDATE-C")), STATE_INCOMPLETE, "MISSING_CANDIDATE_COUNT"),
        ("unknown candidate count", mutate(base, lambda v: v["sources"][0]["reports"][0]["candidate_counts"].__setitem__("CANDIDATE-X", "1")), STATE_CONFLICT, "UNDECLARED_CANDIDATE_COUNT"),
        ("report total mismatch", mutate(base, lambda v: v["sources"][0]["reports"][0].__setitem__("total_records", "999")), STATE_CONFLICT, "REPORT_TOTAL_MISMATCH"),
        ("invalid source commitment", mutate(base, lambda v: v["sources"][0].__setitem__("source_dataset_commitment", "abc")), STATE_UNSUPPORTED, "INVALID_SOURCE_DATASET_COMMITMENT"),
        ("invalid declared report id", mutate(base, lambda v: v["sources"][0].__setitem__("declared_report_set_id", "abc")), STATE_UNSUPPORTED, "INVALID_DECLARED_REPORT_SET_ID"),
        ("declared candidate mismatch", mutate(base, lambda v: v.__setitem__("declared_candidate_set_id", "slang_voting_candidate_set_sha256:" + ("f" * 64))), STATE_CONFLICT, "DECLARED_CANDIDATE_SET_ID_MISMATCH"),
        ("declared boundary mismatch", mutate(base, lambda v: v.__setitem__("declared_reporting_boundary_id", "slang_voting_reporting_boundary_sha256:" + ("f" * 64))), STATE_CONFLICT, "DECLARED_REPORTING_BOUNDARY_ID_MISMATCH"),
        ("duplicate unit report", mutate(base, lambda v: v["sources"][0]["reports"].append(copy.deepcopy(v["sources"][0]["reports"][0]))), STATE_CONFLICT, "DUPLICATE_UNIT_REPORT"),
        ("extra unit report", mutate(base, lambda v: v["sources"][0]["reports"].append({"unit_id": "UNIT-X", "candidate_counts": {"CANDIDATE-A": "1", "CANDIDATE-B": "0", "CANDIDATE-C": "0"}, "non_candidate_count": "0", "total_records": "1"})), STATE_CONFLICT, "UNDECLARED_REPORTING_UNIT"),
        ("unsupported report field", mutate(base, lambda v: v["sources"][0]["reports"][0].__setitem__("winner", "CANDIDATE-A")), STATE_UNSUPPORTED, "UNSUPPORTED_REPORT_FIELD"),
        ("unit weight in sum mode", mutate(base, lambda v: v["sources"][0]["reports"][0].__setitem__("unit_weight", "5")), STATE_UNSUPPORTED, "UNSUPPORTED_REPORT_FIELD"),
        ("top k missing seats", mutate(base, lambda v: v["contest"].__setitem__("decision_rule", {"mode": RULE_TOP_K})), STATE_INCOMPLETE, "MISSING_SEATS_TO_FILL"),
        ("top k boolean seats", mutate(base, lambda v: v["contest"].__setitem__("decision_rule", {"mode": RULE_TOP_K, "seats_to_fill": True})), STATE_UNSUPPORTED, "INVALID_SEATS_TO_FILL"),
        ("seats on unique max", mutate(base, lambda v: v["contest"].__setitem__("decision_rule", {"mode": RULE_UNIQUE_MAX, "seats_to_fill": 1})), STATE_UNSUPPORTED, "SEATS_TO_FILL_NOT_APPLICABLE"),
    ]
    for name, value, expected_state, expected_code in validation_cases:
        actual = build_bundle(value)["result"]
        check("VALIDATION", name + " state", actual["state"] == expected_state)
        check("VALIDATION", name + " code", expected_code in actual["reason_codes"])

    check("RESOURCE", "reachable aggregate digits computed", MAX_REACHABLE_AGGREGATE_DIGITS == 34)
    check("RESOURCE", "reachable aggregate remains below guard", MAX_REACHABLE_AGGREGATE_DIGITS < MAX_AGGREGATE_DIGITS)
    check("RESOURCE", "maximum admitted aggregate accepted", len(str(MAX_REACHABLE_AGGREGATE)) <= MAX_AGGREGATE_DIGITS)

    check("PARSER", "duplicate keys rejected", _strict_load_fails('{"schema":"A","schema":"B"}'))
    check("PARSER", "float rejected", _strict_load_fails('{"value":1.5}'))
    check("PARSER", "NaN rejected", _strict_load_fails('{"value":NaN}'))
    check("PARSER", "Infinity rejected", _strict_load_fails('{"value":Infinity}'))
    check("PARSER", "oversized integer rejected", _strict_load_fails('{"value":9007199254740992}'))
    check("PARSER", "lone surrogate rejected", _strict_load_fails('"\\ud800"'))
    check("PARSER", "portable integer accepted", not _strict_load_fails('{"value":9007199254740991}'))
    check("PARSER", "ordinary object accepted", not _strict_load_fails('{"value":"ok"}'))

    bundle_ok, bundle_reason = verify_bundle(bundle)
    receipt_ok, receipt_reason = verify_receipt(receipt)
    binding_ok, binding_reason = verify_receipt_against_bundle(receipt, bundle)
    check("EVIDENCE", "bundle verifies", bundle_ok and bundle_reason == "PASS")
    check("EVIDENCE", "receipt verifies", receipt_ok and receipt_reason == "PASS")
    check("EVIDENCE", "receipt binding verifies", binding_ok and binding_reason == "PASS")
    check("EVIDENCE", "bundle exact fields", set(bundle) == BUNDLE_KEYS)
    check("EVIDENCE", "receipt exact fields", set(receipt) == RECEIPT_KEYS)

    tampered_bundle = copy.deepcopy(bundle)
    tampered_bundle["result"]["selected_candidate_ids"] = ["CANDIDATE-B"]
    check("EVIDENCE", "tampered bundle rejected", verify_bundle(tampered_bundle)[0] is False)
    tampered_bundle_id = copy.deepcopy(bundle)
    tampered_bundle_id["bundle_id"] = "slang_voting_bundle_sha256:" + ("0" * 64)
    check("EVIDENCE", "tampered bundle id rejected", verify_bundle(tampered_bundle_id)[0] is False)
    tampered_receipt = copy.deepcopy(receipt)
    tampered_receipt["state"] = STATE_ABSTAIN
    check("EVIDENCE", "tampered receipt rejected", verify_receipt(tampered_receipt)[0] is False)
    unrelated_receipt = make_receipt(build_bundle(build_single_source_input()))
    check("EVIDENCE", "unrelated receipt binding rejected", verify_receipt_against_bundle(unrelated_receipt, bundle)[0] is False)

    check("IDENTITY", "candidate set id prefix", result["candidate_set_id"].startswith("slang_voting_candidate_set_sha256:"))
    check("IDENTITY", "boundary id prefix", result["reporting_boundary_id"].startswith("slang_voting_reporting_boundary_sha256:"))
    check("IDENTITY", "report set id prefix", result["report_set_id"].startswith(REPORT_SET_PREFIX))
    check("IDENTITY", "rule profile id prefix", result["rule_profile_id"].startswith("slang_voting_rule_profile_sha256:"))
    check("IDENTITY", "result id prefix", result["result_id"].startswith("slang_voting_result_sha256:"))
    check("IDENTITY", "bundle id prefix", bundle["bundle_id"].startswith("slang_voting_bundle_sha256:"))
    check("IDENTITY", "receipt id prefix", receipt["receipt_id"].startswith("slang_voting_receipt_sha256:"))

    passed = 0
    total = 0
    serialized_bundle = json_file_bytes(bundle)
    check("SERIALIZATION", "terminal LF present", serialized_bundle.endswith(b"\n"))
    check("SERIALIZATION", "exactly one terminal LF", not serialized_bundle.endswith(b"\n\n"))
    check("SERIALIZATION", "no carriage returns", b"\r" not in serialized_bundle)
    check("SERIALIZATION", "valid UTF-8", serialized_bundle.decode("utf-8").endswith("\n"))
    check(
        "SERIALIZATION",
        "strict round trip",
        canonical_json(loads_strict(serialized_bundle.decode("utf-8"))) == canonical_json(bundle),
    )
    with tempfile.TemporaryDirectory() as temporary_directory:
        temporary_path = Path(temporary_directory) / "artifact.json"
        write_json(temporary_path, bundle)
        check("SERIALIZATION", "writer emits exact bytes", temporary_path.read_bytes() == serialized_bundle)

    artifact_expectations = (
        ("frozen example input canonical bytes", "SLANG_Voting_Example_Input_v0_1_2.json", base),
        ("frozen bundle canonical bytes", "SLANG_Voting_Bundle_v0_1_2.json", bundle),
        ("frozen receipt canonical bytes", "SLANG_Voting_Receipt_v0_1_2.json", receipt),
    )
    for name, filename, value in artifact_expectations:
        artifact_path = Path(__file__).with_name(filename)
        check(
            "SERIALIZATION",
            name,
            artifact_path.is_file() and artifact_path.read_bytes() == json_file_bytes(value),
        )

    vector_path = Path(__file__).with_name("SLANG_Voting_Vectors_v0_1_2.json")
    vector_bytes_canonical = False
    if vector_path.is_file():
        vector_value = load_json(vector_path)
        vector_bytes_canonical = vector_path.read_bytes() == json_file_bytes(vector_value)
    check("SERIALIZATION", "frozen vector document canonical bytes", vector_bytes_canonical)

    for group in sorted(groups):
        group_passed = sum(1 for _, condition in groups[group] if condition)
        group_total = len(groups[group])
        passed += group_passed
        total += group_total
        print(f"{group:<24} {group_passed}/{group_total} PASS" if group_passed == group_total else f"{group:<24} {group_passed}/{group_total} FAIL")
        for name, condition in groups[group]:
            if not condition:
                print("  FAIL: " + name)
    print(f"{'TOTAL':<24} {passed}/{total} PASS" if passed == total else f"{'TOTAL':<24} {passed}/{total} FAIL")
    return 0 if passed == total else 1


def _strict_load_fails(text: str) -> bool:
    try:
        loads_strict(text)
    except (TypeError, ValueError, DuplicateKeyError):
        return True
    return False


def public_summary(bundle: Dict[str, Any]) -> Dict[str, Any]:
    """Return the visibility-aware presentation projection.

    Candidate-bearing fields are included only when outcome_visible is true.
    The full result, bundle, and receipt remain unchanged and may retain the
    bounded outcome for reconstruction. This projection does not provide
    confidentiality or access control.
    """
    result = bundle["result"]
    visible = result.get("outcome_visible") is True
    return {
        "summary_schema": PUBLIC_SUMMARY_SCHEMA,
        "version": VERSION,
        "state": result["state"],
        "resolution_state": result["resolution_state"],
        "visibility_state": result["visibility_state"],
        "outcome_visible": visible,
        "outcome_fields_redacted": not visible,
        "selected_candidate_ids": result["selected_candidate_ids"] if visible else None,
        "leading_candidate_ids": result["leading_candidate_ids"] if visible else None,
        "candidate_resolution_totals": (
            result["candidate_resolution_totals"] if visible else None
        ),
        "reason_codes": result["reason_codes"],
        "result_id": result["result_id"],
        "bundle_id": bundle["bundle_id"],
    }


def required_visible_result_exit_code(summary: Dict[str, Any]) -> int:
    return 0 if summary.get("outcome_visible") is True else 3


def print_cli_error(code: str, detail: str) -> None:
    print("ERROR_CODE: " + code, file=sys.stderr)
    print("ERROR_DETAIL: " + detail, file=sys.stderr)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SLANG-Voting bounded reference resolver")
    parser.add_argument("--self-test", action="store_true", help="run the permanent reference audit")
    parser.add_argument("--input", type=Path, help="resolve a strict JSON input file")
    parser.add_argument("--write-bundle", type=Path, help="write the reconstructed bundle")
    parser.add_argument("--write-receipt", type=Path, help="write the compact receipt")
    parser.add_argument(
        "--require-visible-result",
        action="store_true",
        help="return exit code 3 unless the public summary contains a visible resolved outcome",
    )
    parser.add_argument("--verify-bundle", type=Path, help="verify a reconstruction bundle")
    parser.add_argument("--verify-receipt", type=Path, help="verify a compact receipt")
    parser.add_argument(
        "--verify-receipt-against-bundle",
        nargs=2,
        metavar=("RECEIPT", "BUNDLE"),
        help="verify a receipt and its exact bundle binding",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    try:
        if args.require_visible_result and (
            args.self_test
            or args.verify_bundle
            or args.verify_receipt
            or args.verify_receipt_against_bundle
        ):
            raise ValueError(
                "--require-visible-result applies only to input resolution"
            )
        if args.self_test:
            return run_self_test()
        if args.verify_bundle:
            ok, reason = verify_bundle(load_json(args.verify_bundle))
            print("VERIFY: PASS" if ok else "VERIFY: FAIL")
            print(reason)
            return 0 if ok else 1
        if args.verify_receipt:
            ok, reason = verify_receipt(load_json(args.verify_receipt))
            print("VERIFY: PASS" if ok else "VERIFY: FAIL")
            print(reason)
            return 0 if ok else 1
        if args.verify_receipt_against_bundle:
            receipt_path, bundle_path = map(Path, args.verify_receipt_against_bundle)
            ok, reason = verify_receipt_against_bundle(
                load_json(receipt_path), load_json(bundle_path)
            )
            print("VERIFY: PASS" if ok else "VERIFY: FAIL")
            print(reason)
            return 0 if ok else 1

        raw_input = load_json(args.input) if args.input else build_reference_input()
        bundle = build_bundle(raw_input)
        receipt = make_receipt(bundle)
        if args.write_bundle:
            write_json(args.write_bundle, bundle)
        if args.write_receipt:
            write_json(args.write_receipt, receipt)
        summary = public_summary(bundle)
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        if args.require_visible_result:
            exit_code = required_visible_result_exit_code(summary)
            if exit_code != 0:
                print(
                    "NOTICE_CODE: VISIBLE_RESULT_REQUIRED",
                    file=sys.stderr,
                )
                print(
                    "NOTICE_DETAIL: state="
                    + str(summary.get("state"))
                    + ", visibility_state="
                    + str(summary.get("visibility_state")),
                    file=sys.stderr,
                )
            return exit_code
        return 0
    except PortableJSONError as exc:
        print_cli_error("PORTABLE_JSON_BOUNDARY_FAILURE", str(exc))
        return 2
    except OSError as exc:
        print_cli_error("IO_ERROR", str(exc))
        return 2
    except (TypeError, ValueError, MemoryError, RecursionError) as exc:
        print_cli_error("COMMAND_OR_RESOLUTION_ERROR", str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
