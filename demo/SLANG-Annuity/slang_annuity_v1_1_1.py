import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

VERSION = "1.1.1"
MINIMUM_PYTHON_VERSION = (3, 9)
CORE_VERSION = "SLANG-CORE-1-D05"
PROFILE_ID = "SLANG-ANNUITY-PROFILE-1-D01"
RULESET_ID = "SLANG-ANNUITY-RULESET-1-D01"
CANONICALIZATION_ID = "SLANG-CANONICAL-JSON-1-D02"
AUTHORITY_PROFILE_ID = "ANNUITY-PAYOUT-AUTHORITY-EVIDENCE-1"
QUANTUM_PROFILE_ID = "ANNUITY-DECLARED-PERIODIC-BENEFIT-PASS-THROUGH-1"
INPUT_SCHEMA = "SLANG-ANNUITY-INPUT-1"
RESULT_SCHEMA = "SLANG-ANNUITY-RESULT-1"
BUNDLE_SCHEMA = "SLANG-ANNUITY-BUNDLE-1"
RECEIPT_SCHEMA = "SLANG-ANNUITY-RECEIPT-1"
SUMMARY_SCHEMA = "SLANG-ANNUITY-SUMMARY-1"
ATTESTATION_SCHEMA = "SLANG-ANNUITY-ATTESTATION-1"
CONTRACT_SCHEMA = "SLANG-ANNUITY-CONTRACT-1"
STATE_RESOLVED = "RESOLVED"
STATE_INCOMPLETE = "INCOMPLETE"
STATE_CONFLICT = "CONFLICT"
STATE_FORBIDDEN = "FORBIDDEN"
STATE_UNSUPPORTED = "UNSUPPORTED"
STATE_ABSTAIN = "ABSTAIN"
OUTCOME_PAYABLE = "PAYABLE"
OUTCOME_NOT_PAYABLE = "NOT_PAYABLE"
OUTCOME_NONE = "NONE"
VISIBILITY_VISIBLE = "VISIBLE"
VISIBILITY_WITHHELD = "WITHHELD"
VISIBILITY_NONE = "NONE"
EVIDENCE_SINGLE = "SINGLE_AUTHORITY"
EVIDENCE_MULTI = "MULTI_AUTHORITY_EXACT_AGREEMENT"
SUPPORTED_EVIDENCE_MODES = {EVIDENCE_SINGLE, EVIDENCE_MULTI}
SUPPORTED_PAYOUT_MODES = {"ANNUITANT_PERIODIC"}
SUPPORTED_CONTRACT_STATUS = {"ACTIVE", "INACTIVE", "SUSPENDED", "TERMINATED"}
SUPPORTED_PAYOUT_ELECTION = {"ELECTED", "NOT_ELECTED"}
SUPPORTED_PAYEE_STATUS = {"VALID", "NOT_VALID"}
MAX_JSON_DEPTH = 32
MAX_STRING_LENGTH = 1024
MAX_CONTAINER_ITEMS = 4096
MAX_SAFE_INTEGER = 9007199254740991
MAX_INPUT_BYTES = 1048576
CONTEXT_ID_PREFIX = "slang_annuity_context_sha256:"
EVIDENCE_SET_ID_PREFIX = "slang_annuity_evidence_set_sha256:"
EVIDENCE_COMMITMENT_PREFIX = "slang_annuity_evidence_sha256:"
RULE_PROFILE_ID_PREFIX = "slang_annuity_rule_profile_sha256:"
CANONICAL_INPUT_ID_PREFIX = "slang_annuity_canonical_input_sha256:"
RESULT_ID_PREFIX = "slang_annuity_result_sha256:"
OUTCOME_ID_PREFIX = "slang_annuity_outcome_sha256:"
BUNDLE_ID_PREFIX = "slang_annuity_bundle_sha256:"
RECEIPT_ID_PREFIX = "slang_annuity_receipt_sha256:"
ATTESTATION_ID_PREFIX = "slang_annuity_attestation_sha256:"
CONTRACT_ID_PREFIX = "slang_annuity_contract_sha256:"
IDENTITY_DOMAIN_ID_PREFIX = "slang_annuity_identity_domain_sha256:"
INPUT_KEYS = {"schema", "profile_id", "ruleset_id", "context", "annuity_evidence", "declared_context_id", "declared_evidence_set_id"}
CONTEXT_KEYS = {"case_id", "contract_reference", "currency", "payout_mode", "evidence_mode", "evaluation_authorized", "visibility_authorized", "expected_authority_ids"}
EVIDENCE_KEYS = {"schema", "authority_id", "case_id", "contract_reference", "currency", "contract_status", "attained_age_years", "minimum_start_age_years", "credited_service_years", "minimum_vesting_years", "total_contributed_minor", "minimum_contribution_minor", "payout_election", "payee_status", "declared_periodic_payout_minor", "evidence_commitment"}
AGREEMENT_FIELDS = ["case_id", "contract_reference", "currency", "contract_status", "attained_age_years", "minimum_start_age_years", "credited_service_years", "minimum_vesting_years", "total_contributed_minor", "minimum_contribution_minor", "payout_election", "payee_status", "declared_periodic_payout_minor"]
DERIVED_FIELD_SIGNATURES = {
    "agecondition", "ageeligible", "annuityoutcome", "attestationid", "bundleid", "canonicalinputid", "contributioncondition", "contributionsufficient", "eligibilitystate", "outcomeid", "payeecondition", "payoutamount", "payoutamountminor", "payouteligible", "receiptid", "resolutionstate", "resultid", "ruleprofileid", "vestingcomplete", "vestingcondition", "visibilitystate"
}
REASON_CODE_REGISTRY = {
    "PAYOUT_ADMITTED",
    "CONTRACT_NOT_ACTIVE",
    "AGE_CONDITION_NOT_SATISFIED",
    "VESTING_CONDITION_NOT_SATISFIED",
    "CONTRIBUTION_CONDITION_NOT_SATISFIED",
    "PAYOUT_NOT_ELECTED",
    "PAYEE_NOT_VALID",
    "DECLARED_PERIODIC_PAYOUT_NOT_POSITIVE",
    "MISSING_REQUIRED_FIELD",
    "EMPTY_IDENTIFIER_LIST",
    "MISSING_EXPECTED_AUTHORITY",
    "SINGLE_AUTHORITY_REQUIRES_ONE_EXPECTED_AUTHORITY",
    "SINGLE_AUTHORITY_REQUIRES_ONE_EVIDENCE_RECORD",
    "MULTI_AUTHORITY_REQUIRES_MULTIPLE_EXPECTED_AUTHORITIES",
    "MULTI_AUTHORITY_REQUIRES_MULTIPLE_EVIDENCE_RECORDS",
    "DUPLICATE_AUTHORITY_ID",
    "UNEXPECTED_AUTHORITY",
    "EVIDENCE_RESULT_DISAGREEMENT",
    "EVALUATION_NOT_AUTHORIZED",
    "CONTEXT_BINDING_MISMATCH",
    "EVIDENCE_COMMITMENT_MISMATCH",
    "DECLARED_CONTEXT_ID_MISMATCH",
    "DECLARED_EVIDENCE_SET_ID_MISMATCH",
    "FORBIDDEN_DERIVED_FIELD",
    "UNKNOWN_FIELD",
    "UNSUPPORTED_INPUT_SCHEMA",
    "UNSUPPORTED_PROFILE_ID",
    "UNSUPPORTED_RULESET_ID",
    "UNSUPPORTED_EVIDENCE_SCHEMA",
    "UNSUPPORTED_EVIDENCE_MODE",
    "UNSUPPORTED_PAYOUT_MODE",
    "UNSUPPORTED_CONTRACT_STATUS",
    "UNSUPPORTED_PAYOUT_ELECTION",
    "UNSUPPORTED_PAYEE_STATUS",
    "INVALID_IDENTIFIER",
    "INVALID_CURRENCY",
    "INVALID_BOOLEAN",
    "INVALID_NONNEGATIVE_INTEGER",
    "INVALID_POSITIVE_INTEGER",
    "INVALID_COMMITMENT",
    "INVALID_TOP_LEVEL_TYPE",
    "INVALID_CONTEXT_TYPE",
    "INVALID_EVIDENCE_LIST_TYPE",
    "INVALID_EVIDENCE_RECORD_TYPE",
    "JSON_DEPTH_LIMIT",
    "JSON_STRING_LIMIT",
    "JSON_CONTAINER_LIMIT",
    "JSON_INTEGER_LIMIT",
    "FLOAT_NOT_SUPPORTED",
    "NON_STRING_KEY",
    "UNSUPPORTED_JSON_TYPE",
    "OUTCOME_WITHHELD"
}

@dataclass(frozen=True)
class ValidationIssue:
    state: str
    code: str
    path: str

    def __post_init__(self) -> None:
        if self.code not in REASON_CODE_REGISTRY:
            raise ValueError("unregistered reason code: " + self.code)


def canonical_json(value: Any) -> str:
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
    item_count = 0

    def walk(item: Any, depth: int) -> None:
        nonlocal item_count
        if depth > MAX_JSON_DEPTH:
            raise ValueError("JSON_DEPTH_LIMIT")
        if item is None or isinstance(item, bool):
            return
        if isinstance(item, int):
            if abs(item) > MAX_SAFE_INTEGER:
                raise ValueError("JSON_INTEGER_LIMIT")
            return
        if isinstance(item, float):
            raise ValueError("FLOAT_NOT_SUPPORTED")
        if isinstance(item, str):
            if len(item) > MAX_STRING_LENGTH:
                raise ValueError("JSON_STRING_LIMIT")
            return
        if isinstance(item, list):
            item_count += len(item)
            if item_count > MAX_CONTAINER_ITEMS:
                raise ValueError("JSON_CONTAINER_LIMIT")
            for child in item:
                walk(child, depth + 1)
            return
        if isinstance(item, dict):
            item_count += len(item)
            if item_count > MAX_CONTAINER_ITEMS:
                raise ValueError("JSON_CONTAINER_LIMIT")
            for key, child in item.items():
                if not isinstance(key, str):
                    raise ValueError("NON_STRING_KEY")
                if len(key) > MAX_STRING_LENGTH:
                    raise ValueError("JSON_STRING_LIMIT")
                walk(child, depth + 1)
            return
        raise ValueError("UNSUPPORTED_JSON_TYPE")

    walk(value, 0)


def strict_json_load_text(text: str) -> Any:
    if len(text.encode("utf-8")) > MAX_INPUT_BYTES:
        raise ValueError("INPUT_SIZE_LIMIT")

    def pairs_hook(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
        output: Dict[str, Any] = {}
        for key, value in pairs:
            if key in output:
                raise ValueError("DUPLICATE_JSON_KEY:" + key)
            output[key] = value
        return output

    def reject_float(value: str) -> Any:
        raise ValueError("FLOAT_NOT_SUPPORTED:" + value)

    def reject_constant(value: str) -> Any:
        raise ValueError("NONFINITE_NUMBER_NOT_SUPPORTED:" + value)

    loaded = json.loads(text, object_pairs_hook=pairs_hook, parse_float=reject_float, parse_constant=reject_constant)
    validate_portable_json(loaded)
    return loaded


def load_json_file(path: Path) -> Any:
    return strict_json_load_text(path.read_text(encoding="utf-8"))


def normalize_identifier(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized or len(normalized) > 128:
        return None
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]*", normalized):
        return None
    return normalized


def normalize_currency(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    normalized = value.strip().upper()
    if not re.fullmatch(r"[A-Z]{3}", normalized):
        return None
    return normalized


def normalize_commitment(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if not re.fullmatch(r"slang_annuity_evidence_sha256:[0-9a-f]{64}", normalized):
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
    return sorted(issues, key=lambda item: (issue_rank(item.state), item.code, item.path))[0]


def unique_sorted(values: Iterable[str]) -> List[str]:
    return sorted(set(values))


def field_signature(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def scan_forbidden_fields(value: Any, path: str = "$", output: Optional[List[str]] = None) -> List[str]:
    result = [] if output is None else output
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = path + "." + str(key)
            if isinstance(key, str) and field_signature(key) in DERIVED_FIELD_SIGNATURES:
                result.append(child_path)
            scan_forbidden_fields(child, child_path, result)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            scan_forbidden_fields(child, path + "[" + str(index) + "]", result)
    return result


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
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_CURRENCY", path + "." + key))
    return normalized


def required_bool(value: Dict[str, Any], key: str, path: str, issues: List[ValidationIssue]) -> Optional[bool]:
    if key not in value:
        issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_REQUIRED_FIELD", path + "." + key))
        return None
    item = value.get(key)
    if not isinstance(item, bool):
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_BOOLEAN", path + "." + key))
        return None
    return item


def required_nonnegative_int(value: Dict[str, Any], key: str, path: str, issues: List[ValidationIssue]) -> Optional[int]:
    if key not in value:
        issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_REQUIRED_FIELD", path + "." + key))
        return None
    item = value.get(key)
    if isinstance(item, bool) or not isinstance(item, int) or item < 0 or item > MAX_SAFE_INTEGER:
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_NONNEGATIVE_INTEGER", path + "." + key))
        return None
    return item


def required_positive_int(value: Dict[str, Any], key: str, path: str, issues: List[ValidationIssue]) -> Optional[int]:
    item = required_nonnegative_int(value, key, path, issues)
    if item is not None and item <= 0:
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_POSITIVE_INTEGER", path + "." + key))
        return None
    return item


def required_enum(value: Dict[str, Any], key: str, supported: Set[str], code: str, path: str, issues: List[ValidationIssue]) -> Optional[str]:
    if key not in value:
        issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_REQUIRED_FIELD", path + "." + key))
        return None
    item = value.get(key)
    if not isinstance(item, str):
        issues.append(ValidationIssue(STATE_UNSUPPORTED, code, path + "." + key))
        return None
    normalized = item.strip().upper()
    if normalized not in supported:
        issues.append(ValidationIssue(STATE_UNSUPPORTED, code, path + "." + key))
        return None
    return normalized


def normalize_identifier_list(value: Any, path: str, issues: List[ValidationIssue]) -> Optional[List[str]]:
    if not isinstance(value, list):
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_IDENTIFIER", path))
        return None
    if not value:
        issues.append(ValidationIssue(STATE_INCOMPLETE, "EMPTY_IDENTIFIER_LIST", path))
        return None
    normalized: List[str] = []
    for index, item in enumerate(value):
        identifier = normalize_identifier(item)
        if identifier is None:
            issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_IDENTIFIER", path + "[" + str(index) + "]"))
        else:
            normalized.append(identifier)
    return sorted(normalized)


def normalize_context(value: Any) -> Tuple[Optional[Dict[str, Any]], List[ValidationIssue]]:
    issues: List[ValidationIssue] = []
    if not isinstance(value, dict):
        return None, [ValidationIssue(STATE_UNSUPPORTED, "INVALID_CONTEXT_TYPE", "$.context")]
    issues.extend(unknown_key_issues(value, CONTEXT_KEYS, "$.context"))
    case_id = required_identifier(value, "case_id", "$.context", issues)
    contract_reference = required_identifier(value, "contract_reference", "$.context", issues)
    currency = required_currency(value, "currency", "$.context", issues)
    payout_mode = required_enum(value, "payout_mode", SUPPORTED_PAYOUT_MODES, "UNSUPPORTED_PAYOUT_MODE", "$.context", issues)
    evidence_mode = required_enum(value, "evidence_mode", SUPPORTED_EVIDENCE_MODES, "UNSUPPORTED_EVIDENCE_MODE", "$.context", issues)
    evaluation_authorized = required_bool(value, "evaluation_authorized", "$.context", issues)
    visibility_authorized = required_bool(value, "visibility_authorized", "$.context", issues)
    if "expected_authority_ids" not in value:
        issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_REQUIRED_FIELD", "$.context.expected_authority_ids"))
        expected_authority_ids = None
    else:
        expected_authority_ids = normalize_identifier_list(value.get("expected_authority_ids"), "$.context.expected_authority_ids", issues)
    if expected_authority_ids is not None and len(expected_authority_ids) != len(set(expected_authority_ids)):
        issues.append(ValidationIssue(STATE_CONFLICT, "DUPLICATE_AUTHORITY_ID", "$.context.expected_authority_ids"))
    if evidence_mode == EVIDENCE_SINGLE and expected_authority_ids is not None and len(expected_authority_ids) != 1:
        issues.append(ValidationIssue(STATE_INCOMPLETE, "SINGLE_AUTHORITY_REQUIRES_ONE_EXPECTED_AUTHORITY", "$.context.expected_authority_ids"))
    if evidence_mode == EVIDENCE_MULTI and expected_authority_ids is not None and len(expected_authority_ids) < 2:
        issues.append(ValidationIssue(STATE_INCOMPLETE, "MULTI_AUTHORITY_REQUIRES_MULTIPLE_EXPECTED_AUTHORITIES", "$.context.expected_authority_ids"))
    if evaluation_authorized is False:
        issues.append(ValidationIssue(STATE_ABSTAIN, "EVALUATION_NOT_AUTHORIZED", "$.context.evaluation_authorized"))
    if None in (case_id, contract_reference, currency, payout_mode, evidence_mode, evaluation_authorized, visibility_authorized, expected_authority_ids):
        return None, issues
    return {
        "case_id": case_id,
        "contract_reference": contract_reference,
        "currency": currency,
        "payout_mode": payout_mode,
        "evidence_mode": evidence_mode,
        "evaluation_authorized": evaluation_authorized,
        "visibility_authorized": visibility_authorized,
        "expected_authority_ids": expected_authority_ids,
    }, issues


def evidence_commitment_material(record: Dict[str, Any]) -> Dict[str, Any]:
    return {key: record[key] for key in sorted(EVIDENCE_KEYS - {"evidence_commitment"}) if key in record}


def evidence_commitment_for_record(record: Dict[str, Any]) -> str:
    return identity(EVIDENCE_COMMITMENT_PREFIX, evidence_commitment_material(record))


def normalize_evidence_record(value: Any, index: int) -> Tuple[Optional[Dict[str, Any]], List[ValidationIssue]]:
    path = "$.annuity_evidence[" + str(index) + "]"
    issues: List[ValidationIssue] = []
    if not isinstance(value, dict):
        return None, [ValidationIssue(STATE_UNSUPPORTED, "INVALID_EVIDENCE_RECORD_TYPE", path)]
    issues.extend(unknown_key_issues(value, EVIDENCE_KEYS, path))
    schema = value.get("schema")
    if schema is None:
        issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_REQUIRED_FIELD", path + ".schema"))
    elif schema != AUTHORITY_PROFILE_ID:
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "UNSUPPORTED_EVIDENCE_SCHEMA", path + ".schema"))
    authority_id = required_identifier(value, "authority_id", path, issues)
    case_id = required_identifier(value, "case_id", path, issues)
    contract_reference = required_identifier(value, "contract_reference", path, issues)
    currency = required_currency(value, "currency", path, issues)
    contract_status = required_enum(value, "contract_status", SUPPORTED_CONTRACT_STATUS, "UNSUPPORTED_CONTRACT_STATUS", path, issues)
    attained_age_years = required_nonnegative_int(value, "attained_age_years", path, issues)
    minimum_start_age_years = required_nonnegative_int(value, "minimum_start_age_years", path, issues)
    credited_service_years = required_nonnegative_int(value, "credited_service_years", path, issues)
    minimum_vesting_years = required_nonnegative_int(value, "minimum_vesting_years", path, issues)
    total_contributed_minor = required_nonnegative_int(value, "total_contributed_minor", path, issues)
    minimum_contribution_minor = required_nonnegative_int(value, "minimum_contribution_minor", path, issues)
    payout_election = required_enum(value, "payout_election", SUPPORTED_PAYOUT_ELECTION, "UNSUPPORTED_PAYOUT_ELECTION", path, issues)
    payee_status = required_enum(value, "payee_status", SUPPORTED_PAYEE_STATUS, "UNSUPPORTED_PAYEE_STATUS", path, issues)
    declared_periodic_payout_minor = required_nonnegative_int(value, "declared_periodic_payout_minor", path, issues)
    if "evidence_commitment" not in value:
        issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_REQUIRED_FIELD", path + ".evidence_commitment"))
        evidence_commitment = None
    else:
        evidence_commitment = normalize_commitment(value.get("evidence_commitment"))
        if evidence_commitment is None:
            issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_COMMITMENT", path + ".evidence_commitment"))
    fields = [authority_id, case_id, contract_reference, currency, contract_status, attained_age_years, minimum_start_age_years, credited_service_years, minimum_vesting_years, total_contributed_minor, minimum_contribution_minor, payout_election, payee_status, declared_periodic_payout_minor, evidence_commitment]
    if schema != AUTHORITY_PROFILE_ID or any(item is None for item in fields):
        return None, issues
    normalized = {
        "schema": AUTHORITY_PROFILE_ID,
        "authority_id": authority_id,
        "case_id": case_id,
        "contract_reference": contract_reference,
        "currency": currency,
        "contract_status": contract_status,
        "attained_age_years": attained_age_years,
        "minimum_start_age_years": minimum_start_age_years,
        "credited_service_years": credited_service_years,
        "minimum_vesting_years": minimum_vesting_years,
        "total_contributed_minor": total_contributed_minor,
        "minimum_contribution_minor": minimum_contribution_minor,
        "payout_election": payout_election,
        "payee_status": payee_status,
        "declared_periodic_payout_minor": declared_periodic_payout_minor,
        "evidence_commitment": evidence_commitment,
    }
    if evidence_commitment_for_record(normalized) != evidence_commitment:
        issues.append(ValidationIssue(STATE_CONFLICT, "EVIDENCE_COMMITMENT_MISMATCH", path + ".evidence_commitment"))
    return normalized, issues


def context_material(context: Dict[str, Any]) -> Dict[str, Any]:
    return clone(context)


def evidence_set_material(evidence: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    return {"authority_profile_id": AUTHORITY_PROFILE_ID, "records": sorted([clone(item) for item in evidence], key=lambda item: item["authority_id"])}


def agreement_material(record: Dict[str, Any]) -> Dict[str, Any]:
    return {key: record[key] for key in AGREEMENT_FIELDS}


def rule_profile_material() -> Dict[str, Any]:
    return {
        "profile_id": PROFILE_ID,
        "ruleset_id": RULESET_ID,
        "authority_profile_id": AUTHORITY_PROFILE_ID,
        "quantum_profile_id": QUANTUM_PROFILE_ID,
        "supported_payout_modes": sorted(SUPPORTED_PAYOUT_MODES),
        "supported_evidence_modes": sorted(SUPPORTED_EVIDENCE_MODES),
        "state_precedence": [STATE_FORBIDDEN, STATE_CONFLICT, STATE_UNSUPPORTED, STATE_INCOMPLETE, STATE_ABSTAIN, STATE_RESOLVED],
        "quantum_relation": "admitted_payout_amount_minor = declared_periodic_payout_minor",
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
        "schemas": {
            "input": INPUT_SCHEMA,
            "result": RESULT_SCHEMA,
            "bundle": BUNDLE_SCHEMA,
            "receipt": RECEIPT_SCHEMA,
            "summary": SUMMARY_SCHEMA,
            "attestation": ATTESTATION_SCHEMA,
            "contract": CONTRACT_SCHEMA,
        },
        "supported_payout_modes": sorted(SUPPORTED_PAYOUT_MODES),
        "supported_evidence_modes": sorted(SUPPORTED_EVIDENCE_MODES),
        "supported_contract_status": sorted(SUPPORTED_CONTRACT_STATUS),
        "supported_payout_election": sorted(SUPPORTED_PAYOUT_ELECTION),
        "supported_payee_status": sorted(SUPPORTED_PAYEE_STATUS),
        "state_precedence": [STATE_FORBIDDEN, STATE_CONFLICT, STATE_UNSUPPORTED, STATE_INCOMPLETE, STATE_ABSTAIN, STATE_RESOLVED],
        "reason_codes": sorted(REASON_CODE_REGISTRY),
        "identity_domain_material": identity_domain_material(),
        "rule_profile_material": rule_profile_material(),
        "forbidden_derived_field_signatures": sorted(DERIVED_FIELD_SIGNATURES),
        "authority_boundary": {
            "source_authenticity": "NOT_ESTABLISHED_BY_REFERENCE_PROFILE",
            "contract_interpretation_authority": "NONE",
            "legal_entitlement_authority": "NONE",
            "tax_authority": "NONE",
            "actuarial_valuation_authority": "NONE",
            "payment_authority": "NONE",
        },
        "receipt_integrity_scope": "SELF_CONSISTENCY_AND_DECLARED_INVARIANTS_ONLY",
        "receipt_correspondence_scope": "REQUIRES_EXACT_RECONSTRUCTION_BUNDLE",
        "claim_boundary": "BOUNDED_ANNUITANT_PERIODIC_PAYOUT_ADMISSION_ONLY",
    }


def contract_manifest() -> Dict[str, Any]:
    value = contract_manifest_material()
    value["identity_domain_id"] = identity_domain_id()
    value["contract_id"] = identity(CONTRACT_ID_PREFIX, value)
    return value


def contract_id() -> str:
    return contract_manifest()["contract_id"]


def binding_issues(context: Dict[str, Any], evidence: Sequence[Dict[str, Any]]) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    for index, record in enumerate(evidence):
        path = "$.annuity_evidence[" + str(index) + "]"
        if record["case_id"] != context["case_id"] or record["contract_reference"] != context["contract_reference"] or record["currency"] != context["currency"]:
            issues.append(ValidationIssue(STATE_CONFLICT, "CONTEXT_BINDING_MISMATCH", path))
    return issues


def authority_set_issues(context: Dict[str, Any], evidence: Sequence[Dict[str, Any]]) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    expected = context["expected_authority_ids"]
    observed = [item["authority_id"] for item in evidence]
    if len(observed) != len(set(observed)):
        issues.append(ValidationIssue(STATE_CONFLICT, "DUPLICATE_AUTHORITY_ID", "$.annuity_evidence"))
    unexpected = sorted(set(observed) - set(expected))
    missing = sorted(set(expected) - set(observed))
    for authority in unexpected:
        issues.append(ValidationIssue(STATE_CONFLICT, "UNEXPECTED_AUTHORITY", "$.annuity_evidence:" + authority))
    for authority in missing:
        issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_EXPECTED_AUTHORITY", "$.annuity_evidence:" + authority))
    if context["evidence_mode"] == EVIDENCE_SINGLE and len(evidence) != 1:
        issues.append(ValidationIssue(STATE_INCOMPLETE, "SINGLE_AUTHORITY_REQUIRES_ONE_EVIDENCE_RECORD", "$.annuity_evidence"))
    if context["evidence_mode"] == EVIDENCE_MULTI and len(evidence) < 2:
        issues.append(ValidationIssue(STATE_INCOMPLETE, "MULTI_AUTHORITY_REQUIRES_MULTIPLE_EVIDENCE_RECORDS", "$.annuity_evidence"))
    return issues


def evidence_agreement_issues(context: Dict[str, Any], evidence: Sequence[Dict[str, Any]]) -> List[ValidationIssue]:
    if context["evidence_mode"] != EVIDENCE_MULTI or len(evidence) < 2:
        return []
    first = agreement_material(evidence[0])
    for record in evidence[1:]:
        if agreement_material(record) != first:
            return [ValidationIssue(STATE_ABSTAIN, "EVIDENCE_RESULT_DISAGREEMENT", "$.annuity_evidence")]
    return []


def normalize_input(raw_input: Any) -> Tuple[Optional[Dict[str, Any]], List[ValidationIssue]]:
    issues: List[ValidationIssue] = []
    try:
        validate_portable_json(raw_input)
    except ValueError as exc:
        code = str(exc).split(":", 1)[0]
        mapped_codes = {
            "JSON_DEPTH_LIMIT",
            "JSON_STRING_LIMIT",
            "JSON_CONTAINER_LIMIT",
            "JSON_INTEGER_LIMIT",
            "FLOAT_NOT_SUPPORTED",
            "NON_STRING_KEY",
            "UNSUPPORTED_JSON_TYPE",
        }
        mapped = code if code in mapped_codes else "UNKNOWN_FIELD"
        return None, [ValidationIssue(STATE_UNSUPPORTED, mapped, "$")]
    forbidden = scan_forbidden_fields(raw_input)
    for path in forbidden:
        issues.append(ValidationIssue(STATE_FORBIDDEN, "FORBIDDEN_DERIVED_FIELD", path))
    if not isinstance(raw_input, dict):
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_TOP_LEVEL_TYPE", "$"))
        return None, issues
    issues.extend(unknown_key_issues(raw_input, INPUT_KEYS, "$"))
    schema = raw_input.get("schema")
    if schema is None:
        issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_REQUIRED_FIELD", "$.schema"))
    elif schema != INPUT_SCHEMA:
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "UNSUPPORTED_INPUT_SCHEMA", "$.schema"))
    profile_id = raw_input.get("profile_id")
    if profile_id is None:
        issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_REQUIRED_FIELD", "$.profile_id"))
    elif profile_id != PROFILE_ID:
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "UNSUPPORTED_PROFILE_ID", "$.profile_id"))
    ruleset_id = raw_input.get("ruleset_id")
    if ruleset_id is None:
        issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_REQUIRED_FIELD", "$.ruleset_id"))
    elif ruleset_id != RULESET_ID:
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "UNSUPPORTED_RULESET_ID", "$.ruleset_id"))
    if "context" not in raw_input:
        issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_REQUIRED_FIELD", "$.context"))
        context = None
    else:
        context, context_issues = normalize_context(raw_input.get("context"))
        issues.extend(context_issues)
    if "annuity_evidence" not in raw_input:
        issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_REQUIRED_FIELD", "$.annuity_evidence"))
        evidence: Optional[List[Dict[str, Any]]] = None
    elif not isinstance(raw_input.get("annuity_evidence"), list):
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_EVIDENCE_LIST_TYPE", "$.annuity_evidence"))
        evidence = None
    else:
        raw_evidence = raw_input.get("annuity_evidence")
        evidence = []
        for index, record in enumerate(raw_evidence):
            normalized_record, record_issues = normalize_evidence_record(record, index)
            issues.extend(record_issues)
            if normalized_record is not None:
                evidence.append(normalized_record)
        evidence_complete = len(evidence) == len(raw_evidence)
        evidence = sorted(evidence, key=lambda item: item["authority_id"])
    if schema != INPUT_SCHEMA or profile_id != PROFILE_ID or ruleset_id != RULESET_ID or context is None or evidence is None:
        return None, issues
    normalized = {
        "schema": INPUT_SCHEMA,
        "profile_id": PROFILE_ID,
        "ruleset_id": RULESET_ID,
        "context": context,
        "annuity_evidence": evidence,
    }
    issues.extend(binding_issues(context, evidence))
    issues.extend(authority_set_issues(context, evidence))
    issues.extend(evidence_agreement_issues(context, evidence))
    actual_context_id = identity(CONTEXT_ID_PREFIX, context_material(context))
    actual_evidence_set_id = identity(EVIDENCE_SET_ID_PREFIX, evidence_set_material(evidence))
    if "declared_context_id" in raw_input:
        declared_context_id = raw_input.get("declared_context_id")
        if declared_context_id != actual_context_id:
            issues.append(ValidationIssue(STATE_CONFLICT, "DECLARED_CONTEXT_ID_MISMATCH", "$.declared_context_id"))
        else:
            normalized["declared_context_id"] = declared_context_id
    if "declared_evidence_set_id" in raw_input and evidence_complete:
        declared_evidence_set_id = raw_input.get("declared_evidence_set_id")
        if declared_evidence_set_id != actual_evidence_set_id:
            issues.append(ValidationIssue(STATE_CONFLICT, "DECLARED_EVIDENCE_SET_ID_MISMATCH", "$.declared_evidence_set_id"))
        else:
            normalized["declared_evidence_set_id"] = declared_evidence_set_id
    return normalized, issues


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
        "rule_profile_id": identity(RULE_PROFILE_ID_PREFIX, rule_profile_material()),
        "state": STATE_INCOMPLETE,
        "resolution_state": STATE_INCOMPLETE,
        "annuity_outcome": OUTCOME_NONE,
        "visibility_state": VISIBILITY_NONE,
        "currency": "NONE",
        "payout_amount_minor": 0,
        "age_condition": "NONE",
        "vesting_condition": "NONE",
        "contribution_condition": "NONE",
        "contract_condition": "NONE",
        "election_condition": "NONE",
        "payee_condition": "NONE",
        "amount_condition": "NONE",
        "reason_codes": [],
        "missing_dependencies": [],
        "conflicts": [],
        "diagnostics": [],
        "authority_ids": [],
        "context_id": "NONE",
        "evidence_set_id": "NONE",
        "canonical_input_id": "NONE",
        "outcome_id": "NONE",
        "result_id": "NONE",
        "source_authenticity": "NOT_ESTABLISHED_BY_REFERENCE_PROFILE",
        "contract_interpretation_authority": "NONE",
        "legal_entitlement_authority": "NONE",
        "tax_authority": "NONE",
        "actuarial_valuation_authority": "NONE",
        "payment_authority": "NONE",
    }


def result_identity_material(result: Dict[str, Any]) -> Dict[str, Any]:
    value = clone(result)
    value.pop("result_id", None)
    return value


def outcome_identity_material(result: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "state": result["state"],
        "annuity_outcome": result["annuity_outcome"],
        "currency": result["currency"],
        "payout_amount_minor": result["payout_amount_minor"],
        "context_id": result["context_id"],
        "evidence_set_id": result["evidence_set_id"],
        "profile_id": PROFILE_ID,
        "ruleset_id": RULESET_ID,
    }


def resolve_annuity(raw_input: Any) -> Dict[str, Any]:
    result = base_result()
    normalized, issues = normalize_input(raw_input)
    if normalized is not None:
        result["canonical_input_id"] = identity(CANONICAL_INPUT_ID_PREFIX, normalized)
        result["context_id"] = identity(CONTEXT_ID_PREFIX, context_material(normalized["context"]))
        result["evidence_set_id"] = identity(EVIDENCE_SET_ID_PREFIX, evidence_set_material(normalized["annuity_evidence"]))
        result["authority_ids"] = sorted(item["authority_id"] for item in normalized["annuity_evidence"])
        result["currency"] = normalized["context"]["currency"]
    if issues:
        primary = choose_issue(issues)
        result["state"] = primary.state
        result["resolution_state"] = primary.state
        result["reason_codes"] = unique_sorted(issue.code for issue in issues)
        result["missing_dependencies"] = unique_sorted(issue.path for issue in issues if issue.state == STATE_INCOMPLETE)
        result["conflicts"] = unique_sorted(issue.path for issue in issues if issue.state == STATE_CONFLICT)
        result["diagnostics"] = unique_sorted(issue.path + ":" + issue.code for issue in issues)
        result["result_id"] = identity(RESULT_ID_PREFIX, result_identity_material(result))
        return result
    assert normalized is not None
    context = normalized["context"]
    evidence = normalized["annuity_evidence"]
    agreed = evidence[0]
    result["contract_condition"] = "SATISFIED" if agreed["contract_status"] == "ACTIVE" else "NOT_SATISFIED"
    result["age_condition"] = "SATISFIED" if agreed["attained_age_years"] >= agreed["minimum_start_age_years"] else "NOT_SATISFIED"
    result["vesting_condition"] = "SATISFIED" if agreed["credited_service_years"] >= agreed["minimum_vesting_years"] else "NOT_SATISFIED"
    result["contribution_condition"] = "SATISFIED" if agreed["total_contributed_minor"] >= agreed["minimum_contribution_minor"] else "NOT_SATISFIED"
    result["election_condition"] = "SATISFIED" if agreed["payout_election"] == "ELECTED" else "NOT_SATISFIED"
    result["payee_condition"] = "SATISFIED" if agreed["payee_status"] == "VALID" else "NOT_SATISFIED"
    result["amount_condition"] = "SATISFIED" if agreed["declared_periodic_payout_minor"] > 0 else "NOT_SATISFIED"
    failures: List[str] = []
    if result["contract_condition"] != "SATISFIED":
        failures.append("CONTRACT_NOT_ACTIVE")
    if result["age_condition"] != "SATISFIED":
        failures.append("AGE_CONDITION_NOT_SATISFIED")
    if result["vesting_condition"] != "SATISFIED":
        failures.append("VESTING_CONDITION_NOT_SATISFIED")
    if result["contribution_condition"] != "SATISFIED":
        failures.append("CONTRIBUTION_CONDITION_NOT_SATISFIED")
    if result["election_condition"] != "SATISFIED":
        failures.append("PAYOUT_NOT_ELECTED")
    if result["payee_condition"] != "SATISFIED":
        failures.append("PAYEE_NOT_VALID")
    if result["amount_condition"] != "SATISFIED":
        failures.append("DECLARED_PERIODIC_PAYOUT_NOT_POSITIVE")
    result["state"] = STATE_RESOLVED
    result["resolution_state"] = STATE_RESOLVED
    result["visibility_state"] = VISIBILITY_VISIBLE if context["visibility_authorized"] else VISIBILITY_WITHHELD
    if failures:
        result["annuity_outcome"] = OUTCOME_NOT_PAYABLE
        result["payout_amount_minor"] = 0
        result["reason_codes"] = sorted(failures)
    else:
        result["annuity_outcome"] = OUTCOME_PAYABLE
        result["payout_amount_minor"] = agreed["declared_periodic_payout_minor"]
        result["reason_codes"] = ["PAYOUT_ADMITTED"]
    result["outcome_id"] = identity(OUTCOME_ID_PREFIX, outcome_identity_material(result))
    result["result_id"] = identity(RESULT_ID_PREFIX, result_identity_material(result))
    return result


def normalized_projection(raw_input: Any) -> Dict[str, Any]:
    normalized, issues = normalize_input(raw_input)
    return {
        "normalized_input": normalized,
        "validation_state": choose_issue(issues).state if issues else STATE_RESOLVED,
        "reason_codes": unique_sorted(issue.code for issue in issues),
    }


def build_bundle(raw_input: Any) -> Dict[str, Any]:
    bundle = {
        "schema": BUNDLE_SCHEMA,
        "version": VERSION,
        "core_version": CORE_VERSION,
        "canonicalization_id": CANONICALIZATION_ID,
        "identity_domain_id": identity_domain_id(),
        "contract_id": contract_id(),
        "submitted_input": clone(raw_input),
        "normalized_projection": normalized_projection(raw_input),
        "result": resolve_annuity(raw_input),
    }
    bundle["bundle_id"] = identity(BUNDLE_ID_PREFIX, bundle)
    return bundle


def verify_bundle(bundle: Any) -> Tuple[bool, str]:
    if not isinstance(bundle, dict):
        return False, "BUNDLE_NOT_OBJECT"
    required = {"schema", "version", "core_version", "canonicalization_id", "identity_domain_id", "contract_id", "submitted_input", "normalized_projection", "result", "bundle_id"}
    if set(bundle.keys()) != required:
        return False, "BUNDLE_FIELD_SET_MISMATCH"
    if bundle.get("schema") != BUNDLE_SCHEMA or bundle.get("version") != VERSION:
        return False, "BUNDLE_VERSION_MISMATCH"
    if bundle.get("core_version") != CORE_VERSION or bundle.get("canonicalization_id") != CANONICALIZATION_ID:
        return False, "BUNDLE_CORE_MISMATCH"
    if bundle.get("identity_domain_id") != identity_domain_id() or bundle.get("contract_id") != contract_id():
        return False, "BUNDLE_CONTRACT_MISMATCH"
    try:
        rebuilt = build_bundle(bundle.get("submitted_input"))
    except Exception as exc:
        return False, "BUNDLE_REBUILD_ERROR:" + str(exc)
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
        "state": result["state"],
        "annuity_outcome": result["annuity_outcome"],
        "visibility_state": result["visibility_state"],
        "currency": result["currency"],
        "payout_amount_minor": result["payout_amount_minor"],
        "reason_codes": result["reason_codes"],
        "authority_ids": result["authority_ids"],
        "context_id": result["context_id"],
        "evidence_set_id": result["evidence_set_id"],
        "canonical_input_id": result["canonical_input_id"],
        "outcome_id": result["outcome_id"],
        "result_id": result["result_id"],
        "source_authenticity": result["source_authenticity"],
        "contract_interpretation_authority": "NONE",
        "legal_entitlement_authority": "NONE",
        "tax_authority": "NONE",
        "actuarial_valuation_authority": "NONE",
        "payment_authority": "NONE",
    }
    receipt["receipt_id"] = identity(RECEIPT_ID_PREFIX, receipt)
    return receipt


def check_receipt_integrity(receipt: Any) -> Tuple[bool, str]:
    if not isinstance(receipt, dict):
        return False, "RECEIPT_NOT_OBJECT"
    required = {"schema", "version", "core_version", "profile_id", "ruleset_id", "canonicalization_id", "identity_domain_id", "contract_id", "bundle_id", "state", "annuity_outcome", "visibility_state", "currency", "payout_amount_minor", "reason_codes", "authority_ids", "context_id", "evidence_set_id", "canonical_input_id", "outcome_id", "result_id", "source_authenticity", "contract_interpretation_authority", "legal_entitlement_authority", "tax_authority", "actuarial_valuation_authority", "payment_authority", "receipt_id"}
    if set(receipt.keys()) != required:
        return False, "RECEIPT_FIELD_SET_MISMATCH"
    if receipt.get("schema") != RECEIPT_SCHEMA or receipt.get("version") != VERSION:
        return False, "RECEIPT_VERSION_MISMATCH"
    if receipt.get("profile_id") != PROFILE_ID or receipt.get("ruleset_id") != RULESET_ID or receipt.get("canonicalization_id") != CANONICALIZATION_ID:
        return False, "RECEIPT_CONTRACT_MISMATCH"
    if receipt.get("identity_domain_id") != identity_domain_id() or receipt.get("contract_id") != contract_id():
        return False, "RECEIPT_IDENTITY_DOMAIN_MISMATCH"
    for key in ["contract_interpretation_authority", "legal_entitlement_authority", "tax_authority", "actuarial_valuation_authority", "payment_authority"]:
        if receipt.get(key) != "NONE":
            return False, "RECEIPT_AUTHORITY_BOUNDARY_VIOLATION"
    if receipt.get("source_authenticity") != "NOT_ESTABLISHED_BY_REFERENCE_PROFILE":
        return False, "RECEIPT_AUTHENTICITY_CLAIM_VIOLATION"
    if receipt.get("state") == STATE_RESOLVED:
        if receipt.get("annuity_outcome") not in {OUTCOME_PAYABLE, OUTCOME_NOT_PAYABLE}:
            return False, "RECEIPT_RESOLVED_OUTCOME_INVALID"
        if receipt.get("annuity_outcome") == OUTCOME_PAYABLE and (not isinstance(receipt.get("payout_amount_minor"), int) or receipt.get("payout_amount_minor") <= 0):
            return False, "RECEIPT_PAYABLE_AMOUNT_INVALID"
        if receipt.get("annuity_outcome") == OUTCOME_NOT_PAYABLE and receipt.get("payout_amount_minor") != 0:
            return False, "RECEIPT_NOT_PAYABLE_AMOUNT_INVALID"
    else:
        if receipt.get("annuity_outcome") != OUTCOME_NONE or receipt.get("payout_amount_minor") != 0 or receipt.get("outcome_id") != "NONE":
            return False, "RECEIPT_NONRESULT_OUTCOME_LEAK"
    value = clone(receipt)
    supplied = value.pop("receipt_id")
    if supplied != identity(RECEIPT_ID_PREFIX, value):
        return False, "RECEIPT_ID_MISMATCH"
    return True, "PASS"


def verify_receipt_against_bundle(receipt: Any, bundle: Any) -> Tuple[bool, str]:
    ok, detail = check_receipt_integrity(receipt)
    if not ok:
        return False, detail
    ok, detail = verify_bundle(bundle)
    if not ok:
        return False, detail
    expected = make_receipt(bundle)
    if receipt != expected:
        return False, "RECEIPT_BUNDLE_CORRESPONDENCE_MISMATCH"
    return True, "PASS"


def make_summary(raw_input: Any) -> Dict[str, Any]:
    result = resolve_annuity(raw_input)
    summary = {
        "schema": SUMMARY_SCHEMA,
        "version": VERSION,
        "state": result["state"],
        "visibility_state": result["visibility_state"],
        "admission_state": "NONE",
        "annuity_outcome": OUTCOME_NONE,
        "currency": "NONE",
        "payout_amount_minor": 0,
        "reason_codes": result["reason_codes"],
        "outcome_id": "NONE",
        "result_id": result["result_id"],
        "payment_authority": "NONE",
    }
    if result["state"] == STATE_RESOLVED and result["visibility_state"] == VISIBILITY_VISIBLE:
        summary["admission_state"] = "ADMITTED"
        summary["annuity_outcome"] = result["annuity_outcome"]
        summary["currency"] = result["currency"]
        summary["payout_amount_minor"] = result["payout_amount_minor"]
        summary["outcome_id"] = result["outcome_id"]
    elif result["state"] == STATE_RESOLVED and result["visibility_state"] == VISIBILITY_WITHHELD:
        summary["admission_state"] = "WITHHOLD"
        summary["reason_codes"] = ["OUTCOME_WITHHELD"]
        summary["result_id"] = "NONE"
    return summary


def make_attestation(raw_input: Any) -> Dict[str, Any]:
    result = resolve_annuity(raw_input)
    attestation = {
        "schema": ATTESTATION_SCHEMA,
        "version": VERSION,
        "core_version": CORE_VERSION,
        "profile_id": PROFILE_ID,
        "ruleset_id": RULESET_ID,
        "canonicalization_id": CANONICALIZATION_ID,
        "identity_domain_id": identity_domain_id(),
        "contract_id": contract_id(),
        "state": result["state"],
        "reason_codes": result["reason_codes"],
        "missing_dependencies": result["missing_dependencies"],
        "conflicts": result["conflicts"],
        "diagnostics": result["diagnostics"],
        "context_id": result["context_id"],
        "evidence_set_id": result["evidence_set_id"],
        "canonical_input_id": result["canonical_input_id"],
        "result_id": result["result_id"],
        "source_authenticity": result["source_authenticity"],
        "contract_interpretation_authority": "NONE",
        "legal_entitlement_authority": "NONE",
        "tax_authority": "NONE",
        "actuarial_valuation_authority": "NONE",
        "payment_authority": "NONE",
    }
    attestation["attestation_id"] = identity(ATTESTATION_ID_PREFIX, attestation)
    return attestation


def check_attestation_integrity(attestation: Any) -> Tuple[bool, str]:
    if not isinstance(attestation, dict):
        return False, "ATTESTATION_NOT_OBJECT"
    required = {"schema", "version", "core_version", "profile_id", "ruleset_id", "canonicalization_id", "identity_domain_id", "contract_id", "state", "reason_codes", "missing_dependencies", "conflicts", "diagnostics", "context_id", "evidence_set_id", "canonical_input_id", "result_id", "source_authenticity", "contract_interpretation_authority", "legal_entitlement_authority", "tax_authority", "actuarial_valuation_authority", "payment_authority", "attestation_id"}
    if set(attestation.keys()) != required:
        return False, "ATTESTATION_FIELD_SET_MISMATCH"
    if attestation.get("schema") != ATTESTATION_SCHEMA or attestation.get("version") != VERSION:
        return False, "ATTESTATION_VERSION_MISMATCH"
    if attestation.get("identity_domain_id") != identity_domain_id() or attestation.get("contract_id") != contract_id():
        return False, "ATTESTATION_CONTRACT_MISMATCH"
    for key in ["contract_interpretation_authority", "legal_entitlement_authority", "tax_authority", "actuarial_valuation_authority", "payment_authority"]:
        if attestation.get(key) != "NONE":
            return False, "ATTESTATION_AUTHORITY_BOUNDARY_VIOLATION"
    if attestation.get("source_authenticity") != "NOT_ESTABLISHED_BY_REFERENCE_PROFILE":
        return False, "ATTESTATION_AUTHENTICITY_CLAIM_VIOLATION"
    value = clone(attestation)
    supplied = value.pop("attestation_id")
    if supplied != identity(ATTESTATION_ID_PREFIX, value):
        return False, "ATTESTATION_ID_MISMATCH"
    return True, "PASS"


def verify_attestation_against_input(attestation: Any, raw_input: Any) -> Tuple[bool, str]:
    ok, detail = check_attestation_integrity(attestation)
    if not ok:
        return False, detail
    expected = make_attestation(raw_input)
    if attestation != expected:
        return False, "ATTESTATION_INPUT_CORRESPONDENCE_MISMATCH"
    return True, "PASS"


def make_evidence(authority_id: str, overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    record: Dict[str, Any] = {
        "schema": AUTHORITY_PROFILE_ID,
        "authority_id": authority_id,
        "case_id": "ANNUITY-DEMO-001",
        "contract_reference": "CONTRACT-DEMO-001",
        "currency": "USD",
        "contract_status": "ACTIVE",
        "attained_age_years": 68,
        "minimum_start_age_years": 65,
        "credited_service_years": 12,
        "minimum_vesting_years": 10,
        "total_contributed_minor": 18000000,
        "minimum_contribution_minor": 15000000,
        "payout_election": "ELECTED",
        "payee_status": "VALID",
        "declared_periodic_payout_minor": 1250000,
    }
    if overrides:
        record.update(overrides)
    record["evidence_commitment"] = evidence_commitment_for_record(record)
    return record


def build_reference_input(multi: bool = False, visible: bool = True, evaluation_authorized: bool = True) -> Dict[str, Any]:
    authority_ids = ["AUTHORITY-A", "AUTHORITY-B"] if multi else ["AUTHORITY-A"]
    context = {
        "case_id": "ANNUITY-DEMO-001",
        "contract_reference": "CONTRACT-DEMO-001",
        "currency": "USD",
        "payout_mode": "ANNUITANT_PERIODIC",
        "evidence_mode": EVIDENCE_MULTI if multi else EVIDENCE_SINGLE,
        "evaluation_authorized": evaluation_authorized,
        "visibility_authorized": visible,
        "expected_authority_ids": authority_ids,
    }
    evidence = [make_evidence(authority_id) for authority_id in authority_ids]
    raw = {
        "schema": INPUT_SCHEMA,
        "profile_id": PROFILE_ID,
        "ruleset_id": RULESET_ID,
        "context": context,
        "annuity_evidence": evidence,
    }
    normalized, issues = normalize_input(raw)
    if normalized is None or any(issue.state in {STATE_FORBIDDEN, STATE_CONFLICT, STATE_UNSUPPORTED, STATE_INCOMPLETE} for issue in issues):
        raise ValueError("reference input construction failed")
    raw["declared_context_id"] = identity(CONTEXT_ID_PREFIX, context_material(normalized["context"]))
    raw["declared_evidence_set_id"] = identity(EVIDENCE_SET_ID_PREFIX, evidence_set_material(normalized["annuity_evidence"]))
    return raw


def with_evidence_override(raw: Dict[str, Any], index: int, overrides: Dict[str, Any]) -> Dict[str, Any]:
    value = clone(raw)
    record = value["annuity_evidence"][index]
    record.update(overrides)
    record["evidence_commitment"] = evidence_commitment_for_record(record)
    value.pop("declared_evidence_set_id", None)
    return value


def stamp_declared_ids(raw_input: Any) -> Dict[str, Any]:
    if not isinstance(raw_input, dict):
        raise ValueError("STAMP_DECLARED_IDS_BLOCKING_ISSUES: INVALID_TOP_LEVEL_TYPE")
    candidate = clone(raw_input)
    candidate.pop("declared_context_id", None)
    candidate.pop("declared_evidence_set_id", None)
    normalized, issues = normalize_input(candidate)
    blocking = unique_sorted(issue.code for issue in issues)
    if normalized is None or blocking:
        raise ValueError("STAMP_DECLARED_IDS_BLOCKING_ISSUES: " + ",".join(blocking if blocking else ["NORMALIZATION_FAILED"]))
    candidate["declared_context_id"] = identity(CONTEXT_ID_PREFIX, context_material(normalized["context"]))
    candidate["declared_evidence_set_id"] = identity(EVIDENCE_SET_ID_PREFIX, evidence_set_material(normalized["annuity_evidence"]))
    return candidate


def refresh_bindings(raw_input: Any) -> Dict[str, Any]:
    if not isinstance(raw_input, dict):
        raise ValueError("REFRESH_BINDINGS_BLOCKING_ISSUES: INVALID_TOP_LEVEL_TYPE")
    candidate = clone(raw_input)
    candidate.pop("declared_context_id", None)
    candidate.pop("declared_evidence_set_id", None)
    evidence = candidate.get("annuity_evidence")
    if not isinstance(evidence, list):
        raise ValueError("REFRESH_BINDINGS_BLOCKING_ISSUES: INVALID_EVIDENCE_LIST_TYPE")
    for record in evidence:
        if not isinstance(record, dict):
            raise ValueError("REFRESH_BINDINGS_BLOCKING_ISSUES: INVALID_EVIDENCE_RECORD_TYPE")
        record["evidence_commitment"] = evidence_commitment_for_record(record)
    normalized, issues = normalize_input(candidate)
    blocking = unique_sorted(issue.code for issue in issues)
    if normalized is None or blocking:
        raise ValueError("REFRESH_BINDINGS_BLOCKING_ISSUES: " + ",".join(blocking if blocking else ["NORMALIZATION_FAILED"]))
    candidate["declared_context_id"] = identity(CONTEXT_ID_PREFIX, context_material(normalized["context"]))
    candidate["declared_evidence_set_id"] = identity(EVIDENCE_SET_ID_PREFIX, evidence_set_material(normalized["annuity_evidence"]))
    return candidate


def self_test() -> Tuple[int, int, List[str]]:
    checks: List[Tuple[str, bool]] = []

    def check(name: str, condition: bool) -> None:
        checks.append((name, bool(condition)))

    single = build_reference_input(False, True, True)
    result = resolve_annuity(single)
    check("reference_resolved", result["state"] == STATE_RESOLVED)
    check("reference_payable", result["annuity_outcome"] == OUTCOME_PAYABLE)
    check("reference_amount", result["payout_amount_minor"] == 1250000)
    check("reference_visible", result["visibility_state"] == VISIBILITY_VISIBLE)
    check("reference_payment_authority_none", result["payment_authority"] == "NONE")
    check("reference_actuarial_authority_none", result["actuarial_valuation_authority"] == "NONE")
    check("reference_source_authenticity_not_established", result["source_authenticity"] == "NOT_ESTABLISHED_BY_REFERENCE_PROFILE")
    check("reference_ids_present", all(result[key] != "NONE" for key in ["context_id", "evidence_set_id", "canonical_input_id", "outcome_id", "result_id"]))
    check("reference_repeat_deterministic", resolve_annuity(single) == result)

    for name, field, value, reason in [
        ("inactive_contract", "contract_status", "INACTIVE", "CONTRACT_NOT_ACTIVE"),
        ("below_age", "attained_age_years", 60, "AGE_CONDITION_NOT_SATISFIED"),
        ("insufficient_vesting", "credited_service_years", 5, "VESTING_CONDITION_NOT_SATISFIED"),
        ("insufficient_contribution", "total_contributed_minor", 10000000, "CONTRIBUTION_CONDITION_NOT_SATISFIED"),
        ("not_elected", "payout_election", "NOT_ELECTED", "PAYOUT_NOT_ELECTED"),
        ("payee_invalid", "payee_status", "NOT_VALID", "PAYEE_NOT_VALID"),
        ("zero_amount", "declared_periodic_payout_minor", 0, "DECLARED_PERIODIC_PAYOUT_NOT_POSITIVE"),
    ]:
        case = with_evidence_override(single, 0, {field: value})
        observed = resolve_annuity(case)
        check(name + "_resolved", observed["state"] == STATE_RESOLVED)
        check(name + "_not_payable", observed["annuity_outcome"] == OUTCOME_NOT_PAYABLE)
        check(name + "_amount_zero", observed["payout_amount_minor"] == 0)
        check(name + "_reason", reason in observed["reason_codes"])

    missing = clone(single)
    missing["annuity_evidence"][0].pop("attained_age_years")
    missing.pop("declared_evidence_set_id", None)
    missing_result = resolve_annuity(missing)
    check("missing_state", missing_result["state"] == STATE_INCOMPLETE)
    check("missing_reason", "MISSING_REQUIRED_FIELD" in missing_result["reason_codes"])
    check("missing_no_outcome", missing_result["annuity_outcome"] == OUTCOME_NONE)

    forbidden = clone(single)
    forbidden["payout_amount_minor"] = 999999999
    forbidden_result = resolve_annuity(forbidden)
    check("forbidden_state", forbidden_result["state"] == STATE_FORBIDDEN)
    check("forbidden_reason", "FORBIDDEN_DERIVED_FIELD" in forbidden_result["reason_codes"])

    injected_nested = clone(single)
    injected_nested["context"]["payoutEligible"] = True
    injected_nested_result = resolve_annuity(injected_nested)
    check("forbidden_camelcase_state", injected_nested_result["state"] == STATE_FORBIDDEN)

    unknown = clone(single)
    unknown["context"]["new_rule"] = "X"
    unknown_result = resolve_annuity(unknown)
    check("unknown_state", unknown_result["state"] == STATE_UNSUPPORTED)
    check("unknown_reason", "UNKNOWN_FIELD" in unknown_result["reason_codes"])

    unauthorized = build_reference_input(False, True, False)
    unauthorized_result = resolve_annuity(unauthorized)
    check("unauthorized_abstain", unauthorized_result["state"] == STATE_ABSTAIN)
    check("unauthorized_reason", "EVALUATION_NOT_AUTHORIZED" in unauthorized_result["reason_codes"])
    check("unauthorized_no_outcome", unauthorized_result["annuity_outcome"] == OUTCOME_NONE)

    commitment_bad = clone(single)
    commitment_bad["annuity_evidence"][0]["evidence_commitment"] = EVIDENCE_COMMITMENT_PREFIX + "0" * 64
    commitment_bad.pop("declared_evidence_set_id", None)
    commitment_result = resolve_annuity(commitment_bad)
    check("commitment_conflict", commitment_result["state"] == STATE_CONFLICT)
    check("commitment_reason", "EVIDENCE_COMMITMENT_MISMATCH" in commitment_result["reason_codes"])

    context_bad = clone(single)
    context_bad["annuity_evidence"][0]["case_id"] = "ANNUITY-OTHER"
    context_bad["annuity_evidence"][0]["evidence_commitment"] = evidence_commitment_for_record(context_bad["annuity_evidence"][0])
    context_bad.pop("declared_evidence_set_id", None)
    context_result = resolve_annuity(context_bad)
    check("binding_conflict", context_result["state"] == STATE_CONFLICT)
    check("binding_reason", "CONTEXT_BINDING_MISMATCH" in context_result["reason_codes"])

    declared_context_bad = clone(single)
    declared_context_bad["declared_context_id"] = CONTEXT_ID_PREFIX + "0" * 64
    declared_context_result = resolve_annuity(declared_context_bad)
    check("declared_context_conflict", declared_context_result["state"] == STATE_CONFLICT)

    declared_evidence_bad = clone(single)
    declared_evidence_bad["declared_evidence_set_id"] = EVIDENCE_SET_ID_PREFIX + "0" * 64
    declared_evidence_result = resolve_annuity(declared_evidence_bad)
    check("declared_evidence_conflict", declared_evidence_result["state"] == STATE_CONFLICT)

    multi = build_reference_input(True, True, True)
    multi_result = resolve_annuity(multi)
    check("multi_resolved", multi_result["state"] == STATE_RESOLVED)
    check("multi_payable", multi_result["annuity_outcome"] == OUTCOME_PAYABLE)
    reversed_multi = clone(multi)
    reversed_multi["annuity_evidence"].reverse()
    check("evidence_order_independence", resolve_annuity(reversed_multi) == multi_result)

    disagreement = clone(multi)
    disagreement["annuity_evidence"][1]["declared_periodic_payout_minor"] = 1300000
    disagreement["annuity_evidence"][1]["evidence_commitment"] = evidence_commitment_for_record(disagreement["annuity_evidence"][1])
    disagreement.pop("declared_evidence_set_id", None)
    disagreement_result = resolve_annuity(disagreement)
    check("multi_disagreement_abstain", disagreement_result["state"] == STATE_ABSTAIN)
    check("multi_disagreement_reason", "EVIDENCE_RESULT_DISAGREEMENT" in disagreement_result["reason_codes"])

    duplicate = clone(multi)
    duplicate["annuity_evidence"][1]["authority_id"] = "AUTHORITY-A"
    duplicate["annuity_evidence"][1]["evidence_commitment"] = evidence_commitment_for_record(duplicate["annuity_evidence"][1])
    duplicate.pop("declared_evidence_set_id", None)
    duplicate_result = resolve_annuity(duplicate)
    check("duplicate_conflict", duplicate_result["state"] == STATE_CONFLICT)
    check("duplicate_reason", "DUPLICATE_AUTHORITY_ID" in duplicate_result["reason_codes"])

    missing_authority = clone(multi)
    missing_authority["annuity_evidence"] = missing_authority["annuity_evidence"][:1]
    missing_authority.pop("declared_evidence_set_id", None)
    missing_authority_result = resolve_annuity(missing_authority)
    check("missing_authority_incomplete", missing_authority_result["state"] == STATE_INCOMPLETE)
    check("missing_authority_reason", "MISSING_EXPECTED_AUTHORITY" in missing_authority_result["reason_codes"])

    unexpected = clone(single)
    unexpected["annuity_evidence"][0]["authority_id"] = "AUTHORITY-X"
    unexpected["annuity_evidence"][0]["evidence_commitment"] = evidence_commitment_for_record(unexpected["annuity_evidence"][0])
    unexpected.pop("declared_evidence_set_id", None)
    unexpected_result = resolve_annuity(unexpected)
    check("unexpected_authority_conflict", unexpected_result["state"] == STATE_CONFLICT)
    check("unexpected_authority_reason", "UNEXPECTED_AUTHORITY" in unexpected_result["reason_codes"])

    hidden_positive = build_reference_input(False, False, True)
    hidden_negative = with_evidence_override(hidden_positive, 0, {"attained_age_years": 60})
    hidden_positive_summary = make_summary(hidden_positive)
    hidden_negative_summary = make_summary(hidden_negative)
    for key in ["annuity_outcome", "currency", "payout_amount_minor", "outcome_id", "result_id", "reason_codes", "admission_state"]:
        check("withheld_noninterference_" + key, hidden_positive_summary[key] == hidden_negative_summary[key])
    check("withheld_outcome_none", hidden_positive_summary["annuity_outcome"] == OUTCOME_NONE)
    check("withheld_amount_zero", hidden_positive_summary["payout_amount_minor"] == 0)

    bundle = build_bundle(single)
    ok, detail = verify_bundle(bundle)
    check("bundle_verify", ok and detail == "PASS")
    tampered_bundle = clone(bundle)
    tampered_bundle["result"]["payout_amount_minor"] = 1
    check("bundle_tamper_rejected", verify_bundle(tampered_bundle)[0] is False)

    receipt = make_receipt(bundle)
    check("receipt_integrity", check_receipt_integrity(receipt)[0])
    check("receipt_correspondence", verify_receipt_against_bundle(receipt, bundle)[0])
    tampered_receipt = clone(receipt)
    tampered_receipt["payout_amount_minor"] = 2
    check("receipt_tamper_rejected", check_receipt_integrity(tampered_receipt)[0] is False)

    attestation = make_attestation(unauthorized)
    check("attestation_state", attestation["state"] == STATE_ABSTAIN)
    check("attestation_integrity", check_attestation_integrity(attestation)[0])
    check("attestation_correspondence", verify_attestation_against_input(attestation, unauthorized)[0])
    tampered_attestation = clone(attestation)
    tampered_attestation["state"] = STATE_RESOLVED
    check("attestation_tamper_rejected", check_attestation_integrity(tampered_attestation)[0] is False)

    check("contract_id_stable", contract_id() == contract_id())
    check("identity_domain_stable", identity_domain_id() == identity_domain_id())
    edited = clone(single)
    edited["annuity_evidence"][0]["attained_age_years"] = 60
    edited["annuity_evidence"][0]["evidence_commitment"] = evidence_commitment_for_record(edited["annuity_evidence"][0])
    edited_before = resolve_annuity(edited)
    check("stamp_demo_preconflict", edited_before["state"] == STATE_CONFLICT and "DECLARED_EVIDENCE_SET_ID_MISMATCH" in edited_before["reason_codes"])
    stamped = stamp_declared_ids(edited)
    stamped_result = resolve_annuity(stamped)
    check("stamp_demo_resolved", stamped_result["state"] == STATE_RESOLVED)
    check("stamp_demo_not_payable", stamped_result["annuity_outcome"] == OUTCOME_NOT_PAYABLE)
    check("stamp_demo_age_reason", "AGE_CONDITION_NOT_SATISFIED" in stamped_result["reason_codes"])
    broken_stamp = clone(edited)
    broken_stamp["annuity_evidence"][0]["evidence_commitment"] = EVIDENCE_COMMITMENT_PREFIX + "0" * 64
    try:
        stamp_declared_ids(broken_stamp)
        broken_stamp_refused = False
    except ValueError as exc:
        broken_stamp_refused = "EVIDENCE_COMMITMENT_MISMATCH" in str(exc)
    check("stamp_refuses_bad_commitment", broken_stamp_refused)
    refreshed_input = clone(single)
    refreshed_input["annuity_evidence"][0]["attained_age_years"] = 60
    refreshed = refresh_bindings(refreshed_input)
    refreshed_result = resolve_annuity(refreshed)
    check("refresh_bindings_resolved", refreshed_result["state"] == STATE_RESOLVED and refreshed_result["annuity_outcome"] == OUTCOME_NOT_PAYABLE)
    library_float = clone(single)
    library_float["annuity_evidence"][0]["attained_age_years"] = 60.5
    library_float_result = resolve_annuity(library_float)
    check("library_float_reason", library_float_result["state"] == STATE_UNSUPPORTED and "FLOAT_NOT_SUPPORTED" in library_float_result["reason_codes"])
    library_non_string = clone(single)
    library_non_string[1] = "x"
    library_non_string_result = resolve_annuity(library_non_string)
    check("library_non_string_key_reason", library_non_string_result["state"] == STATE_UNSUPPORTED and "NON_STRING_KEY" in library_non_string_result["reason_codes"])
    library_unsupported = clone(single)
    library_unsupported["context"]["case_id"] = {"bad"}
    library_unsupported_result = resolve_annuity(library_unsupported)
    check("library_unsupported_type_reason", library_unsupported_result["state"] == STATE_UNSUPPORTED and "UNSUPPORTED_JSON_TYPE" in library_unsupported_result["reason_codes"])
    causal = clone(single)
    causal["annuity_evidence"][0]["attained_age_years"] = -1
    causal_result = resolve_annuity(causal)
    check("dependency_aware_primary_unsupported", causal_result["state"] == STATE_UNSUPPORTED)
    check("dependency_aware_no_derived_id_conflict", "DECLARED_EVIDENCE_SET_ID_MISMATCH" not in causal_result["reason_codes"])
    check("contract_reason_registry_complete", set(contract_manifest()["reason_codes"]) == REASON_CODE_REGISTRY)

    duplicate_key_rejected = False
    try:
        strict_json_load_text('{"x":1,"x":2}')
    except ValueError:
        duplicate_key_rejected = True
    check("parser_duplicate_key_rejected", duplicate_key_rejected)

    float_rejected = False
    try:
        strict_json_load_text('{"x":1.5}')
    except ValueError:
        float_rejected = True
    check("parser_float_rejected", float_rejected)

    nonfinite_rejected = False
    try:
        strict_json_load_text('{"x":NaN}')
    except ValueError:
        nonfinite_rejected = True
    check("parser_nonfinite_rejected", nonfinite_rejected)

    deep: Any = 0
    for _ in range(MAX_JSON_DEPTH + 2):
        deep = {"x": deep}
    deep_result = resolve_annuity(deep)
    check("library_depth_guard", deep_result["state"] == STATE_UNSUPPORTED and "JSON_DEPTH_LIMIT" in deep_result["reason_codes"])

    parsed_single = strict_json_load_text(canonical_json(single))
    check("strict_parser_library_equivalence", resolve_annuity(parsed_single) == result)

    failures = [name for name, passed in checks if not passed]
    return len(checks), len(checks) - len(failures), failures


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2))


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="slang_annuity_v1_1_1.py")
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
    group.add_argument("--stamp-declared-ids", metavar="INPUT_JSON")
    group.add_argument("--refresh-bindings", metavar="INPUT_JSON")
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
            print("SLANG-Annuity v" + VERSION + " self-test")
            print("TOTAL " + str(passed) + "/" + str(total) + " PASS")
            if failures:
                for name in failures:
                    print("FAIL " + name)
                return 1
            return 0
        if args.version:
            print("SLANG-Annuity " + VERSION)
            return 0
        if args.describe_contract:
            print_json(contract_manifest())
            return 0
        if args.example_input:
            print_json(build_reference_input(False, True, True))
            return 0
        if args.resolve:
            print_json(resolve_annuity(load_json_file(Path(args.resolve))))
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
            print("BUNDLE_RECONSTRUCTION: " + ("PASS" if ok else "FAIL " + detail))
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
            print("RECEIPT_INTEGRITY: " + ("PASS" if ok else "FAIL " + detail))
            print("BUNDLE_CORRESPONDENCE: NOT_CHECKED")
            print("OPERATIONAL_AUTHORITY: NONE")
            return 0 if ok else 1
        if args.verify_receipt:
            if not args.against_bundle:
                raise ValueError("--verify-receipt requires --against-bundle")
            ok, detail = verify_receipt_against_bundle(load_json_file(Path(args.verify_receipt)), load_json_file(Path(args.against_bundle)))
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
            print("ATTESTATION_INTEGRITY: " + ("PASS" if ok else "FAIL " + detail))
            print("INPUT_CORRESPONDENCE: NOT_CHECKED")
            print("OPERATIONAL_AUTHORITY: NONE")
            return 0 if ok else 1
        if args.verify_attestation:
            if not args.against_input:
                raise ValueError("--verify-attestation requires --against-input")
            ok, detail = verify_attestation_against_input(load_json_file(Path(args.verify_attestation)), load_json_file(Path(args.against_input)))
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
        if args.stamp_declared_ids:
            value = stamp_declared_ids(load_json_file(Path(args.stamp_declared_ids)))
            if args.output:
                write_json(Path(args.output), value)
                print("STAMP_DECLARED_IDS: PASS")
                print("SOURCE_AUTHENTICITY: NOT_ESTABLISHED")
            else:
                print_json(value)
            return 0
        if args.refresh_bindings:
            value = refresh_bindings(load_json_file(Path(args.refresh_bindings)))
            if args.output:
                write_json(Path(args.output), value)
                print("REFRESH_BINDINGS: PASS")
                print("SOURCE_AUTHENTICITY: NOT_ESTABLISHED")
            else:
                print_json(value)
            return 0
        print_json(make_summary(build_reference_input(False, True, True)))
        return 0
    except Exception as exc:
        message = str(exc)
        if message.startswith("STAMP_DECLARED_IDS_BLOCKING_ISSUES:"):
            print("STAMP_DECLARED_IDS: FAIL", file=sys.stderr)
            print("BLOCKING_ISSUES: " + message.split(":", 1)[1].strip(), file=sys.stderr)
        elif message.startswith("REFRESH_BINDINGS_BLOCKING_ISSUES:"):
            print("REFRESH_BINDINGS: FAIL", file=sys.stderr)
            print("BLOCKING_ISSUES: " + message.split(":", 1)[1].strip(), file=sys.stderr)
        else:
            print("ERROR: " + message, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
