rules = [
    ("attack", "suspected", lambda s: s.get("failures", 0) > 50),
    ("bruteforce", "true", lambda s: s.get("attack") == "suspected" and s.get("pattern") == "repeated"),
    ("block", "yes", lambda s: s.get("bruteforce") == "true"),
]

state = {
    "failures": 75,
    "pattern": "repeated"
}

changed = True

while changed:
    changed = False
    for key, value, cond in rules:
        if cond(state) and state.get(key) != value:
            state[key] = value
            changed = True

ordered = {k: state[k] for k in ["failures", "pattern", "attack", "bruteforce", "block"] if k in state}
print(ordered)
