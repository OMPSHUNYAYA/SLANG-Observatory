import hashlib

def cert(s):
    raw = "|".join([
        str(s.get("storm_id")),
        str(s.get("track_points")),
        str(s.get("pressure_drop_mb")),
        str(s.get("wind_change_kt")),
        str(s.get("track_jump_km")),
        str(s.get("forecast_window")),
        str(s.get("basin_authorized"))
    ])
    return hashlib.sha256(raw.encode()).hexdigest()[:16]

rules = [
    ("window_valid", True,
     lambda s: s.get("forecast_window") == "open"),

    ("basin_valid", True,
     lambda s: s.get("basin_authorized") is True),

    ("storm_valid", True,
     lambda s: s.get("storm_observed") is True),

    ("track_ready", True,
     lambda s: len(s.get("track_points", [])) >= 3),

    ("motion_coherent", True,
     lambda s: abs(s.get("track_jump_km", 999)) <= 150),

    ("pressure_coherent", True,
     lambda s: abs(s.get("pressure_drop_mb", 999)) <= 20),

    ("wind_coherent", True,
     lambda s: abs(s.get("wind_change_kt", 999)) <= 25),

    ("forecast_visible", True, lambda s:
        s.get("window_valid") and
        s.get("basin_valid") and
        s.get("storm_valid") and
        s.get("track_ready") and
        s.get("motion_coherent") and
        s.get("pressure_coherent") and
        s.get("wind_coherent")
    ),

    ("hurricane_forecast",
     lambda s: {
         "storm_id": s.get("storm_id"),
         "track": tuple(s.get("track_points", [])),
         "status": "STRUCTURALLY_ADMISSIBLE",
         "sigma": cert(s)
     },
     lambda s: s.get("forecast_visible") is True),
]

state = {
    "forecast_window": "open",
    "basin_authorized": True,
    "storm_observed": True,
    "storm_id": "ALPHA-01",
    "track_points": ["P1", "P2", "P3", "P4"],
    "track_jump_km": 80,
    "pressure_drop_mb": 12,
    "wind_change_kt": 18
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