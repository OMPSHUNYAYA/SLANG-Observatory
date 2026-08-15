from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

VERSION = "0.2.1"
MINIMUM_PYTHON_VERSION = (3, 9)
CORE_VERSION = "SLANG-CORE-1-D05"
PROFILE_ID = "SLANG-CLAIMS-PROFILE-1-D03"
RULESET_ID = "SLANG-CLAIMS-RULESET-1-D03"
CANONICALIZATION_ID = "SLANG-CANONICAL-JSON-1-D02"
AUTHORITY_PROFILE_ID = "CLAIM-AUTHORITY-EVIDENCE-1"
QUANTUM_PROFILE_ID = "CLAIM-QUANTUM-NET-AFTER-DEDUCTIBLE-CAP-1"

INPUT_SCHEMA = "SLANG-CLAIMS-INPUT-1"
RESULT_SCHEMA = "SLANG-CLAIMS-RESULT-1"
BUNDLE_SCHEMA = "SLANG-CLAIMS-BUNDLE-1"
RECEIPT_SCHEMA = "SLANG-CLAIMS-RECEIPT-1"
SUMMARY_SCHEMA = "SLANG-CLAIMS-SUMMARY-1"
ATTESTATION_SCHEMA = "SLANG-CLAIMS-ATTESTATION-1"
CONTRACT_SCHEMA = "SLANG-CLAIMS-CONTRACT-1"
SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"

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

OUTCOME_PAYABLE = "PAYABLE"
OUTCOME_NOT_PAYABLE = "NOT_PAYABLE"
OUTCOME_NONE = "NONE"
ADMISSION_ADMIT = "ADMIT"
ADMISSION_DENY = "DENY"
ADMISSION_WITHHOLD = "WITHHOLD"
VISIBILITY_VISIBLE = "VISIBLE"
VISIBILITY_WITHHELD = "WITHHELD"

EVIDENCE_SINGLE = "SINGLE_AUTHORITY"
EVIDENCE_MULTI = "MULTI_AUTHORITY_EXACT_AGREEMENT"
SUPPORTED_EVIDENCE_MODES = {EVIDENCE_SINGLE, EVIDENCE_MULTI}

COVERAGE_COVERED = "COVERED"
COVERAGE_NOT_COVERED = "NOT_COVERED"
OCCURRENCE_ESTABLISHED = "ESTABLISHED"
OCCURRENCE_NOT_ESTABLISHED = "NOT_ESTABLISHED"
CLEAR = "CLEAR"
BLOCKED = "BLOCKED"
SUPPORTED_COVERAGE_RESULTS = {COVERAGE_COVERED, COVERAGE_NOT_COVERED}
SUPPORTED_OCCURRENCE_RESULTS = {OCCURRENCE_ESTABLISHED, OCCURRENCE_NOT_ESTABLISHED}
SUPPORTED_GATE_RESULTS = {CLEAR, BLOCKED}

TOP_LEVEL_KEYS = {
    "schema",
    "profile_id",
    "ruleset_id",
    "context",
    "claim_evidence",
    "declared_context_id",
    "declared_evidence_set_id",
}
CONTEXT_KEYS = {
    "evaluation_id",
    "claim_ref",
    "policy_ref",
    "claimant_ref",
    "loss_event_ref",
    "currency",
    "claim_amount_minor",
    "deductible_minor",
    "remaining_limit_minor",
    "evaluation_authorized",
    "reference_visibility_authorized",
    "evidence_mode",
    "expected_authority_ids",
}
EVIDENCE_KEYS = {
    "schema",
    "evidence_id",
    "authority_id",
    "evaluation_id",
    "claim_ref",
    "policy_ref",
    "claimant_ref",
    "loss_event_ref",
    "currency",
    "coverage_result",
    "occurrence_result",
    "exclusion_result",
    "control_result",
    "assessed_loss_minor",
    "evidence_commitment",
}

FORBIDDEN_FIELD_NAMES = {
    "password",
    "passphrase",
    "secret",
    "private_key",
    "privatekey",
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
    "session_token",
    "otp",
    "one_time_password",
    "recovery_code",
    "card_number",
    "cvv",
    "bank_account",
    "routing_number",
    "iban",
    "ssn",
    "national_id",
    "tax_id",
    "email",
    "phone",
    "address",
    "date_of_birth",
    "dob",
    "medical_record",
    "diagnosis",
    "claim_outcome",
    "payable",
    "payable_amount",
    "payable_amount_minor",
    "payout",
    "payout_amount",
    "approved",
    "approval",
    "admission_state",
    "resolution_state",
    "payment_authority",
    "settlement_authority",
    "legal_authority",
    "policy_interpretation_authority",
    "fraud_determination_authority",
    "money_movement",
    "result_id",
    "bundle_id",
    "receipt_id",
    "summary_id",
    "attestation_id",
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
IDENTIFIER_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9._:@/-]{0,127}$")
CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")
COMMITMENT_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
ASCII_TRIM = "\t\n\r "

CONTEXT_ID_PREFIX = "slang_claims_context_sha256:"
AUTHORITY_MANIFEST_ID_PREFIX = "slang_claims_authority_manifest_sha256:"
EVIDENCE_SET_ID_PREFIX = "slang_claims_evidence_set_sha256:"
EVIDENCE_AGREEMENT_ID_PREFIX = "slang_claims_evidence_agreement_sha256:"
RULE_PROFILE_ID_PREFIX = "slang_claims_rule_profile_sha256:"
SUBMISSION_ID_PREFIX = "slang_claims_submission_sha256:"
CANONICAL_INPUT_ID_PREFIX = "slang_claims_canonical_input_sha256:"
OUTCOME_ID_PREFIX = "slang_claims_outcome_sha256:"
EVALUATION_EVIDENCE_ID_PREFIX = "slang_claims_evaluation_evidence_sha256:"
RESULT_ID_PREFIX = "slang_claims_result_sha256:"
BUNDLE_ID_PREFIX = "slang_claims_bundle_sha256:"
RECEIPT_ID_PREFIX = "slang_claims_receipt_sha256:"
SUMMARY_ID_PREFIX = "slang_claims_summary_sha256:"
IDENTITY_DOMAIN_ID_PREFIX = "slang_claims_identity_domain_sha256:"
ATTESTATION_ID_PREFIX = "slang_claims_attestation_sha256:"
CONTRACT_ID_PREFIX = "slang_claims_contract_sha256:"


class PortableJSONError(ValueError):
    pass


class DuplicateKeyError(PortableJSONError):
    pass


@dataclass(frozen=True)
class ValidationIssue:
    state: str
    code: str
    path: str

    def __post_init__(self) -> None:
        if self.state not in SUPPORTED_STATES:
            raise ValueError("UNREGISTERED_ISSUE_STATE:" + self.state)
        if self.code not in REASON_CODE_REGISTRY:
            raise ValueError("UNREGISTERED_REASON_CODE:" + self.code)


REASON_CODE_REGISTRY = {
    "BOOLEAN_REQUIRED",
    "CLAIM_PAYABILITY_ADMITTED",
    "CONTEXT_OBJECT_REQUIRED",
    "CONTROL_BLOCKS_PAYABILITY",
    "COVERAGE_NOT_ADMITTED",
    "DECLARED_CONTEXT_ID_MISMATCH",
    "DECLARED_EVIDENCE_SET_ID_MISMATCH",
    "DUPLICATE_AUTHORITY_EVIDENCE",
    "DUPLICATE_EVIDENCE_ID",
    "DUPLICATE_IDENTIFIER",
    "EMPTY_IDENTIFIER_LIST",
    "EVALUATION_NOT_AUTHORIZED",
    "EVIDENCE_BINDING_MISMATCH",
    "EVIDENCE_LIST_REQUIRED",
    "EVIDENCE_OBJECT_REQUIRED",
    "EVIDENCE_RESULT_DISAGREEMENT",
    "EXCLUSION_BLOCKS_PAYABILITY",
    "FLOAT_NOT_SUPPORTED",
    "FORBIDDEN_FIELD_PRESENT",
    "IDENTIFIER_LIST_REQUIRED",
    "INTEGER_OUT_OF_PORTABLE_RANGE",
    "INTEGER_OUT_OF_RANGE",
    "INVALID_CURRENCY_UNIT",
    "INVALID_EVIDENCE_COMMITMENT",
    "INVALID_IDENTIFIER",
    "JSON_DEPTH_LIMIT",
    "JSON_NODE_LIMIT",
    "LIST_TOO_LONG",
    "LONE_SURROGATE",
    "MISSING_EXPECTED_AUTHORITY",
    "MISSING_REQUIRED_FIELD",
    "MULTI_AUTHORITY_REQUIRES_AT_LEAST_TWO_AUTHORITIES",
    "MULTI_AUTHORITY_REQUIRES_MULTIPLE_EVIDENCE_RECORDS",
    "NONNEGATIVE_INTEGER_REQUIRED",
    "NON_STRING_OBJECT_KEY",
    "NO_AMOUNT_ABOVE_DEDUCTIBLE",
    "NO_REMAINING_LIMIT",
    "OBJECT_KEY_TOO_LONG",
    "OCCURRENCE_NOT_ADMITTED",
    "OUTCOME_WITHHELD",
    "SINGLE_AUTHORITY_REQUIRES_EXACTLY_ONE_AUTHORITY",
    "SINGLE_AUTHORITY_REQUIRES_EXACTLY_ONE_EVIDENCE_RECORD",
    "STRING_TOO_LONG",
    "TOO_MANY_AUTHORITIES",
    "TOO_MANY_EVIDENCE_RECORDS",
    "TOP_LEVEL_OBJECT_REQUIRED",
    "UNEXPECTED_AUTHORITY",
    "UNKNOWN_FIELD",
    "UNSUPPORTED_CONTROL_RESULT",
    "UNSUPPORTED_COVERAGE_RESULT",
    "UNSUPPORTED_EVIDENCE_MODE",
    "UNSUPPORTED_EVIDENCE_SCHEMA",
    "UNSUPPORTED_EXCLUSION_RESULT",
    "UNSUPPORTED_INPUT_SCHEMA",
    "UNSUPPORTED_JSON_TYPE",
    "UNSUPPORTED_OCCURRENCE_RESULT",
    "UNSUPPORTED_PROFILE_ID",
    "UNSUPPORTED_RULESET_ID",
    "ZERO_PAYABLE_AMOUNT",
}


def canonical_json(value: Any) -> str:
    validate_portable_json(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def clone(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))


def sha256_hex(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def identity(prefix: str, value: Any) -> str:
    return prefix + sha256_hex(value)


def identity_domain_material() -> Dict[str, str]:
    return {
        "core_version": CORE_VERSION,
        "profile_id": PROFILE_ID,
        "ruleset_id": RULESET_ID,
        "canonicalization_id": CANONICALIZATION_ID,
        "authority_profile_id": AUTHORITY_PROFILE_ID,
        "quantum_profile_id": QUANTUM_PROFILE_ID,
    }


def identity_domain_id() -> str:
    return identity(IDENTITY_DOMAIN_ID_PREFIX, identity_domain_material())


def validate_portable_json(value: Any) -> None:
    nodes = 0

    def walk(item: Any, depth: int) -> None:
        nonlocal nodes
        nodes += 1
        if nodes > MAX_JSON_NODES:
            raise PortableJSONError("JSON_NODE_LIMIT")
        if depth > MAX_JSON_DEPTH:
            raise PortableJSONError("JSON_DEPTH_LIMIT")
        if item is None or isinstance(item, bool):
            return
        if isinstance(item, int) and not isinstance(item, bool):
            if abs(item) > MAX_SAFE_INTEGER:
                raise PortableJSONError("INTEGER_OUT_OF_PORTABLE_RANGE")
            return
        if isinstance(item, float):
            raise PortableJSONError("FLOAT_NOT_SUPPORTED")
        if isinstance(item, str):
            if len(item) > MAX_STRING_LENGTH:
                raise PortableJSONError("STRING_TOO_LONG")
            for ch in item:
                cp = ord(ch)
                if 0xD800 <= cp <= 0xDFFF:
                    raise PortableJSONError("LONE_SURROGATE")
            return
        if isinstance(item, list):
            if len(item) > MAX_LIST_LENGTH:
                raise PortableJSONError("LIST_TOO_LONG")
            for child in item:
                walk(child, depth + 1)
            return
        if isinstance(item, dict):
            for key, child in item.items():
                if not isinstance(key, str):
                    raise PortableJSONError("NON_STRING_OBJECT_KEY")
                if len(key) > MAX_STRING_LENGTH:
                    raise PortableJSONError("OBJECT_KEY_TOO_LONG")
                walk(child, depth + 1)
            return
        raise PortableJSONError("UNSUPPORTED_JSON_TYPE")

    walk(value, 0)


def strict_json_load_text(text: str) -> Any:
    if len(text.encode("utf-8")) > MAX_JSON_INPUT_BYTES:
        raise PortableJSONError("JSON_INPUT_TOO_LARGE")

    def pairs_hook(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise DuplicateKeyError("DUPLICATE_OBJECT_KEY:" + key)
            result[key] = value
        return result

    try:
        value = json.loads(text, object_pairs_hook=pairs_hook, parse_constant=lambda x: (_ for _ in ()).throw(PortableJSONError("NON_FINITE_NUMBER")))
    except PortableJSONError:
        raise
    except Exception as exc:
        raise PortableJSONError("INVALID_JSON:" + str(exc))
    validate_portable_json(value)
    return value


def load_json_file(path: Path) -> Any:
    data = path.read_bytes()
    if len(data) > MAX_JSON_INPUT_BYTES:
        raise PortableJSONError("JSON_INPUT_TOO_LARGE")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PortableJSONError("INPUT_NOT_UTF8:" + str(exc))
    return strict_json_load_text(text)


def normalize_identifier(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    normalized = value.strip(ASCII_TRIM).upper()
    if len(normalized) > MAX_IDENTIFIER_LENGTH or not IDENTIFIER_PATTERN.fullmatch(normalized):
        return None
    return normalized


def normalize_currency(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    normalized = value.strip(ASCII_TRIM).upper()
    if not CURRENCY_PATTERN.fullmatch(normalized):
        return None
    return normalized


def normalize_commitment(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    normalized = value.strip(ASCII_TRIM).lower()
    if not COMMITMENT_PATTERN.fullmatch(normalized):
        return None
    return normalized


def issue_rank(state: str) -> int:
    return {
        STATE_FORBIDDEN: 0,
        STATE_CONFLICT: 1,
        STATE_UNSUPPORTED: 2,
        STATE_INCOMPLETE: 3,
        STATE_ABSTAIN: 4,
        STATE_RESOLVED: 5,
    }.get(state, 99)


def choose_issue(issues: Sequence[ValidationIssue]) -> ValidationIssue:
    return sorted(issues, key=lambda x: (issue_rank(x.state), x.code, x.path))[0]


def unique_sorted(values: Iterable[str]) -> List[str]:
    return sorted(set(values))


def field_name_signatures(value: str) -> Tuple[str, str]:
    trimmed = value.strip(ASCII_TRIM)
    separated = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", trimmed)
    separated = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", "_", separated)
    separated = re.sub(r"[^A-Za-z0-9]+", "_", separated).strip("_").lower()
    compact = re.sub(r"[^a-z0-9]", "", separated)
    return separated, compact


FORBIDDEN_FIELD_SIGNATURES = {
    signature
    for name in FORBIDDEN_FIELD_NAMES
    for signature in field_name_signatures(name)
    if signature
}


def scan_forbidden_fields(value: Any, path: str = "$", output: Optional[List[str]] = None) -> List[str]:
    if output is None:
        output = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = key if isinstance(key, str) else str(key)
            child_path = path + "." + key_text
            if isinstance(key, str):
                separated, compact = field_name_signatures(key)
                if separated in FORBIDDEN_FIELD_SIGNATURES or compact in FORBIDDEN_FIELD_SIGNATURES:
                    output.append(child_path)
            scan_forbidden_fields(child, child_path, output)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            scan_forbidden_fields(child, path + "[" + str(index) + "]", output)
    return output


def redact_forbidden_values(value: Any) -> Any:
    if isinstance(value, dict):
        output: Dict[Any, Any] = {}
        for key, child in value.items():
            matched = False
            if isinstance(key, str):
                separated, compact = field_name_signatures(key)
                matched = separated in FORBIDDEN_FIELD_SIGNATURES or compact in FORBIDDEN_FIELD_SIGNATURES
            output[key] = "<FORBIDDEN_VALUE_REDACTED>" if matched else redact_forbidden_values(child)
        return output
    if isinstance(value, list):
        return [redact_forbidden_values(child) for child in value]
    return clone(value)


def unknown_key_issues(value: Dict[str, Any], allowed: Set[str], path: str) -> List[ValidationIssue]:
    return [ValidationIssue(STATE_UNSUPPORTED, "UNKNOWN_FIELD", path + "." + key) for key in sorted(set(value.keys()) - allowed)]


def required_identifier(value: Dict[str, Any], key: str, path: str, issues: List[ValidationIssue]) -> Optional[str]:
    if key not in value:
        issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_REQUIRED_FIELD", path + "." + key))
        return None
    normalized = normalize_identifier(value.get(key))
    if normalized is None:
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_IDENTIFIER", path + "." + key))
    return normalized


def required_currency(value: Dict[str, Any], key: str, path: str, issues: List[ValidationIssue]) -> Optional[str]:
    if key not in value:
        issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_REQUIRED_FIELD", path + "." + key))
        return None
    normalized = normalize_currency(value.get(key))
    if normalized is None:
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_CURRENCY_UNIT", path + "." + key))
    return normalized


def required_bool(value: Dict[str, Any], key: str, path: str, issues: List[ValidationIssue]) -> Optional[bool]:
    if key not in value:
        issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_REQUIRED_FIELD", path + "." + key))
        return None
    item = value.get(key)
    if not isinstance(item, bool):
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "BOOLEAN_REQUIRED", path + "." + key))
        return None
    return item


def required_nonnegative_int(value: Dict[str, Any], key: str, path: str, issues: List[ValidationIssue]) -> Optional[int]:
    if key not in value:
        issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_REQUIRED_FIELD", path + "." + key))
        return None
    item = value.get(key)
    if isinstance(item, bool) or not isinstance(item, int):
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "NONNEGATIVE_INTEGER_REQUIRED", path + "." + key))
        return None
    if item < 0 or item > MAX_SAFE_INTEGER:
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "INTEGER_OUT_OF_RANGE", path + "." + key))
        return None
    return item


def required_enum(value: Dict[str, Any], key: str, supported: Set[str], path: str, issues: List[ValidationIssue]) -> Optional[str]:
    if key not in value:
        issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_REQUIRED_FIELD", path + "." + key))
        return None
    item = value.get(key)
    normalized = normalize_identifier(item)
    if normalized is None or normalized not in supported:
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "UNSUPPORTED_" + key.upper(), path + "." + key))
        return None
    return normalized


def normalize_identifier_list(value: Any, path: str, issues: List[ValidationIssue]) -> Optional[List[str]]:
    if not isinstance(value, list):
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "IDENTIFIER_LIST_REQUIRED", path))
        return None
    if not value:
        issues.append(ValidationIssue(STATE_INCOMPLETE, "EMPTY_IDENTIFIER_LIST", path))
        return None
    normalized: List[str] = []
    for index, item in enumerate(value):
        ident = normalize_identifier(item)
        if ident is None:
            issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_IDENTIFIER", path + "[" + str(index) + "]"))
        else:
            normalized.append(ident)
    if len(normalized) != len(set(normalized)):
        issues.append(ValidationIssue(STATE_CONFLICT, "DUPLICATE_IDENTIFIER", path))
    return sorted(set(normalized))


def normalize_context(value: Any) -> Tuple[Optional[Dict[str, Any]], List[ValidationIssue]]:
    issues: List[ValidationIssue] = []
    if not isinstance(value, dict):
        return None, [ValidationIssue(STATE_UNSUPPORTED, "CONTEXT_OBJECT_REQUIRED", "$.context")]
    issues.extend(unknown_key_issues(value, CONTEXT_KEYS, "$.context"))
    context: Dict[str, Any] = {}
    for key in ["evaluation_id", "claim_ref", "policy_ref", "claimant_ref", "loss_event_ref"]:
        context[key] = required_identifier(value, key, "$.context", issues)
    context["currency"] = required_currency(value, "currency", "$.context", issues)
    for key in ["claim_amount_minor", "deductible_minor", "remaining_limit_minor"]:
        context[key] = required_nonnegative_int(value, key, "$.context", issues)
    context["evaluation_authorized"] = required_bool(value, "evaluation_authorized", "$.context", issues)
    context["reference_visibility_authorized"] = required_bool(value, "reference_visibility_authorized", "$.context", issues)
    context["evidence_mode"] = required_enum(value, "evidence_mode", SUPPORTED_EVIDENCE_MODES, "$.context", issues)
    if "expected_authority_ids" not in value:
        issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_REQUIRED_FIELD", "$.context.expected_authority_ids"))
        context["expected_authority_ids"] = None
    else:
        context["expected_authority_ids"] = normalize_identifier_list(value.get("expected_authority_ids"), "$.context.expected_authority_ids", issues)
    if context.get("evaluation_authorized") is False:
        issues.append(ValidationIssue(STATE_ABSTAIN, "EVALUATION_NOT_AUTHORIZED", "$.context.evaluation_authorized"))
    mode = context.get("evidence_mode")
    expected = context.get("expected_authority_ids")
    if isinstance(expected, list):
        if len(expected) > MAX_EVIDENCE_RECORDS:
            issues.append(ValidationIssue(STATE_UNSUPPORTED, "TOO_MANY_AUTHORITIES", "$.context.expected_authority_ids"))
        if mode == EVIDENCE_SINGLE and len(expected) != 1:
            issues.append(ValidationIssue(STATE_UNSUPPORTED, "SINGLE_AUTHORITY_REQUIRES_EXACTLY_ONE_AUTHORITY", "$.context.expected_authority_ids"))
        if mode == EVIDENCE_MULTI and len(expected) < 2:
            issues.append(ValidationIssue(STATE_UNSUPPORTED, "MULTI_AUTHORITY_REQUIRES_AT_LEAST_TWO_AUTHORITIES", "$.context.expected_authority_ids"))
    return context, issues


def normalize_evidence_record(value: Any, index: int) -> Tuple[Optional[Dict[str, Any]], List[ValidationIssue]]:
    path = "$.claim_evidence[" + str(index) + "]"
    issues: List[ValidationIssue] = []
    if not isinstance(value, dict):
        return None, [ValidationIssue(STATE_UNSUPPORTED, "EVIDENCE_OBJECT_REQUIRED", path)]
    issues.extend(unknown_key_issues(value, EVIDENCE_KEYS, path))
    record: Dict[str, Any] = {}
    schema = value.get("schema")
    if schema is None:
        issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_REQUIRED_FIELD", path + ".schema"))
        record["schema"] = None
    elif schema != AUTHORITY_PROFILE_ID:
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "UNSUPPORTED_EVIDENCE_SCHEMA", path + ".schema"))
        record["schema"] = schema
    else:
        record["schema"] = schema
    for key in ["evidence_id", "authority_id", "evaluation_id", "claim_ref", "policy_ref", "claimant_ref", "loss_event_ref"]:
        record[key] = required_identifier(value, key, path, issues)
    record["currency"] = required_currency(value, "currency", path, issues)
    record["coverage_result"] = required_enum(value, "coverage_result", SUPPORTED_COVERAGE_RESULTS, path, issues)
    record["occurrence_result"] = required_enum(value, "occurrence_result", SUPPORTED_OCCURRENCE_RESULTS, path, issues)
    record["exclusion_result"] = required_enum(value, "exclusion_result", SUPPORTED_GATE_RESULTS, path, issues)
    record["control_result"] = required_enum(value, "control_result", SUPPORTED_GATE_RESULTS, path, issues)
    record["assessed_loss_minor"] = required_nonnegative_int(value, "assessed_loss_minor", path, issues)
    if "evidence_commitment" not in value:
        issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_REQUIRED_FIELD", path + ".evidence_commitment"))
        record["evidence_commitment"] = None
    else:
        commitment = normalize_commitment(value.get("evidence_commitment"))
        if commitment is None:
            issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_EVIDENCE_COMMITMENT", path + ".evidence_commitment"))
        record["evidence_commitment"] = commitment
    return record, issues


def context_material(context: Dict[str, Any]) -> Dict[str, Any]:
    return clone(context)


def authority_manifest_material(context: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "evidence_mode": context["evidence_mode"],
        "expected_authority_ids": context["expected_authority_ids"],
        "authority_profile_id": AUTHORITY_PROFILE_ID,
    }


def evidence_set_material(evidence: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    return {"claim_evidence": sorted([clone(x) for x in evidence], key=lambda x: (x["authority_id"], x["evidence_id"]))}


def rule_profile_material() -> Dict[str, Any]:
    return {
        "profile_id": PROFILE_ID,
        "ruleset_id": RULESET_ID,
        "authority_profile_id": AUTHORITY_PROFILE_ID,
        "quantum_profile_id": QUANTUM_PROFILE_ID,
        "payable_formula": "min(max(min(claim_amount_minor, assessed_loss_minor) - deductible_minor, 0), remaining_limit_minor)",
        "state_precedence": [STATE_FORBIDDEN, STATE_CONFLICT, STATE_UNSUPPORTED, STATE_INCOMPLETE, STATE_ABSTAIN, STATE_RESOLVED],
    }


def contract_manifest_material() -> Dict[str, Any]:
    return {
        "schema": CONTRACT_SCHEMA,
        "version": VERSION,
        "core_version": CORE_VERSION,
        "profile_id": PROFILE_ID,
        "ruleset_id": RULESET_ID,
        "canonicalization_id": CANONICALIZATION_ID,
        "authority_profile_id": AUTHORITY_PROFILE_ID,
        "quantum_profile_id": QUANTUM_PROFILE_ID,
        "identity_domain_id": identity_domain_id(),
        "schemas": {
            "input": INPUT_SCHEMA,
            "result": RESULT_SCHEMA,
            "bundle": BUNDLE_SCHEMA,
            "receipt": RECEIPT_SCHEMA,
            "summary": SUMMARY_SCHEMA,
            "attestation": ATTESTATION_SCHEMA,
        },
        "supported_states": sorted(SUPPORTED_STATES),
        "state_precedence": [STATE_FORBIDDEN, STATE_CONFLICT, STATE_UNSUPPORTED, STATE_INCOMPLETE, STATE_ABSTAIN, STATE_RESOLVED],
        "supported_outcomes": [OUTCOME_NONE, OUTCOME_NOT_PAYABLE, OUTCOME_PAYABLE],
        "supported_admission_states": [ADMISSION_ADMIT, ADMISSION_DENY, ADMISSION_WITHHOLD],
        "supported_evidence_modes": sorted(SUPPORTED_EVIDENCE_MODES),
        "reason_code_registry": sorted(REASON_CODE_REGISTRY),
        "resource_limits": {
            "max_safe_integer": MAX_SAFE_INTEGER,
            "max_json_depth": MAX_JSON_DEPTH,
            "max_json_nodes": MAX_JSON_NODES,
            "max_json_input_bytes": MAX_JSON_INPUT_BYTES,
            "max_identifier_length": MAX_IDENTIFIER_LENGTH,
            "max_string_length": MAX_STRING_LENGTH,
            "max_evidence_records": MAX_EVIDENCE_RECORDS,
            "max_reason_codes": MAX_REASON_CODES,
            "max_list_length": MAX_LIST_LENGTH,
        },
        "authority_exclusions": {
            "payment_authority": "NONE",
            "settlement_authority": "NONE",
            "legal_authority": "NONE",
            "policy_interpretation_authority": "NONE",
            "fraud_determination_authority": "NONE",
            "money_movement": "NONE",
        },
        "receipt_integrity_scope": "SELF_CONSISTENCY_AND_DECLARED_INVARIANTS_ONLY",
        "receipt_correspondence_scope": "REQUIRES_EXACT_RECONSTRUCTION_BUNDLE",
        "attestation_integrity_scope": "SELF_CONSISTENCY_ONLY",
        "attestation_correspondence_scope": "REQUIRES_ORIGINAL_INPUT",
        "forbidden_field_matching": "ASCII_CAMEL_SEPARATOR_AND_COMPACT_SIGNATURES",
        "forbidden_value_commitment": "REDACTED_BEFORE_SUBMISSION_ID",
        "schema_validation_scope": "PREFLIGHT_ONLY",
        "library_entry_validation": "PORTABLE_JSON_AND_RESOURCE_LIMITS_BEFORE_DOMAIN_SCAN",
        "reason_code_emission": "REGISTRY_CLOSED_BY_CONSTRUCTION_AND_RESULT_FIREWALL",
        "python_compatibility": "PYTHON_3_9_COMPATIBLE_SYNTAX_USE_SUPPORTED_CPYTHON_RUNTIME",
        "payable_formula": "min(max(min(claim_amount_minor, assessed_loss_minor) - deductible_minor, 0), remaining_limit_minor)",
    }


def contract_manifest() -> Dict[str, Any]:
    material = contract_manifest_material()
    output = clone(material)
    output["contract_id"] = identity(CONTRACT_ID_PREFIX, material)
    return output


def contract_id() -> str:
    return contract_manifest()["contract_id"]


def binding_issues(context: Dict[str, Any], evidence: Sequence[Dict[str, Any]]) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    fields = ["evaluation_id", "claim_ref", "policy_ref", "claimant_ref", "loss_event_ref", "currency"]
    for index, record in enumerate(evidence):
        for field in fields:
            if record.get(field) is None or context.get(field) is None:
                continue
            if record.get(field) != context.get(field):
                issues.append(ValidationIssue(STATE_CONFLICT, "EVIDENCE_BINDING_MISMATCH", "$.claim_evidence[" + str(index) + "]." + field))
    return issues


def authority_set_issues(context: Dict[str, Any], evidence: Sequence[Dict[str, Any]]) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    expected = context.get("expected_authority_ids") or []
    observed = [record.get("authority_id") for record in evidence if record.get("authority_id") is not None]
    if len(observed) != len(set(observed)):
        issues.append(ValidationIssue(STATE_CONFLICT, "DUPLICATE_AUTHORITY_EVIDENCE", "$.claim_evidence"))
    unexpected = sorted(set(observed) - set(expected))
    missing = sorted(set(expected) - set(observed))
    if unexpected:
        issues.append(ValidationIssue(STATE_CONFLICT, "UNEXPECTED_AUTHORITY", "$.claim_evidence"))
    if missing:
        issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_EXPECTED_AUTHORITY", "$.claim_evidence"))
    mode = context.get("evidence_mode")
    if mode == EVIDENCE_SINGLE and len(evidence) != 1:
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "SINGLE_AUTHORITY_REQUIRES_EXACTLY_ONE_EVIDENCE_RECORD", "$.claim_evidence"))
    if mode == EVIDENCE_MULTI and len(evidence) < 2:
        issues.append(ValidationIssue(STATE_INCOMPLETE, "MULTI_AUTHORITY_REQUIRES_MULTIPLE_EVIDENCE_RECORDS", "$.claim_evidence"))
    return issues


def evidence_uniqueness_issues(evidence: Sequence[Dict[str, Any]]) -> List[ValidationIssue]:
    ids = [record.get("evidence_id") for record in evidence if record.get("evidence_id") is not None]
    if len(ids) != len(set(ids)):
        return [ValidationIssue(STATE_CONFLICT, "DUPLICATE_EVIDENCE_ID", "$.claim_evidence")]
    return []


def agreement_material(evidence: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    if not evidence:
        return {}
    first = evidence[0]
    return {
        "coverage_result": first["coverage_result"],
        "occurrence_result": first["occurrence_result"],
        "exclusion_result": first["exclusion_result"],
        "control_result": first["control_result"],
        "assessed_loss_minor": first["assessed_loss_minor"],
    }


def evidence_agreement_issues(context: Dict[str, Any], evidence: Sequence[Dict[str, Any]]) -> List[ValidationIssue]:
    if context.get("evidence_mode") != EVIDENCE_MULTI or len(evidence) < 2:
        return []
    baseline = agreement_material(evidence)
    for record in evidence[1:]:
        current = {
            "coverage_result": record["coverage_result"],
            "occurrence_result": record["occurrence_result"],
            "exclusion_result": record["exclusion_result"],
            "control_result": record["control_result"],
            "assessed_loss_minor": record["assessed_loss_minor"],
        }
        if current != baseline:
            return [ValidationIssue(STATE_ABSTAIN, "EVIDENCE_RESULT_DISAGREEMENT", "$.claim_evidence")]
    return []


def normalize_input(raw_input: Any) -> Tuple[Optional[Dict[str, Any]], List[ValidationIssue]]:
    issues: List[ValidationIssue] = []
    try:
        validate_portable_json(raw_input)
    except PortableJSONError as exc:
        return None, [ValidationIssue(STATE_UNSUPPORTED, str(exc), "$")]
    forbidden = scan_forbidden_fields(raw_input)
    for path in forbidden:
        issues.append(ValidationIssue(STATE_FORBIDDEN, "FORBIDDEN_FIELD_PRESENT", path))
    if not isinstance(raw_input, dict):
        return None, issues + [ValidationIssue(STATE_UNSUPPORTED, "TOP_LEVEL_OBJECT_REQUIRED", "$")]
    issues.extend(unknown_key_issues(raw_input, TOP_LEVEL_KEYS, "$"))
    schema = raw_input.get("schema")
    if schema is None:
        issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_REQUIRED_FIELD", "$.schema"))
    elif schema != INPUT_SCHEMA:
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "UNSUPPORTED_INPUT_SCHEMA", "$.schema"))
    if raw_input.get("profile_id") is None:
        issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_REQUIRED_FIELD", "$.profile_id"))
    elif raw_input.get("profile_id") != PROFILE_ID:
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "UNSUPPORTED_PROFILE_ID", "$.profile_id"))
    if raw_input.get("ruleset_id") is None:
        issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_REQUIRED_FIELD", "$.ruleset_id"))
    elif raw_input.get("ruleset_id") != RULESET_ID:
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "UNSUPPORTED_RULESET_ID", "$.ruleset_id"))
    context, context_issues = normalize_context(raw_input.get("context"))
    issues.extend(context_issues)
    evidence_value = raw_input.get("claim_evidence")
    evidence: List[Dict[str, Any]] = []
    if evidence_value is None:
        issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_REQUIRED_FIELD", "$.claim_evidence"))
    elif not isinstance(evidence_value, list):
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "EVIDENCE_LIST_REQUIRED", "$.claim_evidence"))
    elif len(evidence_value) > MAX_EVIDENCE_RECORDS:
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "TOO_MANY_EVIDENCE_RECORDS", "$.claim_evidence"))
    else:
        for index, item in enumerate(evidence_value):
            record, record_issues = normalize_evidence_record(item, index)
            issues.extend(record_issues)
            if record is not None:
                evidence.append(record)
    evidence = sorted(evidence, key=lambda x: ((x.get("authority_id") or ""), (x.get("evidence_id") or "")))
    if context is not None:
        issues.extend(binding_issues(context, evidence))
        issues.extend(authority_set_issues(context, evidence))
        issues.extend(evidence_uniqueness_issues(evidence))
        issues.extend(evidence_agreement_issues(context, evidence))
    normalized: Dict[str, Any] = {
        "schema": INPUT_SCHEMA,
        "profile_id": PROFILE_ID,
        "ruleset_id": RULESET_ID,
        "context": context,
        "claim_evidence": evidence,
    }
    if context is not None and not any(x is None for x in context.values()):
        computed_context_id = identity(CONTEXT_ID_PREFIX, context_material(context))
        declared_context_id = raw_input.get("declared_context_id")
        if declared_context_id is None:
            issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_REQUIRED_FIELD", "$.declared_context_id"))
        elif declared_context_id != computed_context_id:
            issues.append(ValidationIssue(STATE_CONFLICT, "DECLARED_CONTEXT_ID_MISMATCH", "$.declared_context_id"))
        normalized["declared_context_id"] = computed_context_id
    else:
        normalized["declared_context_id"] = raw_input.get("declared_context_id")
    evidence_complete = bool(evidence) and all(all(v is not None for v in record.values()) for record in evidence)
    if evidence_complete:
        computed_evidence_set_id = identity(EVIDENCE_SET_ID_PREFIX, evidence_set_material(evidence))
        declared_evidence_set_id = raw_input.get("declared_evidence_set_id")
        if declared_evidence_set_id is None:
            issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_REQUIRED_FIELD", "$.declared_evidence_set_id"))
        elif declared_evidence_set_id != computed_evidence_set_id:
            issues.append(ValidationIssue(STATE_CONFLICT, "DECLARED_EVIDENCE_SET_ID_MISMATCH", "$.declared_evidence_set_id"))
        normalized["declared_evidence_set_id"] = computed_evidence_set_id
    else:
        normalized["declared_evidence_set_id"] = raw_input.get("declared_evidence_set_id")
    return normalized, issues


def compute_quantum(context: Dict[str, Any], agreed: Dict[str, Any]) -> Dict[str, int]:
    claim_amount = context["claim_amount_minor"]
    assessed_loss = agreed["assessed_loss_minor"]
    deductible = context["deductible_minor"]
    remaining_limit = context["remaining_limit_minor"]
    admitted_loss = min(claim_amount, assessed_loss)
    post_deductible = max(admitted_loss - deductible, 0)
    payable = min(post_deductible, remaining_limit)
    return {
        "admitted_loss_minor": admitted_loss,
        "post_deductible_minor": post_deductible,
        "payable_amount_minor": payable,
    }


def base_result() -> Dict[str, Any]:
    return {
        "schema": RESULT_SCHEMA,
        "version": VERSION,
        "core_version": CORE_VERSION,
        "profile_id": PROFILE_ID,
        "ruleset_id": RULESET_ID,
        "canonicalization_id": CANONICALIZATION_ID,
        "authority_profile_id": AUTHORITY_PROFILE_ID,
        "quantum_profile_id": QUANTUM_PROFILE_ID,
        "identity_domain_id": identity_domain_id(),
        "contract_id": contract_id(),
        "state": STATE_INCOMPLETE,
        "resolution_state": STATE_INCOMPLETE,
        "admission_state": ADMISSION_WITHHOLD,
        "claim_outcome": OUTCOME_NONE,
        "outcome_visible": False,
        "visibility_state": VISIBILITY_WITHHELD,
        "currency": "NONE",
        "claim_amount_minor": 0,
        "assessed_loss_minor": 0,
        "admitted_loss_minor": 0,
        "deductible_minor": 0,
        "remaining_limit_minor": 0,
        "post_deductible_minor": 0,
        "payable_amount_minor": 0,
        "evaluation_id": "NONE",
        "claim_ref": "NONE",
        "policy_ref": "NONE",
        "claimant_ref": "NONE",
        "loss_event_ref": "NONE",
        "evidence_mode": "NONE",
        "authority_count": 0,
        "context_id": "NONE",
        "authority_manifest_id": "NONE",
        "evidence_set_id": "NONE",
        "evidence_agreement_id": "NONE",
        "rule_profile_id": identity(RULE_PROFILE_ID_PREFIX, rule_profile_material()),
        "submission_id": "NONE",
        "canonical_input_id": "NONE",
        "outcome_id": "NONE",
        "evaluation_evidence_id": "NONE",
        "result_id": "NONE",
        "reason_codes": [],
        "missing_dependencies": [],
        "conflicts": [],
        "prohibitions": [],
        "payment_authority": "NONE",
        "settlement_authority": "NONE",
        "legal_authority": "NONE",
        "policy_interpretation_authority": "NONE",
        "source_authenticity": "NOT_ESTABLISHED_BY_REFERENCE_PROFILE",
        "claimant_identity_verification": "NOT_ESTABLISHED_BY_REFERENCE_PROFILE",
        "fraud_determination_authority": "NONE",
        "money_movement": "NONE",
    }


def result_identity_material(result: Dict[str, Any]) -> Dict[str, Any]:
    material = clone(result)
    material.pop("result_id", None)
    return material


def resolve_claims(raw_input: Any) -> Dict[str, Any]:
    result = base_result()
    try:
        validate_portable_json(raw_input)
    except PortableJSONError as exc:
        code = str(exc)
        if code not in REASON_CODE_REGISTRY:
            raise RuntimeError("UNREGISTERED_REASON_CODE:" + code)
        result["submission_id"] = "NONE"
        result["state"] = STATE_UNSUPPORTED
        result["resolution_state"] = STATE_UNSUPPORTED
        result["reason_codes"] = [code]
        result["result_id"] = identity(RESULT_ID_PREFIX, result_identity_material(result))
        return result
    try:
        forbidden_paths = scan_forbidden_fields(raw_input)
        submission_material = redact_forbidden_values(raw_input) if forbidden_paths else raw_input
        submission_id = identity(SUBMISSION_ID_PREFIX, submission_material)
    except Exception:
        submission_id = "NONE"
    result["submission_id"] = submission_id
    normalized, issues = normalize_input(raw_input)
    if normalized is not None:
        try:
            result["canonical_input_id"] = identity(CANONICAL_INPUT_ID_PREFIX, normalized)
        except Exception:
            result["canonical_input_id"] = "NONE"
        context = normalized.get("context")
        evidence = normalized.get("claim_evidence") or []
        if isinstance(context, dict):
            for key in ["evaluation_id", "claim_ref", "policy_ref", "claimant_ref", "loss_event_ref", "currency", "claim_amount_minor", "deductible_minor", "remaining_limit_minor", "evidence_mode"]:
                if context.get(key) is not None:
                    result[key] = context[key]
            expected = context.get("expected_authority_ids") or []
            result["authority_count"] = len(expected)
            if all(v is not None for v in context.values()):
                result["context_id"] = identity(CONTEXT_ID_PREFIX, context_material(context))
                result["authority_manifest_id"] = identity(AUTHORITY_MANIFEST_ID_PREFIX, authority_manifest_material(context))
        evidence_complete = bool(evidence) and all(all(v is not None for v in record.values()) for record in evidence)
        if evidence_complete:
            result["evidence_set_id"] = identity(EVIDENCE_SET_ID_PREFIX, evidence_set_material(evidence))
            result["evidence_agreement_id"] = identity(EVIDENCE_AGREEMENT_ID_PREFIX, agreement_material(evidence))
    if issues:
        primary = choose_issue(issues)
        result["state"] = primary.state
        result["resolution_state"] = primary.state
        result["reason_codes"] = unique_sorted(issue.code for issue in issues)[:MAX_REASON_CODES]
        result["missing_dependencies"] = unique_sorted(issue.path for issue in issues if issue.state == STATE_INCOMPLETE)
        result["conflicts"] = unique_sorted(issue.path for issue in issues if issue.state == STATE_CONFLICT)
        result["prohibitions"] = unique_sorted(issue.path for issue in issues if issue.state == STATE_FORBIDDEN)
    else:
        assert normalized is not None
        context = normalized["context"]
        evidence = normalized["claim_evidence"]
        agreed = agreement_material(evidence)
        result["assessed_loss_minor"] = agreed["assessed_loss_minor"]
        gate_positive = (
            agreed["coverage_result"] == COVERAGE_COVERED
            and agreed["occurrence_result"] == OCCURRENCE_ESTABLISHED
            and agreed["exclusion_result"] == CLEAR
            and agreed["control_result"] == CLEAR
        )
        result["state"] = STATE_RESOLVED
        result["resolution_state"] = STATE_RESOLVED
        if gate_positive:
            quantum = compute_quantum(context, agreed)
            result.update(quantum)
            if quantum["payable_amount_minor"] > 0:
                result["claim_outcome"] = OUTCOME_PAYABLE
                result["admission_state"] = ADMISSION_ADMIT
                result["reason_codes"] = ["CLAIM_PAYABILITY_ADMITTED"]
            else:
                result["claim_outcome"] = OUTCOME_NOT_PAYABLE
                result["admission_state"] = ADMISSION_DENY
                if quantum["admitted_loss_minor"] <= context["deductible_minor"]:
                    result["reason_codes"] = ["NO_AMOUNT_ABOVE_DEDUCTIBLE"]
                elif context["remaining_limit_minor"] == 0:
                    result["reason_codes"] = ["NO_REMAINING_LIMIT"]
                else:
                    result["reason_codes"] = ["ZERO_PAYABLE_AMOUNT"]
        else:
            result["claim_outcome"] = OUTCOME_NOT_PAYABLE
            result["admission_state"] = ADMISSION_DENY
            reasons: List[str] = []
            if agreed["coverage_result"] != COVERAGE_COVERED:
                reasons.append("COVERAGE_NOT_ADMITTED")
            if agreed["occurrence_result"] != OCCURRENCE_ESTABLISHED:
                reasons.append("OCCURRENCE_NOT_ADMITTED")
            if agreed["exclusion_result"] != CLEAR:
                reasons.append("EXCLUSION_BLOCKS_PAYABILITY")
            if agreed["control_result"] != CLEAR:
                reasons.append("CONTROL_BLOCKS_PAYABILITY")
            result["reason_codes"] = reasons
        result["outcome_visible"] = bool(context["reference_visibility_authorized"])
        result["visibility_state"] = VISIBILITY_VISIBLE if result["outcome_visible"] else VISIBILITY_WITHHELD
        result["outcome_id"] = identity(OUTCOME_ID_PREFIX, {
            "claim_outcome": result["claim_outcome"],
            "currency": result["currency"],
            "payable_amount_minor": result["payable_amount_minor"],
            "context_id": result["context_id"],
            "evidence_set_id": result["evidence_set_id"],
            "ruleset_id": RULESET_ID,
        })
        result["evaluation_evidence_id"] = identity(EVALUATION_EVIDENCE_ID_PREFIX, {
            "context_id": result["context_id"],
            "authority_manifest_id": result["authority_manifest_id"],
            "evidence_set_id": result["evidence_set_id"],
            "evidence_agreement_id": result["evidence_agreement_id"],
            "rule_profile_id": result["rule_profile_id"],
            "outcome_id": result["outcome_id"],
        })
    if any(code not in REASON_CODE_REGISTRY for code in result["reason_codes"]):
        raise RuntimeError("UNREGISTERED_REASON_CODE_EMITTED")
    result["result_id"] = identity(RESULT_ID_PREFIX, result_identity_material(result))
    return result


def normalized_projection(raw_input: Any) -> Dict[str, Any]:
    normalized, issues = normalize_input(raw_input)
    if normalized is None or issues:
        raise ValueError("INPUT_NOT_RESOLVABLE")
    return normalized


def build_bundle(raw_input: Any) -> Dict[str, Any]:
    result = resolve_claims(raw_input)
    bundle = {
        "schema": BUNDLE_SCHEMA,
        "version": VERSION,
        "core_version": CORE_VERSION,
        "canonicalization_id": CANONICALIZATION_ID,
        "identity_domain_id": identity_domain_id(),
        "contract_id": contract_id(),
        "submitted_input": clone(raw_input),
        "normalized_projection": normalized_projection(raw_input),
        "result": result,
    }
    bundle["bundle_id"] = identity(BUNDLE_ID_PREFIX, bundle)
    return bundle


def verify_bundle(bundle: Any) -> Tuple[bool, str]:
    if not isinstance(bundle, dict):
        return False, "BUNDLE_OBJECT_REQUIRED"
    required = {"schema", "version", "core_version", "canonicalization_id", "identity_domain_id", "contract_id", "submitted_input", "normalized_projection", "result", "bundle_id"}
    if set(bundle.keys()) != required:
        return False, "BUNDLE_KEYS_MISMATCH"
    if bundle.get("schema") != BUNDLE_SCHEMA or bundle.get("version") != VERSION:
        return False, "BUNDLE_VERSION_MISMATCH"
    if bundle.get("core_version") != CORE_VERSION or bundle.get("canonicalization_id") != CANONICALIZATION_ID:
        return False, "BUNDLE_CONTRACT_MISMATCH"
    if bundle.get("identity_domain_id") != identity_domain_id():
        return False, "BUNDLE_IDENTITY_DOMAIN_MISMATCH"
    if bundle.get("contract_id") != contract_id():
        return False, "BUNDLE_CONTRACT_ID_MISMATCH"
    try:
        rebuilt = build_bundle(bundle.get("submitted_input"))
    except Exception as exc:
        return False, "BUNDLE_RECONSTRUCTION_FAILED:" + str(exc)
    if rebuilt != bundle:
        return False, "BUNDLE_RECONSTRUCTION_MISMATCH"
    return True, "PASS"


def make_receipt(bundle: Dict[str, Any]) -> Dict[str, Any]:
    ok, detail = verify_bundle(bundle)
    if not ok:
        raise ValueError(detail)
    result = bundle["result"]
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "version": VERSION,
        "core_version": CORE_VERSION,
        "profile_id": PROFILE_ID,
        "ruleset_id": RULESET_ID,
        "canonicalization_id": CANONICALIZATION_ID,
        "identity_domain_id": identity_domain_id(),
        "contract_id": contract_id(),
        "bundle_id": bundle["bundle_id"],
        "result_id": result["result_id"],
        "submission_id": result["submission_id"],
        "canonical_input_id": result["canonical_input_id"],
        "context_id": result["context_id"],
        "authority_manifest_id": result["authority_manifest_id"],
        "evidence_set_id": result["evidence_set_id"],
        "evidence_agreement_id": result["evidence_agreement_id"],
        "rule_profile_id": result["rule_profile_id"],
        "outcome_id": result["outcome_id"],
        "evaluation_evidence_id": result["evaluation_evidence_id"],
        "evaluation_id": result["evaluation_id"],
        "claim_ref": result["claim_ref"],
        "policy_ref": result["policy_ref"],
        "claimant_ref": result["claimant_ref"],
        "loss_event_ref": result["loss_event_ref"],
        "evidence_mode": result["evidence_mode"],
        "authority_count": result["authority_count"],
        "state": result["state"],
        "resolution_state": result["resolution_state"],
        "admission_state": result["admission_state"],
        "claim_outcome": result["claim_outcome"],
        "outcome_visible": result["outcome_visible"],
        "visibility_state": result["visibility_state"],
        "currency": result["currency"],
        "claim_amount_minor": result["claim_amount_minor"],
        "assessed_loss_minor": result["assessed_loss_minor"],
        "admitted_loss_minor": result["admitted_loss_minor"],
        "deductible_minor": result["deductible_minor"],
        "remaining_limit_minor": result["remaining_limit_minor"],
        "post_deductible_minor": result["post_deductible_minor"],
        "payable_amount_minor": result["payable_amount_minor"],
        "reason_codes": result["reason_codes"],
        "payment_authority": result["payment_authority"],
        "settlement_authority": result["settlement_authority"],
        "legal_authority": result["legal_authority"],
        "policy_interpretation_authority": result["policy_interpretation_authority"],
        "source_authenticity": result["source_authenticity"],
        "claimant_identity_verification": result["claimant_identity_verification"],
        "fraud_determination_authority": result["fraud_determination_authority"],
        "money_movement": result["money_movement"],
    }
    receipt["receipt_id"] = identity(RECEIPT_ID_PREFIX, receipt)
    return receipt


RECEIPT_KEYS = {
    "schema",
    "version",
    "core_version",
    "profile_id",
    "ruleset_id",
    "canonicalization_id",
    "identity_domain_id",
    "contract_id",
    "bundle_id",
    "result_id",
    "submission_id",
    "canonical_input_id",
    "context_id",
    "authority_manifest_id",
    "evidence_set_id",
    "evidence_agreement_id",
    "rule_profile_id",
    "outcome_id",
    "evaluation_evidence_id",
    "evaluation_id",
    "claim_ref",
    "policy_ref",
    "claimant_ref",
    "loss_event_ref",
    "evidence_mode",
    "authority_count",
    "state",
    "resolution_state",
    "admission_state",
    "claim_outcome",
    "outcome_visible",
    "visibility_state",
    "currency",
    "claim_amount_minor",
    "assessed_loss_minor",
    "admitted_loss_minor",
    "deductible_minor",
    "remaining_limit_minor",
    "post_deductible_minor",
    "payable_amount_minor",
    "reason_codes",
    "payment_authority",
    "settlement_authority",
    "legal_authority",
    "policy_interpretation_authority",
    "source_authenticity",
    "claimant_identity_verification",
    "fraud_determination_authority",
    "money_movement",
    "receipt_id",
}


def identity_has_prefix(value: Any, prefix: str) -> bool:
    if not isinstance(value, str) or not value.startswith(prefix):
        return False
    suffix = value[len(prefix):]
    return len(suffix) == 64 and all(ch in "0123456789abcdef" for ch in suffix)


def portable_nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= MAX_SAFE_INTEGER


def check_receipt_integrity(receipt: Any) -> Tuple[bool, str]:
    if not isinstance(receipt, dict):
        return False, "RECEIPT_OBJECT_REQUIRED"
    if set(receipt.keys()) != RECEIPT_KEYS:
        return False, "RECEIPT_KEYS_MISMATCH"
    if receipt.get("schema") != RECEIPT_SCHEMA or receipt.get("version") != VERSION:
        return False, "RECEIPT_VERSION_MISMATCH"
    if receipt.get("core_version") != CORE_VERSION:
        return False, "RECEIPT_CORE_VERSION_MISMATCH"
    if receipt.get("profile_id") != PROFILE_ID or receipt.get("ruleset_id") != RULESET_ID:
        return False, "RECEIPT_PROFILE_RULESET_MISMATCH"
    if receipt.get("canonicalization_id") != CANONICALIZATION_ID:
        return False, "RECEIPT_CANONICALIZATION_MISMATCH"
    if receipt.get("identity_domain_id") != identity_domain_id():
        return False, "RECEIPT_IDENTITY_DOMAIN_MISMATCH"
    if receipt.get("contract_id") != contract_id():
        return False, "RECEIPT_CONTRACT_ID_MISMATCH"
    fixed_authority = {
        "payment_authority": "NONE",
        "settlement_authority": "NONE",
        "legal_authority": "NONE",
        "policy_interpretation_authority": "NONE",
        "fraud_determination_authority": "NONE",
        "money_movement": "NONE",
        "source_authenticity": "NOT_ESTABLISHED_BY_REFERENCE_PROFILE",
        "claimant_identity_verification": "NOT_ESTABLISHED_BY_REFERENCE_PROFILE",
    }
    for key, expected in fixed_authority.items():
        if receipt.get(key) != expected:
            return False, "RECEIPT_AUTHORITY_BOUNDARY_MISMATCH:" + key
    identity_fields = {
        "bundle_id": BUNDLE_ID_PREFIX,
        "result_id": RESULT_ID_PREFIX,
        "submission_id": SUBMISSION_ID_PREFIX,
        "canonical_input_id": CANONICAL_INPUT_ID_PREFIX,
        "context_id": CONTEXT_ID_PREFIX,
        "authority_manifest_id": AUTHORITY_MANIFEST_ID_PREFIX,
        "evidence_set_id": EVIDENCE_SET_ID_PREFIX,
        "evidence_agreement_id": EVIDENCE_AGREEMENT_ID_PREFIX,
        "rule_profile_id": RULE_PROFILE_ID_PREFIX,
        "outcome_id": OUTCOME_ID_PREFIX,
        "evaluation_evidence_id": EVALUATION_EVIDENCE_ID_PREFIX,
    }
    for key, prefix in identity_fields.items():
        if not identity_has_prefix(receipt.get(key), prefix):
            return False, "RECEIPT_IDENTITY_FIELD_INVALID:" + key
    for key in ["evaluation_id", "claim_ref", "policy_ref", "claimant_ref", "loss_event_ref"]:
        if normalize_identifier(receipt.get(key)) != receipt.get(key):
            return False, "RECEIPT_IDENTIFIER_INVALID:" + key
    if receipt.get("evidence_mode") not in SUPPORTED_EVIDENCE_MODES:
        return False, "RECEIPT_EVIDENCE_MODE_INVALID"
    if not portable_nonnegative_int(receipt.get("authority_count")) or not 1 <= receipt["authority_count"] <= MAX_EVIDENCE_RECORDS:
        return False, "RECEIPT_AUTHORITY_COUNT_INVALID"
    if receipt.get("state") != STATE_RESOLVED or receipt.get("resolution_state") != STATE_RESOLVED:
        return False, "RECEIPT_STATE_NOT_RESOLVED"
    if receipt.get("claim_outcome") == OUTCOME_PAYABLE:
        if receipt.get("admission_state") != ADMISSION_ADMIT:
            return False, "RECEIPT_ADMISSION_OUTCOME_MISMATCH"
    elif receipt.get("claim_outcome") == OUTCOME_NOT_PAYABLE:
        if receipt.get("admission_state") != ADMISSION_DENY:
            return False, "RECEIPT_ADMISSION_OUTCOME_MISMATCH"
    else:
        return False, "RECEIPT_OUTCOME_INVALID"
    if not isinstance(receipt.get("outcome_visible"), bool):
        return False, "RECEIPT_VISIBILITY_FLAG_INVALID"
    expected_visibility = VISIBILITY_VISIBLE if receipt["outcome_visible"] else VISIBILITY_WITHHELD
    if receipt.get("visibility_state") != expected_visibility:
        return False, "RECEIPT_VISIBILITY_STATE_MISMATCH"
    if normalize_currency(receipt.get("currency")) != receipt.get("currency"):
        return False, "RECEIPT_CURRENCY_INVALID"
    money_fields = [
        "claim_amount_minor",
        "assessed_loss_minor",
        "admitted_loss_minor",
        "deductible_minor",
        "remaining_limit_minor",
        "post_deductible_minor",
        "payable_amount_minor",
    ]
    for key in money_fields:
        if not portable_nonnegative_int(receipt.get(key)):
            return False, "RECEIPT_MONEY_FIELD_INVALID:" + key
    reasons = receipt.get("reason_codes")
    if not isinstance(reasons, list) or not reasons or len(reasons) > MAX_REASON_CODES:
        return False, "RECEIPT_REASON_CODES_INVALID"
    if any(not isinstance(code, str) or code not in REASON_CODE_REGISTRY for code in reasons):
        return False, "RECEIPT_REASON_CODE_UNKNOWN"
    admitted = min(receipt["claim_amount_minor"], receipt["assessed_loss_minor"])
    post = max(admitted - receipt["deductible_minor"], 0)
    payable = min(post, receipt["remaining_limit_minor"])
    if receipt["claim_outcome"] == OUTCOME_PAYABLE:
        if receipt["admitted_loss_minor"] != admitted:
            return False, "RECEIPT_ADMITTED_LOSS_MISMATCH"
        if receipt["post_deductible_minor"] != post:
            return False, "RECEIPT_POST_DEDUCTIBLE_MISMATCH"
        if receipt["payable_amount_minor"] != payable or payable <= 0:
            return False, "RECEIPT_PAYABLE_AMOUNT_MISMATCH"
        if receipt["reason_codes"] != ["CLAIM_PAYABILITY_ADMITTED"]:
            return False, "RECEIPT_PAYABLE_REASON_MISMATCH"
    else:
        if receipt["payable_amount_minor"] != 0:
            return False, "RECEIPT_NOT_PAYABLE_AMOUNT_NONZERO"
        quantum_negative_reasons = {"NO_AMOUNT_ABOVE_DEDUCTIBLE", "NO_REMAINING_LIMIT", "ZERO_PAYABLE_AMOUNT"}
        gate_negative_reasons = {
            "COVERAGE_NOT_ADMITTED",
            "OCCURRENCE_NOT_ADMITTED",
            "EXCLUSION_BLOCKS_PAYABILITY",
            "CONTROL_BLOCKS_PAYABILITY",
        }
        if set(receipt["reason_codes"]).issubset(quantum_negative_reasons):
            if receipt["admitted_loss_minor"] != admitted or receipt["post_deductible_minor"] != post or payable != 0:
                return False, "RECEIPT_NEGATIVE_QUANTUM_MISMATCH"
        elif set(receipt["reason_codes"]).issubset(gate_negative_reasons):
            if receipt["admitted_loss_minor"] != 0 or receipt["post_deductible_minor"] != 0:
                return False, "RECEIPT_GATE_NEGATIVE_QUANTUM_MISMATCH"
        else:
            return False, "RECEIPT_NOT_PAYABLE_REASON_MISMATCH"
    expected_outcome_id = identity(OUTCOME_ID_PREFIX, {
        "claim_outcome": receipt["claim_outcome"],
        "currency": receipt["currency"],
        "payable_amount_minor": receipt["payable_amount_minor"],
        "context_id": receipt["context_id"],
        "evidence_set_id": receipt["evidence_set_id"],
        "ruleset_id": RULESET_ID,
    })
    if receipt.get("outcome_id") != expected_outcome_id:
        return False, "RECEIPT_OUTCOME_ID_MISMATCH"
    receipt_id = receipt.get("receipt_id")
    if not identity_has_prefix(receipt_id, RECEIPT_ID_PREFIX):
        return False, "RECEIPT_ID_INVALID"
    material = clone(receipt)
    material.pop("receipt_id", None)
    if receipt_id != identity(RECEIPT_ID_PREFIX, material):
        return False, "RECEIPT_ID_MISMATCH"
    return True, "PASS"


def verify_receipt(receipt: Any, bundle: Any = None) -> Tuple[bool, str]:
    if bundle is None:
        return False, "RECEIPT_BUNDLE_REQUIRED"
    return verify_receipt_against_bundle(receipt, bundle)


def verify_receipt_against_bundle(receipt: Any, bundle: Any) -> Tuple[bool, str]:
    ok, detail = verify_bundle(bundle)
    if not ok:
        return False, "BUNDLE:" + detail
    ok, detail = check_receipt_integrity(receipt)
    if not ok:
        return False, "RECEIPT:" + detail
    expected = make_receipt(bundle)
    if receipt != expected:
        return False, "RECEIPT_BUNDLE_MISMATCH"
    return True, "PASS"


ATTESTATION_KEYS = {
    "schema",
    "version",
    "core_version",
    "profile_id",
    "ruleset_id",
    "canonicalization_id",
    "identity_domain_id",
    "contract_id",
    "submission_id",
    "canonical_input_id",
    "context_id",
    "authority_manifest_id",
    "evidence_set_id",
    "evidence_agreement_id",
    "rule_profile_id",
    "result_id",
    "outcome_id",
    "evaluation_id",
    "claim_ref",
    "policy_ref",
    "claimant_ref",
    "loss_event_ref",
    "state",
    "resolution_state",
    "admission_state",
    "claim_outcome",
    "reason_codes",
    "missing_dependencies",
    "conflicts",
    "prohibitions",
    "payment_authority",
    "settlement_authority",
    "legal_authority",
    "policy_interpretation_authority",
    "fraud_determination_authority",
    "money_movement",
    "source_authenticity",
    "attestation_id",
}


def make_attestation(raw_input: Any) -> Dict[str, Any]:
    result = resolve_claims(raw_input)
    attestation = {
        "schema": ATTESTATION_SCHEMA,
        "version": VERSION,
        "core_version": CORE_VERSION,
        "profile_id": PROFILE_ID,
        "ruleset_id": RULESET_ID,
        "canonicalization_id": CANONICALIZATION_ID,
        "identity_domain_id": identity_domain_id(),
        "contract_id": contract_id(),
        "submission_id": result["submission_id"],
        "canonical_input_id": result["canonical_input_id"],
        "context_id": result["context_id"],
        "authority_manifest_id": result["authority_manifest_id"],
        "evidence_set_id": result["evidence_set_id"],
        "evidence_agreement_id": result["evidence_agreement_id"],
        "rule_profile_id": result["rule_profile_id"],
        "result_id": result["result_id"],
        "outcome_id": result["outcome_id"] if result["state"] == STATE_RESOLVED else "NONE",
        "evaluation_id": result["evaluation_id"],
        "claim_ref": result["claim_ref"],
        "policy_ref": result["policy_ref"],
        "claimant_ref": result["claimant_ref"],
        "loss_event_ref": result["loss_event_ref"],
        "state": result["state"],
        "resolution_state": result["resolution_state"],
        "admission_state": result["admission_state"],
        "claim_outcome": result["claim_outcome"] if result["state"] == STATE_RESOLVED else OUTCOME_NONE,
        "reason_codes": result["reason_codes"],
        "missing_dependencies": result["missing_dependencies"],
        "conflicts": result["conflicts"],
        "prohibitions": result["prohibitions"],
        "payment_authority": "NONE",
        "settlement_authority": "NONE",
        "legal_authority": "NONE",
        "policy_interpretation_authority": "NONE",
        "fraud_determination_authority": "NONE",
        "money_movement": "NONE",
        "source_authenticity": "NOT_ESTABLISHED_BY_REFERENCE_PROFILE",
    }
    attestation["attestation_id"] = identity(ATTESTATION_ID_PREFIX, attestation)
    return attestation


def check_attestation_integrity(attestation: Any) -> Tuple[bool, str]:
    if not isinstance(attestation, dict):
        return False, "ATTESTATION_OBJECT_REQUIRED"
    if set(attestation.keys()) != ATTESTATION_KEYS:
        return False, "ATTESTATION_KEYS_MISMATCH"
    if attestation.get("schema") != ATTESTATION_SCHEMA or attestation.get("version") != VERSION:
        return False, "ATTESTATION_VERSION_MISMATCH"
    if attestation.get("core_version") != CORE_VERSION:
        return False, "ATTESTATION_CORE_VERSION_MISMATCH"
    if attestation.get("profile_id") != PROFILE_ID or attestation.get("ruleset_id") != RULESET_ID:
        return False, "ATTESTATION_PROFILE_RULESET_MISMATCH"
    if attestation.get("canonicalization_id") != CANONICALIZATION_ID:
        return False, "ATTESTATION_CANONICALIZATION_MISMATCH"
    if attestation.get("identity_domain_id") != identity_domain_id() or attestation.get("contract_id") != contract_id():
        return False, "ATTESTATION_CONTRACT_MISMATCH"
    if attestation.get("state") not in SUPPORTED_STATES or attestation.get("resolution_state") != attestation.get("state"):
        return False, "ATTESTATION_STATE_INVALID"
    if attestation.get("state") == STATE_RESOLVED:
        if attestation.get("claim_outcome") == OUTCOME_PAYABLE and attestation.get("admission_state") != ADMISSION_ADMIT:
            return False, "ATTESTATION_OUTCOME_ADMISSION_MISMATCH"
        if attestation.get("claim_outcome") == OUTCOME_NOT_PAYABLE and attestation.get("admission_state") != ADMISSION_DENY:
            return False, "ATTESTATION_OUTCOME_ADMISSION_MISMATCH"
        if attestation.get("claim_outcome") not in {OUTCOME_PAYABLE, OUTCOME_NOT_PAYABLE}:
            return False, "ATTESTATION_OUTCOME_INVALID"
        if not identity_has_prefix(attestation.get("outcome_id"), OUTCOME_ID_PREFIX):
            return False, "ATTESTATION_OUTCOME_ID_INVALID"
    else:
        if attestation.get("claim_outcome") != OUTCOME_NONE or attestation.get("admission_state") != ADMISSION_WITHHOLD:
            return False, "ATTESTATION_NONRESULT_MAPPING_INVALID"
        if attestation.get("outcome_id") != "NONE":
            return False, "ATTESTATION_NONRESULT_OUTCOME_ID_PRESENT"
    reasons = attestation.get("reason_codes")
    if not isinstance(reasons, list) or len(reasons) > MAX_REASON_CODES:
        return False, "ATTESTATION_REASON_CODES_INVALID"
    if any(not isinstance(code, str) or code not in REASON_CODE_REGISTRY for code in reasons):
        return False, "ATTESTATION_REASON_CODE_UNKNOWN"
    for key in ["missing_dependencies", "conflicts", "prohibitions"]:
        values = attestation.get(key)
        if not isinstance(values, list) or len(values) > MAX_REASON_CODES or any(not isinstance(x, str) for x in values):
            return False, "ATTESTATION_DIAGNOSTIC_LIST_INVALID:" + key
    fixed = {
        "payment_authority": "NONE",
        "settlement_authority": "NONE",
        "legal_authority": "NONE",
        "policy_interpretation_authority": "NONE",
        "fraud_determination_authority": "NONE",
        "money_movement": "NONE",
        "source_authenticity": "NOT_ESTABLISHED_BY_REFERENCE_PROFILE",
    }
    for key, expected in fixed.items():
        if attestation.get(key) != expected:
            return False, "ATTESTATION_AUTHORITY_BOUNDARY_MISMATCH:" + key
    if not identity_has_prefix(attestation.get("rule_profile_id"), RULE_PROFILE_ID_PREFIX):
        return False, "ATTESTATION_RULE_PROFILE_ID_INVALID"
    if not identity_has_prefix(attestation.get("result_id"), RESULT_ID_PREFIX):
        return False, "ATTESTATION_RESULT_ID_INVALID"
    attestation_id = attestation.get("attestation_id")
    if not identity_has_prefix(attestation_id, ATTESTATION_ID_PREFIX):
        return False, "ATTESTATION_ID_INVALID"
    material = clone(attestation)
    material.pop("attestation_id", None)
    if attestation_id != identity(ATTESTATION_ID_PREFIX, material):
        return False, "ATTESTATION_ID_MISMATCH"
    return True, "PASS"


def verify_attestation(attestation: Any, raw_input: Any = None) -> Tuple[bool, str]:
    if raw_input is None:
        return False, "ATTESTATION_INPUT_REQUIRED"
    return verify_attestation_against_input(attestation, raw_input)


def verify_attestation_against_input(attestation: Any, raw_input: Any) -> Tuple[bool, str]:
    ok, detail = check_attestation_integrity(attestation)
    if not ok:
        return False, "ATTESTATION:" + detail
    expected = make_attestation(raw_input)
    if attestation != expected:
        return False, "ATTESTATION_INPUT_MISMATCH"
    return True, "PASS"


def make_summary(raw_input: Any) -> Dict[str, Any]:
    result = resolve_claims(raw_input)
    visible = bool(result["outcome_visible"] and result["state"] == STATE_RESOLVED)
    resolved_hidden = bool(result["state"] == STATE_RESOLVED and not visible)
    if visible:
        admission_state = result["admission_state"]
        claim_outcome = result["claim_outcome"]
        currency = result["currency"]
        payable_amount_minor = result["payable_amount_minor"]
        reason_codes = result["reason_codes"]
        result_id = result["result_id"]
        outcome_id = result["outcome_id"]
    elif resolved_hidden:
        admission_state = ADMISSION_WITHHOLD
        claim_outcome = OUTCOME_NONE
        currency = "NONE"
        payable_amount_minor = 0
        reason_codes = ["OUTCOME_WITHHELD"]
        result_id = "NONE"
        outcome_id = "NONE"
    else:
        admission_state = ADMISSION_WITHHOLD
        claim_outcome = OUTCOME_NONE
        currency = "NONE"
        payable_amount_minor = 0
        reason_codes = result["reason_codes"]
        result_id = result["result_id"]
        outcome_id = "NONE"
    summary = {
        "schema": SUMMARY_SCHEMA,
        "version": VERSION,
        "profile_id": PROFILE_ID,
        "ruleset_id": RULESET_ID,
        "contract_id": contract_id(),
        "state": result["state"],
        "admission_state": admission_state,
        "visibility_state": result["visibility_state"],
        "claim_outcome": claim_outcome,
        "currency": currency,
        "payable_amount_minor": payable_amount_minor,
        "reason_codes": reason_codes,
        "result_id": result_id,
        "outcome_id": outcome_id,
        "payment_authority": "NONE",
        "settlement_authority": "NONE",
        "money_movement": "NONE",
    }
    summary["summary_id"] = identity(SUMMARY_ID_PREFIX, summary)
    return summary


def commitment(label: str) -> str:
    return "sha256:" + hashlib.sha256(label.encode("utf-8")).hexdigest()


def build_evidence_record(authority_id: str, assessed_loss_minor: int = 450000, coverage_result: str = COVERAGE_COVERED, occurrence_result: str = OCCURRENCE_ESTABLISHED, exclusion_result: str = CLEAR, control_result: str = CLEAR) -> Dict[str, Any]:
    return {
        "schema": AUTHORITY_PROFILE_ID,
        "evidence_id": "EVIDENCE-" + authority_id.split("-")[-1],
        "authority_id": authority_id,
        "evaluation_id": "CLAIM-EVALUATION-001",
        "claim_ref": "CLAIM-ALPHA",
        "policy_ref": "POLICY-ALPHA",
        "claimant_ref": "CLAIMANT-ALPHA",
        "loss_event_ref": "LOSS-EVENT-ALPHA",
        "currency": "USD",
        "coverage_result": coverage_result,
        "occurrence_result": occurrence_result,
        "exclusion_result": exclusion_result,
        "control_result": control_result,
        "assessed_loss_minor": assessed_loss_minor,
        "evidence_commitment": commitment("evidence:" + authority_id + ":" + str(assessed_loss_minor) + ":" + coverage_result + ":" + occurrence_result + ":" + exclusion_result + ":" + control_result),
    }


def attach_declared_ids(raw_input: Dict[str, Any]) -> Dict[str, Any]:
    value = clone(raw_input)
    context, context_issues = normalize_context(value["context"])
    if context is None or any(value is None for value in context.values()):
        raise ValueError("REFERENCE_CONTEXT_INVALID")
    evidence: List[Dict[str, Any]] = []
    for index, item in enumerate(value["claim_evidence"]):
        record, record_issues = normalize_evidence_record(item, index)
        if record is None or any(value is None for value in record.values()):
            raise ValueError("REFERENCE_EVIDENCE_INVALID")
        evidence.append(record)
    evidence = sorted(evidence, key=lambda x: (x["authority_id"], x["evidence_id"]))
    value["declared_context_id"] = identity(CONTEXT_ID_PREFIX, context_material(context))
    value["declared_evidence_set_id"] = identity(EVIDENCE_SET_ID_PREFIX, evidence_set_material(evidence))
    return value


def build_reference_input(multi: bool = False, visible: bool = True) -> Dict[str, Any]:
    authorities = ["CLAIM-AUTHORITY-A", "CLAIM-AUTHORITY-B"] if multi else ["CLAIM-AUTHORITY-A"]
    value = {
        "schema": INPUT_SCHEMA,
        "profile_id": PROFILE_ID,
        "ruleset_id": RULESET_ID,
        "context": {
            "evaluation_id": "CLAIM-EVALUATION-001",
            "claim_ref": "CLAIM-ALPHA",
            "policy_ref": "POLICY-ALPHA",
            "claimant_ref": "CLAIMANT-ALPHA",
            "loss_event_ref": "LOSS-EVENT-ALPHA",
            "currency": "USD",
            "claim_amount_minor": 500000,
            "deductible_minor": 100000,
            "remaining_limit_minor": 1000000,
            "evaluation_authorized": True,
            "reference_visibility_authorized": visible,
            "evidence_mode": EVIDENCE_MULTI if multi else EVIDENCE_SINGLE,
            "expected_authority_ids": authorities,
        },
        "claim_evidence": [build_evidence_record(authority) for authority in authorities],
    }
    return attach_declared_ids(value)


def refresh_declared_ids(value: Dict[str, Any]) -> Dict[str, Any]:
    material = clone(value)
    material.pop("declared_context_id", None)
    material.pop("declared_evidence_set_id", None)
    return attach_declared_ids(material)


def self_test() -> Tuple[int, int, List[str]]:
    checks: List[Tuple[str, bool]] = []

    def check(name: str, condition: bool) -> None:
        checks.append((name, bool(condition)))

    single = build_reference_input(False, True)
    result = resolve_claims(single)
    check("reference_state_resolved", result["state"] == STATE_RESOLVED)
    check("reference_outcome_payable", result["claim_outcome"] == OUTCOME_PAYABLE)
    check("reference_admission_admit", result["admission_state"] == ADMISSION_ADMIT)
    check("reference_payable_amount", result["payable_amount_minor"] == 350000)
    check("reference_admitted_loss", result["admitted_loss_minor"] == 450000)
    check("reference_post_deductible", result["post_deductible_minor"] == 350000)
    check("reference_visible", result["outcome_visible"] is True)
    check("reference_no_payment_authority", result["payment_authority"] == "NONE")
    check("reference_no_money_movement", result["money_movement"] == "NONE")
    check("reference_result_id", result["result_id"].startswith(RESULT_ID_PREFIX))
    check("reference_outcome_id", result["outcome_id"].startswith(OUTCOME_ID_PREFIX))
    check("reference_context_id", result["context_id"] == single["declared_context_id"])
    check("reference_evidence_set_id", result["evidence_set_id"] == single["declared_evidence_set_id"])

    again = resolve_claims(clone(single))
    check("deterministic_result", result == again)
    reordered = {k: single[k] for k in reversed(list(single.keys()))}
    check("object_key_order_invariant", resolve_claims(reordered)["canonical_input_id"] == result["canonical_input_id"])

    multi = build_reference_input(True, True)
    multi_result = resolve_claims(multi)
    check("multi_resolved", multi_result["state"] == STATE_RESOLVED)
    check("multi_payable", multi_result["claim_outcome"] == OUTCOME_PAYABLE)
    reversed_evidence = clone(multi)
    reversed_evidence["claim_evidence"] = list(reversed(reversed_evidence["claim_evidence"]))
    check("evidence_order_invariant", resolve_claims(reversed_evidence)["canonical_input_id"] == multi_result["canonical_input_id"])
    reversed_authorities = clone(multi)
    reversed_authorities["context"]["expected_authority_ids"] = list(reversed(reversed_authorities["context"]["expected_authority_ids"]))
    reversed_authorities = refresh_declared_ids(reversed_authorities)
    check("authority_order_invariant", resolve_claims(reversed_authorities)["context_id"] == multi_result["context_id"])

    hidden = build_reference_input(False, False)
    hidden_result = resolve_claims(hidden)
    hidden_summary = make_summary(hidden)
    check("hidden_still_resolved", hidden_result["state"] == STATE_RESOLVED)
    check("hidden_outcome_withheld", hidden_summary["claim_outcome"] == OUTCOME_NONE)
    check("hidden_amount_withheld", hidden_summary["payable_amount_minor"] == 0)
    check("hidden_summary_reason", hidden_summary["reason_codes"] == ["OUTCOME_WITHHELD"])
    check("hidden_admission_neutral", hidden_summary["admission_state"] == ADMISSION_WITHHOLD)
    check("hidden_result_id_suppressed", hidden_summary["result_id"] == "NONE")
    hidden_negative = clone(hidden)
    hidden_negative["claim_evidence"][0]["coverage_result"] = COVERAGE_NOT_COVERED
    hidden_negative = refresh_declared_ids(hidden_negative)
    hidden_negative_summary = make_summary(hidden_negative)
    check("withheld_outcome_noninterference", hidden_summary == hidden_negative_summary)

    below = clone(single)
    below["context"]["claim_amount_minor"] = 50000
    below["claim_evidence"][0]["assessed_loss_minor"] = 50000
    below = refresh_declared_ids(below)
    below_result = resolve_claims(below)
    check("below_deductible_resolved", below_result["state"] == STATE_RESOLVED)
    check("below_deductible_not_payable", below_result["claim_outcome"] == OUTCOME_NOT_PAYABLE)
    check("below_deductible_zero", below_result["payable_amount_minor"] == 0)

    cap = clone(single)
    cap["context"]["remaining_limit_minor"] = 200000
    cap = refresh_declared_ids(cap)
    cap_result = resolve_claims(cap)
    check("remaining_limit_caps", cap_result["payable_amount_minor"] == 200000)

    evidence_cap = clone(single)
    evidence_cap["claim_evidence"][0]["assessed_loss_minor"] = 300000
    evidence_cap = refresh_declared_ids(evidence_cap)
    evidence_cap_result = resolve_claims(evidence_cap)
    check("assessed_loss_caps", evidence_cap_result["payable_amount_minor"] == 200000)

    for field, replacement, reason in [
        ("coverage_result", COVERAGE_NOT_COVERED, "COVERAGE_NOT_ADMITTED"),
        ("occurrence_result", OCCURRENCE_NOT_ESTABLISHED, "OCCURRENCE_NOT_ADMITTED"),
        ("exclusion_result", BLOCKED, "EXCLUSION_BLOCKS_PAYABILITY"),
        ("control_result", BLOCKED, "CONTROL_BLOCKS_PAYABILITY"),
    ]:
        case = clone(single)
        case["claim_evidence"][0][field] = replacement
        case = refresh_declared_ids(case)
        case_result = resolve_claims(case)
        check(field + "_negative_resolved", case_result["state"] == STATE_RESOLVED)
        check(field + "_negative_denied", case_result["admission_state"] == ADMISSION_DENY)
        check(field + "_negative_reason", reason in case_result["reason_codes"])

    disagreement = clone(multi)
    disagreement["claim_evidence"][1]["assessed_loss_minor"] = 440000
    disagreement = refresh_declared_ids(disagreement)
    disagreement_result = resolve_claims(disagreement)
    check("disagreement_abstains", disagreement_result["state"] == STATE_ABSTAIN)
    check("disagreement_withholds", disagreement_result["admission_state"] == ADMISSION_WITHHOLD)

    missing_authority = clone(multi)
    missing_authority["claim_evidence"] = missing_authority["claim_evidence"][:1]
    missing_authority = refresh_declared_ids(missing_authority)
    missing_result = resolve_claims(missing_authority)
    check("missing_authority_incomplete", missing_result["state"] == STATE_INCOMPLETE)

    unexpected = clone(multi)
    unexpected["claim_evidence"][1]["authority_id"] = "CLAIM-AUTHORITY-X"
    unexpected["claim_evidence"][1]["evidence_id"] = "EVIDENCE-X"
    unexpected = refresh_declared_ids(unexpected)
    unexpected_result = resolve_claims(unexpected)
    check("unexpected_authority_conflict", unexpected_result["state"] == STATE_CONFLICT)

    binding = clone(single)
    binding["claim_evidence"][0]["policy_ref"] = "POLICY-OTHER"
    binding = refresh_declared_ids(binding)
    binding_result = resolve_claims(binding)
    check("binding_conflict", binding_result["state"] == STATE_CONFLICT)

    duplicate = clone(multi)
    duplicate["claim_evidence"][1]["evidence_id"] = duplicate["claim_evidence"][0]["evidence_id"]
    duplicate = refresh_declared_ids(duplicate)
    duplicate_result = resolve_claims(duplicate)
    check("duplicate_evidence_conflict", duplicate_result["state"] == STATE_CONFLICT)

    forbidden = clone(single)
    forbidden["context"]["password"] = "x"
    forbidden_result = resolve_claims(forbidden)
    check("forbidden_field_forbidden", forbidden_result["state"] == STATE_FORBIDDEN)
    check("forbidden_field_withheld", forbidden_result["admission_state"] == ADMISSION_WITHHOLD)
    forbidden_other_value = clone(single)
    forbidden_other_value["context"]["password"] = "different-secret-value"
    check("forbidden_value_redacted_before_submission_commitment", resolve_claims(forbidden_other_value)["submission_id"] == forbidden_result["submission_id"])
    for field_name in ["bankAccount", "bankaccount", "bank-account", "BANK_ACCOUNT", "cardNumber", "dateOfBirth", "payableAmountMinor"]:
        forbidden_variant = clone(single)
        forbidden_variant["context"][field_name] = "x"
        check("forbidden_variant_" + field_name, resolve_claims(forbidden_variant)["state"] == STATE_FORBIDDEN)

    unauthorized = clone(single)
    unauthorized["context"]["evaluation_authorized"] = False
    unauthorized = refresh_declared_ids(unauthorized)
    unauthorized_result = resolve_claims(unauthorized)
    check("unauthorized_abstains", unauthorized_result["state"] == STATE_ABSTAIN)
    check("unauthorized_is_not_conflict_diagnostic", unauthorized_result["conflicts"] == [])

    unknown = clone(single)
    unknown["unexpected"] = True
    unknown_result = resolve_claims(unknown)
    check("unknown_unsupported", unknown_result["state"] == STATE_UNSUPPORTED)

    missing = clone(single)
    del missing["context"]["policy_ref"]
    missing_result2 = resolve_claims(missing)
    check("missing_required_incomplete", missing_result2["state"] == STATE_INCOMPLETE)

    bad_context_id = clone(single)
    bad_context_id["declared_context_id"] = CONTEXT_ID_PREFIX + "0" * 64
    check("context_identity_conflict", resolve_claims(bad_context_id)["state"] == STATE_CONFLICT)
    bad_evidence_id = clone(single)
    bad_evidence_id["declared_evidence_set_id"] = EVIDENCE_SET_ID_PREFIX + "0" * 64
    check("evidence_identity_conflict", resolve_claims(bad_evidence_id)["state"] == STATE_CONFLICT)

    float_case = clone(single)
    float_case["context"]["claim_amount_minor"] = 1.5
    check("float_unsupported", resolve_claims(float_case)["state"] == STATE_UNSUPPORTED)
    negative = clone(single)
    negative["context"]["deductible_minor"] = -1
    check("negative_unsupported", resolve_claims(negative)["state"] == STATE_UNSUPPORTED)
    over = clone(single)
    over["context"]["claim_amount_minor"] = MAX_SAFE_INTEGER + 1
    check("unsafe_integer_unsupported", resolve_claims(over)["state"] == STATE_UNSUPPORTED)

    bundle = build_bundle(single)
    ok, detail = verify_bundle(bundle)
    check("bundle_verifies", ok and detail == "PASS")
    tampered_bundle = clone(bundle)
    tampered_bundle["result"]["payable_amount_minor"] += 1
    check("bundle_tamper_rejected", verify_bundle(tampered_bundle)[0] is False)
    receipt = make_receipt(bundle)
    check("receipt_integrity_passes", check_receipt_integrity(receipt)[0] is True)
    check("receipt_bundle_verifies", verify_receipt_against_bundle(receipt, bundle)[0] is True)
    tampered_receipt = clone(receipt)
    tampered_receipt["payable_amount_minor"] += 1
    check("receipt_tamper_rejected", check_receipt_integrity(tampered_receipt)[0] is False)
    forged_amount_receipt = clone(receipt)
    forged_amount_receipt["payable_amount_minor"] = 999999999
    forged_amount_receipt.pop("receipt_id")
    forged_amount_receipt["receipt_id"] = identity(RECEIPT_ID_PREFIX, forged_amount_receipt)
    check("receipt_self_consistent_amount_forgery_rejected", check_receipt_integrity(forged_amount_receipt)[0] is False)
    forged_authority_receipt = clone(receipt)
    forged_authority_receipt["payment_authority"] = "GRANTED"
    forged_authority_receipt.pop("receipt_id")
    forged_authority_receipt["receipt_id"] = identity(RECEIPT_ID_PREFIX, forged_authority_receipt)
    check("receipt_self_consistent_authority_forgery_rejected", check_receipt_integrity(forged_authority_receipt)[0] is False)
    forged_profile_receipt = clone(receipt)
    forged_profile_receipt["profile_id"] = "OTHER"
    forged_profile_receipt.pop("receipt_id")
    forged_profile_receipt["receipt_id"] = identity(RECEIPT_ID_PREFIX, forged_profile_receipt)
    check("receipt_self_consistent_profile_forgery_rejected", check_receipt_integrity(forged_profile_receipt)[0] is False)
    check("receipt_verify_requires_bundle", verify_receipt(receipt)[1] == "RECEIPT_BUNDLE_REQUIRED")

    summary = make_summary(single)
    check("summary_visible", summary["claim_outcome"] == OUTCOME_PAYABLE)
    check("summary_no_money_movement", summary["money_movement"] == "NONE")
    check("summary_id", summary["summary_id"].startswith(SUMMARY_ID_PREFIX))

    text = canonical_json(single)
    parsed = strict_json_load_text(text)
    check("strict_roundtrip", parsed == single)
    try:
        strict_json_load_text('{"a":1,"a":2}')
        duplicate_rejected = False
    except DuplicateKeyError:
        duplicate_rejected = True
    check("duplicate_json_key_rejected", duplicate_rejected)
    try:
        strict_json_load_text('{"x":1.5}')
        float_rejected = False
    except PortableJSONError:
        float_rejected = True
    check("float_json_rejected", float_rejected)

    normalized_lower = clone(single)
    normalized_lower["context"]["claim_ref"] = "  claim-alpha  "
    normalized_lower["claim_evidence"][0]["claim_ref"] = "claim-alpha"
    normalized_lower = refresh_declared_ids(normalized_lower)
    normalized_lower_result = resolve_claims(normalized_lower)
    check("ascii_identifier_normalization", normalized_lower_result["state"] == STATE_RESOLVED)

    contract = contract_manifest()
    check("contract_id_valid", identity_has_prefix(contract["contract_id"], CONTRACT_ID_PREFIX))
    check("contract_reason_registry_frozen", contract["reason_code_registry"] == sorted(REASON_CODE_REGISTRY))
    check("contract_authority_none", all(value == "NONE" for value in contract["authority_exclusions"].values()))

    abstain_attestation = make_attestation(unauthorized)
    check("attestation_abstain_state", abstain_attestation["state"] == STATE_ABSTAIN)
    check("attestation_abstain_integrity", check_attestation_integrity(abstain_attestation)[0] is True)
    check("attestation_abstain_correspondence", verify_attestation_against_input(abstain_attestation, unauthorized)[0] is True)
    conflict_attestation = make_attestation(binding)
    check("attestation_conflict_state", conflict_attestation["state"] == STATE_CONFLICT)
    forbidden_attestation = make_attestation(forbidden)
    check("attestation_forbidden_state", forbidden_attestation["state"] == STATE_FORBIDDEN)
    incomplete_attestation = make_attestation(missing)
    check("attestation_incomplete_state", incomplete_attestation["state"] == STATE_INCOMPLETE)
    unsupported_attestation = make_attestation(unknown)
    check("attestation_unsupported_state", unsupported_attestation["state"] == STATE_UNSUPPORTED)
    resolved_attestation = make_attestation(single)
    check("attestation_resolved_state", resolved_attestation["state"] == STATE_RESOLVED)
    tampered_attestation = clone(abstain_attestation)
    tampered_attestation["state"] = STATE_RESOLVED
    check("attestation_tamper_rejected", check_attestation_integrity(tampered_attestation)[0] is False)
    check("attestation_verify_requires_input", verify_attestation(abstain_attestation)[1] == "ATTESTATION_INPUT_REQUIRED")

    observed_codes: Set[str] = set()
    for candidate in [single, multi, hidden, hidden_negative, disagreement, missing_authority, unexpected, binding, duplicate, forbidden, unauthorized, unknown, missing, bad_context_id, bad_evidence_id, float_case, negative, over]:
        observed_codes.update(resolve_claims(candidate)["reason_codes"])
    check("reason_registry_covers_reference_cases", observed_codes.issubset(REASON_CODE_REGISTRY))
    invalid_reason_rejected = False
    try:
        ValidationIssue(STATE_UNSUPPORTED, "UNREGISTERED_TEST_REASON", "$")
    except ValueError:
        invalid_reason_rejected = True
    check("reason_registry_construction_firewall", invalid_reason_rejected)
    deep_object: Any = 0
    for _ in range(MAX_JSON_DEPTH + 2):
        deep_object = {"x": deep_object}
    deep_result = resolve_claims(deep_object)
    check("library_entry_depth_guard", deep_result["state"] == STATE_UNSUPPORTED and deep_result["reason_codes"] == ["JSON_DEPTH_LIMIT"])
    parsed_equivalent = strict_json_load_text(canonical_json(single))
    check("library_and_strict_json_entry_equivalence", resolve_claims(single) == resolve_claims(parsed_equivalent))

    failures = [name for name, passed in checks if not passed]
    return len(checks), len(checks) - len(failures), failures


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2))


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="slang_claims_v0_2_1.py")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--self-test", action="store_true")
    group.add_argument("--version", action="store_true")
    group.add_argument("--describe-contract", action="store_true")
    group.add_argument("--example-input", action="store_true")
    group.add_argument("--resolve", metavar="INPUT_JSON")
    group.add_argument("--bundle", metavar="INPUT_JSON")
    group.add_argument("--verify-bundle", metavar="BUNDLE_JSON")
    group.add_argument("--receipt", metavar="BUNDLE_JSON")
    group.add_argument("--check-receipt-integrity", metavar="RECEIPT_JSON")
    group.add_argument("--verify-receipt", metavar="RECEIPT_JSON")
    group.add_argument("--attestation", metavar="INPUT_JSON")
    group.add_argument("--check-attestation-integrity", metavar="ATTESTATION_JSON")
    group.add_argument("--verify-attestation", metavar="ATTESTATION_JSON")
    group.add_argument("--summary", metavar="INPUT_JSON")
    parser.add_argument("--against-bundle", metavar="BUNDLE_JSON")
    parser.add_argument("--against-input", metavar="INPUT_JSON")
    parser.add_argument("--output", metavar="PATH")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    if sys.version_info[:2] < MINIMUM_PYTHON_VERSION:
        print("Python 3.9 or newer is required.", file=sys.stderr)
        return 2
    args = parse_args(argv)
    try:
        if args.self_test:
            total, passed, failures = self_test()
            print("SLANG-Claims v" + VERSION + " self-test")
            print("TOTAL " + str(passed) + "/" + str(total) + " PASS")
            if failures:
                for name in failures:
                    print("FAIL " + name)
                return 1
            return 0
        if args.version:
            print("SLANG-Claims " + VERSION)
            return 0
        if args.describe_contract:
            print_json(contract_manifest())
            return 0
        if args.example_input:
            print_json(build_reference_input(False, True))
            return 0
        if args.resolve:
            print_json(resolve_claims(load_json_file(Path(args.resolve))))
            return 0
        if args.bundle:
            value = build_bundle(load_json_file(Path(args.bundle)))
            if args.output:
                write_json(Path(args.output), value)
            else:
                print_json(value)
            return 0
        if args.verify_bundle:
            ok, detail = verify_bundle(load_json_file(Path(args.verify_bundle)))
            if ok:
                print("BUNDLE_RECONSTRUCTION: PASS")
            else:
                print("BUNDLE_RECONSTRUCTION: FAIL " + detail)
            print("OPERATIONAL_AUTHORITY: NONE")
            return 0 if ok else 1
        if args.receipt:
            value = make_receipt(load_json_file(Path(args.receipt)))
            if args.output:
                write_json(Path(args.output), value)
            else:
                print_json(value)
            return 0
        if args.check_receipt_integrity:
            ok, detail = check_receipt_integrity(load_json_file(Path(args.check_receipt_integrity)))
            if ok:
                print("RECEIPT_INTEGRITY: PASS")
            else:
                print("RECEIPT_INTEGRITY: FAIL " + detail)
            print("BUNDLE_CORRESPONDENCE: NOT_CHECKED")
            print("OPERATIONAL_AUTHORITY: NONE")
            return 0 if ok else 1
        if args.verify_receipt:
            if not args.against_bundle:
                raise ValueError("--verify-receipt requires --against-bundle")
            receipt = load_json_file(Path(args.verify_receipt))
            bundle = load_json_file(Path(args.against_bundle))
            ok, detail = verify_receipt_against_bundle(receipt, bundle)
            if ok:
                print("RECEIPT_INTEGRITY: PASS")
                print("BUNDLE_CORRESPONDENCE: PASS")
            else:
                print("RECEIPT_VERIFICATION: FAIL " + detail)
            print("OPERATIONAL_AUTHORITY: NONE")
            return 0 if ok else 1
        if args.attestation:
            value = make_attestation(load_json_file(Path(args.attestation)))
            if args.output:
                write_json(Path(args.output), value)
            else:
                print_json(value)
            return 0
        if args.check_attestation_integrity:
            ok, detail = check_attestation_integrity(load_json_file(Path(args.check_attestation_integrity)))
            if ok:
                print("ATTESTATION_INTEGRITY: PASS")
            else:
                print("ATTESTATION_INTEGRITY: FAIL " + detail)
            print("INPUT_CORRESPONDENCE: NOT_CHECKED")
            print("OPERATIONAL_AUTHORITY: NONE")
            return 0 if ok else 1
        if args.verify_attestation:
            if not args.against_input:
                raise ValueError("--verify-attestation requires --against-input")
            attestation = load_json_file(Path(args.verify_attestation))
            raw_input = load_json_file(Path(args.against_input))
            ok, detail = verify_attestation_against_input(attestation, raw_input)
            if ok:
                print("ATTESTATION_INTEGRITY: PASS")
                print("INPUT_CORRESPONDENCE: PASS")
            else:
                print("ATTESTATION_VERIFICATION: FAIL " + detail)
            print("OPERATIONAL_AUTHORITY: NONE")
            return 0 if ok else 1
        if args.summary:
            print_json(make_summary(load_json_file(Path(args.summary))))
            return 0
        print_json(make_summary(build_reference_input(False, True)))
        return 0
    except Exception as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
