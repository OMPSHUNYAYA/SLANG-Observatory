import argparse
import copy
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

INPUT_SCHEMA = "SLANG-ANNUITY-INPUT-1"
PROFILE_ID = "SLANG-ANNUITY-PROFILE-1-D01"
RULESET_ID = "SLANG-ANNUITY-RULESET-1-D01"
AUTHORITY_PROFILE_ID = "ANNUITY-PAYOUT-AUTHORITY-EVIDENCE-1"
EVIDENCE_COMMITMENT_PREFIX = "slang_annuity_evidence_sha256:"
CONTEXT_ID_PREFIX = "slang_annuity_context_sha256:"
EVIDENCE_SET_ID_PREFIX = "slang_annuity_evidence_set_sha256:"
PAYOUT_MODE = "ANNUITANT_PERIODIC"
EVIDENCE_SINGLE = "SINGLE_AUTHORITY"
EVIDENCE_MULTI = "MULTI_AUTHORITY_EXACT_AGREEMENT"
EVIDENCE_MATERIAL_KEYS = [
    "attained_age_years",
    "authority_id",
    "case_id",
    "contract_reference",
    "contract_status",
    "credited_service_years",
    "currency",
    "declared_periodic_payout_minor",
    "minimum_contribution_minor",
    "minimum_start_age_years",
    "minimum_vesting_years",
    "payee_status",
    "payout_election",
    "schema",
    "total_contributed_minor",
]


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha256_hex(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def evidence_commitment(record: Dict[str, Any]) -> str:
    material = {key: record[key] for key in EVIDENCE_MATERIAL_KEYS if key in record}
    return EVIDENCE_COMMITMENT_PREFIX + sha256_hex(material)


def context_id(context: Dict[str, Any]) -> str:
    return CONTEXT_ID_PREFIX + sha256_hex(context)


def evidence_set_id(records: List[Dict[str, Any]]) -> str:
    material = {"authority_profile_id": AUTHORITY_PROFILE_ID, "records": sorted(copy.deepcopy(records), key=lambda item: item["authority_id"])}
    return EVIDENCE_SET_ID_PREFIX + sha256_hex(material)


def make_record(authority_id: str, overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
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
    record["evidence_commitment"] = evidence_commitment(record)
    return record


def make_context(authority_ids: List[str], multi: bool, visible: bool, authorized: bool) -> Dict[str, Any]:
    return {
        "case_id": "ANNUITY-DEMO-001",
        "contract_reference": "CONTRACT-DEMO-001",
        "currency": "USD",
        "payout_mode": PAYOUT_MODE,
        "evidence_mode": EVIDENCE_MULTI if multi else EVIDENCE_SINGLE,
        "evaluation_authorized": authorized,
        "visibility_authorized": visible,
        "expected_authority_ids": list(authority_ids),
    }


def make_input(records: List[Dict[str, Any]], context: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "schema": INPUT_SCHEMA,
        "profile_id": PROFILE_ID,
        "ruleset_id": RULESET_ID,
        "context": context,
        "annuity_evidence": records,
    }


def make_bound_input(records: List[Dict[str, Any]], context: Dict[str, Any]) -> Dict[str, Any]:
    value = make_input(records, context)
    value["declared_context_id"] = context_id(context)
    value["declared_evidence_set_id"] = evidence_set_id(records)
    return value


def single_payable() -> Dict[str, Any]:
    return make_input([make_record("AUTHORITY-A")], make_context(["AUTHORITY-A"], False, True, True))


def single_override(overrides: Dict[str, Any]) -> Dict[str, Any]:
    return make_input([make_record("AUTHORITY-A", overrides)], make_context(["AUTHORITY-A"], False, True, True))


def multi_payable() -> Dict[str, Any]:
    authority_ids = ["AUTHORITY-A", "AUTHORITY-B"]
    return make_input([make_record(authority_id) for authority_id in authority_ids], make_context(authority_ids, True, True, True))


def predict_resolved(record: Dict[str, Any]) -> Tuple[str, int, Set[str]]:
    failures: List[str] = []
    if record["contract_status"] != "ACTIVE":
        failures.append("CONTRACT_NOT_ACTIVE")
    if record["attained_age_years"] < record["minimum_start_age_years"]:
        failures.append("AGE_CONDITION_NOT_SATISFIED")
    if record["credited_service_years"] < record["minimum_vesting_years"]:
        failures.append("VESTING_CONDITION_NOT_SATISFIED")
    if record["total_contributed_minor"] < record["minimum_contribution_minor"]:
        failures.append("CONTRIBUTION_CONDITION_NOT_SATISFIED")
    if record["payout_election"] != "ELECTED":
        failures.append("PAYOUT_NOT_ELECTED")
    if record["payee_status"] != "VALID":
        failures.append("PAYEE_NOT_VALID")
    if record["declared_periodic_payout_minor"] <= 0:
        failures.append("DECLARED_PERIODIC_PAYOUT_NOT_POSITIVE")
    if failures:
        return "NOT_PAYABLE", 0, set(failures)
    return "PAYABLE", record["declared_periodic_payout_minor"], {"PAYOUT_ADMITTED"}


def run_core_resolve(core_path: Path, raw_input: Dict[str, Any]) -> Dict[str, Any]:
    temp_path: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
            json.dump(raw_input, handle, ensure_ascii=False)
            temp_path = Path(handle.name)
        completed = subprocess.run(
            [sys.executable, "-B", str(core_path), "--resolve", str(temp_path)],
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise RuntimeError("core --resolve exit {}: {}".format(completed.returncode, completed.stderr.strip()))
        return json.loads(completed.stdout)
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink()
            except FileNotFoundError:
                pass


def run_core_transform(core_path: Path, flag: str, raw_input: Dict[str, Any]) -> Tuple[int, str, str, Optional[Dict[str, Any]]]:
    input_path: Optional[Path] = None
    output_path: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
            json.dump(raw_input, handle, ensure_ascii=False)
            input_path = Path(handle.name)
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
            output_path = Path(handle.name)
        completed = subprocess.run(
            [sys.executable, "-B", str(core_path), flag, str(input_path), "--output", str(output_path)],
            capture_output=True,
            text=True,
        )
        value = None
        if completed.returncode == 0:
            value = json.loads(output_path.read_text(encoding="utf-8"))
        return completed.returncode, completed.stdout, completed.stderr, value
    finally:
        for path in [input_path, output_path]:
            if path is not None:
                try:
                    path.unlink()
                except FileNotFoundError:
                    pass


def run_core_library_case(core_path: Path, expression: str) -> Dict[str, Any]:
    code = (
        "import importlib.util,json;"
        "p=r'" + str(core_path.resolve()).replace("\\", "\\\\") + "';"
        "s=importlib.util.spec_from_file_location('annuity_core',p);"
        "m=importlib.util.module_from_spec(s);s.loader.exec_module(m);"
        "v=" + expression + ";"
        "print(json.dumps(m.resolve_annuity(v),sort_keys=True))"
    )
    completed = subprocess.run([sys.executable, "-B", "-c", code], capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError("library harness exit {}: {}".format(completed.returncode, completed.stderr.strip()))
    return json.loads(completed.stdout)


class Case:
    def __init__(
        self,
        name: str,
        raw: Dict[str, Any],
        state: str,
        outcome: str,
        amount: int,
        reasons_exact: Optional[Set[str]] = None,
        governing_reason: Optional[str] = None,
    ) -> None:
        self.name = name
        self.raw = raw
        self.state = state
        self.outcome = outcome
        self.amount = amount
        self.reasons_exact = reasons_exact
        self.governing_reason = governing_reason


def build_cases() -> List[Case]:
    cases: List[Case] = []
    base_record = make_record("AUTHORITY-A")
    outcome, amount, reasons = predict_resolved(base_record)
    cases.append(Case("reference_payable", single_payable(), "RESOLVED", outcome, amount, reasons_exact=reasons))
    resolved_overrides = [
        ("inactive_contract", {"contract_status": "INACTIVE"}),
        ("suspended_contract", {"contract_status": "SUSPENDED"}),
        ("terminated_contract", {"contract_status": "TERMINATED"}),
        ("below_age", {"attained_age_years": 60}),
        ("age_exact_boundary", {"attained_age_years": 65}),
        ("insufficient_vesting", {"credited_service_years": 9}),
        ("vesting_exact_boundary", {"credited_service_years": 10}),
        ("insufficient_contribution", {"total_contributed_minor": 14999999}),
        ("contribution_exact_boundary", {"total_contributed_minor": 15000000}),
        ("not_elected", {"payout_election": "NOT_ELECTED"}),
        ("payee_invalid", {"payee_status": "NOT_VALID"}),
        ("zero_amount", {"declared_periodic_payout_minor": 0}),
        ("small_positive_amount", {"declared_periodic_payout_minor": 1}),
        ("large_amount_passthrough", {"declared_periodic_payout_minor": 9007199254740991}),
        ("multi_condition_failure", {"contract_status": "INACTIVE", "attained_age_years": 60, "payout_election": "NOT_ELECTED"}),
    ]
    for name, overrides in resolved_overrides:
        record = make_record("AUTHORITY-A", overrides)
        outcome, amount, reasons = predict_resolved(record)
        cases.append(Case(name, single_override(overrides), "RESOLVED", outcome, amount, reasons_exact=reasons))
    unauthorized = make_input([make_record("AUTHORITY-A")], make_context(["AUTHORITY-A"], False, True, False))
    cases.append(Case("evaluation_not_authorized", unauthorized, "ABSTAIN", "NONE", 0, governing_reason="EVALUATION_NOT_AUTHORIZED"))
    missing = single_payable()
    missing["annuity_evidence"][0].pop("attained_age_years")
    cases.append(Case("missing_required_field", missing, "INCOMPLETE", "NONE", 0, governing_reason="MISSING_REQUIRED_FIELD"))
    forbidden = single_payable()
    forbidden["payout_amount_minor"] = 999999999
    cases.append(Case("forbidden_derived_injection", forbidden, "FORBIDDEN", "NONE", 0, governing_reason="FORBIDDEN_DERIVED_FIELD"))
    unknown = single_payable()
    unknown["context"]["unversioned_extension"] = True
    cases.append(Case("unknown_context_field", unknown, "UNSUPPORTED", "NONE", 0, governing_reason="UNKNOWN_FIELD"))
    commitment = single_payable()
    commitment["annuity_evidence"][0]["evidence_commitment"] = EVIDENCE_COMMITMENT_PREFIX + "0" * 64
    cases.append(Case("commitment_mismatch", commitment, "CONFLICT", "NONE", 0, governing_reason="EVIDENCE_COMMITMENT_MISMATCH"))
    binding_record = make_record("AUTHORITY-A", {"case_id": "ANNUITY-OTHER"})
    binding = make_input([binding_record], make_context(["AUTHORITY-A"], False, True, True))
    cases.append(Case("context_binding_mismatch", binding, "CONFLICT", "NONE", 0, governing_reason="CONTEXT_BINDING_MISMATCH"))
    declared_bad = single_payable()
    declared_bad["declared_context_id"] = CONTEXT_ID_PREFIX + "0" * 64
    cases.append(Case("declared_context_id_mismatch", declared_bad, "CONFLICT", "NONE", 0, governing_reason="DECLARED_CONTEXT_ID_MISMATCH"))
    declared_ok = single_payable()
    declared_ok["declared_context_id"] = context_id(declared_ok["context"])
    cases.append(Case("declared_context_id_match", declared_ok, "RESOLVED", "PAYABLE", 1250000, reasons_exact={"PAYOUT_ADMITTED"}))
    cases.append(Case("multi_authority_payable", multi_payable(), "RESOLVED", "PAYABLE", 1250000, reasons_exact={"PAYOUT_ADMITTED"}))
    disagreement = multi_payable()
    disagreement["annuity_evidence"][1] = make_record("AUTHORITY-B", {"declared_periodic_payout_minor": 1300000})
    cases.append(Case("multi_authority_disagreement", disagreement, "ABSTAIN", "NONE", 0, governing_reason="EVIDENCE_RESULT_DISAGREEMENT"))
    return cases


def verify_case(core_path: Path, case: Case) -> List[str]:
    result = run_core_resolve(core_path, case.raw)
    problems: List[str] = []
    if result.get("state") != case.state:
        problems.append("state expected {} got {}".format(case.state, result.get("state")))
    if result.get("annuity_outcome") != case.outcome:
        problems.append("outcome expected {} got {}".format(case.outcome, result.get("annuity_outcome")))
    if result.get("payout_amount_minor") != case.amount:
        problems.append("amount expected {} got {}".format(case.amount, result.get("payout_amount_minor")))
    observed = set(result.get("reason_codes", []))
    if case.reasons_exact is not None and observed != case.reasons_exact:
        problems.append("reason_codes expected exactly {} got {}".format(sorted(case.reasons_exact), sorted(observed)))
    if case.governing_reason is not None and case.governing_reason not in observed:
        problems.append("governing reason {} absent from {}".format(case.governing_reason, sorted(observed)))
    return problems


def check_order_independence(core_path: Path) -> List[str]:
    forward = multi_payable()
    reverse = copy.deepcopy(forward)
    reverse["annuity_evidence"].reverse()
    result_forward = run_core_resolve(core_path, forward)
    result_reverse = run_core_resolve(core_path, reverse)
    if result_forward == result_reverse:
        return []
    differing = sorted(key for key in set(result_forward) | set(result_reverse) if result_forward.get(key) != result_reverse.get(key))
    return ["evidence order changed result on keys: {}".format(differing)]


def check_determinism(core_path: Path, runs: int = 5) -> List[str]:
    reference = run_core_resolve(core_path, single_payable())
    for _ in range(runs - 1):
        if run_core_resolve(core_path, single_payable()) != reference:
            return ["non-deterministic result across repeated resolves"]
    return []


def check_reason_code_union_policy(core_path: Path) -> List[str]:
    problems: List[str] = []
    forbidden = single_payable()
    forbidden["payout_amount_minor"] = 999999999
    forbidden_result = run_core_resolve(core_path, forbidden)
    forbidden_expected = {"FORBIDDEN_DERIVED_FIELD", "UNKNOWN_FIELD"}
    if set(forbidden_result.get("reason_codes", [])) != forbidden_expected:
        problems.append("forbidden reason union expected {} got {}".format(sorted(forbidden_expected), sorted(forbidden_result.get("reason_codes", []))))
    unexpected = single_payable()
    unexpected["annuity_evidence"][0] = make_record("AUTHORITY-B")
    unexpected_result = run_core_resolve(core_path, unexpected)
    unexpected_expected = {"MISSING_EXPECTED_AUTHORITY", "UNEXPECTED_AUTHORITY"}
    if unexpected_result.get("state") != "CONFLICT":
        problems.append("unexpected authority state expected CONFLICT got {}".format(unexpected_result.get("state")))
    if set(unexpected_result.get("reason_codes", [])) != unexpected_expected:
        problems.append("unexpected authority reason union expected {} got {}".format(sorted(unexpected_expected), sorted(unexpected_result.get("reason_codes", []))))
    return problems


def check_evaluation_authorization_scope(core_path: Path) -> List[str]:
    raw = single_payable()
    raw["context"]["evaluation_authorized"] = False
    raw["annuity_evidence"][0].pop("attained_age_years")
    result = run_core_resolve(core_path, raw)
    problems: List[str] = []
    expected_reasons = {
        "EVALUATION_NOT_AUTHORIZED",
        "MISSING_EXPECTED_AUTHORITY",
        "MISSING_REQUIRED_FIELD",
        "SINGLE_AUTHORITY_REQUIRES_ONE_EVIDENCE_RECORD",
    }
    if result.get("state") != "INCOMPLETE":
        problems.append("unauthorized incomplete state expected INCOMPLETE got {}".format(result.get("state")))
    if set(result.get("reason_codes", [])) != expected_reasons:
        problems.append("unauthorized incomplete reasons expected {} got {}".format(sorted(expected_reasons), sorted(result.get("reason_codes", []))))
    diagnostics = set(result.get("diagnostics", []))
    if "$.context.evaluation_authorized:EVALUATION_NOT_AUTHORIZED" not in diagnostics:
        problems.append("evaluation authorization diagnostic missing")
    if "$.annuity_evidence[0].attained_age_years:MISSING_REQUIRED_FIELD" not in diagnostics:
        problems.append("structural diagnostic missing")
    return problems


def check_stamp_declared_ids(core_path: Path) -> List[str]:
    records = [make_record("AUTHORITY-A")]
    context = make_context(["AUTHORITY-A"], False, True, True)
    edited = make_bound_input(records, context)
    edited["annuity_evidence"][0]["attained_age_years"] = 60
    edited["annuity_evidence"][0]["evidence_commitment"] = evidence_commitment(edited["annuity_evidence"][0])
    before = run_core_resolve(core_path, edited)
    problems: List[str] = []
    if before.get("state") != "CONFLICT" or "DECLARED_EVIDENCE_SET_ID_MISMATCH" not in before.get("reason_codes", []):
        problems.append("pre-stamp edited input did not expose stale evidence-set identity")
    rc, out, err, stamped = run_core_transform(core_path, "--stamp-declared-ids", edited)
    if rc != 0 or stamped is None:
        problems.append("stamp command failed: {}".format(err.strip()))
        return problems
    after = run_core_resolve(core_path, stamped)
    if after.get("state") != "RESOLVED" or after.get("annuity_outcome") != "NOT_PAYABLE" or "AGE_CONDITION_NOT_SATISFIED" not in after.get("reason_codes", []):
        problems.append("stamped edited input did not resolve to expected NOT_PAYABLE state")
    broken = copy.deepcopy(edited)
    broken["annuity_evidence"][0]["evidence_commitment"] = EVIDENCE_COMMITMENT_PREFIX + "0" * 64
    rc, out, err, stamped = run_core_transform(core_path, "--stamp-declared-ids", broken)
    if rc != 2 or "EVIDENCE_COMMITMENT_MISMATCH" not in err:
        problems.append("stamp did not refuse broken evidence commitment")
    return problems


def check_refresh_bindings(core_path: Path) -> List[str]:
    records = [make_record("AUTHORITY-A")]
    context = make_context(["AUTHORITY-A"], False, True, True)
    edited = make_bound_input(records, context)
    edited["annuity_evidence"][0]["attained_age_years"] = 60
    rc, out, err, refreshed = run_core_transform(core_path, "--refresh-bindings", edited)
    if rc != 0 or refreshed is None:
        return ["refresh-bindings command failed: {}".format(err.strip())]
    after = run_core_resolve(core_path, refreshed)
    if after.get("state") != "RESOLVED" or after.get("annuity_outcome") != "NOT_PAYABLE" or "AGE_CONDITION_NOT_SATISFIED" not in after.get("reason_codes", []):
        return ["refresh-bindings result mismatch"]
    return []


def check_library_reason_precision(core_path: Path) -> List[str]:
    problems: List[str] = []
    float_result = run_core_library_case(core_path, "{'schema':'SLANG-ANNUITY-INPUT-1','profile_id':'SLANG-ANNUITY-PROFILE-1-D01','ruleset_id':'SLANG-ANNUITY-RULESET-1-D01','context':{},'annuity_evidence':[],'x':1.25}")
    if float_result.get("state") != "UNSUPPORTED" or "FLOAT_NOT_SUPPORTED" not in float_result.get("reason_codes", []):
        problems.append("library float classification mismatch")
    key_result = run_core_library_case(core_path, "{1:'x'}")
    if key_result.get("state") != "UNSUPPORTED" or "NON_STRING_KEY" not in key_result.get("reason_codes", []):
        problems.append("library non-string-key classification mismatch")
    type_result = run_core_library_case(core_path, "{'x':set([1])}")
    if type_result.get("state") != "UNSUPPORTED" or "UNSUPPORTED_JSON_TYPE" not in type_result.get("reason_codes", []):
        problems.append("library unsupported-type classification mismatch")
    return problems


def check_dependency_aware_identity(core_path: Path) -> List[str]:
    records = [make_record("AUTHORITY-A")]
    context = make_context(["AUTHORITY-A"], False, True, True)
    malformed = make_bound_input(records, context)
    malformed["annuity_evidence"][0]["attained_age_years"] = -1
    result = run_core_resolve(core_path, malformed)
    problems: List[str] = []
    if result.get("state") != "UNSUPPORTED":
        problems.append("malformed evidence primary state expected UNSUPPORTED got {}".format(result.get("state")))
    if "INVALID_NONNEGATIVE_INTEGER" not in result.get("reason_codes", []):
        problems.append("causal invalid-integer reason missing")
    if "DECLARED_EVIDENCE_SET_ID_MISMATCH" in result.get("reason_codes", []):
        problems.append("consequential evidence-set mismatch was not suppressed")
    genuine = make_bound_input([make_record("AUTHORITY-A")], make_context(["AUTHORITY-A"], False, True, True))
    genuine["declared_evidence_set_id"] = EVIDENCE_SET_ID_PREFIX + "0" * 64
    genuine_result = run_core_resolve(core_path, genuine)
    if genuine_result.get("state") != "CONFLICT" or "DECLARED_EVIDENCE_SET_ID_MISMATCH" not in genuine_result.get("reason_codes", []):
        problems.append("genuine evidence-set identity mismatch no longer conflicts")
    return problems


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Independent semantic verifier for SLANG-Annuity v1.1.1")
    parser.add_argument("--core", required=True, metavar="PATH")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    core_path = Path(args.core)
    if not core_path.is_file():
        print("ERROR: core not found: {}".format(core_path), file=sys.stderr)
        return 2
    total = 0
    passed = 0
    failures: List[str] = []
    try:
        for case in build_cases():
            total += 1
            problems = verify_case(core_path, case)
            if problems:
                failures.append("{}: {}".format(case.name, "; ".join(problems)))
                if not args.quiet:
                    print("FAIL {:32s} {}".format(case.name, "; ".join(problems)))
            else:
                passed += 1
                if not args.quiet:
                    print("PASS {:32s} state={} outcome={}".format(case.name, case.state, case.outcome))
        checks = [
            ("order_independence", check_order_independence),
            ("determinism", check_determinism),
            ("reason_code_union_policy", check_reason_code_union_policy),
            ("evaluation_authorization_scope", check_evaluation_authorization_scope),
            ("stamp_declared_ids", check_stamp_declared_ids),
            ("refresh_bindings", check_refresh_bindings),
            ("library_reason_precision", check_library_reason_precision),
            ("dependency_aware_identity", check_dependency_aware_identity),
        ]
        for name, checker in checks:
            total += 1
            problems = checker(core_path)
            if problems:
                failures.append("{}: {}".format(name, "; ".join(problems)))
                if not args.quiet:
                    print("FAIL {:32s} {}".format(name, "; ".join(problems)))
            else:
                passed += 1
                if not args.quiet:
                    print("PASS {:32s}".format(name))
    except Exception as exc:
        print("ERROR: {}".format(exc), file=sys.stderr)
        return 2
    print("INDEPENDENT SEMANTIC VERIFIER: TOTAL {}/{} PASS".format(passed, total))
    if failures:
        print("VERIFY: FAIL")
        return 1
    print("VERIFY: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
