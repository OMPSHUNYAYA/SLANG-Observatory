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
OUT_VIDEO = "SLANG_Exam_Structural_Cinema_v2_7.mp4"
OUT_POSTER = "SLANG_Exam_Structural_Cinema_Poster_v2_7.png"
OUT_VERIFY = "SLANG_Exam_Structural_Cinema_VERIFY_v2_7.txt"

BG = (5, 8, 15)
DEEP = (4, 7, 13)
PANEL = (9, 15, 28)
PANEL2 = (13, 22, 40)
WHITE = (248, 251, 255)
MUTED = (190, 205, 228)
GOLD = (255, 214, 112)
ACCENT = (105, 245, 195)
BLUE = (115, 170, 255)
RED = (255, 94, 112)
ORANGE = (255, 174, 72)
GREEN = (85, 228, 145)
PURPLE = (182, 142, 255)
LINE = (72, 88, 124)
DARK_RED = (48, 12, 22)
DARK_GREEN = (10, 38, 25)

SAFE_TOP = 48
SAFE_BOTTOM = 535
TEXT_FLOOR = 535


def load_font(size, bold=False):
    try:
        if os.name == "nt":
            path = r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf"
        else:
            path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


FONT_HERO = load_font(68, True)
FONT_HERO2 = load_font(60, True)
FONT_TITLE = load_font(52, True)
FONT_BIG = load_font(44, True)
FONT_MED = load_font(34, True)
FONT_BODY = load_font(30, True)
FONT_SMALL = load_font(28, True)
FONT_TINY = load_font(24, True)
FONT_CODE = load_font(28, True)


def text_size(draw, text, font):
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0], box[3] - box[1]


def fit_font(draw, text, start, max_width, min_size=18, bold=True):
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


def right(draw, text, x, y, font, color=WHITE):
    w, _ = text_size(draw, text, font)
    draw.text((x - w, y), text, font=font, fill=color)


def center_box(draw, text, box, y, font, color=WHITE):
    f = fit_font(draw, text, font.size, box[2] - box[0] - 38, 20, True)
    w, _ = text_size(draw, text, f)
    draw.text((box[0] + (box[2] - box[0] - w) // 2, y), text, font=f, fill=color)



def footer_band(draw, text, y=535, color=WHITE, outline=GOLD, x1=235, x2=1365):
    y = min(y, TEXT_FLOOR)
    panel(draw, (x1, y - 24, x2, y + 34), fill=(7, 12, 22), outline=outline, width=3, radius=18)
    f = fit_font(draw, text, 25, (x2 - x1) - 90, 19, True)
    center(draw, text, y - 4, f, color)


def safe_center(draw, text, y, font, color=WHITE):
    yy = min(y, TEXT_FLOOR)
    center(draw, text, yy, font, color)


def center_two_lines(draw, line1, line2, y1, y2, font1, font2, color1=WHITE, color2=ACCENT):
    center(draw, line1, y1, font1, color1)
    center(draw, line2, y2, font2, color2)


def add_particles(img, t=0.0, count=18, color=ACCENT, intensity=0.7):
    layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    seed = int(t * 10000) + count * 97 + color[0] * 3 + color[1] * 5 + color[2] * 7
    rng = np.random.default_rng(seed)
    for i in range(count):
        x = int(rng.integers(70, WIDTH - 70))
        y = int(rng.integers(90, TEXT_FLOOR - 20))
        r = int(rng.integers(2, 6))
        alpha = int((85 + rng.integers(0, 100)) * intensity)
        d.ellipse((x - r, y - r, x + r, y + r), fill=(color[0], color[1], color[2], min(220, alpha)))
    return Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")

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


def base_exam_structure():
    return {
        "exam_id": "SLANG-EXAM-CIVILIZATION-DEMO",
        "exam_time": "open",
        "center_authorized": "true",
        "candidate_registered": "true",
        "total_questions": 5,
        "total_marks": 10,
        "blueprint": {
            "algebra": 2,
            "geometry": 1,
            "reasoning": 1,
            "application": 1,
            "difficulty_mix": "easy:1,medium:3,hard:1"
        },
        "approved_questions": [
            {"id": "Q101", "topic": "Algebra", "marks": 2, "difficulty": "Medium", "text": "Solve: 2x + 3 = 11"},
            {"id": "Q102", "topic": "Algebra", "marks": 2, "difficulty": "Medium", "text": "If y = 3x and x = 7, find y."},
            {"id": "Q103", "topic": "Algebra", "marks": 2, "difficulty": "Hard", "text": "Find x when 5x - 4 = 2x + 11."},
            {"id": "Q204", "topic": "Geometry", "marks": 2, "difficulty": "Medium", "text": "Find the area of a triangle with base 8 and height 5."},
            {"id": "Q205", "topic": "Geometry", "marks": 2, "difficulty": "Hard", "text": "Find the perimeter of a square with side 9."},
            {"id": "Q317", "topic": "Reasoning", "marks": 2, "difficulty": "Easy", "text": "Complete the pattern: 2, 4, 8, 16, ?"},
            {"id": "Q318", "topic": "Reasoning", "marks": 2, "difficulty": "Medium", "text": "Which number is the odd one out: 9, 16, 25, 31?"},
            {"id": "Q418", "topic": "Application", "marks": 2, "difficulty": "Hard", "text": "A train covers 180 km in 3 hours. Find its average speed."},
            {"id": "Q419", "topic": "Application", "marks": 2, "difficulty": "Medium", "text": "A shop gives 10% discount on 500. Find the final price."}
        ]
    }


def canonical_question_bank(structure):
    return sorted(structure.get("approved_questions", []), key=lambda q: q["id"])


def required_topic_counts(structure):
    blueprint = structure.get("blueprint", {})
    return {
        "Algebra": blueprint.get("algebra", 0),
        "Geometry": blueprint.get("geometry", 0),
        "Reasoning": blueprint.get("reasoning", 0),
        "Application": blueprint.get("application", 0),
    }


def select_question_paper(structure):
    selected = []
    bank = canonical_question_bank(structure)
    for topic, needed in required_topic_counts(structure).items():
        candidates = [q for q in bank if q.get("topic") == topic and q.get("marks") == 2]
        selected.extend(candidates[:needed])
    return tuple(q["id"] for q in selected[:structure.get("total_questions", 0)])


def topic_coverage_ready(structure):
    bank = canonical_question_bank(structure)
    for topic, needed in required_topic_counts(structure).items():
        available = len([q for q in bank if q.get("topic") == topic and q.get("marks") == 2])
        if available < needed:
            return False
    return True


def resolve_exam(structure):
    state = deepcopy(structure)
    rules = [
        ("window_valid", "true", lambda s: s.get("exam_time") == "open"),
        ("center_valid", "true", lambda s: s.get("center_authorized") == "true"),
        ("candidate_valid", "true", lambda s: s.get("candidate_registered") == "true"),
        ("blueprint_valid", "true", lambda s: s.get("total_questions") == 5 and s.get("total_marks") == 10),
        ("bank_ready", "true", lambda s: len(s.get("approved_questions", [])) >= s.get("total_questions", 0) and topic_coverage_ready(s)),
        ("paper_visible", "true", lambda s:
            s.get("window_valid") == "true" and
            s.get("center_valid") == "true" and
            s.get("candidate_valid") == "true" and
            s.get("blueprint_valid") == "true" and
            s.get("bank_ready") == "true"
        ),
        ("question_paper", lambda s: select_question_paper(s), lambda s: s.get("paper_visible") == "true"),
    ]
    changed = True
    while changed:
        changed = False
        for key, value, cond in rules:
            if cond(state):
                new_value = value(state) if callable(value) else value
                if state.get(key) != new_value:
                    state[key] = new_value
                    changed = True
    result = {
        "structure_signature": structure_signature(structure),
        "structure_certificate": structure_signature(structure)[:16],
        "state": "RESOLVED" if state.get("paper_visible") == "true" else "ABSTAIN",
        "paper_visible": state.get("paper_visible") == "true",
        "paper_identity": certificate(state.get("question_paper", "NO_PAPER")),
        "resolved_state": state
    }
    return result


def gradient(top, mid, bottom):
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img)
    for y in range(HEIGHT):
        t = y / (HEIGHT - 1)
        if t < 0.52:
            p = t / 0.52
            c = tuple(int(top[i] + (mid[i] - top[i]) * p) for i in range(3))
        else:
            p = (t - 0.52) / 0.48
            c = tuple(int(mid[i] + (bottom[i] - mid[i]) * p) for i in range(3))
        draw.line((0, y, WIDTH, y), fill=c)
    return img


def add_vignette(img, strength=130):
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    for i in range(18):
        alpha = int(strength * (i / 18) ** 2)
        d.rectangle((i * 18, i * 12, WIDTH - i * 18, HEIGHT - i * 12), outline=(0, 0, 0, alpha), width=28)
    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


def draw_glow(img, x, y, r, color, pulse=0.0):
    layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for i in range(16, 0, -1):
        rr = int(r * (1 + i * 0.18 + pulse * 0.03))
        alpha = int(8 + i * 7)
        d.ellipse((x - rr, y - rr, x + rr, y + rr), fill=(color[0], color[1], color[2], alpha))
    d.ellipse((x - r, y - r, x + r, y + r), fill=(color[0], color[1], color[2], 245))
    img.alpha_composite(layer)


def draw_school_exterior(draw, t):
    panel(draw, (260, 270, 1340, 720), fill=(18, 30, 48), outline=(90, 110, 150), width=4, radius=18)
    draw.polygon([(210, 280), (800, 120), (1390, 280)], fill=(28, 42, 68), outline=GOLD)
    center(draw, "NATIONAL EXAMINATION CENTER", 315, FONT_BIG, GOLD)
    for i in range(8):
        x = 345 + i * 130
        panel(draw, (x, 405, x + 70, 560), fill=(26, 46, 74), outline=BLUE, width=2, radius=10)
        if i % 2 == 0:
            draw.rectangle((x + 10, 420, x + 60, 545), fill=(255, 225, 130))
    panel(draw, (715, 535, 885, 720), fill=(16, 22, 36), outline=GOLD, width=3, radius=14)
    for i in range(10):
        x = 180 + i * 140 + int(math.sin(t * 2 + i) * 4)
        draw.ellipse((x, 710, x + 24, 734), fill=(30, 45, 65))
        draw.line((x + 12, 734, x + 12, 785), fill=(30, 45, 65), width=5)


def draw_classroom(draw, t, paper_visible=False):
    draw.rectangle((0, 0, WIDTH, HEIGHT), fill=(18, 28, 45))
    draw.polygon([(0, 650), (WIDTH, 650), (WIDTH, HEIGHT), (0, HEIGHT)], fill=(36, 30, 25))
    panel(draw, (130, 95, 1470, 255), fill=(8, 20, 30), outline=ACCENT if paper_visible else LINE, width=4, radius=16)
    title = "RESOLVED PAPER VISIBLE" if paper_visible else "WAITING FOR STRUCTURAL MATURITY"
    center(draw, title, 125, FONT_TITLE, GREEN if paper_visible else GOLD)
    subtitle = "paper_visible = true" if paper_visible else "No paper exists yet"
    center(draw, subtitle, 190, FONT_MED, GREEN if paper_visible else MUTED)
    for row in range(3):
        for col in range(6):
            x = 210 + col * 210
            y = 370 + row * 110
            draw.rounded_rectangle((x, y, x + 105, y + 42), radius=12, fill=(70, 50, 36), outline=(115, 85, 60), width=2)
            draw.ellipse((x + 35, y - 32, x + 68, y + 2), fill=(42, 48, 68))
            draw.line((x + 52, y + 2, x + 52, y + 44), fill=(42, 48, 68), width=5)
            if paper_visible:
                draw.rounded_rectangle((x + 15, y + 8, x + 92, y + 35), radius=5, fill=(245, 248, 250), outline=GREEN)
    draw.rounded_rectangle((40, 585, 190, 720), radius=12, fill=(25, 32, 45), outline=BLUE, width=3)
    draw.ellipse((90, 538, 135, 583), fill=(44, 52, 75))
    draw.line((112, 583, 112, 670), fill=(44, 52, 75), width=8)
    draw.text((58, 725), "Invigilator", font=FONT_TINY, fill=MUTED)


def draw_status_tile(draw, x, y, label, active, delay=0.0):
    color = GREEN if active else RED
    fill = DARK_GREEN if active else DARK_RED
    box = (x, y, x + 285, y + 84)
    panel(draw, box, fill=fill, outline=color, width=3, radius=18)
    mark = "✓" if active else "×"
    draw.text((x + 22, y + 19), mark, font=FONT_MED, fill=color)
    f = fit_font(draw, label, 28, 185, 21, True)
    draw.text((x + 78, y + 15), label, font=f, fill=WHITE)
    draw.text((x + 78, y + 49), "true" if active else "not satisfied", font=FONT_TINY, fill=color)


def draw_dashboard(draw, result, reveal_count=5):
    panel(draw, (110, 42, 1490, 545), fill=(7, 12, 24), outline=BLUE, width=3, radius=28)
    center(draw, "SLANG-Exam Structural Maturity Dashboard", 75, FONT_TITLE, GOLD)
    center(draw, "paper_visible iff structure_mature", 134, FONT_MED, ACCENT)
    labels = ["window_valid", "center_valid", "candidate_valid", "blueprint_valid", "bank_ready"]
    positions = [(180, 195), (660, 195), (1100, 195), (180, 320), (660, 320)]
    for i, label in enumerate(labels):
        active = i < reveal_count and result["resolved_state"].get(label) == "true"
        x, y = positions[i]
        draw_status_tile(draw, x, y, label, active)
    visible = reveal_count >= 5 and result["paper_visible"]
    panel(draw, (465, 420, 1135, 500), fill=DARK_GREEN if visible else (18, 22, 35), outline=GREEN if visible else LINE, width=4, radius=22)
    center(draw, "paper_visible = true" if visible else "paper_visible does not exist", 436, FONT_MED, GREEN if visible else MUTED)
    center(draw, "Paper admitted by structure" if visible else "Absence is valid structure", 474, FONT_TINY, GREEN if visible else MUTED)

def draw_paper(draw, structure, result):
    panel(draw, (255, 35, 1345, 505), fill=(244, 247, 250), outline=GOLD, width=5, radius=22)
    center(draw, "RESOLVED QUESTION PAPER", 58, FONT_TITLE, (8, 22, 48))
    center(draw, "Admitted only after structural maturity", 108, FONT_SMALL, (40, 70, 100))
    ids = list(result["resolved_state"].get("question_paper", []))
    bank = {q["id"]: q for q in structure["approved_questions"]}
    questions = [bank[qid] for qid in ids]
    y = 145
    for i, q in enumerate(questions, 1):
        line = str(i) + ". " + q["text"]
        f = fit_font(draw, line, 26, 960, 21)
        draw.text((305, y), line, font=f, fill=(10, 20, 35))
        draw.text((330, y + 28), q["id"] + " | " + q["topic"] + " | " + q["difficulty"] + " | " + str(q["marks"]) + " marks", font=load_font(19, True), fill=(55, 80, 110))
        y += 57
    panel(draw, (395, 454, 1205, 493), fill=(232, 239, 247), outline=(120, 150, 185), width=2, radius=14)
    center(draw, "paper_identity: " + result["paper_identity"], 461, FONT_TINY, (8, 22, 48))

def draw_old_world_frame(t):
    img = gradient((10, 12, 20), (20, 24, 35), (35, 32, 40)).convert("RGBA")
    draw = ImageDraw.Draw(img)
    draw_school_exterior(draw, t)
    panel(draw, (120, 70, 1480, 160), fill=(50, 10, 20), outline=RED, width=4, radius=20)
    center(draw, "BREAKING: QUESTION PAPER LEAK FEAR", 92, FONT_TITLE, WHITE)
    panel(draw, (300, 540, 1300, 600), fill=(8, 12, 22), outline=GOLD, width=2, radius=18)
    center(draw, "Retests. Panic. Secrecy chains. Public trust collapse.", 557, FONT_MED, WHITE)
    return add_vignette(img.convert("RGB"), 160)

def draw_question_frame(t):
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img)
    panel(draw, (300, 150, 1300, 530), fill=(7, 13, 24), outline=(22, 38, 68), width=2, radius=34)
    center(draw, "What if the final paper", 210, FONT_HERO, WHITE)
    center(draw, "did not exist yet?", 315, FONT_HERO, GOLD)
    center(draw, "No object -> no surface -> no leak", 455, FONT_BIG, ACCENT)
    return add_vignette(img, 120)


def draw_structure_world_frame(t):
    img = gradient((4, 9, 22), (12, 34, 60), (22, 48, 82)).convert("RGBA")
    draw = ImageDraw.Draw(img)
    for i in range(10):
        x = 100 + i * 160
        y = 170 + int(math.sin(t * 3 + i) * 12)
        draw.ellipse((x - 18, y - 18, x + 18, y + 18), fill=ACCENT)
        if i > 0:
            draw.line((x - 160, 170 + int(math.sin(t * 3 + i - 1) * 12), x, y), fill=(105, 245, 195), width=3)
    center(draw, "Only structure exists before the exam", 290, FONT_TITLE, GOLD)
    center(draw, "Syllabus. Blueprint. Gates. Question bank. Authorization.", 360, FONT_MED, WHITE)
    center(draw, "No final paper object exists.", 470, FONT_BIG, ACCENT)
    return add_vignette(img.convert("RGB"), 100)



def draw_dependency_elimination_frame(t):
    img = gradient((5, 8, 16), (9, 18, 36), (15, 32, 58)).convert("RGBA")
    draw = ImageDraw.Draw(img)
    center(draw, "DEPENDENCY ELIMINATION", 52, FONT_HERO, GOLD)
    center(draw, "All assumed dependencies collapse to structure", 118, FONT_MED, ACCENT)
    deps = ["CLOCKS", "SECRECY", "COURIERS", "PANIC"]
    for i, dep in enumerate(deps):
        x = 250 + i * 365
        panel(draw, (x - 105, 190, x + 105, 310), fill=(28, 8, 18), outline=RED, width=3, radius=22)
        draw.ellipse((x - 34, 211, x + 34, 279), outline=RED, width=5)
        draw.line((x - 34, 279, x + 34, 211), fill=RED, width=5)
        w, _ = text_size(draw, dep, FONT_TINY)
        draw.text((x - w // 2, 326), dep, font=FONT_TINY, fill=WHITE)
    for row in range(4):
        for col in range(7):
            x = 330 + col * 155
            y = 380 + row * 38
            pulse = 0.45 + 0.55 * math.sin(t * 7 + row + col)
            fill = (20, int(120 + 95 * pulse), int(105 + 95 * pulse)) if (row + col) % 2 == 0 else (18, 28, 48)
            draw.rounded_rectangle((x - 22, y - 13, x + 22, y + 13), radius=7, fill=fill, outline=GOLD)
    footer_band(draw, "Correctness preserved. Paper visibility admitted only by mature structure.", 535, ACCENT, GOLD)
    img = add_particles(img.convert("RGB"), t, 20, ACCENT, 0.7)
    return add_vignette(img, 70)

def draw_paper_formation_frame(t, structure, result):
    img = gradient((4, 9, 20), (9, 24, 48), (18, 42, 72)).convert("RGB")
    draw = ImageDraw.Draw(img)
    center(draw, "How the Paper Forms", 40, FONT_HERO, GOLD)
    center(draw, "Question bank stays as building blocks. Blueprint admits the final set.", 118, FONT_MED, WHITE)

    bank_box = (70, 165, 520, 505)
    blue_box = (575, 165, 1025, 505)
    set_box = (1080, 165, 1530, 505)
    panel(draw, bank_box, fill=(8, 14, 28), outline=BLUE, width=4, radius=24)
    panel(draw, blue_box, fill=(8, 14, 28), outline=GOLD, width=4, radius=24)
    panel(draw, set_box, fill=(8, 14, 28), outline=ACCENT, width=4, radius=24)

    center_box(draw, "APPROVED QUESTION BANK", bank_box, 192, FONT_SMALL, BLUE)
    center_box(draw, "PAPER BLUEPRINT", blue_box, 192, FONT_SMALL, GOLD)
    center_box(draw, "ADMISSIBLE SET", set_box, 192, FONT_SMALL, ACCENT)

    bank_lines = [
        "Q101 Algebra Medium",
        "Q102 Algebra Medium",
        "Q103 Algebra Hard",
        "Q204 Geometry Medium",
        "Q205 Geometry Hard",
        "Q317 Reasoning Easy",
        "Q318 Reasoning Medium",
        "Q418 Application Hard",
        "Q419 Application Medium",
    ]
    y = 238
    visible_bank = min(len(bank_lines), 3 + int(t * 7))
    bank_font = load_font(21, True)
    for line in bank_lines[:visible_bank]:
        draw.text((105, y), line, font=bank_font, fill=WHITE)
        y += 28

    blueprint_lines = [
        "total_questions = 5",
        "total_marks = 10",
        "Algebra = 2",
        "Geometry = 1",
        "Reasoning = 1",
        "Application = 1",
        "difficulty_mix valid",
        "no duplicate limits",
    ]
    y = 238
    visible_blueprint = min(len(blueprint_lines), 2 + int(t * 7))
    blueprint_font = load_font(21, True)
    for line in blueprint_lines[:visible_blueprint]:
        draw.text((620, y), line, font=blueprint_font, fill=WHITE)
        y += 30

    selected = list(result["resolved_state"].get("question_paper", []))
    y = 238
    visible_selected = min(len(selected), int(max(0, t - 0.25) * 8))
    for qid in selected[:visible_selected]:
        draw.text((1125, y), qid + " admitted", font=FONT_SMALL, fill=ACCENT)
        y += 48

    draw.line((525, 370, 570, 370), fill=GOLD, width=6)
    draw.polygon([(570, 370), (548, 357), (548, 383)], fill=GOLD)
    draw.line((1030, 370, 1075, 370), fill=GOLD, width=6)
    draw.polygon([(1075, 370), (1053, 357), (1053, 383)], fill=GOLD)

    footer_band(draw, "Selection is declared structure, not hidden randomness.", 535, ACCENT, GOLD, 250, 1350)
    img = add_particles(img, t, 10, GOLD, 0.50)
    return add_vignette(img, 75)

def draw_countdown_frame(t, result):
    img = Image.new("RGB", (WIDTH, HEIGHT), (18, 28, 45))
    draw = ImageDraw.Draw(img)
    draw_classroom(draw, t, False)
    seconds = max(0, int(5 - t * 5))
    panel(draw, (610, 280, 990, 370), fill=(8, 15, 28), outline=GOLD, width=4, radius=20)
    center(draw, "Exam starts in " + str(seconds), 305, FONT_BIG, GOLD)
    footer_band(draw, "Paper state: structurally absent", 535, ACCENT, GOLD)
    return add_vignette(img, 90)


def draw_gate_frame(t, result):
    img = gradient((4, 8, 18), (8, 20, 42), (15, 36, 62)).convert("RGB")
    draw = ImageDraw.Draw(img)
    reveal = min(5, int(t * 6))
    draw_dashboard(draw, result, reveal)
    return add_vignette(img, 80)


def draw_resolution_frame(t, structure, result):
    img = Image.new("RGB", (WIDTH, HEIGHT), (18, 28, 45))
    draw = ImageDraw.Draw(img)
    draw_classroom(draw, t, True)
    if t > 0.30:
        alpha = min(1.0, (t - 0.30) / 0.35)
        paper = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        pd = ImageDraw.Draw(paper)
        draw_paper(pd, structure, result)
        paper.putalpha(int(255 * alpha))
        img = Image.alpha_composite(img.convert("RGBA"), paper).convert("RGB")
        draw = ImageDraw.Draw(img)
    footer_band(draw, "The paper was not released. It was admitted.", 535, WHITE, GOLD)
    if t > 0.45:
        img = add_particles(img, t, 28, GOLD, 0.85)
    return add_vignette(img, 60)

def draw_failure_frame(t, structure):
    invalid = deepcopy(structure)
    invalid["center_authorized"] = "false"
    result = resolve_exam(invalid)
    img = gradient((16, 6, 16), (36, 12, 24), (25, 18, 35)).convert("RGB")
    draw = ImageDraw.Draw(img)
    draw_dashboard(draw, result, 5)
    footer_band(draw, "Unauthorized center -> no paper visibility", 535, RED, RED, 270, 1330)
    return add_vignette(img, 100)

def draw_replay_frame(t, result):
    img = gradient((4, 9, 20), (8, 22, 45), (18, 38, 66)).convert("RGB")
    draw = ImageDraw.Draw(img)
    center(draw, "Deterministic Replay", 52, FONT_HERO, GOLD)

    left = (130, 155, 710, 500)
    right_box = (890, 155, 1470, 500)
    panel(draw, left, fill=PANEL, outline=ACCENT, width=4, radius=26)
    panel(draw, right_box, fill=PANEL, outline=ACCENT, width=4, radius=26)

    center_box(draw, "RUN 1", left, 185, FONT_BIG, WHITE)
    center_box(draw, "RUN 2", right_box, 185, FONT_BIG, WHITE)

    draw.text((245, 285), "same structure", font=FONT_MED, fill=ACCENT)
    draw.text((1005, 285), "same structure", font=FONT_MED, fill=ACCENT)

    draw.text((255, 365), "paper_identity", font=FONT_SMALL, fill=MUTED)
    draw.text((1015, 365), "paper_identity", font=FONT_SMALL, fill=MUTED)

    draw.text((220, 415), result["paper_identity"], font=FONT_BIG, fill=GOLD)
    draw.text((980, 415), result["paper_identity"], font=FONT_BIG, fill=GOLD)

    footer_band(draw, "same structure -> same paper_identity", 535, GREEN, GREEN)
    return add_vignette(img, 80)

def draw_civilization_frame(t):
    img = gradient((3, 8, 18), (12, 30, 58), (26, 58, 90)).convert("RGBA")
    draw = ImageDraw.Draw(img)
    center(draw, "Admissibility Before Visibility", 46, FONT_HERO, GOLD)
    center_box_rect = (505, 270, 1095, 380)
    pulse_alpha = 42 + int(24 * (0.5 + 0.5 * math.sin(t * 5)))
    glow = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.rounded_rectangle((478, 246, 1122, 404), radius=36, fill=(255, 214, 112, pulse_alpha), outline=None)
    glow = glow.filter(ImageFilter.GaussianBlur(18))
    img = Image.alpha_composite(img, glow)
    draw = ImageDraw.Draw(img)

    domains = [
        ("Infrastructure", 230, 215),
        ("Aerospace", 800, 205),
        ("Identity", 1370, 215),
        ("AI", 230, 340),
        ("Law", 1370, 340),
        ("Finance", 430, 450),
        ("Exams", 800, 450),
        ("Medicine", 1170, 450),
    ]

    center_left = center_box_rect[0]
    center_right = center_box_rect[2]
    center_top = center_box_rect[1]
    center_bottom = center_box_rect[3]
    hub_points = {
        "Infrastructure": (center_left, center_top + 28),
        "Aerospace": (WIDTH // 2, center_top),
        "Identity": (center_right, center_top + 28),
        "AI": (center_left, center_top + 70),
        "Law": (center_right, center_top + 70),
        "Finance": (center_left + 140, center_bottom),
        "Exams": (WIDTH // 2, center_bottom),
        "Medicine": (center_right - 140, center_bottom),
    }

    line_alpha = 62 + int(22 * (0.5 + 0.5 * math.sin(t * 6)))
    for label, x, y in domains:
        target = hub_points[label]
        if y < center_top:
            start = (x, y + 32)
        elif y > center_bottom:
            start = (x, y - 32)
        elif x < WIDTH // 2:
            start = (x + 127, y)
        else:
            start = (x - 127, y)
        draw.line((start[0], start[1], target[0], target[1]), fill=(105, 245, 195, line_alpha), width=2)

        phase = (math.sin(t * 6 + len(label)) + 1) / 2
        px = int(start[0] + (target[0] - start[0]) * phase)
        py = int(start[1] + (target[1] - start[1]) * phase)
        draw.ellipse((px - 4, py - 4, px + 4, py + 4), fill=(255, 214, 112, 180))

    panel(draw, center_box_rect, fill=(7, 13, 24), outline=GOLD, width=4, radius=26)
    center(draw, "structure_mature", 292, FONT_BIG, GOLD)
    center(draw, "-> visibility admitted", 338, FONT_MED, WHITE)

    for label, x, y in domains:
        panel(draw, (x - 125, y - 30, x + 125, y + 30), fill=(8, 17, 32), outline=ACCENT, width=3, radius=16)
        f = fit_font(draw, label, 24, 205, 16)
        w, _ = text_size(draw, label, f)
        draw.text((x - w // 2, y - 14), label, font=f, fill=WHITE)

    footer_band(draw, "This is not about exams. This is about civilization.", 535, WHITE, ACCENT, 315, 1285)
    return add_vignette(img.convert("RGB"), 70)

def draw_open_source_frame(t):
    img = gradient((3, 8, 18), (9, 26, 50), (18, 44, 76)).convert("RGB")
    draw = ImageDraw.Draw(img)
    center(draw, "Open Source Reference Implementation", 65, FONT_TITLE, GOLD)
    panel(draw, (180, 155, 1420, 540), fill=(7, 13, 24), outline=ACCENT, width=4, radius=28)
    draw.ellipse((255, 235, 425, 405), fill=(245, 248, 252), outline=GOLD, width=4)
    center(draw, "GitHub", 293, FONT_MED, (8, 22, 48))
    lines = [
        "35 KB structural cinema script",
        "Deterministic paper visibility",
        "Question bank -> blueprint -> admissible set",
        "Replay-verifiable paper identity",
        "Admissibility before visibility",
    ]
    y = 190
    for line in lines:
        draw.text((520, y), "✓ " + line, font=FONT_MED, fill=WHITE)
        y += 50
    footer_band(draw, "Open reference. Deterministic. Reproducible.", 535, ACCENT, GOLD)
    return add_vignette(img, 80)

def draw_did_you_know_frame(t):
    img = gradient((3, 8, 18), (9, 26, 50), (18, 44, 76)).convert("RGB")
    draw = ImageDraw.Draw(img)
    center(draw, "DID YOU KNOW?", 62, FONT_TITLE, GOLD)
    center(draw, "This entire cinematic sequence", 145, FONT_BIG, WHITE)
    center(draw, "was structurally resolved", 200, FONT_BIG, ACCENT)
    center(draw, "from a deterministic script.", 255, FONT_BIG, WHITE)
    panel(draw, (1185, 140, 1450, 380), fill=(7, 13, 24), outline=BLUE, width=4, radius=28)
    center_box(draw, "35 KB", (1185, 140, 1450, 380), 238, FONT_TITLE, GOLD)
    panel(draw, (255, 345, 455, 410), fill=PANEL, outline=ACCENT, width=3, radius=18)
    panel(draw, (515, 345, 715, 410), fill=PANEL, outline=ACCENT, width=3, radius=18)
    panel(draw, (775, 345, 975, 410), fill=PANEL, outline=ACCENT, width=3, radius=18)
    center_box(draw, "No editor", (255, 345, 455, 410), 362, FONT_SMALL, WHITE)
    center_box(draw, "No timeline", (515, 345, 715, 410), 362, FONT_SMALL, WHITE)
    center_box(draw, "No manual", (775, 345, 975, 410), 362, FONT_SMALL, WHITE)
    center(draw, "creative_sequence = resolve(structure)", 470, FONT_MED, ACCENT)
    footer_band(draw, "The paper resolves from structure. The film resolves from structure.", 535, WHITE, GOLD, 270, 1330)
    return add_vignette(img, 80)

def draw_final_frame(t, result):
    img = gradient((2, 5, 12), (5, 14, 30), (14, 32, 60)).convert("RGB")
    draw = ImageDraw.Draw(img)
    panel(draw, (300, 70, 1300, 548), fill=(7, 13, 24), outline=(22, 38, 68), width=2, radius=34)
    center(draw, "The paper exists only", 120, FONT_HERO2, WHITE)
    center(draw, "when it is allowed to exist.", 210, FONT_HERO2, GOLD)
    center(draw, "correctness = structure", 318, FONT_BIG, ACCENT)
    center(draw, "Join the Structural Revolution", 418, FONT_TITLE, WHITE)
    center(draw, "github.com/OMPSHUNYAYA", 498, FONT_MED, GREEN)
    center(draw, "Structural cinema resolved without editing dependency", 545, load_font(22, True), GOLD)
    return add_vignette(img, 80)

def make_frame(kind, local_t, structure, result):
    if kind == "old_world":
        return draw_old_world_frame(local_t)
    if kind == "question":
        return draw_question_frame(local_t)
    if kind == "structure_world":
        return draw_structure_world_frame(local_t)
    if kind == "dependency_elimination":
        return draw_dependency_elimination_frame(local_t)
    if kind == "paper_formation":
        return draw_paper_formation_frame(local_t, structure, result)
    if kind == "countdown":
        return draw_countdown_frame(local_t, result)
    if kind == "gates":
        return draw_gate_frame(local_t, result)
    if kind == "resolution":
        return draw_resolution_frame(local_t, structure, result)
    if kind == "failure":
        return draw_failure_frame(local_t, structure)
    if kind == "replay":
        return draw_replay_frame(local_t, result)
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
    structure = base_exam_structure()
    result = resolve_exam(structure)
    timeline = [
        ("old_world", 7.0),
        ("question", 6.2),
        ("structure_world", 6.8),
        ("dependency_elimination", 7.0),
        ("paper_formation", 11.5),
        ("countdown", 7.2),
        ("gates", 9.0),
        ("resolution", 10.0),
        ("failure", 8.3),
        ("replay", 8.0),
        ("civilization", 8.2),
        ("open_source", 7.8),
        ("did_you_know", 8.5),
        ("final", 8.5),
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
            if previous is not None and i < int(0.35 * FPS):
                amount = i / max(1, int(0.35 * FPS) - 1)
                frame = fade(previous, frame, amount)
            if frame_number == total_frames // 2:
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
        "principle": "paper_visibility = resolve(structure)",
        "law": "paper_visible iff structure_mature",
        "structure_signature": result["structure_signature"],
        "structure_certificate": result["structure_certificate"],
        "paper_identity": result["paper_identity"],
        "video_sha256": video_hash,
        "final_certificate": certificate(result["structure_signature"] + "|" + video_hash)
    }
    with open(OUT_VERIFY, "w", encoding="utf-8") as f:
        f.write("SLANG-Exam Civilization-Grade Demo VERIFY\n")
        f.write("Structural Examination Admissibility\n\n")
        f.write("Principle: paper_visibility = resolve(structure)\n")
        f.write("Law: paper_visible iff structure_mature\n")
        f.write("Structure maturity: complete AND consistent\n\n")
        for key in ["structure_signature", "structure_certificate", "paper_identity", "video_sha256", "final_certificate"]:
            f.write(key + ": " + verify[key] + "\n")
        f.write("\nGuarantees:\n")
        f.write("same structure -> same paper_identity\n")
        f.write("incomplete structure -> no paper visibility\n")
        f.write("unauthorized structure -> no paper visibility\n")
        f.write("visibility is earned by admissibility\n")
    return verify


def main():
    verify = render_video()
    print("SLANG-Exam Structural Cinema v2.7")
    print("Created: " + OUT_VIDEO)
    print("Created: " + OUT_POSTER)
    print("Created: " + OUT_VERIFY)
    print("paper_identity: " + verify["paper_identity"])
    print("final_certificate: " + verify["final_certificate"])
    print("Principle: paper_visibility = resolve(structure)")
    print("Law: paper_visible iff structure_mature")


if __name__ == "__main__":
    main()
