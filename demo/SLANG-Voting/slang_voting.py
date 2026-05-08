rules = [
    ("eligible", "true", lambda s: len(s.get("voters", [])) > 0 and all(v in s.get("registered", []) for v in s.get("voters", []))),
    ("valid_votes", "true", lambda s: s.get("eligible") == "true" and len(s.get("votes", {})) == len(s.get("voters", []))),
    ("tally", "complete", lambda s: s.get("valid_votes") == "true" and all(c in ["A", "B", "C"] for c in s.get("votes", {}).values())),
    ("winner", "A", lambda s: s.get("tally") == "complete" and list(s.get("votes", {}).values()).count("A") > list(s.get("votes", {}).values()).count("B") and list(s.get("votes", {}).values()).count("A") > list(s.get("votes", {}).values()).count("C")),
    ("winner", "B", lambda s: s.get("tally") == "complete" and list(s.get("votes", {}).values()).count("B") > list(s.get("votes", {}).values()).count("A") and list(s.get("votes", {}).values()).count("B") > list(s.get("votes", {}).values()).count("C")),
    ("winner", "C", lambda s: s.get("tally") == "complete" and list(s.get("votes", {}).values()).count("C") > list(s.get("votes", {}).values()).count("A") and list(s.get("votes", {}).values()).count("C") > list(s.get("votes", {}).values()).count("B")),
]

state = {
    "registered": ["aarav", "michael", "sofia", "emma"],
    "voters": ["aarav", "michael", "sofia"],
    "votes": {"aarav": "A", "michael": "A", "sofia": "B"}
}

changed = True
while changed:
    changed = False
    for key, value, cond in rules:
        if cond(state) and state.get(key) != value:
            state[key] = value
            changed = True

print(state)