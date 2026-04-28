rules = [
    ("eligible", "true", lambda s: s.get("policy_active") == "yes"),
    ("within_limit", "true", lambda s: s.get("eligible") == "true" and s.get("claim_amount", 0) <= s.get("limit", 0)),
    ("above_deductible", "true", lambda s: s.get("within_limit") == "true" and s.get("claim_amount", 0) > s.get("deductible", 0)),
    ("approved", "true", lambda s: s.get("within_limit") == "true" and s.get("above_deductible") == "true"),
    ("payout", "released", lambda s: s.get("approved") == "true"),
]

state = {
    "policy_active": "yes",
    "claim_amount": 5000,
    "deductible": 1000,
    "limit": 10000
}

changed = True
while changed:
    changed = False
    for key, value, cond in rules:
        if cond(state) and state.get(key) != value:
            state[key] = value
            changed = True

print(state)