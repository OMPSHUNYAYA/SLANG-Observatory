rules = [
    ("authenticated", "true", lambda s: s.get("user") == "alice" and s.get("secret") == "xyz"),
    ("access", "granted", lambda s: s.get("authenticated") == "true"),
]

state = {
    "user": "alice",
    "secret": "xyz"
}

changed = True
while changed:
    changed = False
    for key, value, cond in rules:
        if cond(state) and state.get(key) != value:
            state[key] = value
            changed = True

print(state)
