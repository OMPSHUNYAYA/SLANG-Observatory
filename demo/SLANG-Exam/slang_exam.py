rules = [
    ("window_valid", "true", lambda s: s.get("exam_time") == "open"),
    ("center_valid", "true", lambda s: s.get("center_authorized") == "true"),
    ("candidate_valid", "true", lambda s: s.get("candidate_registered") == "true"),
    ("blueprint_valid", "true", lambda s: s.get("total_questions") == 5 and s.get("total_marks") == 10),
    ("bank_ready", "true", lambda s: len(s.get("approved_questions", [])) >= s.get("total_questions", 0)),
    ("paper_visible", "true", lambda s:
        s.get("window_valid") == "true" and
        s.get("center_valid") == "true" and
        s.get("candidate_valid") == "true" and
        s.get("blueprint_valid") == "true" and
        s.get("bank_ready") == "true"
    ),
    ("question_paper", lambda s: tuple(s.get("approved_questions", [])[:s.get("total_questions", 0)]),
     lambda s: s.get("paper_visible") == "true"),
]

state = {
    "exam_time": "open",
    "center_authorized": "true",
    "candidate_registered": "true",
    "total_questions": 5,
    "total_marks": 10,
    "approved_questions": ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7"]
}

changed = True
while changed:
    changed = False
    for key, value, cond in rules:
        if cond(state):
            new_value = value(state) if callable(value) else value
            if state.get(key) != new_value:
                state[key] = new_value
                changed = True

print(state)