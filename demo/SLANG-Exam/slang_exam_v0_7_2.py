#!/usr/bin/env python3
"""
SLANG-Exam
Bounded structural admissibility and deterministic examination-form assembly.

Python 3.9+
Standard library only
"""

import argparse
import copy
import hashlib
import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple


VERSION = "0.7.2"
CORE_VERSION = "SLANG-CORE-1-D03"
PROFILE_ID = "SLANG-EXAM-PROFILE-1-D05"
RULESET_ID = "SLANG-EXAM-RULESET-1-D05"
CANONICALIZATION_ID = "SLANG-CANONICAL-JSON-1-D02"

INPUT_SCHEMA = "SLANG-EXAM-INPUT-5"
RESULT_SCHEMA = "SLANG-EXAM-RESULT-5"
BUNDLE_SCHEMA = "SLANG-EXAM-BUNDLE-5"
RECEIPT_SCHEMA = "SLANG-EXAM-RECEIPT-4"

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

SUPPORTED_DIFFICULTIES = {"EASY", "MEDIUM", "HARD"}
SUPPORTED_QUESTION_TYPES = {"MCQ", "SHORT", "LONG"}
SUPPORTED_AUDIENCE_SCOPES = {"COMMON", "CENTER", "CANDIDATE"}
SUPPORTED_SELECTOR_MODES = {
    "CANONICAL_RANK",
    "ABSTAIN_ON_MULTIPLE",
    "COMMIT_REVEAL_RANK",
    "MULTI_PARTY_COMMIT_REVEAL",
}

TOP_LEVEL_KEYS = {
    "schema",
    "profile_id",
    "ruleset_id",
    "context",
    "blueprint",
    "selector",
    "question_bank",
    "declared_bank_id",
    "declared_blueprint_id",
}

DERIVED_TOP_LEVEL_KEYS = {
    "state",
    "assembly_state",
    "release_state",
    "paper_visible",
    "paper_bundle",
    "question_paper",
    "selected_questions",
    "paper_id",
    "evaluation_manifest_id",
    "submission_id",
    "canonical_input_id",
    "normalized_projection_id",
    "bank_id",
    "blueprint_id",
    "result_id",
    "selection_context_id",
    "search_evidence",
    "search_evidence_id",
    "commitment_aggregate_id",
    "selector_transcript_id",
    "bundle_id",
    "receipt_id",
    "reason_codes",
    "missing_dependencies",
    "conflicts",
    "prohibitions",
    "unsupported_features",
    "evidence",
    "submitted_input",
    "normalized_projection",
    "normalized_input",
    "result",
}

CONTEXT_KEYS = {
    "exam_id",
    "session_id",
    "audience_scope",
    "audience_id",
    "assembly_authorized",
    "release_authorized",
    "exam_window_open",
    "center_authorized",
    "candidate_valid",
}

BLUEPRINT_REQUIRED_KEYS = {
    "total_questions",
    "total_marks",
    "topic_counts",
    "difficulty_counts",
    "type_counts",
    "max_per_exposure_group",
    "forbidden_pairs",
}
BLUEPRINT_OPTIONAL_KEYS = {"topic_registry_id", "allowed_topics"}
BLUEPRINT_KEYS = BLUEPRINT_REQUIRED_KEYS | BLUEPRINT_OPTIONAL_KEYS

SELECTOR_REQUIRED_KEYS = {"mode", "variant_id"}
SELECTOR_OPTIONAL_KEYS = {
    "selection_event_id",
    "selection_commitment",
    "selection_salt",
    "commitment_manifest",
    "reveal_manifest",
    "declared_commitment_manifest_id",
    "declared_reveal_manifest_id",
}
SELECTOR_KEYS = SELECTOR_REQUIRED_KEYS | SELECTOR_OPTIONAL_KEYS

COMMITMENT_MANIFEST_KEYS = {"parties"}
REVEAL_MANIFEST_KEYS = {"reveals"}
COMMITMENT_PARTY_KEYS = {"party_id", "commitment"}
REVEAL_PARTY_KEYS = {"party_id", "salt"}

MIN_MPCR_PARTIES = 2
MAX_MPCR_PARTIES = 8
MAX_SAFE_INTEGER = (2 ** 53) - 1

SELECTION_CONTEXT_DOMAIN = "SLANG-EXAM-SELECTION-CONTEXT-1"
QUESTION_RANK_DOMAIN = "SLANG-EXAM-QUESTION-RANK-1"
SINGLE_COMMITMENT_DOMAIN = "SLANG-EXAM-SINGLE-PARTY-COMMITMENT-2"
MPCR_PARTY_COMMITMENT_DOMAIN = "SLANG-EXAM-MPCR-PARTY-COMMITMENT-2"
MPCR_COMBINE_DOMAIN = "SLANG-EXAM-MPCR-COMBINE-2"
MPCR_COMMITMENT_AGGREGATE_DOMAIN = "SLANG-EXAM-MPCR-COMMITMENT-AGGREGATE-1"
MPCR_TRANSCRIPT_DOMAIN = "SLANG-EXAM-MPCR-TRANSCRIPT-1"
MPCR_COMMITMENTS_DOMAIN = "SLANG-EXAM-MPCR-COMMITMENTS-2"
MPCR_REVEALS_DOMAIN = "SLANG-EXAM-MPCR-REVEALS-2"
MPCR_PARTICIPANTS_DOMAIN = "SLANG-EXAM-MPCR-PARTICIPANTS-2"

QUESTION_KEYS = {
    "question_id",
    "topic",
    "difficulty",
    "marks",
    "question_type",
    "approved",
    "answer_key_id",
    "content_commitment",
    "exposure_group",
}

MAX_QUESTION_BANK_SIZE = 40
MAX_TOTAL_QUESTIONS = 12
MAX_QUESTION_MARKS = 200
MAX_TOTAL_MARKS = 1000
MAX_SEARCH_NODES = 250000
MAX_JSON_DEPTH = 64
MAX_JSON_NODES = 100000
MAX_JSON_INPUT_BYTES = 4 * 1024 * 1024
HEX_DIGITS = frozenset("0123456789abcdefABCDEF")

RECEIPT_KEYS = {
    "schema",
    "version",
    "core_version",
    "canonicalization_id",
    "identity_domain_id",
    "profile_id",
    "ruleset_id",
    "submission_id",
    "canonical_input_id",
    "bank_id",
    "blueprint_id",
    "selection_context_id",
    "state",
    "assembly_state",
    "release_state",
    "paper_visible",
    "paper_id",
    "evaluation_manifest_id",
    "selection_mode",
    "selection_posture",
    "multiplicity_state",
    "selection_event_id",
    "party_count",
    "commitment_manifest_id",
    "reveal_manifest_id",
    "participant_set_id",
    "commitment_aggregate_id",
    "selector_transcript_id",
    "reason_codes",
    "result_id",
    "search_evidence_id",
    "bundle_id",
    "receipt_id",
}


class DuplicateKeyError(ValueError):
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


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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
    }


def identity_domain_id() -> str:
    return identity("slang_exam_identity_domain_sha256:", identity_domain_material())


def contains_lone_surrogate(value: str) -> bool:
    return any(0xD800 <= ord(char) <= 0xDFFF for char in value)


def validate_portable_json(value: Any, path: str = "$") -> None:
    stack: List[Tuple[Any, str, int]] = [(value, path, 0)]
    nodes = 0

    while stack:
        current, current_path, depth = stack.pop()
        nodes += 1
        if nodes > MAX_JSON_NODES:
            raise ValueError("portable JSON node limit exceeded")
        if depth > MAX_JSON_DEPTH:
            raise ValueError("portable JSON depth limit exceeded at " + current_path)

        if current is None or isinstance(current, bool):
            continue
        if isinstance(current, str):
            if contains_lone_surrogate(current):
                raise ValueError("lone surrogate is not supported at " + current_path)
            continue
        if isinstance(current, int) and not isinstance(current, bool):
            if current < -MAX_SAFE_INTEGER or current > MAX_SAFE_INTEGER:
                raise ValueError("integer outside portable range at " + current_path)
            continue
        if isinstance(current, float):
            raise ValueError("floating-point values are not supported at " + current_path)
        if isinstance(current, list):
            for index in range(len(current) - 1, -1, -1):
                stack.append((current[index], current_path + "[" + str(index) + "]", depth + 1))
            continue
        if isinstance(current, dict):
            items = list(current.items())
            for key, item in reversed(items):
                if not isinstance(key, str):
                    raise TypeError("JSON object key is not a string at " + current_path)
                if contains_lone_surrogate(key):
                    raise ValueError("lone surrogate object key is not supported at " + current_path)
                stack.append((item, current_path + "." + key, depth + 1))
            continue
        raise TypeError(
            "unsupported JSON value at " + current_path + ": " + type(current).__name__
        )


def normalize_text(value: str) -> str:
    return value.strip()


def is_supported_text(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    text = normalize_text(value)
    if not text or not text.isascii():
        return False
    return all(0x20 <= ord(char) <= 0x7E for char in text)


def normalize_id(value: str) -> str:
    return normalize_text(value)


def normalize_label(value: str) -> str:
    return normalize_text(value).upper()


def is_plain_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def normalize_sha256(value: Any) -> Optional[str]:
    if not isinstance(value, str) or len(value) != 64:
        return None
    if any(character not in HEX_DIGITS for character in value):
        return None
    return value.lower()


def is_sha256_hex(value: Any) -> bool:
    return normalize_sha256(value) is not None


def issue_priority(state: str) -> int:
    order = {
        STATE_FORBIDDEN: 0,
        STATE_CONFLICT: 1,
        STATE_UNSUPPORTED: 2,
        STATE_INCOMPLETE: 3,
        STATE_ABSTAIN: 4,
        STATE_RESOLVED: 5,
    }
    return order.get(state, 99)


def choose_primary_issue(issues: Sequence[ValidationIssue]) -> ValidationIssue:
    return sorted(issues, key=lambda item: (issue_priority(item.state), item.code, item.detail))[0]


def normalize_count_map(
    value: Any,
    field_name: str,
    allowed_labels: Optional[Set[str]] = None,
) -> Tuple[Optional[Dict[str, int]], List[ValidationIssue]]:
    issues: List[ValidationIssue] = []
    if value is None:
        issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_" + field_name.upper(), field_name))
        return None, issues
    if not isinstance(value, dict):
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_" + field_name.upper() + "_TYPE", field_name))
        return None, issues

    normalized: Dict[str, int] = {}
    for raw_key, raw_count in value.items():
        if not is_supported_text(raw_key):
            issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_" + field_name.upper() + "_LABEL", repr(raw_key)))
            continue
        label = normalize_label(raw_key)
        if allowed_labels is not None and label not in allowed_labels:
            issues.append(ValidationIssue(STATE_UNSUPPORTED, "UNSUPPORTED_" + field_name.upper() + "_LABEL", label))
            continue
        if label in normalized:
            issues.append(ValidationIssue(STATE_CONFLICT, "NORMALIZED_" + field_name.upper() + "_COLLISION", label))
            continue
        if not is_plain_int(raw_count) or raw_count < 0:
            issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_" + field_name.upper() + "_COUNT", label))
            continue
        normalized[label] = raw_count

    return dict(sorted(normalized.items())), issues


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
    for key in ("exam_id", "session_id", "audience_id"):
        raw = value.get(key)
        if raw is None:
            continue
        if not is_supported_text(raw):
            issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_CONTEXT_IDENTIFIER", key))
        else:
            normalized[key] = normalize_id(raw)

    raw_scope = value.get("audience_scope")
    if raw_scope is not None:
        if not is_supported_text(raw_scope):
            issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_AUDIENCE_SCOPE", "audience_scope"))
        else:
            scope = normalize_label(raw_scope)
            if scope not in SUPPORTED_AUDIENCE_SCOPES:
                issues.append(ValidationIssue(STATE_UNSUPPORTED, "UNSUPPORTED_AUDIENCE_SCOPE", scope))
            else:
                normalized["audience_scope"] = scope

    for key in (
        "assembly_authorized",
        "release_authorized",
        "exam_window_open",
        "center_authorized",
        "candidate_valid",
    ):
        if key not in value:
            continue
        raw = value.get(key)
        if not isinstance(raw, bool):
            issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_CONTEXT_BOOLEAN", key))
        else:
            normalized[key] = raw

    scope = normalized.get("audience_scope")
    audience_id = normalized.get("audience_id")
    if scope == "COMMON" and audience_id is not None and audience_id != "ALL":
        issues.append(ValidationIssue(STATE_CONFLICT, "AUDIENCE_ID_SCOPE_MISMATCH", "COMMON requires audience_id=ALL"))
    if scope in {"CENTER", "CANDIDATE"} and audience_id == "ALL":
        issues.append(ValidationIssue(STATE_CONFLICT, "AUDIENCE_ID_SCOPE_MISMATCH", scope + " requires a bounded audience_id"))

    return normalized, issues


def normalize_commitment_manifest(value: Any) -> Tuple[Optional[Dict[str, Any]], List[ValidationIssue]]:
    issues: List[ValidationIssue] = []
    if value is None:
        return None, [ValidationIssue(STATE_INCOMPLETE, "MISSING_COMMITMENT_MANIFEST", "commitment_manifest")]
    if not isinstance(value, dict):
        return None, [ValidationIssue(STATE_UNSUPPORTED, "INVALID_COMMITMENT_MANIFEST_TYPE", "commitment_manifest")]

    for key in sorted(set(value) - COMMITMENT_MANIFEST_KEYS):
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "UNSUPPORTED_COMMITMENT_MANIFEST_FIELD", key))
    if "parties" not in value:
        issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_COMMITMENT_MANIFEST_FIELD", "parties"))

    raw_parties = value.get("parties")
    if raw_parties is None:
        return {}, issues
    if not isinstance(raw_parties, list):
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_PARTIES_TYPE", "commitment_manifest.parties"))
        return {}, issues
    if len(raw_parties) < MIN_MPCR_PARTIES:
        issues.append(ValidationIssue(STATE_INCOMPLETE, "INSUFFICIENT_PARTIES", str(len(raw_parties))))
    if len(raw_parties) > MAX_MPCR_PARTIES:
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "PARTIES_LIMIT_EXCEEDED", str(len(raw_parties))))

    normalized_parties: List[Dict[str, str]] = []
    seen: Set[str] = set()
    for index, raw_party in enumerate(raw_parties):
        if not isinstance(raw_party, dict):
            issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_PARTY_RECORD", str(index)))
            continue
        for key in sorted(set(raw_party) - COMMITMENT_PARTY_KEYS):
            issues.append(ValidationIssue(STATE_UNSUPPORTED, "UNSUPPORTED_PARTY_FIELD", str(index) + ":" + key))
        for key in sorted(COMMITMENT_PARTY_KEYS):
            if key not in raw_party:
                issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_PARTY_FIELD", str(index) + ":" + key))

        party: Dict[str, str] = {}
        raw_party_id = raw_party.get("party_id")
        if raw_party_id is not None:
            if not is_supported_text(raw_party_id):
                issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_PARTY_ID", str(index)))
            else:
                party_id = normalize_id(raw_party_id)
                if party_id in seen:
                    issues.append(ValidationIssue(STATE_CONFLICT, "DUPLICATE_PARTY_ID", party_id))
                else:
                    seen.add(party_id)
                    party["party_id"] = party_id

        raw_commitment = raw_party.get("commitment")
        if raw_commitment is not None:
            commitment_value = normalize_sha256(raw_commitment)
            if commitment_value is None:
                issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_PARTY_COMMITMENT", str(index)))
            else:
                party["commitment"] = commitment_value

        if set(party) == COMMITMENT_PARTY_KEYS:
            normalized_parties.append(party)

    normalized_parties.sort(key=lambda party: party["party_id"])
    return {"parties": normalized_parties}, issues


def normalize_reveal_manifest(value: Any) -> Tuple[Optional[Dict[str, Any]], List[ValidationIssue]]:
    issues: List[ValidationIssue] = []
    if value is None:
        return None, [ValidationIssue(STATE_INCOMPLETE, "MISSING_REVEAL_MANIFEST", "reveal_manifest")]
    if not isinstance(value, dict):
        return None, [ValidationIssue(STATE_UNSUPPORTED, "INVALID_REVEAL_MANIFEST_TYPE", "reveal_manifest")]

    for key in sorted(set(value) - REVEAL_MANIFEST_KEYS):
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "UNSUPPORTED_REVEAL_MANIFEST_FIELD", key))
    if "reveals" not in value:
        issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_REVEAL_MANIFEST_FIELD", "reveals"))

    raw_reveals = value.get("reveals")
    if raw_reveals is None:
        return {}, issues
    if not isinstance(raw_reveals, list):
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_REVEALS_TYPE", "reveal_manifest.reveals"))
        return {}, issues
    if len(raw_reveals) > MAX_MPCR_PARTIES:
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "REVEALS_LIMIT_EXCEEDED", str(len(raw_reveals))))

    normalized_reveals: List[Dict[str, str]] = []
    seen: Set[str] = set()
    for index, raw_reveal in enumerate(raw_reveals):
        if not isinstance(raw_reveal, dict):
            issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_REVEAL_RECORD", str(index)))
            continue
        for key in sorted(set(raw_reveal) - REVEAL_PARTY_KEYS):
            issues.append(ValidationIssue(STATE_UNSUPPORTED, "UNSUPPORTED_REVEAL_FIELD", str(index) + ":" + key))
        for key in sorted(REVEAL_PARTY_KEYS):
            if key not in raw_reveal:
                issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_REVEAL_FIELD", str(index) + ":" + key))

        reveal: Dict[str, str] = {}
        raw_party_id = raw_reveal.get("party_id")
        if raw_party_id is not None:
            if not is_supported_text(raw_party_id):
                issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_REVEAL_PARTY_ID", str(index)))
            else:
                party_id = normalize_id(raw_party_id)
                if party_id in seen:
                    issues.append(ValidationIssue(STATE_CONFLICT, "DUPLICATE_REVEAL_PARTY_ID", party_id))
                else:
                    seen.add(party_id)
                    reveal["party_id"] = party_id

        raw_salt = raw_reveal.get("salt")
        if raw_salt is not None:
            salt_value = normalize_sha256(raw_salt)
            if salt_value is None:
                issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_PARTY_SALT", str(index)))
            else:
                reveal["salt"] = salt_value

        if set(reveal) == REVEAL_PARTY_KEYS:
            normalized_reveals.append(reveal)

    normalized_reveals.sort(key=lambda reveal: reveal["party_id"])
    return {"reveals": normalized_reveals}, issues


def normalize_selector(value: Any) -> Tuple[Optional[Dict[str, Any]], List[ValidationIssue]]:
    issues: List[ValidationIssue] = []
    if value is None:
        return None, [ValidationIssue(STATE_INCOMPLETE, "MISSING_SELECTOR", "selector")]
    if not isinstance(value, dict):
        return None, [ValidationIssue(STATE_UNSUPPORTED, "INVALID_SELECTOR_TYPE", "selector")]

    for key in sorted(set(value) - SELECTOR_KEYS):
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "UNSUPPORTED_SELECTOR_FIELD", key))
    for key in sorted(SELECTOR_REQUIRED_KEYS):
        if key not in value:
            issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_SELECTOR_FIELD", key))

    normalized: Dict[str, Any] = {}
    raw_mode = value.get("mode")
    if raw_mode is not None:
        if not is_supported_text(raw_mode):
            issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_SELECTOR_MODE", "mode"))
        else:
            mode = normalize_label(raw_mode)
            if mode not in SUPPORTED_SELECTOR_MODES:
                issues.append(ValidationIssue(STATE_UNSUPPORTED, "UNSUPPORTED_SELECTOR_MODE", mode))
            else:
                normalized["mode"] = mode

    raw_variant = value.get("variant_id")
    if raw_variant is not None:
        if not is_supported_text(raw_variant):
            issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_VARIANT_ID", "variant_id"))
        else:
            normalized["variant_id"] = normalize_id(raw_variant)

    mode = normalized.get("mode")
    raw_event_id = value.get("selection_event_id")
    raw_commitment = value.get("selection_commitment")
    raw_salt = value.get("selection_salt")
    raw_commitment_manifest = value.get("commitment_manifest")
    raw_reveal_manifest = value.get("reveal_manifest")

    if mode == "COMMIT_REVEAL_RANK":
        for field_name, raw_value in (
            ("selection_event_id", raw_event_id),
            ("selection_commitment", raw_commitment),
            ("selection_salt", raw_salt),
        ):
            if raw_value is None:
                issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_SELECTOR_FIELD", field_name))

        if raw_event_id is not None:
            if not is_supported_text(raw_event_id):
                issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_SELECTION_EVENT_ID", "selection_event_id"))
            else:
                normalized["selection_event_id"] = normalize_id(raw_event_id)
        if raw_commitment is not None:
            commitment_value = normalize_sha256(raw_commitment)
            if commitment_value is None:
                issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_SELECTION_COMMITMENT", "selection_commitment"))
            else:
                normalized["selection_commitment"] = commitment_value
        if raw_salt is not None:
            salt_value = normalize_sha256(raw_salt)
            if salt_value is None:
                issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_SELECTION_SALT", "selection_salt"))
            else:
                normalized["selection_salt"] = salt_value

        for field_name, raw_value in (
            ("commitment_manifest", raw_commitment_manifest),
            ("reveal_manifest", raw_reveal_manifest),
            ("declared_commitment_manifest_id", value.get("declared_commitment_manifest_id")),
            ("declared_reveal_manifest_id", value.get("declared_reveal_manifest_id")),
        ):
            if raw_value is not None:
                issues.append(ValidationIssue(STATE_UNSUPPORTED, "MPCR_FIELD_NOT_ALLOWED", field_name))

    elif mode == "MULTI_PARTY_COMMIT_REVEAL":
        if raw_event_id is None:
            issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_SELECTOR_FIELD", "selection_event_id"))
        elif not is_supported_text(raw_event_id):
            issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_SELECTION_EVENT_ID", "selection_event_id"))
        else:
            normalized["selection_event_id"] = normalize_id(raw_event_id)

        commitment_manifest, commitment_issues = normalize_commitment_manifest(raw_commitment_manifest)
        reveal_manifest, reveal_issues = normalize_reveal_manifest(raw_reveal_manifest)
        issues.extend(commitment_issues)
        issues.extend(reveal_issues)
        if commitment_manifest is not None:
            normalized["commitment_manifest"] = commitment_manifest
        if reveal_manifest is not None:
            normalized["reveal_manifest"] = reveal_manifest

        for field_name in ("declared_commitment_manifest_id", "declared_reveal_manifest_id"):
            raw_value = value.get(field_name)
            if raw_value is not None:
                if not is_supported_text(raw_value):
                    issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_DECLARED_SELECTOR_ID", field_name))
                else:
                    normalized[field_name] = normalize_id(raw_value)

        if raw_commitment is not None:
            issues.append(ValidationIssue(STATE_UNSUPPORTED, "SELECTION_COMMITMENT_NOT_ALLOWED", mode))
        if raw_salt is not None:
            issues.append(ValidationIssue(STATE_UNSUPPORTED, "SELECTION_SALT_NOT_ALLOWED", mode))

    elif mode in {"CANONICAL_RANK", "ABSTAIN_ON_MULTIPLE"}:
        for field_name, raw_value in (
            ("selection_event_id", raw_event_id),
            ("selection_commitment", raw_commitment),
            ("selection_salt", raw_salt),
            ("commitment_manifest", raw_commitment_manifest),
            ("reveal_manifest", raw_reveal_manifest),
            ("declared_commitment_manifest_id", value.get("declared_commitment_manifest_id")),
            ("declared_reveal_manifest_id", value.get("declared_reveal_manifest_id")),
        ):
            if raw_value is not None:
                issues.append(ValidationIssue(STATE_UNSUPPORTED, "SELECTOR_FIELD_NOT_ALLOWED", mode + ":" + field_name))

    return normalized, issues



def participant_set_material(normalized_input: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    selector = normalized_input["selector"]
    if selector.get("mode") != "MULTI_PARTY_COMMIT_REVEAL":
        return None
    commitments = selector.get("commitment_manifest", {}).get("parties", [])
    return {
        "domain": MPCR_PARTICIPANTS_DOMAIN,
        "selection_event_id": selector.get("selection_event_id"),
        "party_ids": [party["party_id"] for party in commitments],
    }


def participant_set_id(normalized_input: Dict[str, Any]) -> Optional[str]:
    material = participant_set_material(normalized_input)
    if material is None:
        return None
    return identity("slang_exam_mpcr_participants_sha256:", material)


def selection_context_material(
    normalized_input: Dict[str, Any],
    bank_id: str,
    blueprint_id: str,
    participant_id: Optional[str],
) -> Dict[str, Any]:
    context = normalized_input["context"]
    selector = normalized_input["selector"]
    return {
        "domain": SELECTION_CONTEXT_DOMAIN,
        "core_version": CORE_VERSION,
        "profile_id": PROFILE_ID,
        "ruleset_id": RULESET_ID,
        "canonicalization_id": CANONICALIZATION_ID,
        "selector_mode": selector["mode"],
        "selection_event_id": selector.get("selection_event_id"),
        "exam_id": context["exam_id"],
        "session_id": context["session_id"],
        "audience_scope": context["audience_scope"],
        "audience_id": context["audience_id"],
        "variant_id": selector["variant_id"],
        "bank_id": bank_id,
        "blueprint_id": blueprint_id,
        "participant_set_id": participant_id,
    }


def selection_context_id(
    normalized_input: Dict[str, Any],
    bank_id: str,
    blueprint_id: str,
    participant_id: Optional[str],
) -> str:
    return identity(
        "slang_exam_selection_context_sha256:",
        selection_context_material(normalized_input, bank_id, blueprint_id, participant_id),
    )


def single_party_commitment_material(context_id: str, salt: str) -> Dict[str, Any]:
    return {
        "domain": SINGLE_COMMITMENT_DOMAIN,
        "selection_context_id": context_id,
        "salt": salt,
    }


def mpcr_party_commitment_material(
    context_id: str,
    party_id: str,
    salt: str,
) -> Dict[str, Any]:
    return {
        "domain": MPCR_PARTY_COMMITMENT_DOMAIN,
        "selection_context_id": context_id,
        "party_id": party_id,
        "salt": salt,
    }


def mpcr_selector_material(
    normalized_input: Dict[str, Any],
    context_id: str,
    participant_id: str,
) -> Dict[str, Any]:
    selector = normalized_input["selector"]
    commitments = selector["commitment_manifest"]["parties"]
    reveals = selector["reveal_manifest"]["reveals"]
    selection_event_id = selector["selection_event_id"]

    commitment_material = {
        "domain": MPCR_COMMITMENTS_DOMAIN,
        "selection_context_id": context_id,
        "selection_event_id": selection_event_id,
        "commitments": commitments,
    }
    reveal_material = {
        "domain": MPCR_REVEALS_DOMAIN,
        "selection_context_id": context_id,
        "selection_event_id": selection_event_id,
        "reveals": reveals,
    }
    commitment_manifest_id = identity("slang_exam_mpcr_commitments_sha256:", commitment_material)
    reveal_manifest_id = identity("slang_exam_mpcr_reveals_sha256:", reveal_material)

    commitment_aggregate_material = {
        "domain": MPCR_COMMITMENT_AGGREGATE_DOMAIN,
        "selection_context_id": context_id,
        "participant_set_id": participant_id,
        "commitment_manifest_id": commitment_manifest_id,
    }
    selector_transcript_material = {
        "domain": MPCR_TRANSCRIPT_DOMAIN,
        "selection_context_id": context_id,
        "participant_set_id": participant_id,
        "commitment_manifest_id": commitment_manifest_id,
        "reveal_manifest_id": reveal_manifest_id,
    }
    combined_salt_material = {
        "domain": MPCR_COMBINE_DOMAIN,
        "selection_context_id": context_id,
        "participant_set_id": participant_id,
        "reveal_manifest_id": reveal_manifest_id,
        "contributions": reveals,
    }
    return {
        "selection_event_id": selection_event_id,
        "party_count": len(commitments),
        "commitment_manifest_id": commitment_manifest_id,
        "reveal_manifest_id": reveal_manifest_id,
        "participant_set_id": participant_id,
        "commitment_aggregate_id": identity(
            "slang_exam_mpcr_commitment_aggregate_sha256:",
            commitment_aggregate_material,
        ),
        "selector_transcript_id": identity(
            "slang_exam_mpcr_transcript_sha256:",
            selector_transcript_material,
        ),
        "combined_selection_salt": sha256_hex(combined_salt_material),
    }


def validate_selector_context(
    normalized_input: Dict[str, Any],
    context_id: str,
    participant_id: Optional[str],
) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    selector = normalized_input["selector"]
    mode = selector["mode"]

    if mode == "COMMIT_REVEAL_RANK":
        expected = sha256_hex(single_party_commitment_material(context_id, selector["selection_salt"]))
        if expected != selector["selection_commitment"]:
            issues.append(ValidationIssue(STATE_CONFLICT, "SELECTION_COMMITMENT_MISMATCH", "selector"))

    if mode == "MULTI_PARTY_COMMIT_REVEAL":
        commitments = selector["commitment_manifest"].get("parties", [])
        reveals = selector["reveal_manifest"].get("reveals", [])
        commitment_by_party = {item["party_id"]: item["commitment"] for item in commitments}
        reveal_by_party = {item["party_id"]: item["salt"] for item in reveals}

        for party_id in sorted(set(reveal_by_party) - set(commitment_by_party)):
            issues.append(ValidationIssue(STATE_CONFLICT, "UNDECLARED_PARTY_REVEAL", party_id))
        for party_id in sorted(set(commitment_by_party) - set(reveal_by_party)):
            issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_PARTY_REVEAL", party_id))
        for party_id in sorted(set(commitment_by_party) & set(reveal_by_party)):
            expected = sha256_hex(mpcr_party_commitment_material(context_id, party_id, reveal_by_party[party_id]))
            if expected != commitment_by_party[party_id]:
                issues.append(ValidationIssue(STATE_CONFLICT, "PARTY_COMMITMENT_MISMATCH", party_id))

        if not issues and commitments and reveals and participant_id is not None:
            material = mpcr_selector_material(normalized_input, context_id, participant_id)
            declared_commitment_id = selector.get("declared_commitment_manifest_id")
            if declared_commitment_id is not None and declared_commitment_id != material["commitment_manifest_id"]:
                issues.append(ValidationIssue(STATE_CONFLICT, "COMMITMENT_MANIFEST_ID_MISMATCH", "declared_commitment_manifest_id"))
            declared_reveal_id = selector.get("declared_reveal_manifest_id")
            if declared_reveal_id is not None and declared_reveal_id != material["reveal_manifest_id"]:
                issues.append(ValidationIssue(STATE_CONFLICT, "REVEAL_MANIFEST_ID_MISMATCH", "declared_reveal_manifest_id"))

    return issues

def normalize_blueprint(value: Any) -> Tuple[Optional[Dict[str, Any]], List[ValidationIssue]]:
    issues: List[ValidationIssue] = []
    if value is None:
        return None, [ValidationIssue(STATE_INCOMPLETE, "MISSING_BLUEPRINT", "blueprint")]
    if not isinstance(value, dict):
        return None, [ValidationIssue(STATE_UNSUPPORTED, "INVALID_BLUEPRINT_TYPE", "blueprint")]

    for key in sorted(set(value) - BLUEPRINT_KEYS):
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "UNSUPPORTED_BLUEPRINT_FIELD", key))
    for key in sorted(BLUEPRINT_REQUIRED_KEYS):
        if key not in value:
            issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_BLUEPRINT_FIELD", key))

    normalized: Dict[str, Any] = {}

    total_questions = value.get("total_questions")
    if total_questions is not None:
        if not is_plain_int(total_questions) or not (1 <= total_questions <= MAX_TOTAL_QUESTIONS):
            issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_TOTAL_QUESTIONS", repr(total_questions)))
        else:
            normalized["total_questions"] = total_questions

    total_marks = value.get("total_marks")
    if total_marks is not None:
        if not is_plain_int(total_marks) or not (1 <= total_marks <= MAX_TOTAL_MARKS):
            issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_TOTAL_MARKS", repr(total_marks)))
        else:
            normalized["total_marks"] = total_marks

    topic_counts, topic_issues = normalize_count_map(value.get("topic_counts"), "topic_counts")
    difficulty_counts, difficulty_issues = normalize_count_map(
        value.get("difficulty_counts"),
        "difficulty_counts",
        SUPPORTED_DIFFICULTIES,
    )
    type_counts, type_issues = normalize_count_map(
        value.get("type_counts"),
        "type_counts",
        SUPPORTED_QUESTION_TYPES,
    )
    issues.extend(topic_issues)
    issues.extend(difficulty_issues)
    issues.extend(type_issues)

    if topic_counts is not None:
        normalized["topic_counts"] = topic_counts
    if difficulty_counts is not None:
        normalized["difficulty_counts"] = difficulty_counts
    if type_counts is not None:
        normalized["type_counts"] = type_counts

    max_per_group = value.get("max_per_exposure_group")
    if max_per_group is not None:
        if not is_plain_int(max_per_group) or max_per_group <= 0:
            issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_EXPOSURE_GROUP_LIMIT", repr(max_per_group)))
        else:
            normalized["max_per_exposure_group"] = max_per_group

    raw_pairs = value.get("forbidden_pairs")
    normalized_pairs: Set[Tuple[str, str]] = set()
    if raw_pairs is not None:
        if not isinstance(raw_pairs, list):
            issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_FORBIDDEN_PAIRS_TYPE", "forbidden_pairs"))
        else:
            for index, pair in enumerate(raw_pairs):
                if not isinstance(pair, list) or len(pair) != 2:
                    issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_FORBIDDEN_PAIR", str(index)))
                    continue
                first, second = pair
                if not is_supported_text(first) or not is_supported_text(second):
                    issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_FORBIDDEN_PAIR_ID", str(index)))
                    continue
                a = normalize_id(first)
                b = normalize_id(second)
                if a == b:
                    issues.append(ValidationIssue(STATE_CONFLICT, "SELF_FORBIDDEN_PAIR", a))
                    continue
                normalized_pairs.add(tuple(sorted((a, b))))
            normalized["forbidden_pairs"] = [list(pair) for pair in sorted(normalized_pairs)]

    raw_registry_id = value.get("topic_registry_id")
    raw_allowed_topics = value.get("allowed_topics")
    if (raw_registry_id is None) != (raw_allowed_topics is None):
        missing = "allowed_topics" if raw_allowed_topics is None else "topic_registry_id"
        issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_TOPIC_REGISTRY_FIELD", missing))
    elif raw_registry_id is not None and raw_allowed_topics is not None:
        if not is_supported_text(raw_registry_id):
            issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_TOPIC_REGISTRY_ID", "topic_registry_id"))
        else:
            normalized["topic_registry_id"] = normalize_id(raw_registry_id)

        if not isinstance(raw_allowed_topics, list) or not raw_allowed_topics:
            issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_ALLOWED_TOPICS", "allowed_topics"))
        else:
            allowed: Set[str] = set()
            for index, raw_topic in enumerate(raw_allowed_topics):
                if not is_supported_text(raw_topic):
                    issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_ALLOWED_TOPIC", str(index)))
                    continue
                topic = normalize_label(raw_topic)
                if topic in allowed:
                    issues.append(ValidationIssue(STATE_CONFLICT, "DUPLICATE_ALLOWED_TOPIC", topic))
                    continue
                allowed.add(topic)
            normalized["allowed_topics"] = sorted(allowed)

    total_question_count = normalized.get("total_questions")
    for map_name in ("topic_counts", "difficulty_counts", "type_counts"):
        if total_question_count is not None and map_name in normalized:
            total = sum(normalized[map_name].values())
            if total != total_question_count:
                issues.append(
                    ValidationIssue(
                        STATE_CONFLICT,
                        "BLUEPRINT_COUNT_TOTAL_MISMATCH",
                        map_name + "=" + str(total) + ",total_questions=" + str(total_question_count),
                    )
                )

    if "allowed_topics" in normalized and "topic_counts" in normalized:
        allowed_set = set(normalized["allowed_topics"])
        for topic in normalized["topic_counts"]:
            if topic not in allowed_set:
                issues.append(ValidationIssue(STATE_UNSUPPORTED, "TOPIC_NOT_IN_REGISTRY", topic))

    return normalized, issues


def normalize_question_bank(value: Any) -> Tuple[Optional[List[Dict[str, Any]]], List[ValidationIssue]]:
    issues: List[ValidationIssue] = []
    if value is None:
        return None, [ValidationIssue(STATE_INCOMPLETE, "MISSING_QUESTION_BANK", "question_bank")]
    if not isinstance(value, list):
        return None, [ValidationIssue(STATE_UNSUPPORTED, "INVALID_QUESTION_BANK_TYPE", "question_bank")]
    if len(value) > MAX_QUESTION_BANK_SIZE:
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "QUESTION_BANK_LIMIT_EXCEEDED", str(len(value))))

    normalized_items: List[Dict[str, Any]] = []
    seen_ids: Dict[str, Dict[str, Any]] = {}

    for index, raw_item in enumerate(value):
        if not isinstance(raw_item, dict):
            issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_QUESTION_RECORD", str(index)))
            continue

        for key in sorted(set(raw_item) - QUESTION_KEYS):
            issues.append(ValidationIssue(STATE_UNSUPPORTED, "UNSUPPORTED_QUESTION_FIELD", str(index) + ":" + key))
        for key in sorted(QUESTION_KEYS):
            if key not in raw_item:
                issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_QUESTION_FIELD", str(index) + ":" + key))

        item: Dict[str, Any] = {}
        for key in ("question_id", "answer_key_id", "exposure_group"):
            raw = raw_item.get(key)
            if raw is None:
                continue
            if not is_supported_text(raw):
                issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_QUESTION_IDENTIFIER", str(index) + ":" + key))
            else:
                item[key] = normalize_id(raw)

        raw_topic = raw_item.get("topic")
        if raw_topic is not None:
            if not is_supported_text(raw_topic):
                issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_QUESTION_TOPIC", str(index)))
            else:
                item["topic"] = normalize_label(raw_topic)

        raw_difficulty = raw_item.get("difficulty")
        if raw_difficulty is not None:
            if not is_supported_text(raw_difficulty):
                issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_QUESTION_DIFFICULTY", str(index)))
            else:
                difficulty = normalize_label(raw_difficulty)
                if difficulty not in SUPPORTED_DIFFICULTIES:
                    issues.append(ValidationIssue(STATE_UNSUPPORTED, "UNSUPPORTED_QUESTION_DIFFICULTY", difficulty))
                else:
                    item["difficulty"] = difficulty

        raw_type = raw_item.get("question_type")
        if raw_type is not None:
            if not is_supported_text(raw_type):
                issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_QUESTION_TYPE_LABEL", str(index)))
            else:
                question_type = normalize_label(raw_type)
                if question_type not in SUPPORTED_QUESTION_TYPES:
                    issues.append(ValidationIssue(STATE_UNSUPPORTED, "UNSUPPORTED_QUESTION_TYPE", question_type))
                else:
                    item["question_type"] = question_type

        raw_marks = raw_item.get("marks")
        if raw_marks is not None:
            if not is_plain_int(raw_marks) or not (1 <= raw_marks <= MAX_QUESTION_MARKS):
                issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_QUESTION_MARKS", str(index)))
            else:
                item["marks"] = raw_marks

        raw_approved = raw_item.get("approved")
        if raw_approved is not None:
            if not isinstance(raw_approved, bool):
                issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_APPROVED_FLAG", str(index)))
            else:
                item["approved"] = raw_approved

        raw_commitment = raw_item.get("content_commitment")
        if raw_commitment is not None:
            commitment_value = normalize_sha256(raw_commitment)
            if commitment_value is None:
                issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_CONTENT_COMMITMENT", str(index)))
            else:
                item["content_commitment"] = commitment_value

        if set(item) == QUESTION_KEYS:
            question_id = item["question_id"]
            if question_id in seen_ids:
                if seen_ids[question_id] == item:
                    issues.append(ValidationIssue(STATE_CONFLICT, "DUPLICATE_QUESTION_ID", question_id))
                else:
                    issues.append(ValidationIssue(STATE_CONFLICT, "CONTRADICTORY_QUESTION_ID", question_id))
            else:
                seen_ids[question_id] = item
                normalized_items.append(item)

    normalized_items.sort(key=lambda item: item["question_id"])
    return normalized_items, issues


def normalize_input(raw_input: Any) -> Tuple[Optional[Dict[str, Any]], List[ValidationIssue]]:
    issues: List[ValidationIssue] = []
    if not isinstance(raw_input, dict):
        return None, [ValidationIssue(STATE_UNSUPPORTED, "INPUT_NOT_OBJECT", type(raw_input).__name__)]

    for key in sorted(set(raw_input) & DERIVED_TOP_LEVEL_KEYS):
        issues.append(ValidationIssue(STATE_FORBIDDEN, "DERIVED_FIELD_INJECTION", key))
    for key in sorted(set(raw_input) - TOP_LEVEL_KEYS - DERIVED_TOP_LEVEL_KEYS):
        issues.append(ValidationIssue(STATE_UNSUPPORTED, "UNSUPPORTED_TOP_LEVEL_FIELD", key))
    for key in ("schema", "profile_id", "ruleset_id", "context", "blueprint", "selector", "question_bank"):
        if key not in raw_input:
            issues.append(ValidationIssue(STATE_INCOMPLETE, "MISSING_TOP_LEVEL_FIELD", key))

    normalized: Dict[str, Any] = {}
    raw_schema = raw_input.get("schema")
    if raw_schema is not None:
        if raw_schema != INPUT_SCHEMA:
            issues.append(ValidationIssue(STATE_UNSUPPORTED, "UNSUPPORTED_INPUT_SCHEMA", repr(raw_schema)))
        else:
            normalized["schema"] = INPUT_SCHEMA

    raw_profile = raw_input.get("profile_id")
    if raw_profile is not None:
        if raw_profile != PROFILE_ID:
            issues.append(ValidationIssue(STATE_UNSUPPORTED, "UNSUPPORTED_PROFILE_ID", repr(raw_profile)))
        else:
            normalized["profile_id"] = PROFILE_ID

    raw_ruleset = raw_input.get("ruleset_id")
    if raw_ruleset is not None:
        if raw_ruleset != RULESET_ID:
            issues.append(ValidationIssue(STATE_UNSUPPORTED, "UNSUPPORTED_RULESET_ID", repr(raw_ruleset)))
        else:
            normalized["ruleset_id"] = RULESET_ID

    context, context_issues = normalize_context(raw_input.get("context"))
    blueprint, blueprint_issues = normalize_blueprint(raw_input.get("blueprint"))
    selector, selector_issues = normalize_selector(raw_input.get("selector"))
    question_bank, bank_issues = normalize_question_bank(raw_input.get("question_bank"))
    issues.extend(context_issues)
    issues.extend(blueprint_issues)
    issues.extend(selector_issues)
    issues.extend(bank_issues)

    if context is not None:
        normalized["context"] = context
    if blueprint is not None:
        normalized["blueprint"] = blueprint
    if selector is not None:
        normalized["selector"] = selector
    if question_bank is not None:
        normalized["question_bank"] = question_bank

    raw_declared_bank_id = raw_input.get("declared_bank_id")
    if raw_declared_bank_id is not None:
        if not is_supported_text(raw_declared_bank_id):
            issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_DECLARED_BANK_ID", "declared_bank_id"))
        else:
            normalized["declared_bank_id"] = normalize_id(raw_declared_bank_id)

    raw_declared_blueprint_id = raw_input.get("declared_blueprint_id")
    if raw_declared_blueprint_id is not None:
        if not is_supported_text(raw_declared_blueprint_id):
            issues.append(ValidationIssue(STATE_UNSUPPORTED, "INVALID_DECLARED_BLUEPRINT_ID", "declared_blueprint_id"))
        else:
            normalized["declared_blueprint_id"] = normalize_id(raw_declared_blueprint_id)

    if blueprint is not None and question_bank is not None and "allowed_topics" in blueprint:
        allowed = set(blueprint["allowed_topics"])
        for item in question_bank:
            if item["topic"] not in allowed:
                issues.append(ValidationIssue(STATE_UNSUPPORTED, "QUESTION_TOPIC_NOT_IN_REGISTRY", item["question_id"] + ":" + item["topic"]))

    return normalized, issues


def forbidden_pair_set(blueprint: Dict[str, Any]) -> Set[Tuple[str, str]]:
    return {tuple(pair) for pair in blueprint.get("forbidden_pairs", [])}


def counts_match(current: Counter, target: Dict[str, int]) -> bool:
    keys = set(current) | set(target)
    return all(current.get(key, 0) == target.get(key, 0) for key in keys)



def selector_material(
    normalized_input: Dict[str, Any],
    context_id: str,
    participant_id: Optional[str],
) -> Dict[str, Any]:
    selector = normalized_input["selector"]
    mode = selector["mode"]
    material: Dict[str, Any] = {
        "selector_mode": mode,
        "variant_id": selector["variant_id"],
        "selection_posture": "PUBLIC_INPUTS",
        "selection_context_id": context_id,
        "public_binding": {
            "selector_mode": mode,
            "variant_id": selector["variant_id"],
            "selection_context_id": context_id,
        },
        "seed_extension": {},
    }

    if mode == "COMMIT_REVEAL_RANK":
        material["selection_posture"] = "SINGLE_PARTY_COMMIT_REVEAL"
        material["public_binding"].update(
            {
                "selection_event_id": selector["selection_event_id"],
                "selection_commitment": selector["selection_commitment"],
            }
        )
        material["seed_extension"] = {"selection_salt": selector["selection_salt"]}

    if mode == "MULTI_PARTY_COMMIT_REVEAL":
        assert participant_id is not None
        mpcr = mpcr_selector_material(normalized_input, context_id, participant_id)
        material["selection_posture"] = "CONDITIONAL_PRE_REVEAL_RESISTANCE"
        material["public_binding"].update(
            {
                "selection_event_id": mpcr["selection_event_id"],
                "party_count": mpcr["party_count"],
                "commitment_manifest_id": mpcr["commitment_manifest_id"],
                "reveal_manifest_id": mpcr["reveal_manifest_id"],
                "participant_set_id": mpcr["participant_set_id"],
                "commitment_aggregate_id": mpcr["commitment_aggregate_id"],
                "selector_transcript_id": mpcr["selector_transcript_id"],
            }
        )
        material["seed_extension"] = {"combined_selection_salt": mpcr["combined_selection_salt"]}

    return material


def selector_seed(selector_data: Dict[str, Any]) -> Dict[str, Any]:
    seed: Dict[str, Any] = {
        "selection_context_id": selector_data["selection_context_id"],
    }
    seed.update(selector_data["seed_extension"])
    return seed


def question_rank(seed: Dict[str, Any], item: Dict[str, Any]) -> Tuple[str, str]:
    material = {
        "domain": QUESTION_RANK_DOMAIN,
        "seed": seed,
        "question_id": item["question_id"],
        "content_commitment": item["content_commitment"],
    }
    return sha256_hex(material), item["question_id"]

def capacity_diagnostics(normalized_input: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    blueprint = normalized_input["blueprint"]
    eligible = [item for item in normalized_input["question_bank"] if item["approved"]]
    reasons: List[str] = []
    missing: List[str] = []

    available_topics = Counter(item["topic"] for item in eligible)
    available_difficulties = Counter(item["difficulty"] for item in eligible)
    available_types = Counter(item["question_type"] for item in eligible)

    for label, required in blueprint["topic_counts"].items():
        available = available_topics.get(label, 0)
        if available < required:
            reasons.append("MISSING_TOPIC_CAPACITY:" + label)
            missing.append("topic:" + label + ":required=" + str(required) + ":available=" + str(available))

    for label, required in blueprint["difficulty_counts"].items():
        available = available_difficulties.get(label, 0)
        if available < required:
            reasons.append("MISSING_DIFFICULTY_CAPACITY:" + label)
            missing.append("difficulty:" + label + ":required=" + str(required) + ":available=" + str(available))

    for label, required in blueprint["type_counts"].items():
        available = available_types.get(label, 0)
        if available < required:
            reasons.append("MISSING_TYPE_CAPACITY:" + label)
            missing.append("question_type:" + label + ":required=" + str(required) + ":available=" + str(available))

    if len(eligible) < blueprint["total_questions"]:
        reasons.append("MISSING_TOTAL_QUESTION_CAPACITY")
        missing.append("approved_questions:required=" + str(blueprint["total_questions"]) + ":available=" + str(len(eligible)))

    return sorted(set(reasons)), sorted(set(missing))



def find_solutions(
    normalized_input: Dict[str, Any],
    selector_data: Dict[str, Any],
    limit: int,
    node_limit: int,
) -> Tuple[List[List[Dict[str, Any]]], Dict[str, Any]]:
    blueprint = normalized_input["blueprint"]
    seed = selector_seed(selector_data)

    eligible = [item for item in normalized_input["question_bank"] if item["approved"]]
    eligible.sort(key=lambda item: question_rank(seed, item))

    count = len(eligible)
    suffix_topic: List[Counter] = [Counter() for _ in range(count + 1)]
    suffix_difficulty: List[Counter] = [Counter() for _ in range(count + 1)]
    suffix_type: List[Counter] = [Counter() for _ in range(count + 1)]
    suffix_group: List[Counter] = [Counter() for _ in range(count + 1)]
    for index in range(count - 1, -1, -1):
        item = eligible[index]
        suffix_topic[index] = suffix_topic[index + 1].copy()
        suffix_difficulty[index] = suffix_difficulty[index + 1].copy()
        suffix_type[index] = suffix_type[index + 1].copy()
        suffix_group[index] = suffix_group[index + 1].copy()
        suffix_topic[index][item["topic"]] += 1
        suffix_difficulty[index][item["difficulty"]] += 1
        suffix_type[index][item["question_type"]] += 1
        suffix_group[index][item["exposure_group"]] += 1

    target_questions = blueprint["total_questions"]
    target_marks = blueprint["total_marks"]
    target_topics = blueprint["topic_counts"]
    target_difficulties = blueprint["difficulty_counts"]
    target_types = blueprint["type_counts"]
    max_per_group = blueprint["max_per_exposure_group"]
    forbidden_pairs = forbidden_pair_set(blueprint)

    mark_mask = (1 << (target_marks + 1)) - 1
    reachable_marks: List[List[int]] = [
        [0 for _ in range(target_questions + 1)] for _ in range(count + 1)
    ]
    reachable_marks[count][0] = 1
    for index in range(count - 1, -1, -1):
        mark = eligible[index]["marks"]
        for slots in range(target_questions + 1):
            reachable = reachable_marks[index + 1][slots]
            if slots > 0:
                reachable |= reachable_marks[index + 1][slots - 1] << mark
            reachable_marks[index][slots] = reachable & mark_mask

    solutions: List[List[Dict[str, Any]]] = []
    selected: List[Dict[str, Any]] = []
    selected_ids: Set[str] = set()
    marks = 0
    topic_counts: Counter = Counter()
    difficulty_counts: Counter = Counter()
    type_counts: Counter = Counter()
    group_counts: Counter = Counter()
    nodes = 0
    exhausted = False
    best_partial_question_count = 0
    best_partial_marks = 0
    prune_counts: Counter = Counter()

    def valid_partial(item: Dict[str, Any]) -> bool:
        if len(selected) + 1 > target_questions:
            return False
        if marks + item["marks"] > target_marks:
            return False
        if topic_counts[item["topic"]] + 1 > target_topics.get(item["topic"], 0):
            return False
        if difficulty_counts[item["difficulty"]] + 1 > target_difficulties.get(item["difficulty"], 0):
            return False
        if type_counts[item["question_type"]] + 1 > target_types.get(item["question_type"], 0):
            return False
        if group_counts[item["exposure_group"]] + 1 > max_per_group:
            return False
        for existing_id in selected_ids:
            if tuple(sorted((existing_id, item["question_id"]))) in forbidden_pairs:
                return False
        return True

    def complete() -> bool:
        return (
            len(selected) == target_questions
            and marks == target_marks
            and counts_match(topic_counts, target_topics)
            and counts_match(difficulty_counts, target_difficulties)
            and counts_match(type_counts, target_types)
        )

    def record_partial() -> None:
        nonlocal best_partial_question_count, best_partial_marks
        if len(selected) > best_partial_question_count:
            best_partial_question_count = len(selected)
            best_partial_marks = marks
        elif len(selected) == best_partial_question_count and marks > best_partial_marks:
            best_partial_marks = marks

    def feasible(index: int) -> bool:
        remaining_slots = target_questions - len(selected)
        remaining_items = count - index
        if remaining_slots < 0 or remaining_items < remaining_slots:
            prune_counts["remaining_items"] += 1
            return False

        required_marks = target_marks - marks
        if not (0 <= required_marks <= target_marks):
            prune_counts["marks"] += 1
            return False
        reachable = reachable_marks[index][remaining_slots]
        if ((reachable >> required_marks) & 1) == 0:
            prune_counts["marks"] += 1
            return False

        for label, need in target_topics.items():
            if suffix_topic[index].get(label, 0) < need - topic_counts[label]:
                prune_counts["topic_capacity"] += 1
                return False
        for label, need in target_difficulties.items():
            if suffix_difficulty[index].get(label, 0) < need - difficulty_counts[label]:
                prune_counts["difficulty_capacity"] += 1
                return False
        for label, need in target_types.items():
            if suffix_type[index].get(label, 0) < need - type_counts[label]:
                prune_counts["type_capacity"] += 1
                return False

        usable_group_capacity = 0
        for group, remaining in suffix_group[index].items():
            usable_group_capacity += min(remaining, max(0, max_per_group - group_counts[group]))
        if usable_group_capacity < remaining_slots:
            prune_counts["exposure_capacity"] += 1
            return False

        compatible_remaining = 0
        for item in eligible[index:]:
            if all(tuple(sorted((existing_id, item["question_id"]))) not in forbidden_pairs for existing_id in selected_ids):
                compatible_remaining += 1
        if compatible_remaining < remaining_slots:
            prune_counts["forbidden_pair_capacity"] += 1
            return False
        return True

    def recurse(index: int) -> None:
        nonlocal marks, nodes, exhausted
        if exhausted or len(solutions) >= limit:
            return
        if nodes >= node_limit:
            exhausted = True
            return
        nodes += 1

        record_partial()
        if not feasible(index):
            return
        if index == count or len(selected) == target_questions:
            if complete():
                solutions.append(copy.deepcopy(selected))
            return

        item = eligible[index]
        if valid_partial(item):
            selected.append(item)
            selected_ids.add(item["question_id"])
            marks += item["marks"]
            topic_counts[item["topic"]] += 1
            difficulty_counts[item["difficulty"]] += 1
            type_counts[item["question_type"]] += 1
            group_counts[item["exposure_group"]] += 1

            recurse(index + 1)

            group_counts[item["exposure_group"]] -= 1
            type_counts[item["question_type"]] -= 1
            difficulty_counts[item["difficulty"]] -= 1
            topic_counts[item["topic"]] -= 1
            marks -= item["marks"]
            selected_ids.remove(item["question_id"])
            selected.pop()

        recurse(index + 1)

    recurse(0)
    stats = {
        "search_nodes": nodes,
        "search_node_limit": node_limit,
        "search_budget_exhausted": exhausted,
        "admissible_solution_count_lower_bound": len(solutions),
        "decision_solution_threshold": limit,
        "complete_solution_found": bool(solutions),
        "partial_candidate_found": best_partial_question_count > 0,
        "best_partial_question_count": best_partial_question_count,
        "best_partial_marks": best_partial_marks,
        "pruned_by_remaining_items": prune_counts["remaining_items"],
        "pruned_by_marks": prune_counts["marks"],
        "pruned_by_topic_capacity": prune_counts["topic_capacity"],
        "pruned_by_difficulty_capacity": prune_counts["difficulty_capacity"],
        "pruned_by_type_capacity": prune_counts["type_capacity"],
        "pruned_by_exposure_capacity": prune_counts["exposure_capacity"],
        "pruned_by_forbidden_pair_capacity": prune_counts["forbidden_pair_capacity"],
        "marks_dp_state_count": (count + 1) * (target_questions + 1),
        "marks_dp_bits_per_state": target_marks + 1,
        "marks_dp_memory_bound_bits": (count + 1) * (target_questions + 1) * (target_marks + 1),
    }
    return solutions, stats


def make_result(
    submission_id: str,
    canonical_input_id: Optional[str],
    normalized_projection_id: Optional[str],
    state: str,
    assembly_state: str,
    release_state: str,
    reason_codes: Iterable[str],
    missing_dependencies: Iterable[str] = (),
    conflicts: Iterable[str] = (),
    prohibitions: Iterable[str] = (),
    unsupported_features: Iterable[str] = (),
    bank_id: Optional[str] = None,
    blueprint_id: Optional[str] = None,
    selection_context_id_value: Optional[str] = None,
    paper_id: Optional[str] = None,
    evaluation_manifest_id: Optional[str] = None,
    selected_questions: Optional[List[Dict[str, str]]] = None,
    paper_visible: bool = False,
    evidence: Optional[Dict[str, Any]] = None,
    search_evidence: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    operational = search_evidence or {}
    operational_id = (
        identity("slang_exam_search_evidence_sha256:", operational)
        if operational
        else None
    )
    result: Dict[str, Any] = {
        "schema": RESULT_SCHEMA,
        "version": VERSION,
        "core_version": CORE_VERSION,
        "profile_id": PROFILE_ID,
        "ruleset_id": RULESET_ID,
        "canonicalization_id": CANONICALIZATION_ID,
        "identity_domain_id": identity_domain_id(),
        "submission_id": submission_id,
        "canonical_input_id": canonical_input_id,
        "normalized_projection_id": normalized_projection_id,
        "bank_id": bank_id,
        "blueprint_id": blueprint_id,
        "selection_context_id": selection_context_id_value,
        "state": state,
        "assembly_state": assembly_state,
        "release_state": release_state,
        "paper_visible": paper_visible,
        "paper_id": paper_id,
        "evaluation_manifest_id": evaluation_manifest_id,
        "selected_questions": selected_questions if paper_visible else None,
        "reason_codes": sorted(set(reason_codes)),
        "missing_dependencies": sorted(set(missing_dependencies)),
        "conflicts": sorted(set(conflicts)),
        "prohibitions": sorted(set(prohibitions)),
        "unsupported_features": sorted(set(unsupported_features)),
        "evidence": evidence or {},
        "search_evidence_id": operational_id,
        "search_evidence": operational,
    }
    identity_basis = canonical_input_id if canonical_input_id is not None else submission_id
    stable_evidence_keys = {
        "audience_scope",
        "applied_authority_requirements",
        "non_applicable_authority_fields",
        "authority_admitted",
        "selection_mode",
        "selection_posture",
        "canonical_selection_rule",
        "selector_mode",
        "variant_id",
        "selection_context_id",
        "selection_event_id",
        "selection_commitment",
        "party_count",
        "commitment_manifest_id",
        "reveal_manifest_id",
        "participant_set_id",
        "commitment_aggregate_id",
        "selector_transcript_id",
    }
    stable_evidence = {
        key: result["evidence"][key]
        for key in sorted(stable_evidence_keys)
        if key in result["evidence"]
    }
    semantic_identity = {
        "schema": result["schema"],
        "version": result["version"],
        "core_version": result["core_version"],
        "profile_id": result["profile_id"],
        "ruleset_id": result["ruleset_id"],
        "canonicalization_id": result["canonicalization_id"],
        "identity_domain_id": result["identity_domain_id"],
        "identity_basis": identity_basis,
        "canonical_input_id": result["canonical_input_id"],
        "bank_id": result["bank_id"],
        "blueprint_id": result["blueprint_id"],
        "selection_context_id": result["selection_context_id"],
        "state": result["state"],
        "assembly_state": result["assembly_state"],
        "release_state": result["release_state"],
        "paper_visible": result["paper_visible"],
        "paper_id": result["paper_id"],
        "evaluation_manifest_id": result["evaluation_manifest_id"],
        "selected_questions": result["selected_questions"],
        "reason_codes": result["reason_codes"],
        "missing_dependencies": result["missing_dependencies"],
        "conflicts": result["conflicts"],
        "prohibitions": result["prohibitions"],
        "unsupported_features": result["unsupported_features"],
        "evidence": stable_evidence,
    }
    result["result_id"] = identity("slang_exam_result_sha256:", semantic_identity)
    return result

def build_bundle(submitted_input: Any, normalized_projection: Optional[Dict[str, Any]], result: Dict[str, Any]) -> Dict[str, Any]:
    bundle: Dict[str, Any] = {
        "schema": BUNDLE_SCHEMA,
        "version": VERSION,
        "canonicalization_id": CANONICALIZATION_ID,
        "identity_domain_id": identity_domain_id(),
        "submitted_input": submitted_input,
        "normalized_projection": normalized_projection,
        "result": result,
    }
    bundle["bundle_id"] = identity("slang_exam_bundle_sha256:", bundle)
    return bundle



def authority_requirements(context: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    scope = context["audience_scope"]
    required_by_scope = {
        "COMMON": ["assembly_authorized"],
        "CENTER": ["assembly_authorized", "center_authorized"],
        "CANDIDATE": ["assembly_authorized", "center_authorized", "candidate_valid"],
    }
    required = required_by_scope[scope]
    all_authority_fields = ["assembly_authorized", "center_authorized", "candidate_valid"]
    non_applicable = [field for field in all_authority_fields if field not in required]
    return required, non_applicable


def resolve_exam(raw_input: Any) -> Dict[str, Any]:
    try:
        validate_portable_json(raw_input)
        submitted_input = json_clone(raw_input)
    except (TypeError, ValueError) as exc:
        raise TypeError("SLANG-Exam accepts portable JSON values without floats or unsafe integers") from exc

    submission_id = identity("slang_exam_submission_sha256:", submitted_input)
    normalized_projection, issues = normalize_input(submitted_input)
    normalized_projection_id = (
        identity("slang_exam_projection_sha256:", normalized_projection)
        if normalized_projection is not None
        else None
    )

    if issues:
        primary = choose_primary_issue(issues)
        result = make_result(
            submission_id=submission_id,
            canonical_input_id=None,
            normalized_projection_id=normalized_projection_id,
            state=primary.state,
            assembly_state=primary.state,
            release_state="NOT_REACHED",
            reason_codes=[issue.code for issue in issues],
            missing_dependencies=[issue.detail for issue in issues if issue.state == STATE_INCOMPLETE],
            conflicts=[issue.detail for issue in issues if issue.state == STATE_CONFLICT],
            prohibitions=[issue.detail for issue in issues if issue.state == STATE_FORBIDDEN],
            unsupported_features=[issue.detail for issue in issues if issue.state == STATE_UNSUPPORTED],
            evidence={"validation_issue_count": len(issues)},
        )
        return build_bundle(submitted_input, normalized_projection, result)

    assert normalized_projection is not None
    canonical_input_id = identity("slang_exam_input_sha256:", normalized_projection)
    bank_id = identity("slang_exam_bank_sha256:", normalized_projection["question_bank"])
    blueprint_id = identity("slang_exam_blueprint_sha256:", normalized_projection["blueprint"])

    conflicts: List[str] = []
    declared_bank_id = normalized_projection.get("declared_bank_id")
    if declared_bank_id is not None and declared_bank_id != bank_id:
        conflicts.append("declared_bank_id")
    declared_blueprint_id = normalized_projection.get("declared_blueprint_id")
    if declared_blueprint_id is not None and declared_blueprint_id != blueprint_id:
        conflicts.append("declared_blueprint_id")

    bank_ids = {item["question_id"] for item in normalized_projection["question_bank"]}
    for first, second in forbidden_pair_set(normalized_projection["blueprint"]):
        if first not in bank_ids or second not in bank_ids:
            conflicts.append("forbidden_pair_reference:" + first + "|" + second)

    if conflicts:
        reason = "DECLARED_IDENTITY_CONFLICT" if any(item.startswith("declared_") for item in conflicts) else "BLUEPRINT_REFERENCE_CONFLICT"
        result = make_result(
            submission_id=submission_id,
            canonical_input_id=canonical_input_id,
            normalized_projection_id=normalized_projection_id,
            state=STATE_CONFLICT,
            assembly_state=STATE_CONFLICT,
            release_state="NOT_REACHED",
            reason_codes=[reason],
            conflicts=conflicts,
            bank_id=bank_id,
            blueprint_id=blueprint_id,
            evidence={"eligible_question_count": sum(1 for item in normalized_projection["question_bank"] if item["approved"])},
        )
        return build_bundle(submitted_input, normalized_projection, result)

    participant_id = participant_set_id(normalized_projection)
    context_id = selection_context_id(normalized_projection, bank_id, blueprint_id, participant_id)
    selector_issues = validate_selector_context(normalized_projection, context_id, participant_id)
    if selector_issues:
        primary = choose_primary_issue(selector_issues)
        result = make_result(
            submission_id=submission_id,
            canonical_input_id=canonical_input_id,
            normalized_projection_id=normalized_projection_id,
            state=primary.state,
            assembly_state=primary.state,
            release_state="NOT_REACHED",
            reason_codes=[issue.code for issue in selector_issues],
            missing_dependencies=[issue.detail for issue in selector_issues if issue.state == STATE_INCOMPLETE],
            conflicts=[issue.detail for issue in selector_issues if issue.state == STATE_CONFLICT],
            unsupported_features=[issue.detail for issue in selector_issues if issue.state == STATE_UNSUPPORTED],
            bank_id=bank_id,
            blueprint_id=blueprint_id,
            selection_context_id_value=context_id,
            evidence={"selector_issue_count": len(selector_issues)},
        )
        return build_bundle(submitted_input, normalized_projection, result)

    selector_data = selector_material(normalized_projection, context_id, participant_id)
    context = normalized_projection["context"]
    required_authority, non_applicable_authority = authority_requirements(context)
    assembly_prohibitions = [field + "=false" for field in required_authority if not context[field]]
    authority_evidence = {
        "audience_scope": context["audience_scope"],
        "applied_authority_requirements": required_authority,
        "non_applicable_authority_fields": non_applicable_authority,
        "authority_admitted": not assembly_prohibitions,
    }

    if assembly_prohibitions:
        evidence = dict(authority_evidence)
        evidence.update(
            {
                "selection_mode": selector_data["selector_mode"],
                "selection_posture": selector_data["selection_posture"],
            }
        )
        evidence.update(selector_data["public_binding"])
        result = make_result(
            submission_id=submission_id,
            canonical_input_id=canonical_input_id,
            normalized_projection_id=normalized_projection_id,
            state=STATE_FORBIDDEN,
            assembly_state=STATE_FORBIDDEN,
            release_state="NOT_REACHED",
            reason_codes=["ASSEMBLY_NOT_AUTHORIZED"],
            prohibitions=assembly_prohibitions,
            bank_id=bank_id,
            blueprint_id=blueprint_id,
            selection_context_id_value=context_id,
            evidence=evidence,
        )
        return build_bundle(submitted_input, normalized_projection, result)

    capacity_reasons, capacity_missing = capacity_diagnostics(normalized_projection)
    if capacity_reasons:
        evidence = dict(authority_evidence)
        evidence.update(
            {
                "selection_mode": selector_data["selector_mode"],
                "selection_posture": selector_data["selection_posture"],
                "eligible_question_count": sum(1 for item in normalized_projection["question_bank"] if item["approved"]),
            }
        )
        evidence.update(selector_data["public_binding"])
        result = make_result(
            submission_id=submission_id,
            canonical_input_id=canonical_input_id,
            normalized_projection_id=normalized_projection_id,
            state=STATE_INCOMPLETE,
            assembly_state=STATE_INCOMPLETE,
            release_state="NOT_REACHED",
            reason_codes=capacity_reasons,
            missing_dependencies=capacity_missing,
            bank_id=bank_id,
            blueprint_id=blueprint_id,
            selection_context_id_value=context_id,
            evidence=evidence,
        )
        return build_bundle(submitted_input, normalized_projection, result)

    selector_mode = normalized_projection["selector"]["mode"]
    solutions, search_stats = find_solutions(
        normalized_projection,
        selector_data,
        2,
        MAX_SEARCH_NODES,
    )

    if len(solutions) >= 2:
        multiplicity_state = "MULTIPLE_PROVED"
    elif len(solutions) == 1 and not search_stats["search_budget_exhausted"]:
        multiplicity_state = "UNIQUE_PROVED"
    else:
        multiplicity_state = "NOT_ESTABLISHED"

    selector_evidence = dict(authority_evidence)
    selector_evidence.update(
        {
            "selection_mode": selector_mode,
            "selection_posture": selector_data["selection_posture"],
            "canonical_selection_rule": "LEXICOGRAPHIC_FIRST_ADMISSIBLE_RANK_VECTOR",
            "multiplicity_state": multiplicity_state,
        }
    )
    selector_evidence.update(selector_data["public_binding"])

    if not solutions and search_stats["search_budget_exhausted"]:
        result = make_result(
            submission_id=submission_id,
            canonical_input_id=canonical_input_id,
            normalized_projection_id=normalized_projection_id,
            state=STATE_ABSTAIN,
            assembly_state=STATE_ABSTAIN,
            release_state="NOT_REACHED",
            reason_codes=["SEARCH_BUDGET_EXHAUSTED"],
            bank_id=bank_id,
            blueprint_id=blueprint_id,
            selection_context_id_value=context_id,
            evidence=selector_evidence,
            search_evidence=search_stats,
        )
        return build_bundle(submitted_input, normalized_projection, result)

    if not solutions:
        result = make_result(
            submission_id=submission_id,
            canonical_input_id=canonical_input_id,
            normalized_projection_id=normalized_projection_id,
            state=STATE_INCOMPLETE,
            assembly_state=STATE_INCOMPLETE,
            release_state="NOT_REACHED",
            reason_codes=["BLUEPRINT_NOT_SATISFIABLE"],
            missing_dependencies=["cross_constraint_capacity"],
            bank_id=bank_id,
            blueprint_id=blueprint_id,
            selection_context_id_value=context_id,
            evidence=selector_evidence,
            search_evidence=search_stats,
        )
        return build_bundle(submitted_input, normalized_projection, result)

    if selector_mode == "ABSTAIN_ON_MULTIPLE":
        if len(solutions) > 1:
            result = make_result(
                submission_id=submission_id,
                canonical_input_id=canonical_input_id,
                normalized_projection_id=normalized_projection_id,
                state=STATE_ABSTAIN,
                assembly_state=STATE_ABSTAIN,
                release_state="NOT_REACHED",
                reason_codes=["MULTIPLE_ADMISSIBLE_PAPERS_WITHOUT_SELECTION"],
                bank_id=bank_id,
                blueprint_id=blueprint_id,
                selection_context_id_value=context_id,
                evidence=selector_evidence,
                search_evidence=search_stats,
            )
            return build_bundle(submitted_input, normalized_projection, result)
        if search_stats["search_budget_exhausted"]:
            result = make_result(
                submission_id=submission_id,
                canonical_input_id=canonical_input_id,
                normalized_projection_id=normalized_projection_id,
                state=STATE_ABSTAIN,
                assembly_state=STATE_ABSTAIN,
                release_state="NOT_REACHED",
                reason_codes=["UNIQUENESS_NOT_ESTABLISHED"],
                bank_id=bank_id,
                blueprint_id=blueprint_id,
                selection_context_id_value=context_id,
                evidence=selector_evidence,
                search_evidence=search_stats,
            )
            return build_bundle(submitted_input, normalized_projection, result)

    selected = solutions[0]
    selected_public = [
        {
            "question_id": item["question_id"],
            "content_commitment": item["content_commitment"],
        }
        for item in selected
    ]
    paper_material = {
        "profile_id": PROFILE_ID,
        "ruleset_id": RULESET_ID,
        "canonicalization_id": CANONICALIZATION_ID,
        "selection_context_id": context_id,
        "selector_binding": selector_data["public_binding"],
        "selected_questions": selected_public,
    }
    paper_id = identity("slang_exam_paper_sha256:", paper_material)
    evaluation_manifest_id = identity(
        "slang_exam_evaluation_sha256:",
        [
            {
                "question_id": item["question_id"],
                "answer_key_id": item["answer_key_id"],
            }
            for item in selected
        ],
    )

    release_prohibitions: List[str] = []
    if not context["release_authorized"]:
        release_prohibitions.append("release_authorized=false")
    if not context["exam_window_open"]:
        release_prohibitions.append("exam_window_open=false")

    resolved_evidence = dict(selector_evidence)
    resolved_evidence.update(
        {
            "selected_question_count": len(selected),
            "selected_total_marks": sum(item["marks"] for item in selected),
        }
    )

    if release_prohibitions:
        result = make_result(
            submission_id=submission_id,
            canonical_input_id=canonical_input_id,
            normalized_projection_id=normalized_projection_id,
            state=STATE_FORBIDDEN,
            assembly_state=STATE_RESOLVED,
            release_state="WITHHOLD",
            reason_codes=["RELEASE_NOT_AUTHORIZED"],
            prohibitions=release_prohibitions,
            bank_id=bank_id,
            blueprint_id=blueprint_id,
            selection_context_id_value=context_id,
            paper_id=paper_id,
            evaluation_manifest_id=evaluation_manifest_id,
            selected_questions=None,
            paper_visible=False,
            evidence=resolved_evidence,
            search_evidence=search_stats,
        )
    else:
        result = make_result(
            submission_id=submission_id,
            canonical_input_id=canonical_input_id,
            normalized_projection_id=normalized_projection_id,
            state=STATE_RESOLVED,
            assembly_state=STATE_RESOLVED,
            release_state="ALLOW",
            reason_codes=["PAPER_ASSEMBLED_AND_RELEASE_ADMITTED"],
            bank_id=bank_id,
            blueprint_id=blueprint_id,
            selection_context_id_value=context_id,
            paper_id=paper_id,
            evaluation_manifest_id=evaluation_manifest_id,
            selected_questions=selected_public,
            paper_visible=True,
            evidence=resolved_evidence,
            search_evidence=search_stats,
        )

    return build_bundle(submitted_input, normalized_projection, result)

def verify_bundle(bundle: Any) -> Tuple[bool, str]:
    if not isinstance(bundle, dict):
        return False, "BUNDLE_NOT_OBJECT"
    try:
        validate_portable_json(bundle)
    except (TypeError, ValueError):
        return False, "BUNDLE_PORTABLE_JSON_MISMATCH"
    except (MemoryError, RecursionError):
        return False, "RESOURCE_LIMIT_EXCEEDED"
    if bundle.get("schema") != BUNDLE_SCHEMA:
        return False, "BUNDLE_SCHEMA_MISMATCH"
    if bundle.get("version") != VERSION:
        return False, "BUNDLE_VERSION_MISMATCH"
    if bundle.get("canonicalization_id") != CANONICALIZATION_ID:
        return False, "CANONICALIZATION_ID_MISMATCH"
    if bundle.get("identity_domain_id") != identity_domain_id():
        return False, "IDENTITY_DOMAIN_ID_MISMATCH"
    if "submitted_input" not in bundle:
        return False, "SUBMITTED_INPUT_MISSING"
    if "normalized_projection" not in bundle:
        return False, "NORMALIZED_PROJECTION_MISSING"
    if "result" not in bundle:
        return False, "RESULT_MISSING"
    if "bundle_id" not in bundle:
        return False, "BUNDLE_ID_MISSING"

    try:
        expected_bundle = resolve_exam(bundle["submitted_input"])
    except (TypeError, ValueError):
        return False, "SUBMITTED_INPUT_INVALID"
    except (MemoryError, RecursionError):
        return False, "RESOURCE_LIMIT_EXCEEDED"
    try:
        if canonical_json(bundle) != canonical_json(expected_bundle):
            return False, "BUNDLE_RECONSTRUCTION_MISMATCH"
    except (MemoryError, RecursionError):
        return False, "RESOURCE_LIMIT_EXCEEDED"
    return True, "PASS"



def make_receipt(bundle: Dict[str, Any]) -> Dict[str, Any]:
    result = bundle["result"]
    evidence = result.get("evidence", {})
    receipt: Dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "version": VERSION,
        "core_version": CORE_VERSION,
        "canonicalization_id": CANONICALIZATION_ID,
        "identity_domain_id": identity_domain_id(),
        "profile_id": result["profile_id"],
        "ruleset_id": result["ruleset_id"],
        "submission_id": result["submission_id"],
        "canonical_input_id": result["canonical_input_id"],
        "bank_id": result["bank_id"],
        "blueprint_id": result["blueprint_id"],
        "selection_context_id": result["selection_context_id"],
        "state": result["state"],
        "assembly_state": result["assembly_state"],
        "release_state": result["release_state"],
        "paper_visible": result["paper_visible"],
        "paper_id": result["paper_id"],
        "evaluation_manifest_id": result["evaluation_manifest_id"],
        "selection_mode": evidence.get("selection_mode"),
        "selection_posture": evidence.get("selection_posture"),
        "multiplicity_state": evidence.get("multiplicity_state"),
        "selection_event_id": evidence.get("selection_event_id"),
        "party_count": evidence.get("party_count"),
        "commitment_manifest_id": evidence.get("commitment_manifest_id"),
        "reveal_manifest_id": evidence.get("reveal_manifest_id"),
        "participant_set_id": evidence.get("participant_set_id"),
        "commitment_aggregate_id": evidence.get("commitment_aggregate_id"),
        "selector_transcript_id": evidence.get("selector_transcript_id"),
        "reason_codes": result["reason_codes"],
        "result_id": result["result_id"],
        "search_evidence_id": result["search_evidence_id"],
        "bundle_id": bundle["bundle_id"],
    }
    receipt["receipt_id"] = identity("slang_exam_receipt_sha256:", receipt)
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
    if receipt.get("canonicalization_id") != CANONICALIZATION_ID:
        return False, "CANONICALIZATION_ID_MISMATCH"
    if receipt.get("identity_domain_id") != identity_domain_id():
        return False, "IDENTITY_DOMAIN_ID_MISMATCH"
    receipt_id = receipt.get("receipt_id")
    if not isinstance(receipt_id, str):
        return False, "RECEIPT_ID_MISSING"
    material = dict(receipt)
    del material["receipt_id"]
    expected = identity("slang_exam_receipt_sha256:", material)
    if receipt_id != expected:
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


def normalize_commitment_source(source: Dict[str, Any]) -> Tuple[Dict[str, Any], str, str, Optional[str], str]:
    context, context_issues = normalize_context(source.get("context"))
    blueprint, blueprint_issues = normalize_blueprint(source.get("blueprint"))
    question_bank, bank_issues = normalize_question_bank(source.get("question_bank"))
    selector, selector_issues = normalize_selector(source.get("selector"))
    issues = context_issues + blueprint_issues + bank_issues + selector_issues
    if issues or context is None or blueprint is None or question_bank is None or selector is None:
        raise ValueError("source must satisfy the structural commitment context")
    normalized = {
        "context": context,
        "blueprint": blueprint,
        "question_bank": question_bank,
        "selector": selector,
    }
    bank_id = identity("slang_exam_bank_sha256:", question_bank)
    blueprint_id = identity("slang_exam_blueprint_sha256:", blueprint)
    participant_id = participant_set_id(normalized)
    context_id = selection_context_id(normalized, bank_id, blueprint_id, participant_id)
    return normalized, bank_id, blueprint_id, participant_id, context_id


def make_single_party_commitment(source: Dict[str, Any], salt: str) -> str:
    normalized_salt = normalize_sha256(salt)
    if normalized_salt is None:
        raise ValueError("salt must be a 64-character hexadecimal value")
    _, _, _, _, context_id = normalize_commitment_source(source)
    return sha256_hex(single_party_commitment_material(context_id, normalized_salt))


def make_mpcr_party_commitment(source: Dict[str, Any], party_id: str, salt: str) -> str:
    normalized_salt = normalize_sha256(salt)
    if normalized_salt is None or not is_supported_text(party_id):
        raise ValueError("source and party material must satisfy the MPCR profile")
    normalized, _, _, participant_id, context_id = normalize_commitment_source(source)
    if participant_id is None:
        raise ValueError("source must declare an MPCR participant set")
    declared = {
        item["party_id"]
        for item in normalized["selector"]["commitment_manifest"]["parties"]
    }
    normalized_party_id = normalize_id(party_id)
    if normalized_party_id not in declared:
        raise ValueError("party_id must belong to the declared participant set")
    return sha256_hex(mpcr_party_commitment_material(context_id, normalized_party_id, normalized_salt))

def question(
    question_id: str,
    topic: str,
    difficulty: str,
    marks: int,
    question_type: str,
    exposure_group: str,
    approved: bool = True,
) -> Dict[str, Any]:
    return {
        "question_id": question_id,
        "topic": topic,
        "difficulty": difficulty,
        "marks": marks,
        "question_type": question_type,
        "approved": approved,
        "answer_key_id": "AK-" + question_id,
        "content_commitment": commitment("CONTENT|" + question_id),
        "exposure_group": exposure_group,
    }


def build_reference_input() -> Dict[str, Any]:
    return {
        "schema": INPUT_SCHEMA,
        "profile_id": PROFILE_ID,
        "ruleset_id": RULESET_ID,
        "context": {
            "exam_id": "EXAM-REFERENCE-001",
            "session_id": "SESSION-2026-A",
            "audience_scope": "COMMON",
            "audience_id": "ALL",
            "assembly_authorized": True,
            "release_authorized": True,
            "exam_window_open": True,
            "center_authorized": True,
            "candidate_valid": True,
        },
        "blueprint": {
            "total_questions": 5,
            "total_marks": 10,
            "topic_registry_id": "EXAM-TOPICS-1",
            "allowed_topics": ["ALGEBRA", "GEOMETRY", "REASONING", "APPLICATION"],
            "topic_counts": {
                "ALGEBRA": 2,
                "GEOMETRY": 1,
                "REASONING": 1,
                "APPLICATION": 1,
            },
            "difficulty_counts": {
                "EASY": 1,
                "MEDIUM": 3,
                "HARD": 1,
            },
            "type_counts": {
                "MCQ": 2,
                "SHORT": 2,
                "LONG": 1,
            },
            "max_per_exposure_group": 2,
            "forbidden_pairs": [["Q101", "Q201"]],
        },
        "selector": {
            "mode": "CANONICAL_RANK",
            "variant_id": "VARIANT-A",
        },
        "question_bank": [
            question("Q101", "ALGEBRA", "MEDIUM", 2, "MCQ", "G1"),
            question("Q102", "ALGEBRA", "MEDIUM", 2, "SHORT", "G2"),
            question("Q103", "ALGEBRA", "HARD", 2, "LONG", "G3"),
            question("Q104", "ALGEBRA", "EASY", 2, "MCQ", "G4"),
            question("Q201", "GEOMETRY", "MEDIUM", 2, "SHORT", "G1"),
            question("Q202", "GEOMETRY", "HARD", 2, "LONG", "G2"),
            question("Q203", "GEOMETRY", "EASY", 2, "MCQ", "G3"),
            question("Q301", "REASONING", "EASY", 2, "MCQ", "G2"),
            question("Q302", "REASONING", "MEDIUM", 2, "SHORT", "G3"),
            question("Q303", "REASONING", "HARD", 2, "LONG", "G4"),
            question("Q401", "APPLICATION", "MEDIUM", 2, "SHORT", "G1"),
            question("Q402", "APPLICATION", "HARD", 2, "LONG", "G2"),
            question("Q403", "APPLICATION", "EASY", 2, "MCQ", "G4"),
            question("Q999", "APPLICATION", "MEDIUM", 2, "MCQ", "G9", approved=False),
        ],
    }


def build_commit_reveal_input() -> Dict[str, Any]:
    source = build_reference_input()
    salt = hashlib.sha256(b"SLANG-EXAM-REFERENCE-SALT").hexdigest()
    source["selector"] = {
        "mode": "COMMIT_REVEAL_RANK",
        "variant_id": "VARIANT-CR",
        "selection_event_id": "SELECTION-EVENT-CR-001",
        "selection_salt": salt,
        "selection_commitment": "0" * 64,
    }
    source["selector"]["selection_commitment"] = make_single_party_commitment(source, salt)
    return source


def build_mpcr_input() -> Dict[str, Any]:
    source = build_reference_input()
    contributions = [
        ("AUTHORITY-A", hashlib.sha256(b"SLANG-EXAM-MPCR-A").hexdigest()),
        ("AUTHORITY-B", hashlib.sha256(b"SLANG-EXAM-MPCR-B").hexdigest()),
        ("AUTHORITY-C", hashlib.sha256(b"SLANG-EXAM-MPCR-C").hexdigest()),
    ]
    source["selector"] = {
        "mode": "MULTI_PARTY_COMMIT_REVEAL",
        "variant_id": "VARIANT-MPCR",
        "selection_event_id": "SELECTION-EVENT-MPCR-001",
        "commitment_manifest": {
            "parties": [
                {"party_id": party_id, "commitment": "0" * 64}
                for party_id, _ in contributions
            ]
        },
        "reveal_manifest": {
            "reveals": [
                {"party_id": party_id, "salt": salt}
                for party_id, salt in contributions
            ]
        },
    }
    for party in source["selector"]["commitment_manifest"]["parties"]:
        salt = next(
            value
            for party_id, value in contributions
            if party_id == party["party_id"]
        )
        party["commitment"] = make_mpcr_party_commitment(source, party["party_id"], salt)
    return source



def public_summary(bundle: Dict[str, Any]) -> Dict[str, Any]:
    result = bundle["result"]
    evidence = result["evidence"]
    return {
        "schema": result["schema"],
        "version": result["version"],
        "core_version": result["core_version"],
        "profile_id": result["profile_id"],
        "ruleset_id": result["ruleset_id"],
        "canonicalization_id": result["canonicalization_id"],
        "identity_domain_id": result["identity_domain_id"],
        "selection_mode": evidence.get("selection_mode"),
        "selection_posture": evidence.get("selection_posture"),
        "selection_context_id": result["selection_context_id"],
        "multiplicity_state": evidence.get("multiplicity_state"),
        "state": result["state"],
        "assembly_state": result["assembly_state"],
        "release_state": result["release_state"],
        "paper_visible": result["paper_visible"],
        "paper_id": result["paper_id"],
        "selected_questions": result["selected_questions"],
        "reason_codes": result["reason_codes"],
        "submission_id": result["submission_id"],
        "canonical_input_id": result["canonical_input_id"],
        "bank_id": result["bank_id"],
        "blueprint_id": result["blueprint_id"],
        "result_id": result["result_id"],
        "search_evidence_id": result["search_evidence_id"],
        "bundle_id": bundle["bundle_id"],
    }

def strict_object_pairs(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError("duplicate JSON object key: " + key)
        result[key] = value
    return result


def reject_nonfinite_constant(value: str) -> None:
    raise ValueError("non-finite JSON number: " + value)


def reject_float_number(value: str) -> None:
    raise ValueError("floating-point JSON number is not supported: " + value)


def parse_safe_integer(value: str) -> int:
    parsed = int(value, 10)
    if parsed < -MAX_SAFE_INTEGER or parsed > MAX_SAFE_INTEGER:
        raise ValueError("JSON integer outside portable range: " + value)
    return parsed


def loads_strict(text: str) -> Any:
    if len(text.encode("utf-8")) > MAX_JSON_INPUT_BYTES:
        raise ValueError("JSON input exceeds byte limit")
    try:
        value = json.loads(
            text,
            object_pairs_hook=strict_object_pairs,
            parse_constant=reject_nonfinite_constant,
            parse_float=reject_float_number,
            parse_int=parse_safe_integer,
        )
    except RecursionError as exc:
        raise ValueError("JSON nesting exceeds parser limit") from exc
    validate_portable_json(value)
    return value


def load_json(path: Path) -> Any:
    if path.stat().st_size > MAX_JSON_INPUT_BYTES:
        raise ValueError("JSON input exceeds byte limit")
    return loads_strict(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")



def run_self_test() -> int:
    groups: Dict[str, List[Tuple[str, bool]]] = {}

    def check(group: str, name: str, condition: bool) -> None:
        groups.setdefault(group, []).append((name, bool(condition)))

    base = build_reference_input()
    resolved = resolve_exam(base)
    result = resolved["result"]
    receipt = make_receipt(resolved)

    check("REFERENCE", "reference resolves", result["state"] == STATE_RESOLVED)
    check("REFERENCE", "assembly resolves", result["assembly_state"] == STATE_RESOLVED)
    check("REFERENCE", "release admitted", result["release_state"] == "ALLOW")
    check("REFERENCE", "paper visible", result["paper_visible"] is True)
    check("REFERENCE", "five questions selected", len(result["selected_questions"] or []) == 5)
    check("REFERENCE", "ten marks selected", result["evidence"].get("selected_total_marks") == 10)
    check("REFERENCE", "selection context present", isinstance(result["selection_context_id"], str))
    check("REFERENCE", "search evidence identity present", isinstance(result["search_evidence_id"], str))
    check("REFERENCE", "canonical rule declared", result["evidence"].get("canonical_selection_rule") == "LEXICOGRAPHIC_FIRST_ADMISSIBLE_RANK_VECTOR")
    check("REFERENCE", "multiplicity conclusion declared", result["evidence"].get("multiplicity_state") in {"UNIQUE_PROVED", "MULTIPLE_PROVED", "NOT_ESTABLISHED"})

    reordered = copy.deepcopy(base)
    reordered["question_bank"].reverse()
    reordered["blueprint"]["topic_counts"] = dict(reversed(list(reordered["blueprint"]["topic_counts"].items())))
    reordered_result = resolve_exam(reordered)["result"]
    check("DETERMINISM", "reordered canonical input identity stable", result["canonical_input_id"] == reordered_result["canonical_input_id"])
    check("DETERMINISM", "reordered paper identity stable", result["paper_id"] == reordered_result["paper_id"])
    check("DETERMINISM", "reordered result identity stable", result["result_id"] == reordered_result["result_id"])

    repeat_result = resolve_exam(base)["result"]
    check("DETERMINISM", "repeat paper identity stable", result["paper_id"] == repeat_result["paper_id"])
    check("DETERMINISM", "repeat result identity stable", result["result_id"] == repeat_result["result_id"])

    closed = copy.deepcopy(base)
    closed["context"]["release_authorized"] = False
    closed_result = resolve_exam(closed)["result"]
    check("RELEASE", "withheld state forbidden", closed_result["state"] == STATE_FORBIDDEN)
    check("RELEASE", "withheld assembly resolved", closed_result["assembly_state"] == STATE_RESOLVED)
    check("RELEASE", "withheld paper hidden", closed_result["paper_visible"] is False)
    check("RELEASE", "withheld paper identity stable", closed_result["paper_id"] == result["paper_id"])
    check("RELEASE", "release change preserves selection context", closed_result["selection_context_id"] == result["selection_context_id"])

    window_closed = copy.deepcopy(base)
    window_closed["context"]["exam_window_open"] = False
    window_result = resolve_exam(window_closed)["result"]
    check("RELEASE", "closed window withholds", window_result["release_state"] == "WITHHOLD")
    check("RELEASE", "closed window preserves paper", window_result["paper_id"] == result["paper_id"])

    common_center_false = copy.deepcopy(base)
    common_center_false["context"]["center_authorized"] = False
    common_center_result = resolve_exam(common_center_false)["result"]
    check("AUTHORITY", "common ignores center flag", common_center_result["state"] == STATE_RESOLVED)
    check("AUTHORITY", "common records center as non-applicable", "center_authorized" in common_center_result["evidence"].get("non_applicable_authority_fields", []))

    common_candidate_false = copy.deepcopy(base)
    common_candidate_false["context"]["candidate_valid"] = False
    check("AUTHORITY", "common ignores candidate flag", resolve_exam(common_candidate_false)["result"]["state"] == STATE_RESOLVED)

    center = copy.deepcopy(base)
    center["context"]["audience_scope"] = "CENTER"
    center["context"]["audience_id"] = "CENTER-001"
    center["context"]["center_authorized"] = False
    center_result = resolve_exam(center)["result"]
    check("AUTHORITY", "center requires center authority", center_result["state"] == STATE_FORBIDDEN)
    check("AUTHORITY", "center prohibition recorded", "center_authorized=false" in center_result["prohibitions"])

    center_candidate_false = copy.deepcopy(center)
    center_candidate_false["context"]["center_authorized"] = True
    center_candidate_false["context"]["candidate_valid"] = False
    check("AUTHORITY", "center ignores candidate flag", resolve_exam(center_candidate_false)["result"]["state"] == STATE_RESOLVED)

    candidate = copy.deepcopy(base)
    candidate["context"]["audience_scope"] = "CANDIDATE"
    candidate["context"]["audience_id"] = "CANDIDATE-001"
    candidate["context"]["candidate_valid"] = False
    candidate_result = resolve_exam(candidate)["result"]
    check("AUTHORITY", "candidate requires candidate validity", candidate_result["state"] == STATE_FORBIDDEN)

    bad_common_id = copy.deepcopy(base)
    bad_common_id["context"]["audience_id"] = "CENTER-001"
    check("AUTHORITY", "common audience identity mismatch", resolve_exam(bad_common_id)["result"]["state"] == STATE_CONFLICT)

    bad_center_id = copy.deepcopy(base)
    bad_center_id["context"]["audience_scope"] = "CENTER"
    bad_center_id["context"]["audience_id"] = "ALL"
    check("AUTHORITY", "bounded scope rejects ALL", resolve_exam(bad_center_id)["result"]["state"] == STATE_CONFLICT)

    single = build_commit_reveal_input()
    single_bundle = resolve_exam(single)
    single_result = single_bundle["result"]
    check("SINGLE_PARTY", "single-party resolves", single_result["state"] == STATE_RESOLVED)
    check("SINGLE_PARTY", "single-party posture", single_result["evidence"].get("selection_posture") == "SINGLE_PARTY_COMMIT_REVEAL")
    single_tamper = copy.deepcopy(single)
    single_tamper["context"]["audience_id"] = "OTHER"
    single_tamper["context"]["audience_scope"] = "CENTER"
    check("SINGLE_PARTY", "single-party context transplant rejected", resolve_exam(single_tamper)["result"]["state"] == STATE_CONFLICT)

    mpcr = build_mpcr_input()
    mpcr_bundle = resolve_exam(mpcr)
    mpcr_result = mpcr_bundle["result"]
    mpcr_evidence = mpcr_result["evidence"]
    check("MPCR", "MPCR resolves", mpcr_result["state"] == STATE_RESOLVED)
    check("MPCR", "MPCR posture declared", mpcr_evidence.get("selection_posture") == "CONDITIONAL_PRE_REVEAL_RESISTANCE")
    check("MPCR", "MPCR party count", mpcr_evidence.get("party_count") == 3)
    check("MPCR", "participant set identity", isinstance(mpcr_evidence.get("participant_set_id"), str))
    check("MPCR", "commitment manifest identity", isinstance(mpcr_evidence.get("commitment_manifest_id"), str))
    check("MPCR", "reveal manifest identity", isinstance(mpcr_evidence.get("reveal_manifest_id"), str))
    check("MPCR", "commitment aggregate identity", isinstance(mpcr_evidence.get("commitment_aggregate_id"), str))
    check("MPCR", "selector transcript identity", isinstance(mpcr_evidence.get("selector_transcript_id"), str))
    aggregate_digest = mpcr_evidence["commitment_aggregate_id"].split(":", 1)[1]
    commitment_manifest_digest = mpcr_evidence["commitment_manifest_id"].split(":", 1)[1]
    transcript_digest = mpcr_evidence["selector_transcript_id"].split(":", 1)[1]
    reveal_manifest_digest = mpcr_evidence["reveal_manifest_id"].split(":", 1)[1]
    check("MPCR", "commitment aggregate digest distinct", aggregate_digest != commitment_manifest_digest)
    check("MPCR", "transcript digest distinct from reveal", transcript_digest != reveal_manifest_digest)
    check("MPCR", "aggregate digest distinct from transcript", aggregate_digest != transcript_digest)

    mpcr_reordered = copy.deepcopy(mpcr)
    mpcr_reordered["selector"]["commitment_manifest"]["parties"].reverse()
    mpcr_reordered["selector"]["reveal_manifest"]["reveals"].reverse()
    mpcr_reordered_result = resolve_exam(mpcr_reordered)["result"]
    check("MPCR", "party order identity stable", mpcr_result["result_id"] == mpcr_reordered_result["result_id"])
    check("MPCR", "party order paper stable", mpcr_result["paper_id"] == mpcr_reordered_result["paper_id"])

    mpcr_upper = copy.deepcopy(mpcr)
    for party in mpcr_upper["selector"]["commitment_manifest"]["parties"]:
        party["commitment"] = party["commitment"].upper()
    for reveal in mpcr_upper["selector"]["reveal_manifest"]["reveals"]:
        reveal["salt"] = reveal["salt"].upper()
    check("MPCR", "hex case normalization stable", resolve_exam(mpcr_upper)["result"]["result_id"] == mpcr_result["result_id"])

    mpcr_withheld = copy.deepcopy(mpcr)
    mpcr_withheld["context"]["release_authorized"] = False
    mpcr_withheld_result = resolve_exam(mpcr_withheld)["result"]
    check("MPCR", "release change preserves MPCR context", mpcr_withheld_result["selection_context_id"] == mpcr_result["selection_context_id"])
    check("MPCR", "release change preserves MPCR paper", mpcr_withheld_result["paper_id"] == mpcr_result["paper_id"])

    def transplant(source: Dict[str, Any], mutator) -> Dict[str, Any]:
        value = copy.deepcopy(source)
        mutator(value)
        return value

    mpcr_audience = transplant(mpcr, lambda value: value["context"].update({"audience_scope": "CENTER", "audience_id": "CENTER-002"}))
    check("CONTEXT_BINDING", "audience transplant rejected", resolve_exam(mpcr_audience)["result"]["state"] == STATE_CONFLICT)

    mpcr_bank = transplant(mpcr, lambda value: value["question_bank"][0].update({"content_commitment": commitment("OTHER-CONTENT")}))
    check("CONTEXT_BINDING", "bank transplant rejected", resolve_exam(mpcr_bank)["result"]["state"] == STATE_CONFLICT)

    mpcr_blueprint = transplant(mpcr, lambda value: value["blueprint"]["forbidden_pairs"].append(["Q102", "Q202"]))
    check("CONTEXT_BINDING", "blueprint transplant rejected", resolve_exam(mpcr_blueprint)["result"]["state"] == STATE_CONFLICT)

    mpcr_variant = transplant(mpcr, lambda value: value["selector"].update({"variant_id": "OTHER-VARIANT"}))
    check("CONTEXT_BINDING", "variant transplant rejected", resolve_exam(mpcr_variant)["result"]["state"] == STATE_CONFLICT)

    mpcr_event = transplant(mpcr, lambda value: value["selector"].update({"selection_event_id": "OTHER-EVENT"}))
    check("CONTEXT_BINDING", "event transplant rejected", resolve_exam(mpcr_event)["result"]["state"] == STATE_CONFLICT)

    mpcr_roster = copy.deepcopy(mpcr)
    mpcr_roster["selector"]["commitment_manifest"]["parties"][0]["party_id"] = "AUTHORITY-X"
    mpcr_roster["selector"]["reveal_manifest"]["reveals"][0]["party_id"] = "AUTHORITY-X"
    check("CONTEXT_BINDING", "roster transplant rejected", resolve_exam(mpcr_roster)["result"]["state"] == STATE_CONFLICT)

    mpcr_missing = copy.deepcopy(mpcr)
    mpcr_missing["selector"]["reveal_manifest"]["reveals"].pop()
    mpcr_missing_bundle = resolve_exam(mpcr_missing)
    check("MPCR_STATES", "missing reveal incomplete", mpcr_missing_bundle["result"]["state"] == STATE_INCOMPLETE)

    mpcr_mismatch = copy.deepcopy(mpcr)
    mpcr_mismatch["selector"]["reveal_manifest"]["reveals"][0]["salt"] = commitment("MISMATCH")
    mpcr_mismatch_bundle = resolve_exam(mpcr_mismatch)
    check("MPCR_STATES", "commitment mismatch conflict", mpcr_mismatch_bundle["result"]["state"] == STATE_CONFLICT)

    mpcr_duplicate = copy.deepcopy(mpcr)
    mpcr_duplicate["selector"]["commitment_manifest"]["parties"].append(copy.deepcopy(mpcr_duplicate["selector"]["commitment_manifest"]["parties"][0]))
    check("MPCR_STATES", "duplicate party conflict", resolve_exam(mpcr_duplicate)["result"]["state"] == STATE_CONFLICT)

    insufficient = copy.deepcopy(base)
    for item in insufficient["question_bank"]:
        if item["topic"] == "GEOMETRY":
            item["approved"] = False
    insufficient_result = resolve_exam(insufficient)["result"]
    check("CAPACITY", "missing topic capacity incomplete", insufficient_result["state"] == STATE_INCOMPLETE)
    check("CAPACITY", "topic reason recorded", "MISSING_TOPIC_CAPACITY:GEOMETRY" in insufficient_result["reason_codes"])

    impossible_marks = copy.deepcopy(base)
    impossible_marks["blueprint"]["total_marks"] = 11
    impossible_result = resolve_exam(impossible_marks)["result"]
    check("CAPACITY", "unreachable marks incomplete", impossible_result["state"] == STATE_INCOMPLETE)
    check("CAPACITY", "marks prune recorded", impossible_result["search_evidence"].get("pruned_by_marks", 0) > 0)

    abstain = copy.deepcopy(base)
    abstain["selector"] = {"mode": "ABSTAIN_ON_MULTIPLE", "variant_id": "VARIANT-A"}
    abstain_result = resolve_exam(abstain)["result"]
    check("MULTIPLICITY", "multiple papers abstain", abstain_result["state"] == STATE_ABSTAIN)
    check("MULTIPLICITY", "multiple proved", abstain_result["evidence"].get("multiplicity_state") == "MULTIPLE_PROVED")

    unique = copy.deepcopy(base)
    selected_ids = {item["question_id"] for item in result["selected_questions"] or []}
    for item in unique["question_bank"]:
        item["approved"] = item["question_id"] in selected_ids
    unique["selector"] = {"mode": "ABSTAIN_ON_MULTIPLE", "variant_id": "UNIQUE-A"}
    unique_result = resolve_exam(unique)["result"]
    check("MULTIPLICITY", "unique paper resolves", unique_result["state"] == STATE_RESOLVED)
    check("MULTIPLICITY", "unique paper proved", unique_result["evidence"].get("multiplicity_state") == "UNIQUE_PROVED")

    normalized_base, base_issues = normalize_input(base)
    check("SEARCH", "base normalization succeeds", normalized_base is not None and not base_issues)
    assert normalized_base is not None
    base_bank_id = identity("slang_exam_bank_sha256:", normalized_base["question_bank"])
    base_blueprint_id = identity("slang_exam_blueprint_sha256:", normalized_base["blueprint"])
    base_participant_id = participant_set_id(normalized_base)
    base_context_id = selection_context_id(normalized_base, base_bank_id, base_blueprint_id, base_participant_id)
    base_selector_data = selector_material(normalized_base, base_context_id, base_participant_id)
    limited_solutions, limited_stats = find_solutions(normalized_base, base_selector_data, 2, 1)
    check("SEARCH", "node limit respected", limited_stats["search_nodes"] <= limited_stats["search_node_limit"])
    check("SEARCH", "small node budget exhausts", limited_stats["search_budget_exhausted"] is True)
    check("SEARCH", "small node budget has no forced conclusion", len(limited_solutions) <= 1)

    full_solutions, full_stats = find_solutions(normalized_base, base_selector_data, 2, MAX_SEARCH_NODES)
    check("SEARCH", "full search finds canonical paper", bool(full_solutions))
    check("SEARCH", "full search node limit respected", full_stats["search_nodes"] <= full_stats["search_node_limit"])
    check("SEARCH", "pruning counters present", all(key in full_stats for key in (
        "pruned_by_marks",
        "pruned_by_topic_capacity",
        "pruned_by_difficulty_capacity",
        "pruned_by_type_capacity",
        "pruned_by_exposure_capacity",
        "pruned_by_forbidden_pair_capacity",
    )))
    check("SEARCH", "marks memory bound declared", full_stats["marks_dp_memory_bound_bits"] > 0)

    adversarial_marks = build_adversarial_marks_input()
    adversarial_result = resolve_exam(adversarial_marks)["result"]
    check("MARKS_BOUND", "large question marks rejected", adversarial_result["state"] == STATE_UNSUPPORTED)
    check("MARKS_BOUND", "question marks reason present", "INVALID_QUESTION_MARKS" in adversarial_result["reason_codes"])
    check("MARKS_BOUND", "invalid marks skip search", not adversarial_result["search_evidence"])

    over_total_marks = copy.deepcopy(base)
    over_total_marks["blueprint"]["total_marks"] = MAX_TOTAL_MARKS + 1
    over_total_result = resolve_exam(over_total_marks)["result"]
    check("MARKS_BOUND", "total marks bound enforced", over_total_result["state"] == STATE_UNSUPPORTED)
    check("MARKS_BOUND", "total marks reason present", "INVALID_TOTAL_MARKS" in over_total_result["reason_codes"])

    maximum_question_marks = copy.deepcopy(base)
    maximum_question_marks["question_bank"][0]["marks"] = MAX_QUESTION_MARKS
    _, maximum_question_issues = normalize_input(maximum_question_marks)
    check("MARKS_BOUND", "maximum question marks admitted", not any(issue.code == "INVALID_QUESTION_MARKS" for issue in maximum_question_issues))

    bounded_marks = build_bounded_marks_input()
    normalized_bounded, bounded_issues = normalize_input(bounded_marks)
    check("MARKS_BOUND", "bounded marks admitted", normalized_bounded is not None and not bounded_issues)
    assert normalized_bounded is not None
    bounded_bank_id = identity("slang_exam_bank_sha256:", normalized_bounded["question_bank"])
    bounded_blueprint_id = identity("slang_exam_blueprint_sha256:", normalized_bounded["blueprint"])
    bounded_participant_id = participant_set_id(normalized_bounded)
    bounded_context_id = selection_context_id(normalized_bounded, bounded_bank_id, bounded_blueprint_id, bounded_participant_id)
    bounded_selector_data = selector_material(normalized_bounded, bounded_context_id, bounded_participant_id)
    _, bounded_stats = find_solutions(normalized_bounded, bounded_selector_data, 2, MAX_SEARCH_NODES)
    check("MARKS_BOUND", "bounded marks respect node limit", bounded_stats["search_nodes"] <= bounded_stats["search_node_limit"])
    check("MARKS_BOUND", "bounded marks memory is finite", bounded_stats["marks_dp_memory_bound_bits"] <= (MAX_QUESTION_BANK_SIZE + 1) * (MAX_TOTAL_QUESTIONS + 1) * (MAX_TOTAL_MARKS + 1))

    check("HASH_SYNTAX", "uppercase hexadecimal normalized", normalize_sha256("A" * 64) == "a" * 64)
    check("HASH_SYNTAX", "leading plus rejected", normalize_sha256("+" + "a" * 63) is None)
    check("HASH_SYNTAX", "underscore rejected", normalize_sha256("a" * 31 + "_" + "a" * 32) is None)
    check("HASH_SYNTAX", "leading whitespace rejected", normalize_sha256(" " + "a" * 63) is None)
    check("HASH_SYNTAX", "hexadecimal prefix rejected", normalize_sha256("0x" + "a" * 62) is None)
    check("HASH_SYNTAX", "non-hexadecimal character rejected", normalize_sha256("g" + "a" * 63) is None)

    at_depth_limit: Any = None
    for _ in range(MAX_JSON_DEPTH):
        at_depth_limit = [at_depth_limit]
    depth_limit_admitted = True
    try:
        validate_portable_json(at_depth_limit)
    except (TypeError, ValueError):
        depth_limit_admitted = False
    check("RESOURCE_BOUND", "maximum JSON depth admitted", depth_limit_admitted)

    above_depth_limit: Any = [at_depth_limit]
    depth_limit_rejected = False
    try:
        validate_portable_json(above_depth_limit)
    except ValueError:
        depth_limit_rejected = True
    check("RESOURCE_BOUND", "excessive JSON depth rejected", depth_limit_rejected)
    check("RESOURCE_BOUND", "oversized JSON text rejected", _strict_load_fails(" " * (MAX_JSON_INPUT_BYTES + 1)))

    synthetic_result_a = make_result(
        submission_id="submission",
        canonical_input_id="canonical",
        normalized_projection_id="projection",
        state=STATE_RESOLVED,
        assembly_state=STATE_RESOLVED,
        release_state="ALLOW",
        reason_codes=["PAPER_ASSEMBLED_AND_RELEASE_ADMITTED"],
        bank_id="bank",
        blueprint_id="blueprint",
        selection_context_id_value="context",
        paper_id="paper",
        evaluation_manifest_id="evaluation",
        selected_questions=[],
        paper_visible=True,
        evidence={"multiplicity_state": "MULTIPLE_PROVED"},
        search_evidence={"search_nodes": 10},
    )
    synthetic_result_b = make_result(
        submission_id="submission",
        canonical_input_id="canonical",
        normalized_projection_id="projection",
        state=STATE_RESOLVED,
        assembly_state=STATE_RESOLVED,
        release_state="ALLOW",
        reason_codes=["PAPER_ASSEMBLED_AND_RELEASE_ADMITTED"],
        bank_id="bank",
        blueprint_id="blueprint",
        selection_context_id_value="context",
        paper_id="paper",
        evaluation_manifest_id="evaluation",
        selected_questions=[],
        paper_visible=True,
        evidence={"multiplicity_state": "NOT_ESTABLISHED"},
        search_evidence={"search_nodes": 20},
    )
    check("IDENTITY", "search metrics do not change result identity", synthetic_result_a["result_id"] == synthetic_result_b["result_id"])
    check("IDENTITY", "multiplicity evidence does not change result identity", synthetic_result_a["result_id"] == synthetic_result_b["result_id"])
    check("IDENTITY", "search metrics change search identity", synthetic_result_a["search_evidence_id"] != synthetic_result_b["search_evidence_id"])

    variant = copy.deepcopy(base)
    variant["selector"]["variant_id"] = "VARIANT-B"
    variant_result = resolve_exam(variant)["result"]
    check("IDENTITY", "variant changes selection context", result["selection_context_id"] != variant_result["selection_context_id"])
    check("IDENTITY", "variant changes paper identity", result["paper_id"] != variant_result["paper_id"])

    duplicate = copy.deepcopy(base)
    duplicate["question_bank"].append(copy.deepcopy(duplicate["question_bank"][0]))
    conflict_bundle = resolve_exam(duplicate)
    check("VALIDATION", "duplicate question conflict", conflict_bundle["result"]["state"] == STATE_CONFLICT)

    inject_state = copy.deepcopy(base)
    inject_state["state"] = STATE_RESOLVED
    injection_bundle = resolve_exam(inject_state)
    check("VALIDATION", "derived field injection forbidden", injection_bundle["result"]["state"] == STATE_FORBIDDEN)

    unknown_top = copy.deepcopy(base)
    unknown_top["unexpected"] = 1
    check("VALIDATION", "unknown top field unsupported", resolve_exam(unknown_top)["result"]["state"] == STATE_UNSUPPORTED)

    unsupported_schema = copy.deepcopy(base)
    unsupported_schema["schema"] = "OTHER"
    unsupported_bundle = resolve_exam(unsupported_schema)
    check("VALIDATION", "unsupported schema", unsupported_bundle["result"]["state"] == STATE_UNSUPPORTED)

    incomplete = copy.deepcopy(base)
    del incomplete["selector"]
    incomplete_bundle = resolve_exam(incomplete)
    check("VALIDATION", "missing selector incomplete", incomplete_bundle["result"]["state"] == STATE_INCOMPLETE)

    check("PORTABILITY", "duplicate JSON key rejected", _strict_load_fails('{"a":1,"a":2}'))
    check("PORTABILITY", "non-finite JSON rejected", _strict_load_fails('{"a":NaN}'))
    check("PORTABILITY", "float JSON rejected", _strict_load_fails('{"a":0.1}'))
    check("PORTABILITY", "unsafe integer JSON rejected", _strict_load_fails('{"a":9007199254740992}'))
    try:
        resolve_exam({"unexpected": 0.1})
        direct_float_rejected = False
    except TypeError:
        direct_float_rejected = True
    check("PORTABILITY", "direct float rejected", direct_float_rejected)
    try:
        resolve_exam({"unexpected": MAX_SAFE_INTEGER + 1})
        direct_unsafe_rejected = False
    except TypeError:
        direct_unsafe_rejected = True
    check("PORTABILITY", "direct unsafe integer rejected", direct_unsafe_rejected)
    try:
        resolve_exam({"unexpected": "\ud800"})
        lone_surrogate_rejected = False
    except TypeError:
        lone_surrogate_rejected = True
    check("PORTABILITY", "lone surrogate rejected", lone_surrogate_rejected)

    mpcr_receipt = make_receipt(mpcr_bundle)
    check("RECEIPT", "reference receipt verifies", verify_receipt(receipt) == (True, "PASS"))
    check("RECEIPT", "reference receipt binds bundle", verify_receipt_against_bundle(receipt, resolved) == (True, "PASS"))
    check("RECEIPT", "MPCR receipt verifies", verify_receipt(mpcr_receipt) == (True, "PASS"))
    check("RECEIPT", "MPCR receipt carries aggregate", mpcr_receipt["commitment_aggregate_id"] == mpcr_evidence["commitment_aggregate_id"])
    check("RECEIPT", "MPCR receipt carries transcript", mpcr_receipt["selector_transcript_id"] == mpcr_evidence["selector_transcript_id"])

    check("BUNDLE", "resolved bundle verifies", verify_bundle(resolved) == (True, "PASS"))
    check("BUNDLE", "incomplete bundle verifies", verify_bundle(incomplete_bundle) == (True, "PASS"))
    check("BUNDLE", "conflict bundle verifies", verify_bundle(conflict_bundle) == (True, "PASS"))
    check("BUNDLE", "unsupported bundle verifies", verify_bundle(unsupported_bundle) == (True, "PASS"))
    check("BUNDLE", "MPCR bundle verifies", verify_bundle(mpcr_bundle) == (True, "PASS"))
    check("BUNDLE", "MPCR incomplete bundle verifies", verify_bundle(mpcr_missing_bundle) == (True, "PASS"))
    check("BUNDLE", "MPCR conflict bundle verifies", verify_bundle(mpcr_mismatch_bundle) == (True, "PASS"))

    tampered_result = copy.deepcopy(resolved)
    tampered_result["result"]["result_id"] = "tampered"
    check("TAMPER", "result identity tamper fails", verify_bundle(tampered_result)[0] is False)

    tampered_search = copy.deepcopy(resolved)
    tampered_search["result"]["search_evidence"]["search_nodes"] += 1
    check("TAMPER", "search evidence tamper fails", verify_bundle(tampered_search)[0] is False)

    tampered_receipt = copy.deepcopy(mpcr_receipt)
    tampered_receipt["selector_transcript_id"] = "tampered"
    check("TAMPER", "receipt transcript tamper fails", verify_receipt(tampered_receipt)[0] is False)

    extended_receipt = copy.deepcopy(receipt)
    extended_receipt["extra"] = "value"
    material = dict(extended_receipt)
    material.pop("receipt_id")
    extended_receipt["receipt_id"] = identity("slang_exam_receipt_sha256:", material)
    check("TAMPER", "receipt extra field rejected", verify_receipt(extended_receipt)[0] is False)

    other_bundle = resolve_exam(variant)
    check("TAMPER", "receipt wrong bundle fails", verify_receipt_against_bundle(receipt, other_bundle)[0] is False)

    total_pass = 0
    total_fail = 0
    print("SLANG-Exam v" + VERSION + " Self-Test")
    print("=" * 72)
    for group in sorted(groups):
        passed = sum(1 for _, ok in groups[group] if ok)
        failed = len(groups[group]) - passed
        total_pass += passed
        total_fail += failed
        print("{:<20} {:>3}/{:<3} PASS".format(group, passed, len(groups[group])))
        if failed:
            for name, ok in groups[group]:
                if not ok:
                    print("  FAIL: " + name)
    print("-" * 72)
    print("TOTAL                {}/{} PASS".format(total_pass, total_pass + total_fail))
    return 0 if total_fail == 0 else 1

def _strict_load_fails(text: str) -> bool:
    try:
        loads_strict(text)
    except (DuplicateKeyError, TypeError, ValueError, json.JSONDecodeError):
        return True
    return False


def build_search_budget_input() -> Dict[str, Any]:
    source = {
        "schema": INPUT_SCHEMA,
        "profile_id": PROFILE_ID,
        "ruleset_id": RULESET_ID,
        "context": {
            "exam_id": "EXAM-BUDGET-001",
            "session_id": "SESSION-BUDGET-A",
            "audience_scope": "COMMON",
            "audience_id": "ALL",
            "assembly_authorized": True,
            "release_authorized": True,
            "exam_window_open": True,
            "center_authorized": True,
            "candidate_valid": True,
        },
        "blueprint": {
            "total_questions": 12,
            "total_marks": 12,
            "topic_registry_id": "BUDGET-TOPICS-1",
            "allowed_topics": ["GENERAL"],
            "topic_counts": {"GENERAL": 12},
            "difficulty_counts": {"MEDIUM": 12},
            "type_counts": {"MCQ": 12},
            "max_per_exposure_group": 11,
            "forbidden_pairs": [],
        },
        "selector": {
            "mode": "CANONICAL_RANK",
            "variant_id": "BUDGET-A",
        },
        "question_bank": [],
    }
    for index in range(40):
        source["question_bank"].append(
            question(
                "QB{:02d}".format(index),
                "GENERAL",
                "MEDIUM",
                1,
                "MCQ",
                "ONE-GROUP",
            )
        )
    return source


def build_adversarial_marks_input() -> Dict[str, Any]:
    """Build an input that exceeds the declared per-question marks bound."""
    source = build_search_budget_input()
    source["blueprint"]["total_marks"] = MAX_TOTAL_MARKS
    source["question_bank"] = []
    for index in range(MAX_QUESTION_BANK_SIZE):
        source["question_bank"].append(
            question(
                "QA{:02d}".format(index),
                "GENERAL",
                "MEDIUM",
                1 << index,
                "MCQ",
                "ONE-GROUP",
            )
        )
    return source


def build_bounded_marks_input() -> Dict[str, Any]:
    """Build a full bank whose marks remain within the declared profile."""
    source = build_search_budget_input()
    source["blueprint"]["total_marks"] = MAX_TOTAL_MARKS
    source["question_bank"] = []
    for index in range(MAX_QUESTION_BANK_SIZE):
        marks = 1 + (index * 5) % MAX_QUESTION_MARKS
        source["question_bank"].append(
            question(
                "QC{:02d}".format(index),
                "GENERAL",
                "MEDIUM",
                marks,
                "MCQ",
                "ONE-GROUP",
            )
        )
    return source


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="SLANG-Exam bounded structural admissibility reference demo."
    )
    parser.add_argument("--input", type=Path, help="Resolve a JSON input file.")
    parser.add_argument("--self-test", "--audit", action="store_true", help="Run the permanent self-test.")
    parser.add_argument("--bundle", action="store_true", help="Print the complete reconstruction bundle.")
    parser.add_argument("--receipt", action="store_true", help="Print the compact receipt.")
    parser.add_argument("--write-bundle", type=Path, help="Write the complete reconstruction bundle.")
    parser.add_argument("--write-receipt", type=Path, help="Write the compact receipt.")
    parser.add_argument("--verify-bundle", type=Path, help="Verify and reconstruct a saved bundle.")
    parser.add_argument("--verify-receipt", type=Path, help="Verify a saved receipt identity.")
    parser.add_argument(
        "--verify-receipt-against-bundle",
        nargs=2,
        metavar=("RECEIPT", "BUNDLE"),
        help="Verify a receipt and its binding to a reconstruction bundle.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)

    if args.self_test:
        return run_self_test()

    if args.verify_bundle is not None:
        try:
            bundle = load_json(args.verify_bundle)
        except (OSError, UnicodeError, DuplicateKeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            print("VERIFY: FAIL")
            print("Reason: " + str(exc))
            return 1
        ok, reason = verify_bundle(bundle)
        print("VERIFY: " + ("PASS" if ok else "FAIL"))
        print("Reason: " + reason)
        return 0 if ok else 1

    if args.verify_receipt is not None:
        try:
            receipt = load_json(args.verify_receipt)
        except (OSError, UnicodeError, DuplicateKeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            print("VERIFY: FAIL")
            print("Reason: " + str(exc))
            return 1
        ok, reason = verify_receipt(receipt)
        print("VERIFY: " + ("PASS" if ok else "FAIL"))
        print("Reason: " + reason)
        return 0 if ok else 1

    if args.verify_receipt_against_bundle is not None:
        receipt_path = Path(args.verify_receipt_against_bundle[0])
        bundle_path = Path(args.verify_receipt_against_bundle[1])
        try:
            receipt = load_json(receipt_path)
            bundle = load_json(bundle_path)
        except (OSError, UnicodeError, DuplicateKeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            print("VERIFY: FAIL")
            print("Reason: " + str(exc))
            return 1
        ok, reason = verify_receipt_against_bundle(receipt, bundle)
        print("VERIFY: " + ("PASS" if ok else "FAIL"))
        print("Reason: " + reason)
        return 0 if ok else 1

    if args.input is not None:
        try:
            source = load_json(args.input)
        except (OSError, UnicodeError, DuplicateKeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            print("INPUT: FAIL")
            print("Reason: " + str(exc))
            return 1
    else:
        source = build_reference_input()

    try:
        bundle = resolve_exam(source)
    except (TypeError, ValueError) as exc:
        print("INPUT: FAIL")
        print("Reason: " + str(exc))
        return 1
    except (MemoryError, RecursionError):
        print("INPUT: FAIL")
        print("Reason: RESOURCE_LIMIT_EXCEEDED")
        return 1

    receipt = make_receipt(bundle)

    if args.write_bundle is not None:
        try:
            write_json(args.write_bundle, bundle)
        except OSError as exc:
            print("WRITE: FAIL")
            print("Reason: " + str(exc))
            return 1
        print("WROTE: " + str(args.write_bundle))

    if args.write_receipt is not None:
        try:
            write_json(args.write_receipt, receipt)
        except OSError as exc:
            print("WRITE: FAIL")
            print("Reason: " + str(exc))
            return 1
        print("WROTE: " + str(args.write_receipt))

    if args.bundle:
        output = bundle
    elif args.receipt:
        output = receipt
    else:
        output = public_summary(bundle)
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())