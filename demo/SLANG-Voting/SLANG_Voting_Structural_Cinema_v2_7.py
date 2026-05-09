#!/usr/bin/env python3
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import cv2
import numpy as np
import hashlib
import math
import os
from copy import deepcopy

VERSION = "2.7"
WIDTH = 1600
HEIGHT = 900
FPS = 24
OUT_VIDEO = "SLANG_Voting_Structural_Cinema_v2_7.mp4"
OUT_POSTER = "SLANG_Voting_Structural_Cinema_Poster_v2_7.png"
OUT_VERIFY = "SLANG_Voting_Structural_Cinema_VERIFY_v2_7.txt"

BG = (4, 7, 14)
DEEP = (3, 6, 12)
PANEL = (8, 15, 28)
PANEL2 = (12, 24, 44)
WHITE = (248, 251, 255)
MUTED = (185, 203, 230)
GOLD = (255, 211, 104)
ACCENT = (92, 242, 210)
BLUE = (95, 158, 255)
RED = (255, 86, 108)
ORANGE = (255, 170, 70)
GREEN = (76, 226, 138)
PURPLE = (180, 132, 255)
LINE = (70, 90, 128)
DARK_RED = (46, 10, 22)
DARK_GREEN = (9, 37, 25)
DARK_GOLD = (45, 35, 15)
SAFE_TOP = 42
TEXT_FLOOR = 592
CONTENT_BOTTOM = 620


def load_font(size, bold=False):
    try:
        if os.name == "nt":
            path = r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf"
        else:
            path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


FONT_HERO = load_font(72, True)
FONT_HERO2 = load_font(62, True)
FONT_TITLE = load_font(52, True)
FONT_BIG = load_font(44, True)
FONT_MED = load_font(38, True)
FONT_BODY = load_font(32, True)
FONT_SMALL = load_font(28, True)
FONT_TINY = load_font(24, True)
FONT_CODE = load_font(29, True)


def text_size(draw, text, font):
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0], box[3] - box[1]


def fit_font(draw, text, start, max_width, min_size=16, bold=True):
    size = start
    while size >= min_size:
        f = load_font(size, bold)
        if text_size(draw, text, f)[0] <= max_width:
            return f
        size -= 2
    return load_font(min_size, bold)


def center(draw, text, y, font, color=WHITE):
    w, _ = text_size(draw, text, font)
    draw.text(((WIDTH - w) // 2, y), text, font=font, fill=color)


def center_fit(draw, text, y, max_width, start_size, color=WHITE, min_size=18):
    font = fit_font(draw, text, start_size, max_width, min_size, True)
    center(draw, text, y, font, color)


def center_box_text(draw, text, box, y, start_size, color=WHITE, min_size=16):
    f = fit_font(draw, text, start_size, box[2] - box[0] - 30, min_size, True)
    w, _ = text_size(draw, text, f)
    draw.text((box[0] + (box[2] - box[0] - w) // 2, y), text, font=f, fill=color)


def panel(draw, box, fill=PANEL, outline=LINE, width=2, radius=28):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def canonical_text(value):
    if isinstance(value, dict):
        return "{" + "|".join(str(k) + "=" + canonical_text(value[k]) for k in sorted(value)) + "}"
    if isinstance(value, list):
        return "[" + "|".join(canonical_text(v) for v in value) + "]"
    if isinstance(value, tuple):
        return "(" + "|".join(canonical_text(v) for v in value) + ")"
    return str(value)


def sha256_hex(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def structure_signature(structure):
    return sha256_hex(canonical_text(structure))


def certificate(value):
    return sha256_hex(canonical_text(value))[:16]


def base_voting_structure():
    return {
        "civic_process": "participation_remains_under_existing_rules",
        "registered": ["voter_01", "voter_02", "voter_03", "voter_04", "voter_05"],
        "participants": ["voter_01", "voter_02", "voter_03", "voter_04"],
        "records": {"voter_01": "A", "voter_02": "A", "voter_03": "B", "voter_04": "C"},
        "candidate_set": ["A", "B", "C"],
        "rule": "highest_valid_record_count_wins",
        "rule_set": {"method": "plurality", "quorum_min": 1, "tie_rule_declared": "false"},
        "jurisdiction_rules_declared": "true",
        "oversight_external": "true"
    }


def resolve_voting(structure):
    state = deepcopy(structure)
    rules = [
        ("participation_valid", "true", lambda s: len(s.get("participants", [])) > 0 and all(v in s.get("registered", []) for v in s.get("participants", []))),
        ("records_complete", "true", lambda s: s.get("participation_valid") == "true" and len(s.get("records", {})) == len(s.get("participants", []))),
        ("rules_declared", "true", lambda s: s.get("jurisdiction_rules_declared") == "true" and len(s.get("candidate_set", [])) > 0 and isinstance(s.get("rule_set", {}), dict)),
        ("quorum_met", "true", lambda s: s.get("records_complete") == "true" and len(s.get("participants", [])) >= int(s.get("rule_set", {}).get("quorum_min", 1))),
        ("tally_structure", "complete", lambda s: s.get("records_complete") == "true" and s.get("rules_declared") == "true" and all(c in s.get("candidate_set", []) for c in s.get("records", {}).values())),
        ("structure_mature", "true", lambda s: s.get("participation_valid") == "true" and s.get("records_complete") == "true" and s.get("rules_declared") == "true" and s.get("quorum_met") == "true" and s.get("tally_structure") == "complete"),
        ("winner_visible", "true", lambda s: s.get("structure_mature") == "true"),
    ]
    changed = True
    while changed:
        changed = False
        for key, value, cond in rules:
            if cond(state) and state.get(key) != value:
                state[key] = value
                changed = True
    winner = None
    terminal_state = "ABSTAIN"
    if state.get("rules_declared") == "true" and state.get("records_complete") == "true" and state.get("quorum_met") != "true":
        terminal_state = "QUORUM_NOT_MET"
        state.pop("winner_visible", None)
        state["structural_state"] = terminal_state
    elif state.get("winner_visible") == "true":
        counts = {c: list(state.get("records", {}).values()).count(c) for c in state.get("candidate_set", [])}
        top = max(counts.values()) if counts else 0
        top_candidates = sorted([k for k, v in counts.items() if v == top])
        if len(top_candidates) == 1:
            winner = top_candidates[0]
            state["winner"] = winner
            terminal_state = "RESOLVED"
        else:
            state.pop("winner_visible", None)
            terminal_state = "TIE_REQUIRES_DECLARED_RULE"
            state["structural_state"] = terminal_state
    else:
        state["structural_state"] = "ABSTAIN"
    result = {
        "structure_signature": structure_signature(structure),
        "structure_certificate": structure_signature(structure)[:16],
        "state": terminal_state,
        "winner_visible": state.get("winner_visible") == "true",
        "winner_identity": certificate(winner if winner else terminal_state),
        "winner": winner,
        "resolved_state": state,
        "collapse_formula": "phi((m, a, s)) = m"
    }
    return result

def gradient(top, mid, bottom):
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img)
    for y in range(HEIGHT):
        t = y / (HEIGHT - 1)
        if t < 0.55:
            p = t / 0.55
            c = tuple(int(top[i] + (mid[i] - top[i]) * p) for i in range(3))
        else:
            p = (t - 0.55) / 0.45
            c = tuple(int(mid[i] + (bottom[i] - mid[i]) * p) for i in range(3))
        draw.line((0, y, WIDTH, y), fill=c)
    return img


def add_vignette(img, strength=120):
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    for i in range(20):
        alpha = int(strength * (i / 20) ** 2)
        d.rectangle((i * 18, i * 12, WIDTH - i * 18, HEIGHT - i * 12), outline=(0, 0, 0, alpha), width=32)
    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


def add_particles(img, t=0.0, count=24, color=ACCENT, intensity=0.65):
    layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    seed = int(t * 10000) + count * 97 + color[0] * 3 + color[1] * 5 + color[2] * 7
    rng = np.random.default_rng(seed)
    for _ in range(count):
        x = int(rng.integers(65, WIDTH - 65))
        y = int(rng.integers(75, TEXT_FLOOR - 5))
        r = int(rng.integers(2, 6))
        alpha = int((70 + rng.integers(0, 120)) * intensity)
        d.ellipse((x - r, y - r, x + r, y + r), fill=(color[0], color[1], color[2], min(225, alpha)))
    return Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")


def light_sweep(img, t, color=ACCENT):
    layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    x = int(-240 + (WIDTH + 480) * t)
    for i in range(80):
        alpha = max(0, 28 - i // 3)
        d.line((x + i * 5, 0, x - 240 + i * 5, CONTENT_BOTTOM), fill=(color[0], color[1], color[2], alpha), width=2)
    return Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")


def footer_band(draw, text, y=592, color=WHITE, outline=GOLD, x1=260, x2=1340):
    y = min(y, TEXT_FLOOR)
    panel(draw, (x1, y - 26, x2, y + 34), fill=(6, 12, 24), outline=outline, width=3, radius=18)
    center_fit(draw, text, y - 8, (x2 - x1) - 70, 30, color, 20)


def top_label(draw, title, subtitle=None, color=GOLD):
    panel(draw, (155, 48, 1445, 128), fill=(5, 11, 22), outline=ACCENT, width=3, radius=22)
    center_fit(draw, title, 70, 1190, 43, color, 28)
    if subtitle:
        center_fit(draw, subtitle, 134, 1260, 25, MUTED, 18)


def draw_people_group(draw, x, y, color=BLUE, scale=1.0):
    r = int(16 * scale)
    body_w = int(30 * scale)
    body_h = int(40 * scale)
    for dx in [-32, 0, 32]:
        cx = x + int(dx * scale)
        draw.ellipse((cx - r, y - r, cx + r, y + r), fill=color)
        draw.rounded_rectangle((cx - body_w // 2, y + r - 2, cx + body_w // 2, y + r + body_h), radius=int(9 * scale), fill=color)


def draw_civic_symbol(draw, x, y, label, color):
    draw_people_group(draw, x, y, color, 0.78)
    panel(draw, (x - 95, y + 92, x + 95, y + 142), fill=(6, 12, 24), outline=(80, 100, 138), width=2, radius=12)
    center_box_text(draw, label, (x - 95, y + 92, x + 95, y + 142), y + 105, 22, WHITE, 15)


def draw_chain_node(draw, x, y, label, color=BLUE):
    panel(draw, (x - 120, y - 50, x + 120, y + 50), fill=PANEL, outline=color, width=3, radius=18)
    center_box_text(draw, label, (x - 120, y - 50, x + 120, y + 50), y - 13, 24, WHITE, 15)


def draw_status_card(draw, x, y, title, body, color, symbol):
    panel(draw, (x, y, x + 340, y + 150), fill=(7, 13, 24), outline=color, width=3, radius=24)
    draw.text((x + 22, y + 30), symbol, font=FONT_BIG, fill=color)
    draw.text((x + 88, y + 30), title, font=FONT_SMALL, fill=color)
    lines = body.split("|")
    yy = y + 72
    for line in lines:
        draw.text((x + 88, yy), line, font=FONT_TINY, fill=WHITE)
        yy += 25


def draw_global_arc(draw, t, y=400):
    cx, cy = WIDTH // 2, y
    for r, color in [(330, BLUE), (250, ACCENT), (170, GOLD)]:
        start = int(20 + 160 * t)
        end = int(210 + 120 * t)
        draw.arc((cx - r, cy - r // 2, cx + r, cy + r // 2), start=start, end=end, fill=color, width=3)
    for i in range(14):
        angle = 2 * math.pi * (i / 14 + t * 0.08)
        x = cx + int(math.cos(angle) * 360)
        yy = cy + int(math.sin(angle) * 110)
        draw.ellipse((x - 5, yy - 5, x + 5, yy + 5), fill=ACCENT if i % 2 else GOLD)


def draw_waiting_frame(t):
    img = gradient((2, 5, 12), (7, 18, 36), (16, 34, 58)).convert("RGB")
    draw = ImageDraw.Draw(img)
    center_fit(draw, "THE WORLD WAITS", 44, 1400, 72, GOLD, 38)
    center_fit(draw, "FOR ELECTION RESULTS", 126, 1400, 72, GOLD, 38)
    center_fit(draw, "TRUST WAITS FOR PROOF", 246, 1400, 64, WHITE, 36)
    draw_global_arc(draw, t, 482)
    for i, x in enumerate([245, 465, 685, 905, 1125, 1345]):
        y = 430 + int(math.sin(t * 5 + i) * 12)
        color = BLUE if i % 2 == 0 else ACCENT
        draw_people_group(draw, x, y, color, 0.88)
    footer_band(draw, "Counting day is about confidence.", 592, WHITE, ACCENT, 400, 1200)
    img = add_particles(img, t, 22, ACCENT, 0.42)
    return add_vignette(light_sweep(img, t, BLUE), 105)

def draw_process_pressure_frame(t):
    img = gradient((8, 8, 16), (18, 16, 30), (34, 20, 35)).convert("RGB")
    draw = ImageDraw.Draw(img)
    center_fit(draw, "COUNTING DELAY CREATES DOUBT", 64, 1360, 60, GOLD, 32)
    center_fit(draw, "Waiting is normal. Uncertainty is painful.", 138, 1320, 38, MUTED, 24)
    labels = ["Record", "Move", "Aggregate", "Reconcile", "Review", "Declare"]
    xs = [190, 430, 670, 910, 1150, 1390]
    for i, label in enumerate(labels):
        y = 330 + int(math.sin(t * 4 + i) * 9)
        draw_chain_node(draw, xs[i], y, label, RED if i in [2, 3] else ORANGE)
        if i < len(labels) - 1:
            y2 = 330 + int(math.sin(t * 4 + i + 1) * 9)
            draw.line((xs[i] + 124, y, xs[i+1] - 124, y2), fill=ORANGE, width=5)
            draw.polygon([(xs[i+1]-132, y2), (xs[i+1]-156, y2 - 12), (xs[i+1]-156, y2 + 12)], fill=ORANGE)
    footer_band(draw, "People need a result they can trust.", 592, WHITE, GOLD, 410, 1190)
    return add_vignette(add_particles(img, t, 18, ORANGE, 0.55), 130)

def draw_infrastructure_bias_frame(t):
    img = gradient((3, 7, 15), (8, 24, 45), (14, 40, 72)).convert("RGB")
    draw = ImageDraw.Draw(img)
    center_fit(draw, "SHOULD SPEED DECIDE TRUST?", 62, 1400, 64, GOLD, 32)
    center_fit(draw, "Different access. Same human stake.", 140, 1320, 38, MUTED, 24)
    bases = [(260, "Low bandwidth", RED, 0.25), (550, "Shared device", ORANGE, 0.45), (840, "Stable access", BLUE, 0.65), (1130, "Fast network", GREEN, 0.9)]
    for x, label, color, speed in bases:
        panel(draw, (x - 115, 240, x + 115, 500), fill=(7, 13, 24), outline=color, width=3, radius=22)
        draw_people_group(draw, x, 300, color, 0.72)
        bars = int(1 + speed * 4)
        for i in range(5):
            h = 20 + i * 18
            fill = color if i < bars else (42, 55, 72)
            draw.rounded_rectangle((x - 52 + i * 24, 425 - h, x - 38 + i * 24, 425), radius=4, fill=fill)
        center_box_text(draw, label, (x - 115, 445, x + 115, 490), 455, 20, WHITE, 14)
    footer_band(draw, "Fairness must not depend on device, location, or speed.", 592, ACCENT, GOLD, 300, 1300)
    return add_vignette(light_sweep(add_particles(img, t, 16, BLUE, 0.5), t, ACCENT), 100)


def draw_participation_remains_frame(t):
    img = gradient((3, 8, 18), (8, 24, 48), (16, 42, 72)).convert("RGB")
    draw = ImageDraw.Draw(img)
    center_fit(draw, "PEOPLE STILL PARTICIPATE", 60, 1360, 64, GOLD, 34)
    center_fit(draw, "Rules, institutions, and oversight remain.", 138, 1320, 38, MUTED, 24)
    labels = ["Register", "Verify", "Participate", "Record", "Review"]
    colors = [BLUE, ACCENT, BLUE, ACCENT, BLUE]
    xs = [250, 525, 800, 1075, 1350]
    for i, label in enumerate(labels):
        draw_civic_symbol(draw, xs[i], 260 + int(math.sin(t * 3 + i) * 5), label, colors[i])
        if i < len(labels) - 1:
            draw.line((xs[i] + 100, 360, xs[i+1] - 100, 360), fill=(110, 140, 188), width=3)
    footer_band(draw, "Trust is checked after people participate.", 592, WHITE, GOLD, 340, 1260)
    return add_vignette(add_particles(img, t, 15, ACCENT, 0.45), 90)


def draw_structural_question_frame(t):
    img = gradient((2, 5, 12), (5, 14, 30), (12, 32, 58)).convert("RGB")
    draw = ImageDraw.Draw(img)
    glow = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    pulse = 30 + int(28 * (0.5 + 0.5 * math.sin(t * 6)))
    gd.ellipse((500, 165, 1100, 585), fill=(92, 242, 210, pulse))
    glow = glow.filter(ImageFilter.GaussianBlur(46))
    img = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")
    draw = ImageDraw.Draw(img)
    center_fit(draw, "WHAT MAKES A RESULT", 150, 1300, 66, WHITE, 34)
    center_fit(draw, "TRUSTWORTHY?", 245, 1320, 76, GOLD, 38)
    center_fit(draw, "Proof that the structure is ready.", 395, 1300, 38, MUTED, 24)
    footer_band(draw, "Not early. Not forced. Only supported.", 592, ACCENT, ACCENT, 420, 1180)
    return add_vignette(light_sweep(img, t, GOLD), 90)


def draw_structure_recorded_frame(t):
    img = gradient((3, 7, 16), (8, 22, 44), (16, 42, 70)).convert("RGB")
    draw = ImageDraw.Draw(img)
    center_fit(draw, "TRUST NEEDS STRUCTURE", 56, 1360, 64, GOLD, 34)
    center_fit(draw, "Records. Rules. Oversight. Consistency.", 132, 1300, 38, MUTED, 24)
    cx, cy = WIDTH // 2, 360
    nodes = [
        (420, 250, "Participation"), (800, 220, "Rules"), (1180, 250, "Records"),
        (490, 440, "Eligibility"), (800, 445, "Consistency"), (1110, 440, "Oversight")
    ]
    for i, (x, y, label) in enumerate(nodes):
        draw.line((cx, cy, x, y), fill=(65, 210, 190), width=3)
    panel(draw, (650, 300, 950, 420), fill=(7, 13, 24), outline=GOLD, width=4, radius=24)
    center_box_text(draw, "STRUCTURE", (650, 300, 950, 420), 338, 34, GOLD, 22)
    for i, (x, y, label) in enumerate(nodes):
        pulse = 0.5 + 0.5 * math.sin(t * 6 + i)
        color = ACCENT if i % 2 else BLUE
        draw.ellipse((x - 18, y - 18, x + 18, y + 18), fill=color)
        panel(draw, (x - 105, y + 30, x + 105, y + 75), fill=(7, 13, 24), outline=color, width=2, radius=12)
        center_box_text(draw, label, (x - 105, y + 30, x + 105, y + 75), y + 41, 19, WHITE, 13)
        r = int(24 + pulse * 8)
        draw.ellipse((x - r, y - r, x + r, y + r), outline=color, width=1)
    footer_band(draw, "Only declared structure can support a result.", 592, WHITE, GOLD, 360, 1240)
    return add_vignette(add_particles(img, t, 20, ACCENT, 0.55), 85)


def draw_validation_frame(t, result):
    img = gradient((3, 7, 16), (7, 20, 42), (14, 36, 64)).convert("RGB")
    draw = ImageDraw.Draw(img)
    center_fit(draw, "CHECKS TURN GREEN", 54, 1360, 66, GOLD, 34)
    center_fit(draw, "One by one, trust becomes supportable.", 132, 1320, 38, MUTED, 24)
    checks = ["participation_valid", "records_complete", "rules_declared", "tally_structure", "structure_mature"]
    labels = ["Participation", "Records", "Rules", "Tally", "Maturity"]
    for i, label in enumerate(labels):
        x = 190 + i * 305
        y = 285
        active = i <= min(4, int(t * 6))
        color = GREEN if active else LINE
        panel(draw, (x - 115, y - 60, x + 115, y + 105), fill=(7, 13, 24), outline=color, width=3, radius=22)
        mark = "✓" if active else "•"
        center_box_text(draw, mark, (x - 115, y - 40, x + 115, y + 20), y - 44, 48, color, 30)
        center_box_text(draw, label, (x - 115, y + 24, x + 115, y + 75), y + 34, 22, WHITE, 14)
        if i < len(labels) - 1:
            draw.line((x + 120, y + 20, x + 185, y + 20), fill=color, width=4)
    visible = int(t * 6) >= 5
    footer_band(draw, "All gates green. Result can appear." if visible else "No green gates. No forced result.", 592, ACCENT if visible else MUTED, GOLD, 390, 1210)
    return add_vignette(light_sweep(add_particles(img, t, 12, GREEN, 0.45), t, ACCENT), 85)


def draw_counting_reveal_frame(t, result):
    img = gradient((2, 5, 12), (8, 22, 44), (16, 40, 70)).convert("RGB")
    draw = ImageDraw.Draw(img)
    center_fit(draw, "COUNTING DAY", 52, 1360, 70, GOLD, 36)
    center_fit(draw, "A result should appear only when trust is ready.", 132, 1320, 38, MUTED, 24)
    gate_names = ["Participation", "Records", "Rules", "Tally", "Consistency"]
    phase = min(1.0, t)
    if phase < 0.46:
        numbers = ["5", "4", "3", "2", "1", "0"]
        idx = min(5, int(phase / 0.46 * len(numbers)))
        center_fit(draw, numbers[idx], 245, 1100, 130, GOLD, 70)
        center_fit(draw, "Trust is still forming...", 440, 1000, 42, ACCENT, 26)
    else:
        reveal = min(5, int((phase - 0.46) / 0.44 * 6))
        for i, label in enumerate(gate_names):
            x = 180 + i * 310
            y = 285
            active = i < reveal
            color = GREEN if active else LINE
            fill = DARK_GREEN if active else (7, 13, 24)
            panel(draw, (x - 120, y - 65, x + 120, y + 115), fill=fill, outline=color, width=4, radius=22)
            center_box_text(draw, "✓" if active else "•", (x - 120, y - 48, x + 120, y + 15), y - 52, 54, color, 28)
            center_box_text(draw, label, (x - 120, y + 30, x + 120, y + 88), y + 42, 22, WHITE, 14)
            if i < len(gate_names) - 1:
                draw.line((x + 125, y + 23, x + 185, y + 23), fill=color, width=5)
        if reveal >= 5:
            panel(draw, (420, 500, 1180, 570), fill=(7, 13, 24), outline=GOLD, width=4, radius=20)
            center_fit(draw, "RESULT ADMITTED", 516, 680, 38, GOLD, 24)
        else:
            center_fit(draw, "A result waits until every gate is ready.", 515, 1180, 36, MUTED, 22)
    footer_band(draw, "No premature result. No forced declaration.", 592, WHITE, ACCENT, 390, 1210)
    return add_vignette(light_sweep(add_particles(img, t, 22, GREEN, 0.45), t, ACCENT), 88)


def draw_formula_frame(t):
    img = gradient((2, 5, 12), (5, 14, 30), (12, 28, 54)).convert("RGB")
    draw = ImageDraw.Draw(img)
    center_fit(draw, "THE STRUCTURAL RULE", 64, 1380, 64, GOLD, 34)
    panel(draw, (245, 200, 1355, 350), fill=(7, 13, 24), outline=ACCENT, width=4, radius=28)
    center_fit(draw, "winner_visible iff structure_mature", 244, 1040, 46, ACCENT, 26)
    panel(draw, (310, 405, 1290, 520), fill=(7, 13, 24), outline=GOLD, width=3, radius=24)
    center_fit(draw, "structure_mature = complete AND consistent", 438, 920, 38, GOLD, 24)
    footer_band(draw, "The result is not forced. It is admitted by structure.", 592, WHITE, ACCENT, 310, 1290)
    return add_vignette(add_particles(light_sweep(img, t, ACCENT), t, 22, GOLD, 0.55), 80)


def draw_states_frame(t):
    img = gradient((4, 8, 18), (8, 22, 44), (16, 38, 66)).convert("RGB")
    draw = ImageDraw.Draw(img)
    center_fit(draw, "SAFE OUTCOMES", 52, 1360, 66, GOLD, 34)
    center_fit(draw, "Sometimes the right answer is to wait.", 130, 1320, 38, MUTED, 24)
    cards = [
        (90, 235, "RESOLVED", "Complete structure|Winner visible", GREEN, "✓"),
        (465, 235, "ABSTAIN", "Conditions missing|No forced outcome", BLUE, "?"),
        (840, 235, "CONFLICT", "Contradiction present|No unsafe winner", ORANGE, "!"),
        (1215, 235, "FORBIDDEN", "Prohibited state|Visibility blocked", RED, "×"),
    ]
    for c in cards:
        draw_status_card(draw, *c)
    footer_band(draw, "Silence is not failure. It is safety.", 592, ACCENT, GOLD, 420, 1180)
    return add_vignette(add_particles(img, t, 16, ACCENT, 0.5), 90)


def draw_silence_frame(t):
    img = gradient((2, 4, 10), (8, 8, 18), (14, 18, 32)).convert("RGB")
    draw = ImageDraw.Draw(img)
    center_fit(draw, "INCOMPLETE STRUCTURE", 150, 1300, 66, MUTED, 34)
    center_fit(draw, "NO FORCED DECLARATION", 250, 1120, 60, GOLD, 34)
    center_fit(draw, "absence = valid structural state", 395, 1200, 40, ACCENT, 24)
    for i in range(5):
        alpha = 70 + int(50 * math.sin(t * 6 + i))
        x = 390 + i * 205
        draw.rounded_rectangle((x, 485, x + 105, 515), radius=15, fill=(70, 90, 128), outline=(70, 90, 128))
        draw.rectangle((x + 14, 491, x + 90, 509), fill=(3, 6, 12))
    footer_band(draw, "The safest result may be no result yet.", 592, WHITE, ACCENT, 390, 1210)
    return add_vignette(img, 120)


def draw_fairness_frame(t):
    img = gradient((3, 7, 15), (9, 26, 50), (18, 48, 82)).convert("RGB")
    draw = ImageDraw.Draw(img)
    center_fit(draw, "FAIRNESS BEYOND SPEED", 58, 1360, 66, GOLD, 34)
    center_fit(draw, "Different paths. Same support.", 136, 1320, 40, MUTED, 24)
    left = (130, 230, 710, 500)
    right = (890, 230, 1470, 500)
    panel(draw, left, fill=(7, 13, 24), outline=BLUE, width=3, radius=26)
    panel(draw, right, fill=(7, 13, 24), outline=ACCENT, width=3, radius=26)
    center_box_text(draw, "PATH A", left, 260, 32, BLUE, 22)
    center_box_text(draw, "PATH B", right, 260, 32, ACCENT, 22)
    for i, x in enumerate([250, 410, 570]):
        draw_people_group(draw, x, 340 + int(math.sin(t * 3 + i) * 5), BLUE, 0.6)
    for i, x in enumerate([1010, 1170, 1330]):
        draw_people_group(draw, x, 340 + int(math.sin(t * 3 + i + 3) * 5), ACCENT, 0.6)
    center_box_text(draw, "structure complete", left, 455, 26, WHITE, 18)
    center_box_text(draw, "structure complete", right, 455, 26, WHITE, 18)
    draw.line((715, 365, 885, 365), fill=GOLD, width=5)
    center_fit(draw, "same structure -> same visibility", 510, 1250, 32, GOLD, 21)
    footer_band(draw, "Trust should not be a privilege of speed.", 592, ACCENT, GOLD, 400, 1200)
    return add_vignette(light_sweep(add_particles(img, t, 18, BLUE, 0.45), t, GOLD), 90)


def draw_replay_frame(t, result):
    img = gradient((3, 7, 16), (7, 20, 42), (15, 38, 68)).convert("RGB")
    draw = ImageDraw.Draw(img)
    center_fit(draw, "SAME STRUCTURE. SAME RESULT.", 58, 1360, 58, GOLD, 30)
    center_fit(draw, "Repeatable trust. No hidden guess.", 136, 1300, 38, MUTED, 24)
    left = (130, 210, 710, 510)
    right = (890, 210, 1470, 510)
    panel(draw, left, fill=PANEL, outline=ACCENT, width=4, radius=26)
    panel(draw, right, fill=PANEL, outline=ACCENT, width=4, radius=26)
    center_box_text(draw, "RUN 1", left, 245, 38, WHITE, 24)
    center_box_text(draw, "RUN 2", right, 245, 38, WHITE, 24)
    center_box_text(draw, "winner_identity", left, 340, 28, MUTED, 18)
    center_box_text(draw, "winner_identity", right, 340, 28, MUTED, 18)
    center_box_text(draw, result["winner_identity"], left, 395, 38, GOLD, 22)
    center_box_text(draw, result["winner_identity"], right, 395, 38, GOLD, 22)
    footer_band(draw, "S1 = S2 -> Outcome1 = Outcome2", 590, GREEN, GREEN, 350, 1250)
    return add_vignette(add_particles(light_sweep(img, t, ACCENT), t, 14, GOLD, 0.55), 85)


def draw_not_replacement_frame(t):
    img = gradient((4, 8, 18), (10, 22, 42), (18, 42, 70)).convert("RGB")
    draw = ImageDraw.Draw(img)
    center_fit(draw, "NOT A REPLACEMENT", 52, 1360, 68, GOLD, 36)
    center_fit(draw, "People, laws, and institutions remain.", 140, 1300, 38, MUTED, 24)
    items = ["Participation remains", "Institutions remain", "Rules remain", "Oversight remains", "Final authority remains"]
    coords = [(340, 285), (800, 285), (1260, 285), (570, 430), (1030, 430)]
    center_point = (800, 365)
    for i, (x, y) in enumerate(coords):
        color = BLUE if i % 2 else ACCENT
        pulse = 0.35 + 0.65 * abs(math.sin(t * 4 + i))
        line_color = tuple(int(c * pulse) for c in color)
        draw.line((center_point[0], center_point[1], x, y), fill=line_color, width=2)
    for i, item in enumerate(items):
        x, y = coords[i]
        color = BLUE if i % 2 else ACCENT
        panel(draw, (x - 200, y - 40, x + 200, y + 50), fill=(7, 13, 24), outline=color, width=3, radius=18)
        center_box_text(draw, item, (x - 200, y - 40, x + 200, y + 50), y - 11, 29, WHITE, 18)
    footer_band(draw, "The shift is trust before visibility.", 600, WHITE, GOLD, 440, 1160)
    return add_vignette(add_particles(img, t, 16, ACCENT, 0.45), 90)

def draw_eliminates_frame(t):
    img = gradient((4, 8, 18), (8, 22, 42), (16, 36, 62)).convert("RGB")
    draw = ImageDraw.Draw(img)
    center_fit(draw, "WHAT THIS REMOVES", 52, 1450, 68, GOLD, 36)
    center_fit(draw, "Not people. Not institutions. Only dependency.", 132, 1320, 38, MUTED, 24)
    items = ["Pressure", "Sequence", "Speed advantage", "Forced result", "Unsupported claim", "Process dependency"]
    for i, item in enumerate(items):
        x = 280 + (i % 3) * 520
        y = 245 + (i // 3) * 145
        panel(draw, (x - 175, y - 45, x + 175, y + 55), fill=(34, 10, 20), outline=RED, width=3, radius=18)
        draw.ellipse((x - 145, y - 22, x - 105, y + 18), outline=RED, width=5)
        draw.line((x - 145, y + 18, x - 105, y - 22), fill=RED, width=5)
        draw.text((x - 80, y - 12), item, font=fit_font(draw, item, 24, 230, 15), fill=WHITE)
    footer_band(draw, "Remove dependency. Preserve trust.", 592, ACCENT, GOLD, 430, 1170)
    return add_vignette(light_sweep(add_particles(img, t, 18, RED, 0.3), t, ACCENT), 95)


def draw_civilization_frame(t):
    img = gradient((2, 6, 14), (8, 24, 50), (20, 58, 92)).convert("RGB")
    draw = ImageDraw.Draw(img)
    center_fit(draw, "TRUST MADE VISIBLE", 58, 1360, 70, GOLD, 36)
    cx, cy = WIDTH // 2, 360
    for r, color in [(385, BLUE), (290, ACCENT), (195, GOLD)]:
        draw.ellipse((cx - r, cy - r // 2, cx + r, cy + r // 2), outline=color, width=2)
    for i in range(18):
        ang = 2 * math.pi * (i / 18 + t * 0.05)
        x = cx + int(math.cos(ang) * 395)
        y = cy + int(math.sin(ang) * 125)
        draw.ellipse((x - 9, y - 9, x + 9, y + 9), fill=ACCENT if i % 2 else GOLD)
        draw.line((cx, cy, x, y), fill=(60, 120, 160), width=1)
    panel(draw, (570, 295, 1030, 425), fill=(7, 13, 24), outline=GOLD, width=4, radius=28)
    center_box_text(draw, "structure_mature", (570, 295, 1030, 425), 322, 36, GOLD, 22)
    center_box_text(draw, "-> visibility admitted", (570, 295, 1030, 425), 370, 28, WHITE, 18)
    footer_band(draw, "Not replacing systems. Making trust visible.", 592, WHITE, ACCENT, 390, 1210)
    return add_vignette(light_sweep(add_particles(img, t, 26, ACCENT, 0.5), t, GOLD), 75)

def draw_open_source_frame(t):
    img = gradient((3, 7, 16), (8, 24, 48), (18, 48, 78)).convert("RGB")
    draw = ImageDraw.Draw(img)
    center_fit(draw, "PUBLIC STRUCTURAL DEMO", 58, 1360, 62, GOLD, 34)
    panel(draw, (180, 170, 1420, 540), fill=(7, 13, 24), outline=ACCENT, width=4, radius=28)
    draw.ellipse((255, 235, 425, 405), fill=(245, 248, 252), outline=GOLD, width=4)
    center_box_text(draw, "OPEN", (255, 235, 425, 405), 300, 34, (8, 22, 48), 22)
    lines = [
        "Tiny deterministic cinema script",
        "Generic election-result demonstration",
        "No country-specific claims",
        "Authority remains external",
        "Replayable structural output",
    ]
    y = 205
    for line in lines:
        draw.text((520, y), "✓ " + line, font=FONT_MED, fill=WHITE)
        y += 58
    footer_band(draw, "Public demo. Neutral framing. Replayable output.", 592, ACCENT, GOLD, 300, 1300)
    return add_vignette(add_particles(light_sweep(img, t, ACCENT), t, 15, GOLD, 0.45), 80)


def draw_did_you_know_frame(t):
    img = gradient((2, 6, 14), (8, 24, 48), (16, 42, 76)).convert("RGB")
    draw = ImageDraw.Draw(img)
    center_fit(draw, "DID YOU KNOW?", 62, 1360, 52, GOLD, 30)
    center_fit(draw, "This entire civic cinema", 140, 760, 46, WHITE, 28)
    center_fit(draw, "was resolved from a tiny", 205, 760, 46, ACCENT, 28)
    center_fit(draw, "deterministic script.", 270, 760, 46, ACCENT, 28)
    panel(draw, (1210, 170, 1465, 360), fill=(7, 13, 24), outline=BLUE, width=4, radius=28)
    center_box_text(draw, "45 KB", (1210, 170, 1465, 360), 245, 44, GOLD, 24)
    small = [(240, "No editor"), (500, "No timeline"), (760, "No manual"), (1020, "No politics")]
    for x, label in small:
        panel(draw, (x, 400, x + 210, 465), fill=PANEL, outline=ACCENT, width=3, radius=18)
        center_box_text(draw, label, (x, 400, x + 210, 465), 418, 24, WHITE, 15)
    center_fit(draw, "creative_sequence = resolve(structure)", 512, 1250, 31, ACCENT, 20)
    footer_band(draw, "The concept resolves from structure. The film resolves from structure.", 592, WHITE, GOLD, 260, 1340)
    return add_vignette(light_sweep(add_particles(img, t, 20, ACCENT, 0.55), t, BLUE), 80)

def draw_final_frame(t, result):
    img = gradient((2, 4, 10), (5, 14, 30), (14, 36, 64)).convert("RGB")
    draw = ImageDraw.Draw(img)
    glow = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    pulse = 40 + int(35 * (0.5 + 0.5 * math.sin(t * 5)))
    gd.rounded_rectangle((260, 70, 1340, 590), radius=38, fill=(92, 242, 210, pulse))
    glow = glow.filter(ImageFilter.GaussianBlur(36))
    img = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")
    draw = ImageDraw.Draw(img)
    panel(draw, (300, 78, 1300, 590), fill=(7, 13, 24), outline=(22, 38, 68), width=2, radius=34)
    center_fit(draw, "TRUST WAITS", 125, 920, 68, WHITE, 36)
    center_fit(draw, "FOR STRUCTURE", 212, 920, 68, GOLD, 36)
    center_fit(draw, "A result appears only when it is supported.", 312, 900, 38, ACCENT, 24)
    center_fit(draw, "Join the Structural Revolution", 410, 900, 48, WHITE, 28)
    center_fit(draw, "github.com/OMPSHUNYAYA", 488, 900, 34, GREEN, 20)
    center_fit(draw, "SLANG-Voting | Structural Admissibility Cinema", 548, 900, 23, GOLD, 16)
    return add_vignette(add_particles(img, t, 22, GOLD, 0.55), 75)



def draw_shunyaya_formula_frame(t, result):
    img = gradient((2, 5, 12), (5, 14, 30), (12, 32, 58)).convert("RGB")
    draw = ImageDraw.Draw(img)
    center_fit(draw, "SHUNYAYA STRUCTURAL GUARANTEE", 56, 1400, 58, GOLD, 30)
    center_fit(draw, "Classical result preserved. Structure reveals support.", 132, 1320, 38, MUTED, 24)
    panel(draw, (230, 210, 1370, 355), fill=(7, 13, 24), outline=ACCENT, width=4, radius=28)
    center_fit(draw, "phi((m, a, s)) = m", 250, 1080, 64, GOLD, 34)
    panel(draw, (280, 405, 1320, 520), fill=(7, 13, 24), outline=GOLD, width=3, radius=24)
    center_fit(draw, "m remains the declared classical result", 430, 960, 36, WHITE, 22)
    center_fit(draw, "a and s reveal structural admissibility", 470, 960, 34, ACCENT, 20)
    footer_band(draw, "Nothing is altered. Unsupported visibility is refused.", 592, WHITE, GOLD, 315, 1285)
    return add_vignette(add_particles(light_sweep(img, t, ACCENT), t, 18, GOLD, 0.50), 85)


def draw_parallel_verification_frame(t, result):
    img = gradient((3, 7, 15), (8, 24, 48), (16, 42, 72)).convert("RGB")
    draw = ImageDraw.Draw(img)
    center_fit(draw, "INDEPENDENT VERIFICATION", 52, 1400, 62, GOLD, 32)
    center_fit(draw, "Same structure. Same identity. Anywhere.", 132, 1380, 40, MUTED, 24)
    observers = [("OBSERVER 1", "Region A", BLUE), ("OBSERVER 2", "Region B", ACCENT), ("OBSERVER 3", "Region C", GREEN)]
    for i, (label, loc, color) in enumerate(observers):
        x = 360 + i * 440
        panel(draw, (x - 160, 230, x + 160, 490), fill=(7, 13, 24), outline=color, width=3, radius=24)
        center_box_text(draw, label, (x - 160, 230, x + 160, 280), 246, 30, color, 20)
        center_box_text(draw, loc, (x - 160, 270, x + 160, 320), 286, 24, MUTED, 16)
        center_box_text(draw, "structure", (x - 160, 320, x + 160, 360), 328, 24, WHITE, 16)
        center_box_text(draw, result["structure_certificate"], (x - 160, 350, x + 160, 395), 365, 28, GOLD, 18)
        center_box_text(draw, "winner_identity", (x - 160, 400, x + 160, 440), 408, 23, WHITE, 15)
        center_box_text(draw, result["winner_identity"], (x - 160, 430, x + 160, 475), 445, 30, GREEN, 18)
    footer_band(draw, "Independent replay can reproduce the same identity.", 592, WHITE, GOLD, 330, 1270)
    return add_vignette(add_particles(light_sweep(img, t, ACCENT), t, 18, GOLD, 0.48), 80)


def draw_jurisdiction_patterns_frame(t):
    img = gradient((2, 6, 14), (7, 20, 42), (14, 36, 68)).convert("RGB")
    draw = ImageDraw.Draw(img)
    center_fit(draw, "ONE ENGINE. LOCAL RULES.", 52, 1400, 64, GOLD, 34)
    center_fit(draw, "Every place declares its own structure.", 132, 1380, 40, MUTED, 24)
    examples = [
        ("Country A", "plurality", "highest count wins", BLUE),
        ("State B", "majority", "threshold required", ACCENT),
        ("Country C", "ranked", "redistribute by rule", GREEN),
        ("Region D", "allocation", "declared seats rule", PURPLE)
    ]
    for i, (place, system, rule, color) in enumerate(examples):
        x = 190 + (i % 2) * 620
        y = 220 + (i // 2) * 185
        panel(draw, (x, y, x + 540, y + 145), fill=(7, 13, 24), outline=color, width=3, radius=22)
        center_box_text(draw, place, (x, y, x + 540, y + 50), y + 22, 30, color, 20)
        center_box_text(draw, system, (x, y + 50, x + 540, y + 90), y + 62, 28, WHITE, 18)
        center_box_text(draw, rule, (x, y + 92, x + 540, y + 135), y + 105, 24, MUTED, 16)
    footer_band(draw, "The engine stays universal. The rules stay local.", 592, WHITE, GOLD, 340, 1260)
    return add_vignette(add_particles(img, t, 16, ACCENT, 0.48), 90)


def draw_input_warning_frame(t, result):
    img = gradient((4, 8, 18), (10, 22, 42), (20, 36, 58)).convert("RGB")
    draw = ImageDraw.Draw(img)
    center_fit(draw, "STRUCTURE MUST BE TRUE", 52, 1400, 64, GOLD, 34)
    center_fit(draw, "A clean resolver cannot repair false input.", 132, 1380, 40, MUTED, 24)
    panel(draw, (150, 220, 720, 500), fill=(7, 13, 24), outline=GREEN, width=3, radius=24)
    center_box_text(draw, "RECORDED STRUCTURE", (150, 220, 720, 275), 238, 29, GREEN, 18)
    center_box_text(draw, result["structure_certificate"], (150, 285, 720, 340), 304, 36, GOLD, 22)
    center_box_text(draw, "winner_identity", (150, 350, 720, 395), 362, 27, WHITE, 18)
    center_box_text(draw, result["winner_identity"], (150, 395, 720, 455), 414, 34, GREEN, 20)
    panel(draw, (880, 220, 1450, 500), fill=(34, 10, 20), outline=RED, width=3, radius=24)
    center_box_text(draw, "FALSE OR ALTERED INPUT", (880, 220, 1450, 275), 238, 29, RED, 18)
    center_box_text(draw, "different signature", (880, 285, 1450, 340), 304, 33, RED, 20)
    center_box_text(draw, "different support", (880, 350, 1450, 405), 368, 30, MUTED, 18)
    center_box_text(draw, "or no support", (880, 400, 1450, 455), 418, 30, MUTED, 18)
    footer_band(draw, "Consistency is proven. Input truth still needs governance.", 592, WHITE, GOLD, 290, 1310)
    return add_vignette(add_particles(img, t, 18, RED, 0.35), 95)


def draw_code_kernel_frame(t, result):
    img = gradient((3, 7, 16), (8, 22, 44), (16, 40, 70)).convert("RGB")
    draw = ImageDraw.Draw(img)
    center_fit(draw, "TINY STRUCTURAL KERNEL", 52, 1400, 64, GOLD, 34)
    center_fit(draw, "A small script reveals the admissibility state.", 132, 1380, 38, MUTED, 24)
    panel(draw, (170, 205, 1430, 520), fill=(5, 10, 20), outline=ACCENT, width=3, radius=20)
    code_lines = [
        "rules = declared_structure",
        "propagate until stable",
        "if complete AND consistent:",
        "    result_visible = true",
        "else:",
        "    no forced declaration"
    ]
    y = 235
    for line in code_lines:
        color = GOLD if "visible" in line or "forced" in line else WHITE
        draw.text((240, y), line, font=FONT_CODE, fill=color)
        y += 43
    center_fit(draw, "No hidden guess. No premature visibility.", 522, 1280, 34, ACCENT, 22)
    footer_band(draw, "The kernel demonstrates replay, not legal certification.", 600, WHITE, GOLD, 330, 1270)
    return add_vignette(add_particles(light_sweep(img, t, GOLD), t, 14, ACCENT, 0.50), 85)

def make_frame(kind, local_t, structure, result):
    if kind == "waiting":
        return draw_waiting_frame(local_t)
    if kind == "process_pressure":
        return draw_process_pressure_frame(local_t)
    if kind == "infrastructure_bias":
        return draw_infrastructure_bias_frame(local_t)
    if kind == "participation_remains":
        return draw_participation_remains_frame(local_t)
    if kind == "structural_question":
        return draw_structural_question_frame(local_t)
    if kind == "structure_recorded":
        return draw_structure_recorded_frame(local_t)
    if kind == "validation":
        return draw_validation_frame(local_t, result)
    if kind == "counting_reveal":
        return draw_counting_reveal_frame(local_t, result)
    if kind == "shunyaya_formula":
        return draw_shunyaya_formula_frame(local_t, result)
    if kind == "code_kernel":
        return draw_code_kernel_frame(local_t, result)
    if kind == "parallel_verification":
        return draw_parallel_verification_frame(local_t, result)
    if kind == "jurisdiction_patterns":
        return draw_jurisdiction_patterns_frame(local_t)
    if kind == "input_warning":
        return draw_input_warning_frame(local_t, result)
    if kind == "formula":
        return draw_formula_frame(local_t)
    if kind == "states":
        return draw_states_frame(local_t)
    if kind == "silence":
        return draw_silence_frame(local_t)
    if kind == "fairness":
        return draw_fairness_frame(local_t)
    if kind == "replay":
        return draw_replay_frame(local_t, result)
    if kind == "not_replacement":
        return draw_not_replacement_frame(local_t)
    if kind == "eliminates":
        return draw_eliminates_frame(local_t)
    if kind == "civilization":
        return draw_civilization_frame(local_t)
    if kind == "open_source":
        return draw_open_source_frame(local_t)
    if kind == "did_you_know":
        return draw_did_you_know_frame(local_t)
    return draw_final_frame(local_t, result)


def fade(a, b, amount):
    return Image.blend(a, b, amount)


def render_video():
    structure = base_voting_structure()
    result = resolve_voting(structure)
    timeline = [
        ("waiting", 7.5),
        ("process_pressure", 7.0),
        ("infrastructure_bias", 7.4),
        ("participation_remains", 7.6),
        ("structural_question", 6.8),
        ("shunyaya_formula", 7.6),
        ("structure_recorded", 7.6),
        ("code_kernel", 6.8),
        ("counting_reveal", 9.6),
        ("validation", 7.2),
        ("parallel_verification", 7.8),
        ("jurisdiction_patterns", 7.6),
        ("input_warning", 7.4),
        ("states", 7.2),
        ("silence", 6.8),
        ("fairness", 7.4),
        ("replay", 7.0),
        ("not_replacement", 7.2),
        ("eliminates", 7.0),
        ("civilization", 7.6),
        ("open_source", 6.8),
        ("did_you_know", 7.2),
        ("final", 8.6),
    ]
    writer = cv2.VideoWriter(OUT_VIDEO, cv2.VideoWriter_fourcc(*"mp4v"), FPS, (WIDTH, HEIGHT))
    poster = None
    previous = None
    frame_number = 0
    total_frames = sum(int(seconds * FPS) for _, seconds in timeline)
    for kind, seconds in timeline:
        frames = int(seconds * FPS)
        for i in range(frames):
            local_t = i / max(1, frames - 1)
            frame = make_frame(kind, local_t, structure, result)
            if previous is not None and i < int(0.45 * FPS):
                amount = i / max(1, int(0.45 * FPS) - 1)
                frame = fade(previous, frame, amount)
            if frame_number == int(total_frames * 0.53):
                poster = frame.copy()
            arr = cv2.cvtColor(np.array(frame), cv2.COLOR_RGB2BGR)
            writer.write(arr)
            previous = frame
            frame_number += 1
    writer.release()
    if poster:
        poster.save(OUT_POSTER)
    video_hash = file_sha256(OUT_VIDEO)
    verify = {
        "version": VERSION,
        "principle": "winner_visibility = resolve(structure) | phi((m, a, s)) = m",
        "law": "winner_visible iff structure_mature",
        "structure_signature": result["structure_signature"],
        "structure_certificate": result["structure_certificate"],
        "winner_identity": result["winner_identity"],
        "video_sha256": video_hash,
        "final_certificate": certificate(result["structure_signature"] + "|" + video_hash)
    }
    with open(OUT_VERIFY, "w", encoding="utf-8") as f:
        f.write("Shunyaya Structural Election Admissibility Cinema VERIFY\n")
        f.write("Generic Civic Structural Admissibility Demonstration\n\n")
        f.write("Principle: winner_visibility = resolve(structure)\n")
        f.write("Shunyaya collapse: phi((m, a, s)) = m\n")
        f.write("Law: winner_visible iff structure_mature\n")
        f.write("Structure maturity: complete AND consistent\n\n")
        for key in ["structure_signature", "structure_certificate", "winner_identity", "video_sha256", "final_certificate"]:
            f.write(key + ": " + verify[key] + "\n")
        f.write("\nBoundaries:\n")
        f.write("citizen participation remains unchanged\n")
        f.write("institutions and legal authority remain external\n")
        f.write("the demo studies structural admissibility only\n")
        f.write("incomplete structure -> no forced visibility\n")
        f.write("same structure -> same winner_identity\n")
        f.write("consistency is proven; input truth still needs governance\n")
        f.write("this is a structural admissibility demonstration, not legal certification\n")
    return verify


def main():
    verify = render_video()
    print("Shunyaya Structural Election Admissibility Cinema v2.7")
    print("Created: " + OUT_VIDEO)
    print("Created: " + OUT_POSTER)
    print("Created: " + OUT_VERIFY)
    print("winner_identity: " + verify["winner_identity"])
    print("final_certificate: " + verify["final_certificate"])
    print("Principle: winner_visibility = resolve(structure)")
    print("Shunyaya collapse: phi((m, a, s)) = m")
    print("Law: winner_visible iff structure_mature")


if __name__ == "__main__":
    main()
