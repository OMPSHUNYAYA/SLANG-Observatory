rules = [
    ("account_exists", "true", lambda s: "email" in s),
    ("token_valid", "true", lambda s: "reset_token" in s and len(s.get("reset_token", "")) > 10),
    ("password_strong", "true", lambda s: len(s.get("new_password", "")) >= 8),
    ("reset_success", "true", lambda s:
        s.get("account_exists") == "true" and
        s.get("token_valid") == "true" and
        s.get("password_strong") == "true"),
]

state = {
    "email": "user@example.com",
    "reset_token": "abc123xyz789",
    "new_password": "SecurePass2025!"
}

changed = True
while changed:
    changed = False
    for key, value, cond in rules:
        if cond(state) and state.get(key) != value:
            state[key] = value
            changed = True

print(state)