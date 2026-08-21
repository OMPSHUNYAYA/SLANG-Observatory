import argparse
import hashlib
import json

SCHEMA_ID = "SLANG-HURRICANE-STRUCTURAL-ADMISSION-DEMO-1"
RULESET_ID = "SLANG-HURRICANE-STRUCTURAL-ADMISSION-RULESET-1"

DEMO_MIN_TRACK_POINTS = 3
DEMO_MAX_TRACK_JUMP_KM = 150
DEMO_MAX_PRESSURE_CHANGE_MB = 20
DEMO_MAX_WIND_CHANGE_KT = 25

RULES = {
    "window_valid": {
        "field": "forecast_window",
        "operator": "equals",
        "value": "open",
    },
    "basin_valid": {
        "field": "basin_authorized",
        "operator": "is_true",
        "value": True,
    },
    "storm_valid": {
        "field": "storm_observed",
        "operator": "is_true",
        "value": True,
    },
    "track_ready": {
        "field": "track_points",
        "operator": "minimum_count",
        "value": DEMO_MIN_TRACK_POINTS,
    },
    "motion_coherent": {
        "field": "track_jump_km",
        "operator": "absolute_maximum",
        "value": DEMO_MAX_TRACK_JUMP_KM,
    },
    "pressure_coherent": {
        "field": "pressure_change_mb",
        "operator": "absolute_maximum",
        "value": DEMO_MAX_PRESSURE_CHANGE_MB,
    },
    "wind_coherent": {
        "field": "wind_change_kt",
        "operator": "absolute_maximum",
        "value": DEMO_MAX_WIND_CHANGE_KT,
    },
}

REQUIRED_GATES = (
    "window_valid",
    "basin_valid",
    "storm_valid",
    "track_ready",
    "motion_coherent",
    "pressure_coherent",
    "wind_coherent",
)

DEFAULT_INPUT = {
    "storm_id": "ALPHA-01",
    "forecast_window": "open",
    "basin_authorized": True,
    "storm_observed": True,
    "track_points": ["P1", "P2", "P3", "P4"],
    "track_jump_km": 80,
    "pressure_change_mb": 12,
    "wind_change_kt": 18,
}


def canonical_bytes(value):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")


def sha256_hex(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def evaluate_rule(source, rule):
    field = rule["field"]
    operator = rule["operator"]
    expected = rule["value"]
    actual = source.get(field)

    if operator == "equals":
        return actual == expected

    if operator == "is_true":
        return actual is True

    if operator == "minimum_count":
        return isinstance(actual, (list, tuple)) and len(actual) >= expected

    if operator == "absolute_maximum":
        return (
            isinstance(actual, (int, float))
            and not isinstance(actual, bool)
            and abs(actual) <= expected
        )

    raise ValueError("UNKNOWN_RULE_OPERATOR")


def resolve(source):
    source = dict(source)
    gates = {
        name: evaluate_rule(source, RULES[name])
        for name in REQUIRED_GATES
    }

    admitted = all(gates.values())
    status = "ADMITTED" if admitted else "NOT_ADMITTED"

    core = {
        "schema_id": SCHEMA_ID,
        "ruleset_id": RULESET_ID,
        "scope": "STRUCTURAL_ADMISSION_DEMONSTRATION",
        "source": source,
        "gates": gates,
        "status": status,
    }

    result = dict(core)
    result["receipt_sha256"] = sha256_hex(core)
    result["meteorological_prediction_performed"] = False
    return result


def self_test():
    checks = []

    a = resolve(DEFAULT_INPUT)
    b = resolve(dict(reversed(list(DEFAULT_INPUT.items()))))

    checks.append(a["status"] == "ADMITTED")
    checks.append(a["receipt_sha256"] == b["receipt_sha256"])
    checks.append(a["meteorological_prediction_performed"] is False)
    checks.append(len(a["receipt_sha256"]) == 64)

    x = dict(DEFAULT_INPUT)
    x["track_points"] = ["P1", "P2"]
    checks.append(resolve(x)["status"] == "NOT_ADMITTED")
    checks.append(resolve(x)["gates"]["track_ready"] is False)

    x = dict(DEFAULT_INPUT)
    x["track_jump_km"] = 400
    checks.append(resolve(x)["status"] == "NOT_ADMITTED")
    checks.append(resolve(x)["gates"]["motion_coherent"] is False)

    x = dict(DEFAULT_INPUT)
    x["pressure_change_mb"] = 45
    checks.append(resolve(x)["status"] == "NOT_ADMITTED")
    checks.append(resolve(x)["gates"]["pressure_coherent"] is False)

    x = dict(DEFAULT_INPUT)
    x["wind_change_kt"] = 60
    checks.append(resolve(x)["status"] == "NOT_ADMITTED")
    checks.append(resolve(x)["gates"]["wind_coherent"] is False)

    x = dict(DEFAULT_INPUT)
    x["forecast_window"] = "closed"
    checks.append(resolve(x)["status"] == "NOT_ADMITTED")
    checks.append(resolve(x)["gates"]["window_valid"] is False)

    x = dict(DEFAULT_INPUT)
    x["basin_authorized"] = False
    checks.append(resolve(x)["status"] == "NOT_ADMITTED")
    checks.append(resolve(x)["gates"]["basin_valid"] is False)

    x = dict(DEFAULT_INPUT)
    x["storm_observed"] = False
    checks.append(resolve(x)["status"] == "NOT_ADMITTED")
    checks.append(resolve(x)["gates"]["storm_valid"] is False)

    x = dict(DEFAULT_INPUT)
    x["track_jump_km"] = True
    checks.append(resolve(x)["status"] == "NOT_ADMITTED")
    checks.append(resolve(x)["gates"]["motion_coherent"] is False)

    x = dict(DEFAULT_INPUT)
    x["pressure_change_mb"] = False
    checks.append(resolve(x)["status"] == "NOT_ADMITTED")
    checks.append(resolve(x)["gates"]["pressure_coherent"] is False)

    x = dict(DEFAULT_INPUT)
    x["wind_change_kt"] = True
    checks.append(resolve(x)["status"] == "NOT_ADMITTED")
    checks.append(resolve(x)["gates"]["wind_coherent"] is False)

    passed = sum(bool(v) for v in checks)
    total = len(checks)

    print("SLANG-Hurricane structural admission demonstration self-test")
    print(f"checks:{passed}/{total} " + ("PASS" if passed == total else "FAIL"))
    print("schema_id:" + SCHEMA_ID)
    print("ruleset_id:" + RULESET_ID)
    print("meteorological_prediction_performed:false")
    return 0 if passed == total else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return self_test()

    print(json.dumps(resolve(DEFAULT_INPUT), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
