#!/usr/bin/env python3
"""
SLANG-ResetPassword
Bounded deterministic admission of declared reset-authorization evidence.

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


VERSION = "0.1.0"
MINIMUM_PYTHON_VERSION = (3, 9)
SECRET_MATERIAL_PROCESSED_BY_PROFILE = False
CORE_VERSION = "SLANG-CORE-1-D05"
PROFILE_ID = "SLANG-RESET-PASSWORD-PROFILE-1-D01"
RULESET_ID = "SLANG-RESET-PASSWORD-RULESET-1-D01"
CANONICALIZATION_ID = "SLANG-CANONICAL-JSON-1-D02"
AUTHORIZER_PROFILE_ID = "RESET-AUTHORIZER-EVIDENCE-1"

INPUT_SCHEMA = "SLANG-RESET-PASSWORD-INPUT-1"
RESULT_SCHEMA = "SLANG-RESET-PASSWORD-RESULT-1"
BUNDLE_SCHEMA = "SLANG-RESET-PASSWORD-BUNDLE-1"
RECEIPT_SCHEMA = "SLANG-RESET-PASSWORD-RECEIPT-1"
PUBLIC_SUMMARY_SCHEMA = "SLANG-RESET-PASSWORD-PUBLIC-SUMMARY-1"
REASON_CODE_OUTCOME_WITHHELD = "RESET_OUTCOME_WITHHELD"
OUTCOME_REVEALING_REASON_CODES = frozenset({
    "RESET_AUTHORIZATION_EVIDENCE_ADMITTED",
    "RESET_NOT_AUTHORIZED_EVIDENCE_ADMITTED",
})

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

OUTCOME_RESET_AUTHORIZED = "RESET_AUTHORIZED"
OUTCOME_RESET_NOT_AUTHORIZED = "RESET_NOT_AUTHORIZED"
OUTCOME_NONE = "NONE"
SUPPORTED_AUTHORIZATION_RESULTS = {OUTCOME_RESET_AUTHORIZED, OUTCOME_RESET_NOT_AUTHORIZED}

ADMISSION_ADMIT = "ADMIT"
ADMISSION_DENY = "DENY"
ADMISSION_WITHHOLD = "WITHHOLD"

VISIBILITY_VISIBLE = "VISIBLE"
VISIBILITY_WITHHELD = "WITHHELD"

EVIDENCE_SINGLE_AUTHORIZER = "SINGLE_AUTHORIZER"
EVIDENCE_MULTI_AUTHORIZER = "MULTI_AUTHORIZER_EXACT_AGREEMENT"
SUPPORTED_EVIDENCE_MODES = {
    EVIDENCE_SINGLE_AUTHORIZER,
    EVIDENCE_MULTI_AUTHORIZER,
}

TOP_LEVEL_KEYS = {
    "schema",
    "profile_id",
    "ruleset_id",
    "context",
    "authorization_evidence",
    "declared_context_id",
    "declared_evidence_set_id",
}

DERIVED_TOP_LEVEL_KEYS = {
    "state",
    "resolution_state",
    "authorization_outcome",
    "admission_state",
    "visibility_state",
    "outcome_visible",
    "authenticated",
    "access",
    "grant",
    "granted",
    "session",
    "session_id",
    "session_token",
    "access_token",
    "refresh_token",
    "reset_authorized",
    "reset_approved",
    "credential_replaced",
    "credential_mutated",
    "reset_executed",
    "reset_authority",
    "credential_mutation_authority",
    "submission_id",
    "canonical_input_id",
    "context_id",
    "authorizer_manifest_id",
    "evidence_set_id",
    "evidence_agreement_id",
    "rule_profile_id",
    "outcome_id",
    "evaluation_evidence_id",
    "result_id",
    "bundle_id",
    "receipt_id",
    "public_summary_id",
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

FORBIDDEN_FIELD_NAMES = {
    "password",
    "raw_password",
    "current_password",
    "old_password",
    "new_password",
    "reset_token",
    "reset_code",
    "token",
    "otp",
    "one_time_password",
    "recovery_code",
    "backup_code",
    "recovery_secret",
    "authorization_code",
    "secret",
    "raw_secret",
    "password_hash",
    "stored_hash",
    "credential_hash",
    "salt",
    "pepper",
    "private_key",
    "session_token",
    "access_token",
    "refresh_token",
    "authenticated",
    "access",
    "grant",
    "granted",
    "login_success",
    "authentication_success",
    "reset_authorized",
    "reset_approved",
    "credential_replaced",
    "credential_mutated",
    "reset_executed",
    "reset_authority",
    "credential_mutation_authority",
    "resolution_state",
    "authorization_outcome",
    "admission_state",
    "outcome_visible",
    "result_id",
    "bundle_id",
    "receipt_id",
    "public_summary_id",
}

CONTEXT_KEYS = {
    "evaluation_id",
    "subject_ref",
    "credential_ref",
    "credential_version_before",
    "replacement_request_ref",
    "relying_party_ref",
    "recovery_case_ref",
    "evidence_mode",
    "expected_authorizer_ids",
    "evaluation_authorized",
    "reference_visibility_authorized",
}

EVIDENCE_KEYS = {
    "evidence_id",
    "authorizer_id",
    "authorizer_profile_id",
    "subject_ref",
    "credential_ref",
    "credential_version_before",
    "replacement_request_ref",
    "relying_party_ref",
    "recovery_case_ref",
    "authorization_result",
    "evidence_commitment",
}

MAX_SAFE_INTEGER = (2 ** 53) - 1
MAX_JSON_DEPTH = 48
MAX_JSON_NODES = 50000
MAX_JSON_INPUT_BYTES = 1024 * 1024
MAX_IDENTIFIER_LENGTH = 128
MAX_STRING_LENGTH = 1024
MAX_EVIDENCE_RECORDS = 8
MAX_REASON_CODES = 64
MAX_LIST_LENGTH = 256
HEX_DIGITS = frozenset("0123456789abcdefABCDEF")
LOWER_HEX_DIGITS = frozenset("0123456789abcdef")
IDENTIFIER_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9._:@/-]{0,127}$")
COMMITMENT_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
ASCII_TRIM_CHARACTERS = "\t\n\r "
ASCII_UPPER_TRANSLATION = str.maketrans(
    "abcdefghijklmnopqrstuvwxyz",
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
)
ASCII_LOWER_TRANSLATION = str.maketrans(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "abcdefghijklmnopqrstuvwxyz",
)

CONTEXT_ID_PREFIX = "slang_reset_password_context_sha256:"
AUTHORIZER_MANIFEST_ID_PREFIX = "slang_reset_password_authorizer_manifest_sha256:"
EVIDENCE_SET_ID_PREFIX = "slang_reset_password_evidence_set_sha256:"
EVIDENCE_AGREEMENT_ID_PREFIX = "slang_reset_password_evidence_agreement_sha256:"
RULE_PROFILE_ID_PREFIX = "slang_reset_password_rule_profile_sha256:"
SUBMISSION_ID_PREFIX = "slang_reset_password_submission_sha256:"
CANONICAL_INPUT_ID_PREFIX = "slang_reset_password_canonical_input_sha256:"
OUTCOME_ID_PREFIX = "slang_reset_password_outcome_sha256:"
EVALUATION_EVIDENCE_ID_PREFIX = "slang_reset_password_evaluation_evidence_sha256:"
RESULT_ID_PREFIX = "slang_reset_password_result_sha256:"
BUNDLE_ID_PREFIX = "slang_reset_password_bundle_sha256:"
RECEIPT_ID_PREFIX = "slang_reset_password_receipt_sha256:"
PUBLIC_SUMMARY_ID_PREFIX = "slang_reset_password_public_summary_sha256:"

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
    "subject_ref",
    "credential_ref",
    "credential_version_before",
    "replacement_request_ref",
    "relying_party_ref",
    "recovery_case_ref",
    "evidence_mode",
    "authorizer_count",
    "state",
    "resolution_state",
    "authorization_outcome",
    "admission_state",
    "visibility_state",
    "outcome_visible",
    "submission_id",
    "canonical_input_id",
    "context_id",
    "authorizer_manifest_id",
    "evidence_set_id",
    "evidence_agreement_id",
    "rule_profile_id",
    "outcome_id",
    "evaluation_evidence_id",
    "result_id",
    "reason_codes",
    "execution_authority",
    "reset_authority",
    "credential_mutation_authority",
    "authentication_authority",
    "access_authority",
    "session_authority",
    "source_authenticity",
    "bundle_id",
    "receipt_id",
}

PUBLIC_SUMMARY_KEYS = {
    "summary_schema",
    "version",
    "state",
    "resolution_state",
    "visibility_state",
    "outcome_visible",
    "outcome_fields_redacted",
    "authorization_outcome",
    "admission_state",
    "reason_codes",
    "execution_authority",
    "reset_authority",
    "credential_mutation_authority",
    "authentication_authority",
    "access_authority",
    "session_authority",
    "result_id",
    "bundle_id",
    "public_summary_id",
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
        "project": "SLANG-RESET-PASSWORD",
        "version": VERSION,
        "core_version": CORE_VERSION,
        "profile_id": PROFILE_ID,
        "ruleset_id": RULESET_ID,
        "canonicalization_id": CANONICALIZATION_ID,
        "input_schema": INPUT_SCHEMA,
        "result_schema": RESULT_SCHEMA,
        "bundle_schema": BUNDLE_SCHEMA,
        "receipt_schema": RECEIPT_SCHEMA,
        "authorizer_profile_id": AUTHORIZER_PROFILE_ID,
    }


def identity_domain_id() -> str:
    return identity("slang_reset_password_identity_domain_sha256:", identity_domain_material())


def contains_lone_surrogate(value: str) -> bool:
    return any(0xD800 <= ord(character) <= 0xDFFF for character in value)


def validate_portable_json(value: Any, path: str = "$") -> None:
    node_count = 0

    def walk(node: Any, node_path: str, depth: int) -> None:
        nonlocal node_count
        node_count += 1
        if node_count > MAX_JSON_NODES:
            raise PortableJSONError("JSON node limit exceeded")
        if depth > MAX_JSON_DEPTH:
            raise PortableJSONError("JSON depth limit exceeded")
        if node is None or isinstance(node, bool):
            return
        if isinstance(node, int) and not isinstance(node, bool):
            if abs(node) > MAX_SAFE_INTEGER:
                raise PortableJSONError(node_path + ": integer exceeds portable safe range")
            return
        if isinstance(node, float):
            raise PortableJSONError(node_path + ": floating-point values are not supported")
        if isinstance(node, str):
            if len(node) > MAX_STRING_LENGTH:
                raise PortableJSONError(node_path + ": string length limit exceeded")
            if contains_lone_surrogate(node):
                raise PortableJSONError(node_path + ": lone surrogate is not portable")
            return
        if isinstance(node, list):
            if len(node) > MAX_LIST_LENGTH:
                raise PortableJSONError(node_path + ": array length limit exceeded")
            for index, item in enumerate(node):
                walk(item, f"{node_path}[{index}]", depth + 1)
            return
        if isinstance(node, dict):
            if len(node) > MAX_LIST_LENGTH:
                raise PortableJSONError(node_path + ": object member limit exceeded")
            for key, item in node.items():
                if not isinstance(key, str):
                    raise PortableJSONError(node_path + ": object keys must be strings")
                if len(key) > MAX_IDENTIFIER_LENGTH:
                    raise PortableJSONError(node_path + ": object key length limit exceeded")
                if contains_lone_surrogate(key):
                    raise PortableJSONError(node_path + ": object key contains lone surrogate")
                walk(item, node_path + "." + key, depth + 1)
            return
        raise PortableJSONError(node_path + ": unsupported JSON value type")

    walk(value, path, 0)


def validate_submitted_input_boundary(value: Any) -> None:
    validate_portable_json(value)
    canonical_size = len(canonical_json(value).encode("utf-8"))
    if canonical_size > MAX_JSON_INPUT_BYTES:
        raise PortableJSONError(
            "$: canonical serialized byte length "
            + str(canonical_size)
            + " exceeds input limit "
            + str(MAX_JSON_INPUT_BYTES)
        )


def is_ascii_lexical_string(value: str) -> bool:
    return all(
        ord(character) in (0x09, 0x0A, 0x0D)
        or 0x20 <= ord(character) <= 0x7E
        for character in value
    )


def ascii_trim(value: str) -> str:
    return value.strip(ASCII_TRIM_CHARACTERS)


def ascii_upper(value: str) -> str:
    return value.translate(ASCII_UPPER_TRANSLATION)


def ascii_lower(value: str) -> str:
    return value.translate(ASCII_LOWER_TRANSLATION)


def normalize_ascii_field_name(value: Any) -> Optional[str]:
    if not isinstance(value, str) or not is_ascii_lexical_string(value):
        return None
    return ascii_lower(ascii_trim(value))


def normalize_identifier(value: Any) -> Optional[str]:
    if not isinstance(value, str) or not is_ascii_lexical_string(value):
        return None
    normalized = ascii_upper(ascii_trim(value))
    if len(normalized) > MAX_IDENTIFIER_LENGTH:
        return None
    if not IDENTIFIER_PATTERN.fullmatch(normalized):
        return None
    return normalized


def normalize_commitment(value: Any) -> Optional[str]:
    if not isinstance(value, str) or not is_ascii_lexical_string(value):
        return None
    normalized = ascii_lower(ascii_trim(value))
    if not COMMITMENT_PATTERN.fullmatch(normalized):
        return None
    return normalized


def is_identity_with_prefix(value: Any, prefix: str) -> bool:
    if not isinstance(value, str) or not value.startswith(prefix):
        return False
    digest = value[len(prefix):]
    return len(digest) == 64 and all(character in LOWER_HEX_DIGITS for character in digest)


def issue_priority(state: str) -> int:
    return {
        STATE_FORBIDDEN: 0,
        STATE_CONFLICT: 1,
        STATE_UNSUPPORTED: 2,
        STATE_INCOMPLETE: 3,
        STATE_ABSTAIN: 4,
        STATE_RESOLVED: 5,
    }.get(state, 99)


def choose_primary_issue(issues: Sequence[ValidationIssue]) -> ValidationIssue:
    if not issues:
        raise ValueError("at least one issue is required")
    return min(issues, key=lambda issue: (issue_priority(issue.state), issue.code, issue.detail))


def unique_sorted(values: Iterable[str]) -> List[str]:
    return sorted(set(values))


def issue_lists(
    issues: Sequence[ValidationIssue],
) -> Tuple[List[str], List[str], List[str], List[str], List[str]]:
    reason_codes = unique_sorted(issue.code for issue in issues)[:MAX_REASON_CODES]
    missing = unique_sorted(
        issue.code for issue in issues if issue.state == STATE_INCOMPLETE
    )[:MAX_REASON_CODES]
    conflicts = unique_sorted(
        issue.code for issue in issues if issue.state == STATE_CONFLICT
    )[:MAX_REASON_CODES]
    prohibitions = unique_sorted(
        issue.code for issue in issues if issue.state == STATE_FORBIDDEN
    )[:MAX_REASON_CODES]
    unsupported = unique_sorted(
        issue.code for issue in issues if issue.state == STATE_UNSUPPORTED
    )[:MAX_REASON_CODES]
    return reason_codes, missing, conflicts, prohibitions, unsupported


def scan_forbidden_field_paths(value: Any, path: str = "$") -> List[str]:
    paths: List[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            key_lower = normalize_ascii_field_name(key)
            child_path = path + "." + str(key)
            if key_lower in FORBIDDEN_FIELD_NAMES:
                paths.append(child_path)
            paths.extend(scan_forbidden_field_paths(item, child_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            paths.extend(scan_forbidden_field_paths(item, f"{path}[{index}]"))
    return unique_sorted(paths)


def redact_forbidden_values(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: Dict[str, Any] = {}
        for key, item in value.items():
            key_lower = normalize_ascii_field_name(key)
            if key_lower in FORBIDDEN_FIELD_NAMES:
                redacted[key] = "<FORBIDDEN_VALUE_REDACTED>"
            else:
                redacted[key] = redact_forbidden_values(item)
        return redacted
    if isinstance(value, list):
        return [redact_forbidden_values(item) for item in value]
    return value


def unknown_key_issues(value: Dict[str, Any], allowed: Set[str], path: str) -> List[ValidationIssue]:
    return [
        ValidationIssue(STATE_UNSUPPORTED, "UNKNOWN_FIELD", path + "." + key)
        for key in sorted(set(value) - allowed)
    ]


def normalize_required_identifier(
    value: Dict[str, Any], key: str, path: str, issues: List[ValidationIssue]
) -> Optional[str]:
    if key not in value:
        issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_REQUIRED_FIELD", path + "." + key))
        return None
    normalized = normalize_identifier(value.get(key))
    if normalized is None:
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_IDENTIFIER", path + "." + key))
    return normalized


def normalize_required_bool(
    value: Dict[str, Any], key: str, path: str, issues: List[ValidationIssue]
) -> Optional[bool]:
    if key not in value:
        issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_REQUIRED_FIELD", path + "." + key))
        return None
    result = value.get(key)
    if not isinstance(result, bool):
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "BOOLEAN_REQUIRED", path + "." + key))
        return None
    return result


def normalize_identifier_list(
    value: Any,
    path: str,
    minimum: int,
    maximum: int,
    issues: List[ValidationIssue],
) -> Optional[List[str]]:
    if not isinstance(value, list):
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "IDENTIFIER_LIST_REQUIRED", path))
        return None
    if len(value) < minimum:
        issues.append(ValidationIssue(STATE_INCOMPLETE, "INSUFFICIENT_AUTHORIZER_IDENTIFIERS", path))
    if len(value) > maximum:
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "AUTHORIZER_LIMIT_EXCEEDED", path))
    normalized: List[str] = []
    for index, item in enumerate(value[:maximum]):
        identifier_value = normalize_identifier(item)
        if identifier_value is None:
            issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_IDENTIFIER", f"{path}[{index}]"))
        else:
            normalized.append(identifier_value)
    if len(normalized) != len(set(normalized)):
        issues.append(ValidationIssue(STATE_CONFLICT, "DUPLICATE_AUTHORIZER_ID", path))
    return sorted(set(normalized))


def normalize_context(value: Any) -> Tuple[Optional[Dict[str, Any]], List[ValidationIssue]]:
    issues: List[ValidationIssue] = []
    if value is None:
        issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_REQUIRED_FIELD", "$.context"))
        return None, issues
    if not isinstance(value, dict):
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "CONTEXT_OBJECT_REQUIRED", "$.context"))
        return None, issues
    issues.extend(unknown_key_issues(value, CONTEXT_KEYS, "$.context"))

    normalized: Dict[str, Any] = {
        "evaluation_id": normalize_required_identifier(value, "evaluation_id", "$.context", issues),
        "subject_ref": normalize_required_identifier(value, "subject_ref", "$.context", issues),
        "credential_ref": normalize_required_identifier(value, "credential_ref", "$.context", issues),
        "credential_version_before": normalize_required_identifier(value, "credential_version_before", "$.context", issues),
        "replacement_request_ref": normalize_required_identifier(value, "replacement_request_ref", "$.context", issues),
        "relying_party_ref": normalize_required_identifier(value, "relying_party_ref", "$.context", issues),
        "recovery_case_ref": normalize_required_identifier(value, "recovery_case_ref", "$.context", issues),
        "evaluation_authorized": normalize_required_bool(value, "evaluation_authorized", "$.context", issues),
        "reference_visibility_authorized": normalize_required_bool(
            value, "reference_visibility_authorized", "$.context", issues
        ),
    }

    if "evidence_mode" not in value:
        issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_REQUIRED_FIELD", "$.context.evidence_mode"))
        evidence_mode = None
    else:
        evidence_mode = normalize_identifier(value.get("evidence_mode"))
        if evidence_mode not in SUPPORTED_EVIDENCE_MODES:
            issues.append(ValidationIssue(STATE_UNSUPPORTED, "UNSUPPORTED_EVIDENCE_MODE", "$.context.evidence_mode"))
    normalized["evidence_mode"] = evidence_mode

    if "expected_authorizer_ids" not in value:
        issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_REQUIRED_FIELD", "$.context.expected_authorizer_ids"))
        expected_authorizers = None
    else:
        expected_authorizers = normalize_identifier_list(
            value.get("expected_authorizer_ids"),
            "$.context.expected_authorizer_ids",
            1,
            MAX_EVIDENCE_RECORDS,
            issues,
        )
    normalized["expected_authorizer_ids"] = expected_authorizers

    if evidence_mode == EVIDENCE_SINGLE_AUTHORIZER and expected_authorizers is not None and len(expected_authorizers) != 1:
        issues.append(ValidationIssue(STATE_CONFLICT, "SINGLE_AUTHORIZER_COUNT_MISMATCH", "$.context.expected_authorizer_ids"))
    if evidence_mode == EVIDENCE_MULTI_AUTHORIZER and expected_authorizers is not None and len(expected_authorizers) < 2:
        issues.append(ValidationIssue(STATE_INCOMPLETE, "MULTI_AUTHORIZER_REQUIRES_AT_LEAST_TWO", "$.context.expected_authorizer_ids"))

    if normalized.get("evaluation_authorized") is False:
        issues.append(ValidationIssue(STATE_ABSTAIN, "EVALUATION_NOT_AUTHORIZED", "$.context.evaluation_authorized"))

    return normalized, issues


def normalize_evidence_record(
    value: Any,
    index: int,
) -> Tuple[Optional[Dict[str, Any]], List[ValidationIssue]]:
    issues: List[ValidationIssue] = []
    path = f"$.authorization_evidence[{index}]"
    if not isinstance(value, dict):
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "EVIDENCE_OBJECT_REQUIRED", path))
        return None, issues
    issues.extend(unknown_key_issues(value, EVIDENCE_KEYS, path))

    normalized: Dict[str, Any] = {
        "evidence_id": normalize_required_identifier(value, "evidence_id", path, issues),
        "authorizer_id": normalize_required_identifier(value, "authorizer_id", path, issues),
        "authorizer_profile_id": normalize_required_identifier(value, "authorizer_profile_id", path, issues),
        "subject_ref": normalize_required_identifier(value, "subject_ref", path, issues),
        "credential_ref": normalize_required_identifier(value, "credential_ref", path, issues),
        "credential_version_before": normalize_required_identifier(value, "credential_version_before", path, issues),
        "replacement_request_ref": normalize_required_identifier(value, "replacement_request_ref", path, issues),
        "relying_party_ref": normalize_required_identifier(value, "relying_party_ref", path, issues),
        "recovery_case_ref": normalize_required_identifier(value, "recovery_case_ref", path, issues),
    }

    authorizer_profile = normalized.get("authorizer_profile_id")
    if authorizer_profile is not None and authorizer_profile != AUTHORIZER_PROFILE_ID:
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "UNSUPPORTED_AUTHORIZER_PROFILE", path + ".authorizer_profile_id"))

    if "authorization_result" not in value:
        issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_REQUIRED_FIELD", path + ".authorization_result"))
        authorization_result = None
    else:
        authorization_result = normalize_identifier(value.get("authorization_result"))
        if authorization_result not in SUPPORTED_AUTHORIZATION_RESULTS:
            issues.append(ValidationIssue(STATE_UNSUPPORTED, "UNSUPPORTED_AUTHORIZATION_RESULT", path + ".authorization_result"))
    normalized["authorization_result"] = authorization_result

    if "evidence_commitment" not in value:
        issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_REQUIRED_FIELD", path + ".evidence_commitment"))
        evidence_commitment = None
    else:
        evidence_commitment = normalize_commitment(value.get("evidence_commitment"))
        if evidence_commitment is None:
            issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_EVIDENCE_COMMITMENT", path + ".evidence_commitment"))
    normalized["evidence_commitment"] = evidence_commitment
    return normalized, issues


def context_material(context: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "evaluation_id": context["evaluation_id"],
        "subject_ref": context["subject_ref"],
        "credential_ref": context["credential_ref"],
        "credential_version_before": context["credential_version_before"],
        "replacement_request_ref": context["replacement_request_ref"],
        "relying_party_ref": context["relying_party_ref"],
        "recovery_case_ref": context["recovery_case_ref"],
        "evidence_mode": context["evidence_mode"],
        "expected_authorizer_ids": context["expected_authorizer_ids"],
        "evaluation_authorized": context["evaluation_authorized"],
        "reference_visibility_authorized": context["reference_visibility_authorized"],
    }


def authorizer_manifest_material(context: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "evidence_mode": context["evidence_mode"],
        "expected_authorizer_ids": context["expected_authorizer_ids"],
        "authorizer_profile_id": AUTHORIZER_PROFILE_ID,
    }


def evidence_set_material(evidence: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "authorizer_profile_id": AUTHORIZER_PROFILE_ID,
        "records": list(evidence),
    }


def rule_profile_material() -> Dict[str, Any]:
    return {
        "profile_id": PROFILE_ID,
        "ruleset_id": RULESET_ID,
        "supported_evidence_modes": sorted(SUPPORTED_EVIDENCE_MODES),
        "supported_authorization_results": sorted(SUPPORTED_AUTHORIZATION_RESULTS),
        "agreement_rule": "EXACT",
        "execution_authority": "NONE",
        "reset_authority": "NONE",
        "credential_mutation_authority": "NONE",
        "authentication_authority": "NONE",
        "access_authority": "NONE",
        "session_authority": "NONE",
    }


def normalize_declared_identity(
    raw_input: Dict[str, Any],
    key: str,
    prefix: str,
    expected: Optional[str],
    issues: List[ValidationIssue],
) -> Optional[str]:
    if key not in raw_input:
        issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_DECLARED_IDENTITY", "$." + key))
        return None
    value = raw_input.get(key)
    if not is_identity_with_prefix(value, prefix):
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_DECLARED_IDENTITY", "$." + key))
        return None
    if expected is not None and value != expected:
        issues.append(ValidationIssue(STATE_CONFLICT, "DECLARED_IDENTITY_MISMATCH", "$." + key))
    return value


def binding_issues(context: Dict[str, Any], evidence: Sequence[Dict[str, Any]]) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    mappings = (
        ("subject_ref", "SUBJECT_BINDING_MISMATCH"),
        ("credential_ref", "CREDENTIAL_BINDING_MISMATCH"),
        ("credential_version_before", "CREDENTIAL_VERSION_BEFORE_MISMATCH"),
        ("replacement_request_ref", "REPLACEMENT_REQUEST_BINDING_MISMATCH"),
        ("relying_party_ref", "RELYING_PARTY_BINDING_MISMATCH"),
        ("recovery_case_ref", "RECOVERY_CASE_BINDING_MISMATCH"),
    )
    for index, record in enumerate(evidence):
        for field, code in mappings:
            context_value = context.get(field)
            record_value = record.get(field)
            if context_value is not None and record_value is not None and context_value != record_value:
                issues.append(
                    ValidationIssue(
                        STATE_CONFLICT,
                        code,
                        f"$.authorization_evidence[{index}].{field}",
                    )
                )
    return issues


def authorizer_set_issues(context: Dict[str, Any], evidence: Sequence[Dict[str, Any]]) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    expected = context.get("expected_authorizer_ids")
    actual = sorted(record["authorizer_id"] for record in evidence if record.get("authorizer_id") is not None)
    if expected is None:
        return issues
    expected_set = set(expected)
    actual_set = set(actual)
    if expected_set - actual_set:
        issues.append(ValidationIssue(STATE_INCOMPLETE, "EXPECTED_AUTHORIZER_EVIDENCE_MISSING", "$.authorization_evidence"))
    if actual_set - expected_set:
        issues.append(ValidationIssue(STATE_CONFLICT, "UNEXPECTED_AUTHORIZER_EVIDENCE", "$.authorization_evidence"))
    if context.get("evidence_mode") == EVIDENCE_SINGLE_AUTHORIZER and len(actual) == 0:
        issues.append(ValidationIssue(STATE_INCOMPLETE, "SINGLE_AUTHORIZER_EVIDENCE_MISSING", "$.authorization_evidence"))
    elif context.get("evidence_mode") == EVIDENCE_SINGLE_AUTHORIZER and len(actual) > 1:
        issues.append(ValidationIssue(STATE_CONFLICT, "SINGLE_AUTHORIZER_EVIDENCE_COUNT_MISMATCH", "$.authorization_evidence"))
    if context.get("evidence_mode") == EVIDENCE_MULTI_AUTHORIZER and len(actual) < 2:
        issues.append(ValidationIssue(STATE_INCOMPLETE, "MULTI_AUTHORIZER_EVIDENCE_INCOMPLETE", "$.authorization_evidence"))
    return issues


def evidence_uniqueness_issues(evidence: Sequence[Dict[str, Any]]) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    evidence_ids = [record.get("evidence_id") for record in evidence if record.get("evidence_id") is not None]
    authorizer_ids = [record.get("authorizer_id") for record in evidence if record.get("authorizer_id") is not None]
    if len(evidence_ids) != len(set(evidence_ids)):
        issues.append(ValidationIssue(STATE_CONFLICT, "DUPLICATE_EVIDENCE_ID", "$.authorization_evidence"))
    if len(authorizer_ids) != len(set(authorizer_ids)):
        issues.append(ValidationIssue(STATE_CONFLICT, "DUPLICATE_AUTHORIZER_ID", "$.authorization_evidence"))
    return issues


def evidence_agreement_issues(context: Dict[str, Any], evidence: Sequence[Dict[str, Any]]) -> List[ValidationIssue]:
    if context.get("evidence_mode") != EVIDENCE_MULTI_AUTHORIZER:
        return []
    outcomes = {record.get("authorization_result") for record in evidence if record.get("authorization_result") is not None}
    if len(outcomes) > 1:
        return [ValidationIssue(STATE_CONFLICT, "EVIDENCE_RESULT_DISAGREEMENT", "$.authorization_evidence")]
    return []


def normalize_input(
    raw_input: Any,
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any], List[ValidationIssue], List[str]]:
    validate_submitted_input_boundary(raw_input)
    forbidden_paths = scan_forbidden_field_paths(raw_input)
    issues: List[ValidationIssue] = [
        ValidationIssue(STATE_FORBIDDEN, "FORBIDDEN_FIELD_PRESENT", path)
        for path in forbidden_paths
    ]

    if not isinstance(raw_input, dict):
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "INPUT_OBJECT_REQUIRED", "$"))
        projection = {
            "schema": None,
            "profile_id": None,
            "ruleset_id": None,
            "context": None,
            "authorization_evidence": [],
            "declared_context_id": None,
            "declared_evidence_set_id": None,
        }
        return None, projection, issues, forbidden_paths

    issues.extend(unknown_key_issues(raw_input, TOP_LEVEL_KEYS | DERIVED_TOP_LEVEL_KEYS, "$"))
    for key in sorted(set(raw_input) & DERIVED_TOP_LEVEL_KEYS):
        issues.append(ValidationIssue(STATE_FORBIDDEN, "CALLER_DERIVED_FIELD_FORBIDDEN", "$." + key))

    schema = raw_input.get("schema")
    if "schema" not in raw_input:
        issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_REQUIRED_FIELD", "$.schema"))
    elif schema != INPUT_SCHEMA:
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "UNSUPPORTED_SCHEMA", "$.schema"))

    profile_id = raw_input.get("profile_id")
    if "profile_id" not in raw_input:
        issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_REQUIRED_FIELD", "$.profile_id"))
    elif profile_id != PROFILE_ID:
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "UNSUPPORTED_PROFILE", "$.profile_id"))

    ruleset_id = raw_input.get("ruleset_id")
    if "ruleset_id" not in raw_input:
        issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_REQUIRED_FIELD", "$.ruleset_id"))
    elif ruleset_id != RULESET_ID:
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "UNSUPPORTED_RULESET", "$.ruleset_id"))

    context, context_issues = normalize_context(raw_input.get("context"))
    issues.extend(context_issues)

    evidence_raw = raw_input.get("authorization_evidence")
    normalized_evidence: List[Dict[str, Any]] = []
    if "authorization_evidence" not in raw_input:
        issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_REQUIRED_FIELD", "$.authorization_evidence"))
    elif not isinstance(evidence_raw, list):
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "EVIDENCE_ARRAY_REQUIRED", "$.authorization_evidence"))
    else:
        if len(evidence_raw) == 0:
            issues.append(ValidationIssue(STATE_INCOMPLETE, "AUTHORIZER_EVIDENCE_MISSING", "$.authorization_evidence"))
        if len(evidence_raw) > MAX_EVIDENCE_RECORDS:
            issues.append(ValidationIssue(STATE_UNSUPPORTED, "EVIDENCE_RECORD_LIMIT_EXCEEDED", "$.authorization_evidence"))
        else:
            for index, raw_record in enumerate(evidence_raw):
                record, record_issues = normalize_evidence_record(raw_record, index)
                issues.extend(record_issues)
                if record is not None:
                    normalized_evidence.append(record)

    normalized_evidence = sorted(
        normalized_evidence,
        key=lambda record: (
            record.get("authorizer_id") or "",
            record.get("evidence_id") or "",
            canonical_json(record),
        ),
    )

    if context is not None:
        issues.extend(evidence_uniqueness_issues(normalized_evidence))
        issues.extend(binding_issues(context, normalized_evidence))
        issues.extend(authorizer_set_issues(context, normalized_evidence))
        issues.extend(evidence_agreement_issues(context, normalized_evidence))

    expected_context_id = None
    expected_evidence_set_id = None
    context_blocked = any(
        issue.detail.startswith("$.context")
        and issue.state in {STATE_FORBIDDEN, STATE_CONFLICT, STATE_UNSUPPORTED, STATE_INCOMPLETE}
        for issue in issues
    )
    evidence_blocked = any(
        issue.detail.startswith("$.authorization_evidence")
        and issue.state in {STATE_FORBIDDEN, STATE_CONFLICT, STATE_UNSUPPORTED, STATE_INCOMPLETE}
        for issue in issues
    )
    if (
        context is not None
        and not context_blocked
        and all(value is not None for value in context.values())
    ):
        expected_context_id = identity(CONTEXT_ID_PREFIX, context_material(context))
    if (
        normalized_evidence
        and not evidence_blocked
        and all(all(value is not None for value in record.values()) for record in normalized_evidence)
    ):
        expected_evidence_set_id = identity(EVIDENCE_SET_ID_PREFIX, evidence_set_material(normalized_evidence))

    declared_context_id = normalize_declared_identity(
        raw_input,
        "declared_context_id",
        CONTEXT_ID_PREFIX,
        expected_context_id,
        issues,
    )
    declared_evidence_set_id = normalize_declared_identity(
        raw_input,
        "declared_evidence_set_id",
        EVIDENCE_SET_ID_PREFIX,
        expected_evidence_set_id,
        issues,
    )

    projection = {
        "schema": schema if isinstance(schema, str) else None,
        "profile_id": profile_id if isinstance(profile_id, str) else None,
        "ruleset_id": ruleset_id if isinstance(ruleset_id, str) else None,
        "context": context,
        "authorization_evidence": normalized_evidence,
        "declared_context_id": declared_context_id,
        "declared_evidence_set_id": declared_evidence_set_id,
    }
    computational = {
        "context": context,
        "authorization_evidence": normalized_evidence,
        "expected_context_id": expected_context_id,
        "expected_evidence_set_id": expected_evidence_set_id,
    }
    return computational, projection, issues, forbidden_paths


def make_base_result() -> Dict[str, Any]:
    return {
        "schema": RESULT_SCHEMA,
        "version": VERSION,
        "core_version": CORE_VERSION,
        "canonicalization_id": CANONICALIZATION_ID,
        "identity_domain_id": identity_domain_id(),
        "profile_id": PROFILE_ID,
        "ruleset_id": RULESET_ID,
        "authorizer_profile_id": AUTHORIZER_PROFILE_ID,
        "evaluation_id": None,
        "subject_ref": None,
        "credential_ref": None,
        "credential_version_before": None,
        "replacement_request_ref": None,
        "relying_party_ref": None,
        "recovery_case_ref": None,
        "evidence_mode": None,
        "authorizer_count": 0,
        "state": STATE_INCOMPLETE,
        "resolution_state": STATE_INCOMPLETE,
        "authorization_outcome": OUTCOME_NONE,
        "admission_state": ADMISSION_WITHHOLD,
        "visibility_state": VISIBILITY_WITHHELD,
        "outcome_visible": False,
        "submission_id": None,
        "canonical_input_id": None,
        "context_id": None,
        "authorizer_manifest_id": None,
        "evidence_set_id": None,
        "evidence_agreement_id": None,
        "rule_profile_id": identity(RULE_PROFILE_ID_PREFIX, rule_profile_material()),
        "outcome_id": None,
        "evaluation_evidence_id": None,
        "result_id": None,
        "reason_codes": [],
        "missing_dependencies": [],
        "conflicts": [],
        "prohibitions": [],
        "unsupported_features": [],
        "execution_authority": "NONE",
        "reset_authority": "NONE",
        "credential_mutation_authority": "NONE",
        "authentication_authority": "NONE",
        "access_authority": "NONE",
        "session_authority": "NONE",
        "source_authenticity": "NOT_ESTABLISHED_BY_REFERENCE_PROFILE",
        "identity_ownership": "NOT_ESTABLISHED_BY_REFERENCE_PROFILE",
        "secret_material_processed": SECRET_MATERIAL_PROCESSED_BY_PROFILE,
    }


def redacted_submitted_input(raw_input: Any) -> Any:
    return redact_forbidden_values(json_clone(raw_input))


def result_identity_material(result: Dict[str, Any]) -> Dict[str, Any]:
    return {
        key: value
        for key, value in result.items()
        if key not in {"result_id", "submission_id"}
    }


def resolve_reset_password(raw_input: Any) -> Dict[str, Any]:
    computational, projection, issues, forbidden_paths = normalize_input(raw_input)
    safe_input = redacted_submitted_input(raw_input)
    result = make_base_result()
    result["submission_id"] = identity(SUBMISSION_ID_PREFIX, safe_input)
    result["canonical_input_id"] = identity(CANONICAL_INPUT_ID_PREFIX, projection)

    context = computational.get("context") if computational is not None else None
    evidence = computational.get("authorization_evidence", []) if computational is not None else []

    if context is not None:
        for field in (
            "evaluation_id",
            "subject_ref",
            "credential_ref",
            "credential_version_before",
            "replacement_request_ref",
            "relying_party_ref",
            "recovery_case_ref",
            "evidence_mode",
        ):
            result[field] = context.get(field)
        result["context_id"] = computational.get("expected_context_id")
        if all(context.get(key) is not None for key in ("evidence_mode", "expected_authorizer_ids")):
            result["authorizer_manifest_id"] = identity(
                AUTHORIZER_MANIFEST_ID_PREFIX,
                authorizer_manifest_material(context),
            )

    result["authorizer_count"] = len(evidence)
    result["evidence_set_id"] = computational.get("expected_evidence_set_id") if computational is not None else None

    valid_outcomes = [record.get("authorization_result") for record in evidence if record.get("authorization_result") in SUPPORTED_AUTHORIZATION_RESULTS]
    if context is not None and evidence:
        agreement_material = {
            "context_id": result["context_id"],
            "evidence_set_id": result["evidence_set_id"],
            "evidence_mode": context.get("evidence_mode"),
            "outcomes": sorted(valid_outcomes),
        }
        result["evidence_agreement_id"] = identity(EVIDENCE_AGREEMENT_ID_PREFIX, agreement_material)

    reason_codes, missing, conflicts, prohibitions, unsupported = issue_lists(issues)
    result["reason_codes"] = reason_codes
    result["missing_dependencies"] = missing
    result["conflicts"] = conflicts
    result["prohibitions"] = prohibitions
    result["unsupported_features"] = unsupported

    if issues:
        primary = choose_primary_issue(issues)
        result["state"] = primary.state
        result["resolution_state"] = primary.state
    else:
        if len(valid_outcomes) != len(evidence) or not valid_outcomes:
            result["state"] = STATE_INCOMPLETE
            result["resolution_state"] = STATE_INCOMPLETE
            result["reason_codes"] = ["AUTHORIZATION_OUTCOME_UNAVAILABLE"]
            result["missing_dependencies"] = ["AUTHORIZATION_OUTCOME_UNAVAILABLE"]
        else:
            outcome = valid_outcomes[0]
            result["state"] = STATE_RESOLVED
            result["resolution_state"] = STATE_RESOLVED
            result["authorization_outcome"] = outcome
            result["admission_state"] = ADMISSION_ADMIT if outcome == OUTCOME_RESET_AUTHORIZED else ADMISSION_DENY
            visibility_authorized = context.get("reference_visibility_authorized") is True if context else False
            result["visibility_state"] = VISIBILITY_VISIBLE if visibility_authorized else VISIBILITY_WITHHELD
            result["outcome_visible"] = visibility_authorized
            result["reason_codes"] = [
                "RESET_AUTHORIZATION_EVIDENCE_ADMITTED" if outcome == OUTCOME_RESET_AUTHORIZED else "RESET_NOT_AUTHORIZED_EVIDENCE_ADMITTED"
            ]

    outcome_material = {
        "state": result["state"],
        "authorization_outcome": result["authorization_outcome"],
        "admission_state": result["admission_state"],
        "visibility_state": result["visibility_state"],
        "context_id": result["context_id"],
        "evidence_set_id": result["evidence_set_id"],
        "evidence_agreement_id": result["evidence_agreement_id"],
        "rule_profile_id": result["rule_profile_id"],
        "reason_codes": result["reason_codes"],
    }
    result["outcome_id"] = identity(OUTCOME_ID_PREFIX, outcome_material)
    evaluation_evidence_material = {
        "canonical_input_id": result["canonical_input_id"],
        "context_id": result["context_id"],
        "authorizer_manifest_id": result["authorizer_manifest_id"],
        "evidence_set_id": result["evidence_set_id"],
        "evidence_agreement_id": result["evidence_agreement_id"],
        "outcome_id": result["outcome_id"],
        "forbidden_field_paths": forbidden_paths,
    }
    result["evaluation_evidence_id"] = identity(
        EVALUATION_EVIDENCE_ID_PREFIX,
        evaluation_evidence_material,
    )
    result["result_id"] = identity(RESULT_ID_PREFIX, result_identity_material(result))
    return result


def normalized_projection(raw_input: Any) -> Dict[str, Any]:
    _, projection, _, _ = normalize_input(raw_input)
    return projection


def build_bundle(raw_input: Any) -> Dict[str, Any]:
    validate_submitted_input_boundary(raw_input)
    safe_input = redacted_submitted_input(raw_input)
    bundle: Dict[str, Any] = {
        "schema": BUNDLE_SCHEMA,
        "version": VERSION,
        "core_version": CORE_VERSION,
        "canonicalization_id": CANONICALIZATION_ID,
        "identity_domain_id": identity_domain_id(),
        "submitted_input": safe_input,
        "normalized_projection": normalized_projection(safe_input),
        "result": resolve_reset_password(safe_input),
        "bundle_id": None,
    }
    bundle["bundle_id"] = identity(
        BUNDLE_ID_PREFIX,
        {key: value for key, value in bundle.items() if key != "bundle_id"},
    )
    return bundle


def verify_bundle(bundle: Any) -> Tuple[bool, str]:
    try:
        validate_portable_json(bundle)
    except PortableJSONError as exc:
        return False, "PORTABLE_JSON_BOUNDARY_FAILURE: " + str(exc)
    if not isinstance(bundle, dict):
        return False, "BUNDLE_OBJECT_REQUIRED"
    if set(bundle) != BUNDLE_KEYS:
        return False, "BUNDLE_FIELDS_MISMATCH"
    if bundle.get("schema") != BUNDLE_SCHEMA:
        return False, "BUNDLE_SCHEMA_MISMATCH"
    if bundle.get("version") != VERSION:
        return False, "BUNDLE_VERSION_MISMATCH"
    if bundle.get("core_version") != CORE_VERSION:
        return False, "BUNDLE_CORE_VERSION_MISMATCH"
    if bundle.get("canonicalization_id") != CANONICALIZATION_ID:
        return False, "BUNDLE_CANONICALIZATION_MISMATCH"
    if bundle.get("identity_domain_id") != identity_domain_id():
        return False, "BUNDLE_IDENTITY_DOMAIN_MISMATCH"
    try:
        expected = build_bundle(bundle.get("submitted_input"))
    except (PortableJSONError, TypeError, ValueError, MemoryError, RecursionError) as exc:
        return False, "BUNDLE_RECONSTRUCTION_FAILURE: " + str(exc)
    if canonical_json(bundle) != canonical_json(expected):
        return False, "BUNDLE_RECONSTRUCTION_MISMATCH"
    return True, "PASS"


def make_receipt(bundle: Dict[str, Any]) -> Dict[str, Any]:
    ok, reason = verify_bundle(bundle)
    if not ok:
        raise ValueError("cannot make receipt from invalid bundle: " + reason)
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
        "subject_ref": result["subject_ref"],
        "credential_ref": result["credential_ref"],
        "credential_version_before": result["credential_version_before"],
        "replacement_request_ref": result["replacement_request_ref"],
        "relying_party_ref": result["relying_party_ref"],
        "recovery_case_ref": result["recovery_case_ref"],
        "evidence_mode": result["evidence_mode"],
        "authorizer_count": result["authorizer_count"],
        "state": result["state"],
        "resolution_state": result["resolution_state"],
        "authorization_outcome": result["authorization_outcome"],
        "admission_state": result["admission_state"],
        "visibility_state": result["visibility_state"],
        "outcome_visible": result["outcome_visible"],
        "submission_id": result["submission_id"],
        "canonical_input_id": result["canonical_input_id"],
        "context_id": result["context_id"],
        "authorizer_manifest_id": result["authorizer_manifest_id"],
        "evidence_set_id": result["evidence_set_id"],
        "evidence_agreement_id": result["evidence_agreement_id"],
        "rule_profile_id": result["rule_profile_id"],
        "outcome_id": result["outcome_id"],
        "evaluation_evidence_id": result["evaluation_evidence_id"],
        "result_id": result["result_id"],
        "reason_codes": result["reason_codes"],
        "execution_authority": result["execution_authority"],
        "reset_authority": result["reset_authority"],
        "credential_mutation_authority": result["credential_mutation_authority"],
        "authentication_authority": result["authentication_authority"],
        "access_authority": result["access_authority"],
        "session_authority": result["session_authority"],
        "source_authenticity": result["source_authenticity"],
        "bundle_id": bundle["bundle_id"],
        "receipt_id": None,
    }
    receipt["receipt_id"] = identity(
        RECEIPT_ID_PREFIX,
        {key: value for key, value in receipt.items() if key != "receipt_id"},
    )
    return receipt


def verify_receipt(receipt: Any) -> Tuple[bool, str]:
    try:
        validate_portable_json(receipt)
    except PortableJSONError as exc:
        return False, "PORTABLE_JSON_BOUNDARY_FAILURE: " + str(exc)
    if not isinstance(receipt, dict):
        return False, "RECEIPT_OBJECT_REQUIRED"
    if set(receipt) != RECEIPT_KEYS:
        return False, "RECEIPT_FIELDS_MISMATCH"
    if receipt.get("schema") != RECEIPT_SCHEMA:
        return False, "RECEIPT_SCHEMA_MISMATCH"
    if receipt.get("version") != VERSION:
        return False, "RECEIPT_VERSION_MISMATCH"
    if receipt.get("core_version") != CORE_VERSION:
        return False, "RECEIPT_CORE_VERSION_MISMATCH"
    if receipt.get("canonicalization_id") != CANONICALIZATION_ID:
        return False, "RECEIPT_CANONICALIZATION_MISMATCH"
    if receipt.get("identity_domain_id") != identity_domain_id():
        return False, "RECEIPT_IDENTITY_DOMAIN_MISMATCH"
    expected_id = identity(
        RECEIPT_ID_PREFIX,
        {key: value for key, value in receipt.items() if key != "receipt_id"},
    )
    if receipt.get("receipt_id") != expected_id:
        return False, "RECEIPT_IDENTITY_MISMATCH"
    if receipt.get("execution_authority") != "NONE":
        return False, "EXECUTION_AUTHORITY_MISMATCH"
    if receipt.get("reset_authority") != "NONE":
        return False, "RESET_AUTHORITY_MISMATCH"
    if receipt.get("credential_mutation_authority") != "NONE":
        return False, "CREDENTIAL_MUTATION_AUTHORITY_MISMATCH"
    if receipt.get("authentication_authority") != "NONE":
        return False, "AUTHENTICATION_AUTHORITY_MISMATCH"
    if receipt.get("access_authority") != "NONE":
        return False, "ACCESS_AUTHORITY_MISMATCH"
    if receipt.get("session_authority") != "NONE":
        return False, "SESSION_AUTHORITY_MISMATCH"
    return True, "PASS"


def verify_receipt_against_bundle(receipt: Any, bundle: Any) -> Tuple[bool, str]:
    bundle_ok, bundle_reason = verify_bundle(bundle)
    if not bundle_ok:
        return False, "BUNDLE_INVALID: " + bundle_reason
    receipt_ok, receipt_reason = verify_receipt(receipt)
    if not receipt_ok:
        return False, "RECEIPT_INVALID: " + receipt_reason
    expected = make_receipt(bundle)
    if canonical_json(receipt) != canonical_json(expected):
        return False, "RECEIPT_BUNDLE_BINDING_MISMATCH"
    return True, "PASS"


def commitment(label: str) -> str:
    return "sha256:" + hashlib.sha256(label.encode("utf-8")).hexdigest()


def build_evidence_record(
    authorizer_id: str,
    evidence_id: str,
    outcome: str,
    context: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "authorizer_id": authorizer_id,
        "authorizer_profile_id": AUTHORIZER_PROFILE_ID,
        "subject_ref": context["subject_ref"],
        "credential_ref": context["credential_ref"],
        "credential_version_before": context["credential_version_before"],
        "replacement_request_ref": context["replacement_request_ref"],
        "relying_party_ref": context["relying_party_ref"],
        "recovery_case_ref": context["recovery_case_ref"],
        "authorization_result": outcome,
        "evidence_commitment": commitment(evidence_id + ":" + outcome),
    }


def attach_declared_identities(raw_input: Dict[str, Any]) -> Dict[str, Any]:
    candidate = copy.deepcopy(raw_input)
    context, context_issues = normalize_context(candidate.get("context"))
    if context is None or any(issue.state in {STATE_FORBIDDEN, STATE_UNSUPPORTED, STATE_INCOMPLETE, STATE_CONFLICT} for issue in context_issues):
        raise ValueError("context cannot be committed")
    evidence: List[Dict[str, Any]] = []
    for index, raw_record in enumerate(candidate.get("authorization_evidence", [])):
        record, record_issues = normalize_evidence_record(raw_record, index)
        if record is None or record_issues:
            raise ValueError("evidence cannot be committed")
        evidence.append(record)
    evidence = sorted(evidence, key=lambda record: (record["authorizer_id"], record["evidence_id"], canonical_json(record)))
    candidate["declared_context_id"] = identity(CONTEXT_ID_PREFIX, context_material(context))
    candidate["declared_evidence_set_id"] = identity(EVIDENCE_SET_ID_PREFIX, evidence_set_material(evidence))
    return candidate


def build_reference_input(outcome: str = OUTCOME_RESET_AUTHORIZED, visible: bool = True) -> Dict[str, Any]:
    context: Dict[str, Any] = {
        "evaluation_id": "RESET-EVALUATION-001",
        "subject_ref": "SUBJECT-ALPHA",
        "credential_ref": "CREDENTIAL-ALPHA",
        "credential_version_before": "CREDENTIAL-VERSION-003",
        "replacement_request_ref": "REPLACEMENT-REQUEST-001",
        "relying_party_ref": "RELYING-PARTY-PORTAL",
        "recovery_case_ref": "RECOVERY-CASE-001",
        "evidence_mode": EVIDENCE_SINGLE_AUTHORIZER,
        "expected_authorizer_ids": ["AUTHORIZER-A"],
        "evaluation_authorized": True,
        "reference_visibility_authorized": visible,
    }
    raw_input = {
        "schema": INPUT_SCHEMA,
        "profile_id": PROFILE_ID,
        "ruleset_id": RULESET_ID,
        "context": context,
        "authorization_evidence": [
            build_evidence_record("AUTHORIZER-A", "RESET-EVIDENCE-001", outcome, context)
        ],
    }
    return attach_declared_identities(raw_input)


def build_multi_authorizer_input(outcome: str = OUTCOME_RESET_AUTHORIZED) -> Dict[str, Any]:
    context: Dict[str, Any] = {
        "evaluation_id": "RESET-EVALUATION-002",
        "subject_ref": "SUBJECT-BETA",
        "credential_ref": "CREDENTIAL-BETA",
        "credential_version_before": "CREDENTIAL-VERSION-007",
        "replacement_request_ref": "REPLACEMENT-REQUEST-002",
        "relying_party_ref": "RELYING-PARTY-ADMIN",
        "recovery_case_ref": "RECOVERY-CASE-002",
        "evidence_mode": EVIDENCE_MULTI_AUTHORIZER,
        "expected_authorizer_ids": ["AUTHORIZER-A", "AUTHORIZER-B"],
        "evaluation_authorized": True,
        "reference_visibility_authorized": True,
    }
    raw_input = {
        "schema": INPUT_SCHEMA,
        "profile_id": PROFILE_ID,
        "ruleset_id": RULESET_ID,
        "context": context,
        "authorization_evidence": [
            build_evidence_record("AUTHORIZER-A", "RESET-EVIDENCE-201", outcome, context),
            build_evidence_record("AUTHORIZER-B", "RESET-EVIDENCE-202", outcome, context),
        ],
    }
    return attach_declared_identities(raw_input)


def strict_object_pairs(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError("duplicate JSON key: " + key)
        result[key] = value
    return result


def reject_nonfinite_constant(value: str) -> None:
    raise PortableJSONError("non-finite JSON number is not supported: " + value)


def reject_float_number(value: str) -> None:
    raise PortableJSONError("floating-point JSON number is not supported: " + value)


def parse_safe_integer(value: str) -> int:
    parsed = int(value)
    if abs(parsed) > MAX_SAFE_INTEGER:
        raise PortableJSONError("JSON integer exceeds portable safe range")
    return parsed


def loads_strict(text: str) -> Any:
    if not isinstance(text, str):
        raise TypeError("JSON text must be a string")
    if len(text.encode("utf-8")) > MAX_JSON_INPUT_BYTES:
        raise PortableJSONError("JSON input byte limit exceeded")
    value = json.loads(
        text,
        object_pairs_hook=strict_object_pairs,
        parse_constant=reject_nonfinite_constant,
        parse_float=reject_float_number,
        parse_int=parse_safe_integer,
    )
    validate_portable_json(value)
    return value


def load_json(path: Path) -> Any:
    data = path.read_bytes()
    if len(data) > MAX_JSON_INPUT_BYTES:
        raise PortableJSONError("JSON input byte limit exceeded")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PortableJSONError("JSON file must be UTF-8") from exc
    return loads_strict(text)


def json_file_bytes(value: Any) -> bytes:
    validate_portable_json(value)
    return (canonical_json(value) + "\n").encode("utf-8")


def write_json(path: Path, value: Any) -> None:
    path.write_bytes(json_file_bytes(value))


def mutate(source: Dict[str, Any], fn) -> Dict[str, Any]:
    candidate = copy.deepcopy(source)
    fn(candidate)
    return candidate


def presentation_reason_codes(result: Dict[str, Any]) -> List[str]:
    codes = list(result.get("reason_codes", []))
    if result.get("outcome_visible") is True:
        return codes
    if result.get("resolution_state") == STATE_RESOLVED:
        return [REASON_CODE_OUTCOME_WITHHELD]
    return unique_sorted(
        code for code in codes if code not in OUTCOME_REVEALING_REASON_CODES
    )[:MAX_REASON_CODES]


def public_summary(bundle: Dict[str, Any]) -> Dict[str, Any]:
    result = bundle["result"]
    visible = result.get("outcome_visible") is True
    summary: Dict[str, Any] = {
        "summary_schema": PUBLIC_SUMMARY_SCHEMA,
        "version": VERSION,
        "state": result["state"],
        "resolution_state": result["resolution_state"],
        "visibility_state": result["visibility_state"],
        "outcome_visible": visible,
        "outcome_fields_redacted": not visible,
        "authorization_outcome": result["authorization_outcome"] if visible else None,
        "admission_state": result["admission_state"] if visible else None,
        "reason_codes": presentation_reason_codes(result),
        "execution_authority": result["execution_authority"],
        "reset_authority": result["reset_authority"],
        "credential_mutation_authority": result["credential_mutation_authority"],
        "authentication_authority": result["authentication_authority"],
        "access_authority": result["access_authority"],
        "session_authority": result["session_authority"],
        "result_id": result["result_id"] if visible else None,
        "bundle_id": bundle["bundle_id"] if visible else None,
        "public_summary_id": None,
    }
    summary["public_summary_id"] = identity(
        PUBLIC_SUMMARY_ID_PREFIX,
        {key: value for key, value in summary.items() if key != "public_summary_id"},
    )
    return summary


def verify_public_summary(summary: Any) -> Tuple[bool, str]:
    try:
        validate_portable_json(summary)
    except PortableJSONError as exc:
        return False, "PORTABLE_JSON_BOUNDARY_FAILURE: " + str(exc)
    if not isinstance(summary, dict):
        return False, "PUBLIC_SUMMARY_OBJECT_REQUIRED"
    if set(summary) != PUBLIC_SUMMARY_KEYS:
        return False, "PUBLIC_SUMMARY_FIELDS_MISMATCH"
    if summary.get("summary_schema") != PUBLIC_SUMMARY_SCHEMA:
        return False, "PUBLIC_SUMMARY_SCHEMA_MISMATCH"
    if summary.get("version") != VERSION:
        return False, "PUBLIC_SUMMARY_VERSION_MISMATCH"
    expected_id = identity(
        PUBLIC_SUMMARY_ID_PREFIX,
        {key: value for key, value in summary.items() if key != "public_summary_id"},
    )
    if summary.get("public_summary_id") != expected_id:
        return False, "PUBLIC_SUMMARY_IDENTITY_MISMATCH"
    if summary.get("state") != summary.get("resolution_state"):
        return False, "PUBLIC_SUMMARY_STATE_MISMATCH"
    if summary.get("resolution_state") not in SUPPORTED_STATES:
        return False, "PUBLIC_SUMMARY_STATE_INVALID"
    for field, code in (
        ("execution_authority", "EXECUTION_AUTHORITY_MISMATCH"),
        ("reset_authority", "RESET_AUTHORITY_MISMATCH"),
        ("credential_mutation_authority", "CREDENTIAL_MUTATION_AUTHORITY_MISMATCH"),
        ("authentication_authority", "AUTHENTICATION_AUTHORITY_MISMATCH"),
        ("access_authority", "ACCESS_AUTHORITY_MISMATCH"),
        ("session_authority", "SESSION_AUTHORITY_MISMATCH"),
    ):
        if summary.get(field) != "NONE":
            return False, code
    reason_codes = summary.get("reason_codes")
    if (
        not isinstance(reason_codes, list)
        or len(reason_codes) > MAX_REASON_CODES
        or any(not isinstance(code, str) for code in reason_codes)
        or reason_codes != unique_sorted(reason_codes)
    ):
        return False, "PUBLIC_SUMMARY_REASON_CODES_INVALID"
    visible = summary.get("outcome_visible")
    if visible not in (True, False):
        return False, "PUBLIC_SUMMARY_VISIBILITY_INVALID"
    if summary.get("outcome_fields_redacted") != (visible is False):
        return False, "PUBLIC_SUMMARY_REDACTION_FLAG_MISMATCH"
    if visible is True:
        if summary.get("visibility_state") != VISIBILITY_VISIBLE:
            return False, "PUBLIC_SUMMARY_VISIBILITY_STATE_MISMATCH"
        outcome = summary.get("authorization_outcome")
        admission = summary.get("admission_state")
        if summary.get("resolution_state") != STATE_RESOLVED:
            return False, "PUBLIC_SUMMARY_VISIBLE_STATE_INVALID"
        if outcome == OUTCOME_RESET_AUTHORIZED:
            if admission != ADMISSION_ADMIT:
                return False, "PUBLIC_SUMMARY_ADMISSION_MISMATCH"
            if (
                "RESET_AUTHORIZATION_EVIDENCE_ADMITTED" not in reason_codes
                or "RESET_NOT_AUTHORIZED_EVIDENCE_ADMITTED" in reason_codes
            ):
                return False, "PUBLIC_SUMMARY_REASON_OUTCOME_MISMATCH"
        elif outcome == OUTCOME_RESET_NOT_AUTHORIZED:
            if admission != ADMISSION_DENY:
                return False, "PUBLIC_SUMMARY_ADMISSION_MISMATCH"
            if (
                "RESET_NOT_AUTHORIZED_EVIDENCE_ADMITTED" not in reason_codes
                or "RESET_AUTHORIZATION_EVIDENCE_ADMITTED" in reason_codes
            ):
                return False, "PUBLIC_SUMMARY_REASON_OUTCOME_MISMATCH"
        else:
            return False, "PUBLIC_SUMMARY_OUTCOME_INVALID"
        if not is_identity_with_prefix(summary.get("result_id"), RESULT_ID_PREFIX):
            return False, "PUBLIC_SUMMARY_RESULT_ID_INVALID"
        if not is_identity_with_prefix(summary.get("bundle_id"), BUNDLE_ID_PREFIX):
            return False, "PUBLIC_SUMMARY_BUNDLE_ID_INVALID"
    else:
        if summary.get("visibility_state") != VISIBILITY_WITHHELD:
            return False, "PUBLIC_SUMMARY_VISIBILITY_STATE_MISMATCH"
        if summary.get("authorization_outcome") is not None:
            return False, "PUBLIC_SUMMARY_OUTCOME_NOT_REDACTED"
        if summary.get("admission_state") is not None:
            return False, "PUBLIC_SUMMARY_ADMISSION_NOT_REDACTED"
        if summary.get("result_id") is not None:
            return False, "PUBLIC_SUMMARY_RESULT_ID_NOT_REDACTED"
        if summary.get("bundle_id") is not None:
            return False, "PUBLIC_SUMMARY_BUNDLE_ID_NOT_REDACTED"
        if any(code in OUTCOME_REVEALING_REASON_CODES for code in reason_codes):
            return False, "PUBLIC_SUMMARY_REASON_CODE_LEAK"
        if summary.get("resolution_state") == STATE_RESOLVED and reason_codes != [REASON_CODE_OUTCOME_WITHHELD]:
            return False, "PUBLIC_SUMMARY_WITHHELD_REASON_MISMATCH"
    return True, "PASS"


def verify_public_summary_against_bundle(summary: Any, bundle: Any) -> Tuple[bool, str]:
    bundle_ok, bundle_reason = verify_bundle(bundle)
    if not bundle_ok:
        return False, "BUNDLE_INVALID: " + bundle_reason
    summary_ok, summary_reason = verify_public_summary(summary)
    if not summary_ok:
        return False, "PUBLIC_SUMMARY_INVALID: " + summary_reason
    expected = public_summary(bundle)
    if canonical_json(summary) != canonical_json(expected):
        return False, "PUBLIC_SUMMARY_BUNDLE_BINDING_MISMATCH"
    return True, "PASS"


def required_visible_result_exit_code(summary: Dict[str, Any]) -> int:
    return 0 if summary.get("outcome_visible") is True else 3


def _strict_load_fails(text: str) -> bool:
    try:
        loads_strict(text)
    except (TypeError, ValueError, DuplicateKeyError, PortableJSONError):
        return True
    return False


def run_self_test() -> int:
    groups: Dict[str, List[Tuple[str, bool]]] = {}

    def check(group: str, name: str, condition: bool) -> None:
        groups.setdefault(group, []).append((name, bool(condition)))

    reference = build_reference_input()
    reference_result = resolve_reset_password(reference)
    reference_bundle = build_bundle(reference)
    reference_receipt = make_receipt(reference_bundle)
    reference_summary = public_summary(reference_bundle)
    not_authorized = build_reference_input(OUTCOME_RESET_NOT_AUTHORIZED)
    not_authorized_result = resolve_reset_password(not_authorized)
    multi = build_multi_authorizer_input()
    multi_result = resolve_reset_password(multi)

    check("REFERENCE", "reference state resolved", reference_result["state"] == STATE_RESOLVED)
    check("REFERENCE", "reference outcome authorized", reference_result["authorization_outcome"] == OUTCOME_RESET_AUTHORIZED)
    check("REFERENCE", "reference admission admit", reference_result["admission_state"] == ADMISSION_ADMIT)
    check("REFERENCE", "reference outcome visible", reference_result["outcome_visible"] is True)
    check("REFERENCE", "reference authorizer count", reference_result["authorizer_count"] == 1)
    check("REFERENCE", "reference no secret processing", reference_result["secret_material_processed"] is False)
    check("REFERENCE", "reference execution authority none", reference_result["execution_authority"] == "NONE")
    check("REFERENCE", "reference reset authority none", reference_result["reset_authority"] == "NONE")
    check("REFERENCE", "reference credential mutation authority none", reference_result["credential_mutation_authority"] == "NONE")
    check("REFERENCE", "reference authentication authority none", reference_result["authentication_authority"] == "NONE")
    check("REFERENCE", "reference access authority none", reference_result["access_authority"] == "NONE")
    check("REFERENCE", "reference session authority none", reference_result["session_authority"] == "NONE")
    check("REFERENCE", "source authenticity not established", reference_result["source_authenticity"] == "NOT_ESTABLISHED_BY_REFERENCE_PROFILE")
    check("REFERENCE", "identity ownership not established", reference_result["identity_ownership"] == "NOT_ESTABLISHED_BY_REFERENCE_PROFILE")

    check("NEGATIVE", "reset-not-authorized state resolved", not_authorized_result["state"] == STATE_RESOLVED)
    check("NEGATIVE", "reset-not-authorized outcome", not_authorized_result["authorization_outcome"] == OUTCOME_RESET_NOT_AUTHORIZED)
    check("NEGATIVE", "reset-not-authorized admission deny", not_authorized_result["admission_state"] == ADMISSION_DENY)
    check("NEGATIVE", "reset-not-authorized is not conflict", not_authorized_result["state"] != STATE_CONFLICT)
    check("NEGATIVE", "reset-not-authorized visible", not_authorized_result["outcome_visible"] is True)
    check("NEGATIVE", "reset-not-authorized result distinct", not_authorized_result["result_id"] != reference_result["result_id"])

    check("MULTI_AUTHORIZER", "multi state resolved", multi_result["state"] == STATE_RESOLVED)
    check("MULTI_AUTHORIZER", "multi outcome authorized", multi_result["authorization_outcome"] == OUTCOME_RESET_AUTHORIZED)
    check("MULTI_AUTHORIZER", "multi authorizer count", multi_result["authorizer_count"] == 2)
    check("MULTI_AUTHORIZER", "multi evidence mode", multi_result["evidence_mode"] == EVIDENCE_MULTI_AUTHORIZER)

    hidden = build_reference_input(visible=False)
    hidden_negative = build_reference_input(OUTCOME_RESET_NOT_AUTHORIZED, visible=False)
    hidden_result = resolve_reset_password(hidden)
    check("PRESENTATION", "hidden result remains resolved", hidden_result["state"] == STATE_RESOLVED)
    check("PRESENTATION", "hidden outcome retained in result", hidden_result["authorization_outcome"] == OUTCOME_RESET_AUTHORIZED)
    check("PRESENTATION", "hidden visibility state", hidden_result["visibility_state"] == VISIBILITY_WITHHELD)
    check("PRESENTATION", "hidden outcome flag false", hidden_result["outcome_visible"] is False)
    hidden_summary = public_summary(build_bundle(hidden))
    hidden_negative_summary = public_summary(build_bundle(hidden_negative))
    visible_summary = public_summary(reference_bundle)
    check("PRESENTATION", "hidden summary redacts outcome", hidden_summary["authorization_outcome"] is None)
    check("PRESENTATION", "hidden summary redacts admission", hidden_summary["admission_state"] is None)
    check("PRESENTATION", "hidden summary marks redaction", hidden_summary["outcome_fields_redacted"] is True)
    check("PRESENTATION", "hidden summary neutral reason", hidden_summary["reason_codes"] == [REASON_CODE_OUTCOME_WITHHELD])
    check("PRESENTATION", "hidden summary redacts result id", hidden_summary["result_id"] is None)
    check("PRESENTATION", "hidden summary redacts bundle id", hidden_summary["bundle_id"] is None)
    check("PRESENTATION", "hidden outcomes have identical summaries", canonical_json(hidden_summary) == canonical_json(hidden_negative_summary))
    check("PRESENTATION", "hidden summary contains no authorized token", "RESET_AUTHORIZED" not in canonical_json(hidden_summary))
    check("PRESENTATION", "hidden summary contains no not-authorized token", "RESET_NOT_AUTHORIZED" not in canonical_json(hidden_summary))
    check("PRESENTATION", "hidden summary contains no private identity prefix", RESULT_ID_PREFIX not in canonical_json(hidden_summary) and BUNDLE_ID_PREFIX not in canonical_json(hidden_summary))
    check("PRESENTATION", "visible summary shows outcome", visible_summary["authorization_outcome"] == OUTCOME_RESET_AUTHORIZED)
    check("PRESENTATION", "visible summary shows admission", visible_summary["admission_state"] == ADMISSION_ADMIT)
    check("PRESENTATION", "visible summary retains result id", is_identity_with_prefix(visible_summary["result_id"], RESULT_ID_PREFIX))
    check("PRESENTATION", "visible summary retains bundle id", is_identity_with_prefix(visible_summary["bundle_id"], BUNDLE_ID_PREFIX))
    check("PRESENTATION", "visible summary verifies", verify_public_summary(visible_summary) == (True, "PASS"))
    check("PRESENTATION", "hidden summary verifies", verify_public_summary(hidden_summary) == (True, "PASS"))
    check("PRESENTATION", "hidden summary bundle binding verifies", verify_public_summary_against_bundle(hidden_summary, build_bundle(hidden)) == (True, "PASS"))
    check("PRESENTATION", "visible result exit code", required_visible_result_exit_code(visible_summary) == 0)
    check("PRESENTATION", "hidden result exit code", required_visible_result_exit_code(hidden_summary) == 3)

    tampered_hidden_outcome = copy.deepcopy(hidden_summary)
    tampered_hidden_outcome["authorization_outcome"] = OUTCOME_RESET_AUTHORIZED
    tampered_hidden_outcome["public_summary_id"] = identity(
        PUBLIC_SUMMARY_ID_PREFIX,
        {key: value for key, value in tampered_hidden_outcome.items() if key != "public_summary_id"},
    )
    tampered_hidden_reason = copy.deepcopy(hidden_summary)
    tampered_hidden_reason["reason_codes"] = ["RESET_AUTHORIZATION_EVIDENCE_ADMITTED"]
    tampered_hidden_reason["public_summary_id"] = identity(
        PUBLIC_SUMMARY_ID_PREFIX,
        {key: value for key, value in tampered_hidden_reason.items() if key != "public_summary_id"},
    )
    tampered_hidden_result_id = copy.deepcopy(hidden_summary)
    tampered_hidden_result_id["result_id"] = hidden_result["result_id"]
    tampered_hidden_result_id["public_summary_id"] = identity(
        PUBLIC_SUMMARY_ID_PREFIX,
        {key: value for key, value in tampered_hidden_result_id.items() if key != "public_summary_id"},
    )
    tampered_hidden_bundle_id = copy.deepcopy(hidden_summary)
    tampered_hidden_bundle_id["bundle_id"] = build_bundle(hidden)["bundle_id"]
    tampered_hidden_bundle_id["public_summary_id"] = identity(
        PUBLIC_SUMMARY_ID_PREFIX,
        {key: value for key, value in tampered_hidden_bundle_id.items() if key != "public_summary_id"},
    )
    check("PRESENTATION", "tampered hidden outcome rejected", verify_public_summary(tampered_hidden_outcome)[1] == "PUBLIC_SUMMARY_OUTCOME_NOT_REDACTED")
    check("PRESENTATION", "tampered hidden reason rejected", verify_public_summary(tampered_hidden_reason)[1] == "PUBLIC_SUMMARY_REASON_CODE_LEAK")
    check("PRESENTATION", "tampered hidden result id rejected", verify_public_summary(tampered_hidden_result_id)[1] == "PUBLIC_SUMMARY_RESULT_ID_NOT_REDACTED")
    check("PRESENTATION", "tampered hidden bundle id rejected", verify_public_summary(tampered_hidden_bundle_id)[1] == "PUBLIC_SUMMARY_BUNDLE_ID_NOT_REDACTED")

    missing_context = mutate(reference, lambda value: value.pop("context"))
    missing_evidence = mutate(reference, lambda value: value.pop("authorization_evidence"))
    empty_evidence = mutate(reference, lambda value: value.__setitem__("authorization_evidence", []))
    missing_declared_context = mutate(reference, lambda value: value.pop("declared_context_id"))
    missing_declared_evidence = mutate(reference, lambda value: value.pop("declared_evidence_set_id"))
    for name, candidate in (
        ("missing context", missing_context),
        ("missing evidence", missing_evidence),
        ("empty evidence", empty_evidence),
        ("missing declared context", missing_declared_context),
        ("missing declared evidence", missing_declared_evidence),
    ):
        result = resolve_reset_password(candidate)
        check("INCOMPLETE", name + " state", result["state"] == STATE_INCOMPLETE)
        check("INCOMPLETE", name + " withheld", result["admission_state"] == ADMISSION_WITHHOLD)
        check("INCOMPLETE", name + " no outcome", result["authorization_outcome"] == OUTCOME_NONE)

    missing_context_field = mutate(reference, lambda value: value["context"].pop("replacement_request_ref"))
    missing_evidence_field = mutate(reference, lambda value: value["authorization_evidence"][0].pop("recovery_case_ref"))
    check("INCOMPLETE", "missing context field", resolve_reset_password(missing_context_field)["state"] == STATE_INCOMPLETE)
    check("INCOMPLETE", "missing evidence field", resolve_reset_password(missing_evidence_field)["state"] == STATE_INCOMPLETE)

    unauthorized = mutate(reference, lambda value: value["context"].__setitem__("evaluation_authorized", False))
    unauthorized = attach_declared_identities({key: value for key, value in unauthorized.items() if key not in {"declared_context_id", "declared_evidence_set_id"}})
    unauthorized_result = resolve_reset_password(unauthorized)
    check("ABSTAIN", "unauthorized state abstain", unauthorized_result["state"] == STATE_ABSTAIN)
    check("ABSTAIN", "unauthorized outcome none", unauthorized_result["authorization_outcome"] == OUTCOME_NONE)
    check("ABSTAIN", "unauthorized admission withheld", unauthorized_result["admission_state"] == ADMISSION_WITHHOLD)
    check("ABSTAIN", "unauthorized reason", "EVALUATION_NOT_AUTHORIZED" in unauthorized_result["reason_codes"])

    binding_fields = (
        ("subject_ref", "SUBJECT-BINDING-MISMATCH"),
        ("credential_ref", "CREDENTIAL-BINDING-MISMATCH"),
        ("credential_version_before", "CREDENTIAL-VERSION-999"),
        ("replacement_request_ref", "REPLACEMENT-REQUEST-999"),
        ("relying_party_ref", "RELYING-PARTY-OTHER"),
        ("recovery_case_ref", "RECOVERY-CASE-999"),
    )
    expected_codes = {
        "subject_ref": "SUBJECT_BINDING_MISMATCH",
        "credential_ref": "CREDENTIAL_BINDING_MISMATCH",
        "credential_version_before": "CREDENTIAL_VERSION_BEFORE_MISMATCH",
        "replacement_request_ref": "REPLACEMENT_REQUEST_BINDING_MISMATCH",
        "relying_party_ref": "RELYING_PARTY_BINDING_MISMATCH",
        "recovery_case_ref": "RECOVERY_CASE_BINDING_MISMATCH",
    }
    for field, replacement in binding_fields:
        candidate = mutate(reference, lambda value, f=field, r=replacement: value["authorization_evidence"][0].__setitem__(f, r))
        candidate = attach_declared_identities({key: value for key, value in candidate.items() if key not in {"declared_context_id", "declared_evidence_set_id"}})
        result = resolve_reset_password(candidate)
        check("CONTEXT_BINDING", field + " conflict state", result["state"] == STATE_CONFLICT)
        check("CONTEXT_BINDING", field + " reason", expected_codes[field] in result["reason_codes"])
        check("CONTEXT_BINDING", field + " outcome withheld", result["authorization_outcome"] == OUTCOME_NONE)

    disagreement = build_multi_authorizer_input()
    disagreement["authorization_evidence"][1]["authorization_result"] = OUTCOME_RESET_NOT_AUTHORIZED
    disagreement["authorization_evidence"][1]["evidence_commitment"] = commitment("disagreement")
    disagreement = attach_declared_identities({key: value for key, value in disagreement.items() if key not in {"declared_context_id", "declared_evidence_set_id"}})
    disagreement_result = resolve_reset_password(disagreement)
    check("AGREEMENT", "disagreement conflict", disagreement_result["state"] == STATE_CONFLICT)
    check("AGREEMENT", "disagreement reason", "EVIDENCE_RESULT_DISAGREEMENT" in disagreement_result["reason_codes"])
    check("AGREEMENT", "disagreement no majority", disagreement_result["authorization_outcome"] == OUTCOME_NONE)
    check(
        "AGREEMENT",
        "agreement material identity retained on disagreement",
        isinstance(disagreement_result["evidence_agreement_id"], str)
        and disagreement_result["evidence_agreement_id"].startswith(EVIDENCE_AGREEMENT_ID_PREFIX),
    )

    missing_authorizer = build_multi_authorizer_input()
    missing_authorizer["authorization_evidence"] = missing_authorizer["authorization_evidence"][:1]
    missing_authorizer = attach_declared_identities({key: value for key, value in missing_authorizer.items() if key not in {"declared_context_id", "declared_evidence_set_id"}})
    missing_authorizer_result = resolve_reset_password(missing_authorizer)
    check("AGREEMENT", "missing authorizer incomplete", missing_authorizer_result["state"] == STATE_INCOMPLETE)
    check("AGREEMENT", "missing authorizer reason", "EXPECTED_AUTHORIZER_EVIDENCE_MISSING" in missing_authorizer_result["reason_codes"])

    unexpected_authorizer = build_reference_input()
    context = unexpected_authorizer["context"]
    unexpected_authorizer["authorization_evidence"].append(build_evidence_record("AUTHORIZER-B", "EVIDENCE-002", OUTCOME_RESET_AUTHORIZED, context))
    unexpected_authorizer = attach_declared_identities({key: value for key, value in unexpected_authorizer.items() if key not in {"declared_context_id", "declared_evidence_set_id"}})
    unexpected_result = resolve_reset_password(unexpected_authorizer)
    check("AGREEMENT", "unexpected authorizer conflict", unexpected_result["state"] == STATE_CONFLICT)
    check("AGREEMENT", "unexpected authorizer reason", "UNEXPECTED_AUTHORIZER_EVIDENCE" in unexpected_result["reason_codes"])

    duplicate_evidence = build_multi_authorizer_input()
    duplicate_evidence["authorization_evidence"][1]["evidence_id"] = duplicate_evidence["authorization_evidence"][0]["evidence_id"]
    duplicate_evidence = attach_declared_identities({key: value for key, value in duplicate_evidence.items() if key not in {"declared_context_id", "declared_evidence_set_id"}})
    duplicate_result = resolve_reset_password(duplicate_evidence)
    check("AGREEMENT", "duplicate evidence conflict", duplicate_result["state"] == STATE_CONFLICT)
    check("AGREEMENT", "duplicate evidence reason", "DUPLICATE_EVIDENCE_ID" in duplicate_result["reason_codes"])

    duplicate_authorizer = build_multi_authorizer_input()
    duplicate_authorizer["authorization_evidence"][1]["authorizer_id"] = duplicate_authorizer["authorization_evidence"][0]["authorizer_id"]
    duplicate_authorizer = attach_declared_identities({key: value for key, value in duplicate_authorizer.items() if key not in {"declared_context_id", "declared_evidence_set_id"}})
    duplicate_authorizer_result = resolve_reset_password(duplicate_authorizer)
    check("AGREEMENT", "duplicate authorizer conflict", duplicate_authorizer_result["state"] == STATE_CONFLICT)
    check("AGREEMENT", "duplicate authorizer reason", "DUPLICATE_AUTHORIZER_ID" in duplicate_authorizer_result["reason_codes"])

    forbidden_cases = (
        ("raw password", "password", "NotARealPassword"),
        ("new password", "new_password", "NotARealNewPassword"),
        ("reset token", "reset_token", "NotARealResetToken"),
        ("one-time password", "otp", "123456"),
        ("recovery code", "recovery_code", "NotARealRecoveryCode"),
        ("raw secret", "secret", "NotARealSecret"),
        ("password hash", "password_hash", "hash-value"),
        ("stored hash", "stored_hash", "hash-value"),
        ("salt", "salt", "salt-value"),
        ("pepper", "pepper", "pepper-value"),
        ("session token", "session_token", "token-value"),
        ("access token", "access_token", "token-value"),
        ("caller authenticated", "authenticated", True),
        ("caller reset authorized", "reset_authorized", True),
        ("caller credential replaced", "credential_replaced", True),
        ("caller reset authority", "reset_authority", "GRANTED"),
        ("caller access", "access", "GRANTED"),
        ("caller outcome", "authorization_outcome", OUTCOME_RESET_AUTHORIZED),
        ("caller result id", "result_id", RESULT_ID_PREFIX + ("0" * 64)),
        ("caller public summary id", "public_summary_id", PUBLIC_SUMMARY_ID_PREFIX + ("0" * 64)),
    )
    for name, key, value in forbidden_cases:
        candidate = mutate(reference, lambda item, k=key, v=value: item.__setitem__(k, v))
        result = resolve_reset_password(candidate)
        bundle = build_bundle(candidate)
        serialized = canonical_json(bundle)
        check("FORBIDDEN", name + " state", result["state"] == STATE_FORBIDDEN)
        check("FORBIDDEN", name + " reason", "FORBIDDEN_FIELD_PRESENT" in result["reason_codes"] or "CALLER_DERIVED_FIELD_FORBIDDEN" in result["reason_codes"])
        check("FORBIDDEN", name + " no outcome", result["authorization_outcome"] == OUTCOME_NONE)
        check(
            "PRIVACY",
            name + " value redacted",
            bundle["submitted_input"].get(key) == "<FORBIDDEN_VALUE_REDACTED>",
        )
        check("PRIVACY", name + " redaction marker", "<FORBIDDEN_VALUE_REDACTED>" in serialized)

    nested_secret = mutate(reference, lambda value: value["context"].__setitem__("metadata", {"password": "NestedSecret"}))
    nested_result = resolve_reset_password(nested_secret)
    nested_bundle = build_bundle(nested_secret)
    check("FORBIDDEN", "nested secret forbidden", nested_result["state"] == STATE_FORBIDDEN)
    check("PRIVACY", "nested secret redacted", "NestedSecret" not in canonical_json(nested_bundle))

    unsupported_cases = []
    unsupported_cases.append(("schema", mutate(reference, lambda value: value.__setitem__("schema", "OTHER-SCHEMA")), "UNSUPPORTED_SCHEMA"))
    unsupported_cases.append(("profile", mutate(reference, lambda value: value.__setitem__("profile_id", "OTHER-PROFILE")), "UNSUPPORTED_PROFILE"))
    unsupported_cases.append(("ruleset", mutate(reference, lambda value: value.__setitem__("ruleset_id", "OTHER-RULESET")), "UNSUPPORTED_RULESET"))
    unsupported_cases.append(("evidence mode", mutate(reference, lambda value: value["context"].__setitem__("evidence_mode", "MAJORITY")), "UNSUPPORTED_EVIDENCE_MODE"))
    unsupported_cases.append(("authorizer profile", mutate(reference, lambda value: value["authorization_evidence"][0].__setitem__("authorizer_profile_id", "OTHER-AUTHORIZER-PROFILE")), "UNSUPPORTED_AUTHORIZER_PROFILE"))
    unsupported_cases.append(("authorization result", mutate(reference, lambda value: value["authorization_evidence"][0].__setitem__("authorization_result", "UNKNOWN")), "UNSUPPORTED_AUTHORIZATION_RESULT"))
    unsupported_cases.append(("unknown top-level field", mutate(reference, lambda value: value.__setitem__("extension", "VALUE")), "UNKNOWN_FIELD"))
    unsupported_cases.append(("unknown context field", mutate(reference, lambda value: value["context"].__setitem__("extension", "VALUE")), "UNKNOWN_FIELD"))
    unsupported_cases.append(("unknown evidence field", mutate(reference, lambda value: value["authorization_evidence"][0].__setitem__("extension", "VALUE")), "UNKNOWN_FIELD"))
    for name, candidate, code in unsupported_cases:
        result = resolve_reset_password(candidate)
        check("UNSUPPORTED", name + " state", result["state"] == STATE_UNSUPPORTED)
        check("UNSUPPORTED", name + " reason", code in result["reason_codes"])
        check("UNSUPPORTED", name + " no outcome", result["authorization_outcome"] == OUTCOME_NONE)

    malformed_commitment = mutate(reference, lambda value: value["authorization_evidence"][0].__setitem__("evidence_commitment", "sha256:ABC"))
    malformed_result = resolve_reset_password(malformed_commitment)
    check("UNSUPPORTED", "malformed commitment state", malformed_result["state"] == STATE_UNSUPPORTED)
    check("UNSUPPORTED", "malformed commitment reason", "INVALID_EVIDENCE_COMMITMENT" in malformed_result["reason_codes"])

    declared_context_mismatch = mutate(reference, lambda value: value.__setitem__("declared_context_id", CONTEXT_ID_PREFIX + ("0" * 64)))
    declared_evidence_mismatch = mutate(reference, lambda value: value.__setitem__("declared_evidence_set_id", EVIDENCE_SET_ID_PREFIX + ("0" * 64)))
    check("IDENTITY", "declared context mismatch conflict", resolve_reset_password(declared_context_mismatch)["state"] == STATE_CONFLICT)
    check("IDENTITY", "declared evidence mismatch conflict", resolve_reset_password(declared_evidence_mismatch)["state"] == STATE_CONFLICT)
    check("IDENTITY", "declared context mismatch reason", "DECLARED_IDENTITY_MISMATCH" in resolve_reset_password(declared_context_mismatch)["reason_codes"])
    check("IDENTITY", "declared evidence mismatch reason", "DECLARED_IDENTITY_MISMATCH" in resolve_reset_password(declared_evidence_mismatch)["reason_codes"])

    malformed_declared_context = mutate(reference, lambda value: value.__setitem__("declared_context_id", "bad"))
    malformed_declared_evidence = mutate(reference, lambda value: value.__setitem__("declared_evidence_set_id", "bad"))
    check("IDENTITY", "malformed declared context unsupported", resolve_reset_password(malformed_declared_context)["state"] == STATE_UNSUPPORTED)
    check("IDENTITY", "malformed declared evidence unsupported", resolve_reset_password(malformed_declared_evidence)["state"] == STATE_UNSUPPORTED)

    identity_prefixes = (
        ("submission", reference_result["submission_id"], SUBMISSION_ID_PREFIX),
        ("canonical input", reference_result["canonical_input_id"], CANONICAL_INPUT_ID_PREFIX),
        ("context", reference_result["context_id"], CONTEXT_ID_PREFIX),
        ("authorizer manifest", reference_result["authorizer_manifest_id"], AUTHORIZER_MANIFEST_ID_PREFIX),
        ("evidence set", reference_result["evidence_set_id"], EVIDENCE_SET_ID_PREFIX),
        ("evidence agreement", reference_result["evidence_agreement_id"], EVIDENCE_AGREEMENT_ID_PREFIX),
        ("rule profile", reference_result["rule_profile_id"], RULE_PROFILE_ID_PREFIX),
        ("outcome", reference_result["outcome_id"], OUTCOME_ID_PREFIX),
        ("evaluation evidence", reference_result["evaluation_evidence_id"], EVALUATION_EVIDENCE_ID_PREFIX),
        ("result", reference_result["result_id"], RESULT_ID_PREFIX),
        ("bundle", reference_bundle["bundle_id"], BUNDLE_ID_PREFIX),
        ("receipt", reference_receipt["receipt_id"], RECEIPT_ID_PREFIX),
        ("public summary", reference_summary["public_summary_id"], PUBLIC_SUMMARY_ID_PREFIX),
    )
    for name, value, prefix in identity_prefixes:
        check("IDENTITY", name + " prefix", isinstance(value, str) and value.startswith(prefix))
        check("IDENTITY", name + " digest length", isinstance(value, str) and len(value[len(prefix):]) == 64)

    repeated_result = resolve_reset_password(copy.deepcopy(reference))
    repeated_bundle = build_bundle(copy.deepcopy(reference))
    repeated_receipt = make_receipt(repeated_bundle)
    repeated_summary = public_summary(repeated_bundle)
    check("DETERMINISM", "result exact repeat", canonical_json(repeated_result) == canonical_json(reference_result))
    check("DETERMINISM", "bundle exact repeat", canonical_json(repeated_bundle) == canonical_json(reference_bundle))
    check("DETERMINISM", "receipt exact repeat", canonical_json(repeated_receipt) == canonical_json(reference_receipt))
    check("DETERMINISM", "result id exact repeat", repeated_result["result_id"] == reference_result["result_id"])
    check("DETERMINISM", "bundle id exact repeat", repeated_bundle["bundle_id"] == reference_bundle["bundle_id"])
    check("DETERMINISM", "receipt id exact repeat", repeated_receipt["receipt_id"] == reference_receipt["receipt_id"])
    check("DETERMINISM", "public summary exact repeat", canonical_json(repeated_summary) == canonical_json(reference_summary))
    check("DETERMINISM", "public summary id exact repeat", repeated_summary["public_summary_id"] == reference_summary["public_summary_id"])

    reordered_top = {key: reference[key] for key in reversed(list(reference.keys()))}
    reordered_context = copy.deepcopy(reference)
    reordered_context["context"] = {key: reordered_context["context"][key] for key in reversed(list(reordered_context["context"].keys()))}
    reordered_evidence_fields = copy.deepcopy(reference)
    record = reordered_evidence_fields["authorization_evidence"][0]
    reordered_evidence_fields["authorization_evidence"][0] = {key: record[key] for key in reversed(list(record.keys()))}
    reordered_multi = copy.deepcopy(multi)
    reordered_multi["authorization_evidence"] = list(reversed(reordered_multi["authorization_evidence"]))
    check("ORDER_INDEPENDENCE", "top-level key order", resolve_reset_password(reordered_top)["result_id"] == reference_result["result_id"])
    check("ORDER_INDEPENDENCE", "context key order", resolve_reset_password(reordered_context)["result_id"] == reference_result["result_id"])
    check("ORDER_INDEPENDENCE", "evidence field order", resolve_reset_password(reordered_evidence_fields)["result_id"] == reference_result["result_id"])
    check("ORDER_INDEPENDENCE", "evidence record order", resolve_reset_password(reordered_multi)["result_id"] == multi_result["result_id"])
    check("ORDER_INDEPENDENCE", "evidence set identity order", resolve_reset_password(reordered_multi)["evidence_set_id"] == multi_result["evidence_set_id"])

    normalized_case = copy.deepcopy(reference)
    normalized_case["context"]["subject_ref"] = " subject-alpha "
    normalized_case["authorization_evidence"][0]["subject_ref"] = "subject-alpha"
    normalized_case = attach_declared_identities({key: value for key, value in normalized_case.items() if key not in {"declared_context_id", "declared_evidence_set_id"}})
    normalized_case_result = resolve_reset_password(normalized_case)
    check("NORMALIZATION", "identifier case normalized", normalized_case_result["subject_ref"] == "SUBJECT-ALPHA")
    check("NORMALIZATION", "normalized case resolved", normalized_case_result["state"] == STATE_RESOLVED)

    ascii_trimmed_case = copy.deepcopy(reference)
    ascii_trimmed_case["context"]["subject_ref"] = "\t subject-alpha \r\n"
    ascii_trimmed_case["authorization_evidence"][0]["subject_ref"] = " subject-alpha\t"
    ascii_trimmed_case = attach_declared_identities(
        {
            key: value
            for key, value in ascii_trimmed_case.items()
            if key not in {"declared_context_id", "declared_evidence_set_id"}
        }
    )
    ascii_trimmed_result = resolve_reset_password(ascii_trimmed_case)
    check("NORMALIZATION", "ASCII trim characters admitted", ascii_trimmed_result["state"] == STATE_RESOLVED)
    check("NORMALIZATION", "ASCII trim characters normalized", ascii_trimmed_result["subject_ref"] == "SUBJECT-ALPHA")
    check("NORMALIZATION", "NEL identifier rejected", normalize_identifier("SUBJECT-ALPHA\u0085") is None)
    check("NORMALIZATION", "NBSP identifier rejected", normalize_identifier("SUBJECT-ALPHA\u00a0") is None)
    check("NORMALIZATION", "EM SPACE identifier rejected", normalize_identifier("\u2003SUBJECT-ALPHA") is None)
    check("NORMALIZATION", "sharp-s identifier rejected", normalize_identifier("ßprint") is None)
    check("NORMALIZATION", "ligature identifier rejected", normalize_identifier("ﬁle") is None)
    check("NORMALIZATION", "fullwidth identifier rejected", normalize_identifier("ＳUBJECT-ALPHA") is None)
    commitment_value = commitment("ASCII-LEXICAL-TEST")
    check(
        "NORMALIZATION",
        "ASCII commitment trim and case normalization",
        normalize_commitment(" \t" + commitment_value.upper() + "\r\n") == commitment_value,
    )
    check("NORMALIZATION", "NEL commitment rejected", normalize_commitment(commitment_value + "\u0085") is None)
    check("NORMALIZATION", "NBSP commitment rejected", normalize_commitment(commitment_value + "\u00a0") is None)
    check(
        "NORMALIZATION",
        "non-ASCII commitment character rejected",
        normalize_commitment("sha256:" + ("a" * 63) + "ａ") is None,
    )

    padded_forbidden = mutate(reference, lambda value: value.__setitem__(" PASSWORD ", "PaddedSecret"))
    padded_forbidden_result = resolve_reset_password(padded_forbidden)
    padded_forbidden_bundle = build_bundle(padded_forbidden)
    nested_mixed_case_forbidden = mutate(
        reference,
        lambda value: value.__setitem__("container", {"Password": "NestedCaseSecret"}),
    )
    non_ascii_forbidden_name = mutate(
        reference,
        lambda value: value.__setitem__("password\u0085", "NotNameMatched"),
    )
    non_ascii_lookalike_name = mutate(
        reference,
        lambda value: value.__setitem__("ｐassword", "NotNameMatched"),
    )
    check("FORBIDDEN", "ASCII-padded forbidden field detected", padded_forbidden_result["state"] == STATE_FORBIDDEN)
    check(
        "PRIVACY",
        "ASCII-padded forbidden field redacted",
        "PaddedSecret" not in canonical_json(padded_forbidden_bundle)
        and "<FORBIDDEN_VALUE_REDACTED>" in canonical_json(padded_forbidden_bundle),
    )
    check(
        "FORBIDDEN",
        "nested mixed-case forbidden field detected",
        resolve_reset_password(nested_mixed_case_forbidden)["state"] == STATE_FORBIDDEN,
    )
    non_ascii_forbidden_result = resolve_reset_password(non_ascii_forbidden_name)
    non_ascii_lookalike_result = resolve_reset_password(non_ascii_lookalike_name)
    check("UNSUPPORTED", "non-ASCII-suffixed field name unsupported", non_ascii_forbidden_result["state"] == STATE_UNSUPPORTED)
    check(
        "UNSUPPORTED",
        "non-ASCII-suffixed field name not folded to forbidden",
        "FORBIDDEN_FIELD_PRESENT" not in non_ascii_forbidden_result["reason_codes"],
    )
    check("UNSUPPORTED", "non-ASCII lookalike field name unsupported", non_ascii_lookalike_result["state"] == STATE_UNSUPPORTED)
    check(
        "UNSUPPORTED",
        "non-ASCII lookalike field name not folded to forbidden",
        "FORBIDDEN_FIELD_PRESENT" not in non_ascii_lookalike_result["reason_codes"],
    )

    changed_request = copy.deepcopy(reference)
    changed_request["context"]["replacement_request_ref"] = "REPLACEMENT-REQUEST-NEW"
    changed_request["authorization_evidence"][0]["replacement_request_ref"] = "REPLACEMENT-REQUEST-NEW"
    changed_request = attach_declared_identities({key: value for key, value in changed_request.items() if key not in {"declared_context_id", "declared_evidence_set_id"}})
    changed_request_result = resolve_reset_password(changed_request)
    check("IDENTITY_CHANGE", "request changes context id", changed_request_result["context_id"] != reference_result["context_id"])
    check("IDENTITY_CHANGE", "request changes canonical id", changed_request_result["canonical_input_id"] != reference_result["canonical_input_id"])
    check("IDENTITY_CHANGE", "request changes result id", changed_request_result["result_id"] != reference_result["result_id"])

    changed_version = copy.deepcopy(reference)
    changed_version["context"]["credential_version_before"] = "VERSION-004"
    changed_version["authorization_evidence"][0]["credential_version_before"] = "VERSION-004"
    changed_version = attach_declared_identities({key: value for key, value in changed_version.items() if key not in {"declared_context_id", "declared_evidence_set_id"}})
    changed_version_result = resolve_reset_password(changed_version)
    check("IDENTITY_CHANGE", "credential version changes context id", changed_version_result["context_id"] != reference_result["context_id"])
    check("IDENTITY_CHANGE", "credential version changes result id", changed_version_result["result_id"] != reference_result["result_id"])

    changed_commitment = copy.deepcopy(reference)
    changed_commitment["authorization_evidence"][0]["evidence_commitment"] = commitment("different-evidence")
    changed_commitment = attach_declared_identities({key: value for key, value in changed_commitment.items() if key not in {"declared_context_id", "declared_evidence_set_id"}})
    changed_commitment_result = resolve_reset_password(changed_commitment)
    check("IDENTITY_CHANGE", "commitment changes evidence set id", changed_commitment_result["evidence_set_id"] != reference_result["evidence_set_id"])
    check("IDENTITY_CHANGE", "commitment changes result id", changed_commitment_result["result_id"] != reference_result["result_id"])

    precedence_forbidden_over_conflict = mutate(
        reference,
        lambda value: (
            value.__setitem__("password", "secret"),
            value.__setitem__("declared_context_id", CONTEXT_ID_PREFIX + ("0" * 64)),
        ),
    )
    precedence_forbidden_over_incomplete = mutate(
        reference,
        lambda value: (value.__setitem__("password", "secret"), value.pop("context")),
    )
    precedence_conflict_over_unsupported = copy.deepcopy(reference)
    precedence_conflict_over_unsupported["authorization_evidence"][0]["subject_ref"] = "SUBJECT-OTHER"
    precedence_conflict_over_unsupported["profile_id"] = "OTHER-PROFILE"
    precedence_conflict_over_incomplete = mutate(
        reference,
        lambda value: (
            value.__setitem__("declared_context_id", CONTEXT_ID_PREFIX + ("0" * 64)),
            value.pop("authorization_evidence"),
        ),
    )
    precedence_unsupported_over_incomplete = mutate(
        reference,
        lambda value: (value.__setitem__("profile_id", "OTHER-PROFILE"), value.pop("context")),
    )
    precedence_unsupported_over_abstain = copy.deepcopy(reference)
    precedence_unsupported_over_abstain["profile_id"] = "OTHER-PROFILE"
    precedence_unsupported_over_abstain["context"]["evaluation_authorized"] = False
    precedence_unsupported_over_abstain = attach_declared_identities(
        {
            key: value
            for key, value in precedence_unsupported_over_abstain.items()
            if key not in {"declared_context_id", "declared_evidence_set_id"}
        }
    )
    precedence_abstain = copy.deepcopy(reference)
    precedence_abstain["context"]["evaluation_authorized"] = False
    precedence_abstain = attach_declared_identities(
        {
            key: value
            for key, value in precedence_abstain.items()
            if key not in {"declared_context_id", "declared_evidence_set_id"}
        }
    )
    precedence_incomplete_over_abstain = mutate(
        precedence_abstain,
        lambda value: value.pop("declared_context_id"),
    )
    precedence_incomplete_result = resolve_reset_password(precedence_incomplete_over_abstain)
    check(
        "PRECEDENCE",
        "forbidden over conflict",
        resolve_reset_password(precedence_forbidden_over_conflict)["state"] == STATE_FORBIDDEN,
    )
    check(
        "PRECEDENCE",
        "forbidden over incomplete",
        resolve_reset_password(precedence_forbidden_over_incomplete)["state"] == STATE_FORBIDDEN,
    )
    check(
        "PRECEDENCE",
        "conflict over unsupported",
        resolve_reset_password(precedence_conflict_over_unsupported)["state"] == STATE_CONFLICT,
    )
    check(
        "PRECEDENCE",
        "conflict over incomplete",
        resolve_reset_password(precedence_conflict_over_incomplete)["state"] == STATE_CONFLICT,
    )
    check(
        "PRECEDENCE",
        "unsupported over incomplete",
        resolve_reset_password(precedence_unsupported_over_incomplete)["state"] == STATE_UNSUPPORTED,
    )
    check(
        "PRECEDENCE",
        "unsupported over abstain",
        resolve_reset_password(precedence_unsupported_over_abstain)["state"] == STATE_UNSUPPORTED,
    )
    check(
        "PRECEDENCE",
        "incomplete over abstain",
        precedence_incomplete_result["state"] == STATE_INCOMPLETE,
    )
    check(
        "PRECEDENCE",
        "incomplete over abstain retains both reasons",
        "EVALUATION_NOT_AUTHORIZED" in precedence_incomplete_result["reason_codes"]
        and "MISSING_DECLARED_IDENTITY" in precedence_incomplete_result["reason_codes"],
    )
    check(
        "PRECEDENCE",
        "abstain when unauthorized is the only issue",
        resolve_reset_password(precedence_abstain)["state"] == STATE_ABSTAIN,
    )
    check(
        "PRECEDENCE",
        "resolved when no issue exists",
        reference_result["state"] == STATE_RESOLVED,
    )

    oversized_evidence = copy.deepcopy(reference)
    context = oversized_evidence["context"]
    oversized_evidence["authorization_evidence"] = [
        build_evidence_record(f"AUTHORIZER-{index}", f"EVIDENCE-{index}", OUTCOME_RESET_AUTHORIZED, context)
        for index in range(MAX_EVIDENCE_RECORDS + 1)
    ]
    oversized_result = resolve_reset_password(oversized_evidence)
    check("RESOURCE", "evidence record limit", oversized_result["state"] == STATE_UNSUPPORTED)
    check("RESOURCE", "evidence record reason", "EVIDENCE_RECORD_LIMIT_EXCEEDED" in oversized_result["reason_codes"])

    long_identifier = mutate(reference, lambda value: value["context"].__setitem__("subject_ref", "A" * (MAX_IDENTIFIER_LENGTH + 1)))
    long_string = {"value": "A" * (MAX_STRING_LENGTH + 1)}
    check("RESOURCE", "identifier length rejected", resolve_reset_password(long_identifier)["state"] == STATE_UNSUPPORTED)
    try:
        validate_portable_json(long_string)
        long_string_rejected = False
    except PortableJSONError:
        long_string_rejected = True
    check("RESOURCE", "string length rejected", long_string_rejected)

    deep_value: Any = 0
    for _ in range(MAX_JSON_DEPTH + 1):
        deep_value = [deep_value]
    try:
        validate_portable_json(deep_value)
        deep_value_rejected = False
    except PortableJSONError:
        deep_value_rejected = True
    check("RESOURCE", "depth limit rejected", deep_value_rejected)

    node_limit_value = [[0 for _ in range(195)] for _ in range(256)]
    try:
        validate_portable_json(node_limit_value)
        node_limit_rejected = False
    except PortableJSONError:
        node_limit_rejected = True
    check("RESOURCE", "node limit rejected", node_limit_rejected)

    direct_value = [["REFERENCE-VALUE-0001" for _ in range(194)] for _ in range(256)]
    try:
        validate_portable_json(direct_value)
        direct_value_accepted = True
    except PortableJSONError:
        direct_value_accepted = False
    direct_value_text = canonical_json(direct_value)
    check("RESOURCE", "direct object within structural limits", direct_value_accepted)
    check(
        "RESOURCE",
        "serialized byte ceiling applies to JSON text",
        len(direct_value_text.encode("utf-8")) > MAX_JSON_INPUT_BYTES
        and _strict_load_fails(direct_value_text),
    )
    try:
        resolve_reset_password(direct_value)
        direct_resolver_rejected = False
    except PortableJSONError:
        direct_resolver_rejected = True
    try:
        build_bundle(direct_value)
        direct_bundle_rejected = False
    except PortableJSONError:
        direct_bundle_rejected = True
    check("RESOURCE", "direct resolver canonical byte ceiling", direct_resolver_rejected)
    check("RESOURCE", "direct bundle canonical byte ceiling", direct_bundle_rejected)

    diagnostic_issues = []
    for index in range(MAX_REASON_CODES + 16):
        diagnostic_issues.extend(
            [
                ValidationIssue(STATE_INCOMPLETE, f"MISSING_{index:03d}", "resource-test"),
                ValidationIssue(STATE_CONFLICT, f"CONFLICT_{index:03d}", "resource-test"),
                ValidationIssue(STATE_FORBIDDEN, f"FORBIDDEN_{index:03d}", "resource-test"),
                ValidationIssue(STATE_UNSUPPORTED, f"UNSUPPORTED_{index:03d}", "resource-test"),
            ]
        )
    bounded_reason_codes, bounded_missing, bounded_conflicts, bounded_prohibitions, bounded_unsupported = issue_lists(diagnostic_issues)
    check("RESOURCE", "reason code list capped", len(bounded_reason_codes) == MAX_REASON_CODES)
    check("RESOURCE", "missing dependency list capped", len(bounded_missing) == MAX_REASON_CODES)
    check("RESOURCE", "conflict list capped", len(bounded_conflicts) == MAX_REASON_CODES)
    check("RESOURCE", "prohibition list capped", len(bounded_prohibitions) == MAX_REASON_CODES)
    check("RESOURCE", "unsupported feature list capped", len(bounded_unsupported) == MAX_REASON_CODES)

    check("PARSER", "duplicate key rejected", _strict_load_fails('{"a":1,"a":2}'))
    check("PARSER", "floating point rejected", _strict_load_fails('{"value":1.5}'))
    check("PARSER", "NaN rejected", _strict_load_fails('{"value":NaN}'))
    check("PARSER", "Infinity rejected", _strict_load_fails('{"value":Infinity}'))
    check("PARSER", "unsafe integer rejected", _strict_load_fails('{"value":9007199254740992}'))
    check("PARSER", "ordinary integer accepted", not _strict_load_fails('{"value":42}'))
    check("PARSER", "ordinary object accepted", not _strict_load_fails('{"value":"ok"}'))
    check("PARSER", "top-level array parsed", not _strict_load_fails('[1,2,3]'))
    check("PARSER", "top-level array unsupported by resolver", resolve_reset_password([1, 2, 3])["state"] == STATE_UNSUPPORTED)

    bundle_ok, bundle_reason = verify_bundle(reference_bundle)
    receipt_ok, receipt_reason = verify_receipt(reference_receipt)
    binding_ok, binding_reason = verify_receipt_against_bundle(reference_receipt, reference_bundle)
    summary_ok, summary_reason = verify_public_summary(reference_summary)
    summary_binding_ok, summary_binding_reason = verify_public_summary_against_bundle(reference_summary, reference_bundle)
    check("EVIDENCE", "bundle verifies", bundle_ok and bundle_reason == "PASS")
    check("EVIDENCE", "receipt verifies", receipt_ok and receipt_reason == "PASS")
    check("EVIDENCE", "receipt binding verifies", binding_ok and binding_reason == "PASS")
    check("EVIDENCE", "public summary verifies", summary_ok and summary_reason == "PASS")
    check("EVIDENCE", "public summary binding verifies", summary_binding_ok and summary_binding_reason == "PASS")
    check("EVIDENCE", "bundle exact fields", set(reference_bundle) == BUNDLE_KEYS)
    check("EVIDENCE", "receipt exact fields", set(reference_receipt) == RECEIPT_KEYS)
    check("EVIDENCE", "public summary exact fields", set(reference_summary) == PUBLIC_SUMMARY_KEYS)

    tampered_bundle = copy.deepcopy(reference_bundle)
    tampered_bundle["result"]["admission_state"] = ADMISSION_DENY
    tampered_bundle_id = copy.deepcopy(reference_bundle)
    tampered_bundle_id["bundle_id"] = BUNDLE_ID_PREFIX + ("0" * 64)
    tampered_receipt = copy.deepcopy(reference_receipt)
    tampered_receipt["state"] = STATE_CONFLICT
    unrelated_receipt = make_receipt(build_bundle(not_authorized))
    check("EVIDENCE", "tampered bundle rejected", verify_bundle(tampered_bundle)[0] is False)
    check("EVIDENCE", "tampered bundle id rejected", verify_bundle(tampered_bundle_id)[0] is False)
    check("EVIDENCE", "tampered receipt rejected", verify_receipt(tampered_receipt)[0] is False)
    check("EVIDENCE", "unrelated receipt binding rejected", verify_receipt_against_bundle(unrelated_receipt, reference_bundle)[0] is False)

    secret_bundle = build_bundle(mutate(reference, lambda value: value.__setitem__("password", "DictionaryWord")))
    secret_receipt = make_receipt(secret_bundle)
    check("PRIVACY", "bundle contains no raw password", "DictionaryWord" not in canonical_json(secret_bundle))
    check("PRIVACY", "receipt contains no raw password", "DictionaryWord" not in canonical_json(secret_receipt))
    check("PRIVACY", "receipt has no password field", "password" not in {key.lower() for key in secret_receipt})
    check("PRIVACY", "receipt authentication authority remains none", secret_receipt["authentication_authority"] == "NONE")
    check("PRIVACY", "receipt reset authority remains none", secret_receipt["reset_authority"] == "NONE")
    check("PRIVACY", "receipt credential mutation authority remains none", secret_receipt["credential_mutation_authority"] == "NONE")

    reference_value_input = copy.deepcopy(reference)
    reference_value_input["context"]["subject_ref"] = "HUNTER2"
    reference_value_input["authorization_evidence"][0]["subject_ref"] = "HUNTER2"
    reference_value_input = attach_declared_identities(
        {
            key: value
            for key, value in reference_value_input.items()
            if key not in {"declared_context_id", "declared_evidence_set_id"}
        }
    )
    reference_value_bundle = build_bundle(reference_value_input)
    reference_value_result = reference_value_bundle["result"]
    reference_value_serialized = canonical_json(reference_value_bundle)
    check("PRIVACY", "allowed reference value remains supported", reference_value_result["state"] == STATE_RESOLVED)
    check("PRIVACY", "allowed reference value remains in bundle", "HUNTER2" in reference_value_serialized)
    check("PRIVACY", "allowed reference value is not redacted", "<FORBIDDEN_VALUE_REDACTED>" not in reference_value_serialized)
    check("PRIVACY", "allowed reference value is not content-classified", "FORBIDDEN_FIELD_PRESENT" not in reference_value_result["reason_codes"])

    serialized_bundle = json_file_bytes(reference_bundle)
    check("SERIALIZATION", "terminal LF present", serialized_bundle.endswith(b"\n"))
    check("SERIALIZATION", "exactly one terminal LF", not serialized_bundle.endswith(b"\n\n"))
    check("SERIALIZATION", "no carriage returns", b"\r" not in serialized_bundle)
    check("SERIALIZATION", "valid UTF-8", serialized_bundle.decode("utf-8").endswith("\n"))
    check("SERIALIZATION", "strict round trip", canonical_json(loads_strict(serialized_bundle.decode("utf-8"))) == canonical_json(reference_bundle))
    with tempfile.TemporaryDirectory() as temporary_directory:
        temporary_path = Path(temporary_directory) / "artifact.json"
        write_json(temporary_path, reference_bundle)
        check("SERIALIZATION", "writer emits exact bytes", temporary_path.read_bytes() == serialized_bundle)

    passed = 0
    total = 0
    for group in sorted(groups):
        group_passed = sum(1 for _, condition in groups[group] if condition)
        group_total = len(groups[group])
        passed += group_passed
        total += group_total
        print(
            f"{group:<24} {group_passed}/{group_total} PASS"
            if group_passed == group_total
            else f"{group:<24} {group_passed}/{group_total} FAIL"
        )
        for name, condition in groups[group]:
            if not condition:
                print("  FAIL: " + name)
    print(
        f"{'TOTAL':<24} {passed}/{total} PASS"
        if passed == total
        else f"{'TOTAL':<24} {passed}/{total} FAIL"
    )
    return 0 if passed == total else 1


def print_cli_error(code: str, detail: str) -> None:
    print("ERROR_CODE: " + code, file=sys.stderr)
    print("ERROR_DETAIL: " + detail, file=sys.stderr)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="SLANG-ResetPassword bounded credential-replacement authorization evidence resolver"
    )
    parser.add_argument("--self-test", action="store_true", help="run the permanent reference audit")
    parser.add_argument("--input", type=Path, help="resolve a strict JSON input file")
    parser.add_argument("--write-reference-input", type=Path, help="write the canonical reference input")
    parser.add_argument("--write-bundle", type=Path, help="write the reconstruction bundle")
    parser.add_argument("--write-receipt", type=Path, help="write the compact receipt")
    parser.add_argument("--write-public-summary", type=Path, help="write the visibility-aware public summary")
    parser.add_argument(
        "--require-visible-result",
        action="store_true",
        help="return exit code 3 unless the public summary contains a visible resolved outcome",
    )
    parser.add_argument("--verify-bundle", type=Path, help="verify a reconstruction bundle")
    parser.add_argument("--verify-receipt", type=Path, help="verify a compact receipt")
    parser.add_argument("--verify-public-summary", type=Path, help="verify a public summary")
    parser.add_argument(
        "--verify-receipt-against-bundle",
        nargs=2,
        metavar=("RECEIPT", "BUNDLE"),
        help="verify a receipt and its exact bundle binding",
    )
    parser.add_argument(
        "--verify-public-summary-against-bundle",
        nargs=2,
        metavar=("SUMMARY", "BUNDLE"),
        help="verify a public summary and its exact bundle projection",
    )
    parser.add_argument(
        "--print-identity-domain",
        action="store_true",
        help="print the versioned identity-domain material",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    if sys.version_info < MINIMUM_PYTHON_VERSION:
        print_cli_error(
            "UNSUPPORTED_PYTHON_VERSION",
            "SLANG-ResetPassword v" + VERSION + " requires Python 3.9 or later",
        )
        return 2
    args = parse_args(argv)
    try:
        if args.require_visible_result and (
            args.self_test
            or args.verify_bundle
            or args.verify_receipt
            or args.verify_public_summary
            or args.verify_receipt_against_bundle
            or args.verify_public_summary_against_bundle
            or args.print_identity_domain
        ):
            raise ValueError("--require-visible-result applies only to input resolution")
        if args.self_test:
            return run_self_test()
        if args.print_identity_domain:
            print(json.dumps(identity_domain_material(), ensure_ascii=False, indent=2, sort_keys=True))
            return 0
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
                load_json(receipt_path),
                load_json(bundle_path),
            )
            print("VERIFY: PASS" if ok else "VERIFY: FAIL")
            print(reason)
            return 0 if ok else 1
        if args.verify_public_summary:
            ok, reason = verify_public_summary(load_json(args.verify_public_summary))
            print("VERIFY: PASS" if ok else "VERIFY: FAIL")
            print(reason)
            return 0 if ok else 1
        if args.verify_public_summary_against_bundle:
            summary_path, bundle_path = map(Path, args.verify_public_summary_against_bundle)
            ok, reason = verify_public_summary_against_bundle(
                load_json(summary_path),
                load_json(bundle_path),
            )
            print("VERIFY: PASS" if ok else "VERIFY: FAIL")
            print(reason)
            return 0 if ok else 1

        raw_input = load_json(args.input) if args.input else build_reference_input()
        if args.write_reference_input:
            write_json(args.write_reference_input, raw_input)
        bundle = build_bundle(raw_input)
        receipt = make_receipt(bundle)
        if args.write_bundle:
            write_json(args.write_bundle, bundle)
        if args.write_receipt:
            write_json(args.write_receipt, receipt)
        summary = public_summary(bundle)
        if args.write_public_summary:
            write_json(args.write_public_summary, summary)
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        if args.require_visible_result:
            exit_code = required_visible_result_exit_code(summary)
            if exit_code != 0:
                print("NOTICE_CODE: VISIBLE_RESULT_REQUIRED", file=sys.stderr)
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
