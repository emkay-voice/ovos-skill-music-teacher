"""The lesson on the screen: a keyboard, a fretboard, a chord chart or the
tuner, with the notes in order underneath - green when right, red when not.

SVG pictures for the stock SYSTEM_ImageFrame page (as ovos-skill-jamband
does), so every OVOS GUI shows them: Emkay, a Mark II, ovos-shell.
"""
from __future__ import annotations

import base64
import math
from html import escape

W, H = 1080, 1180
BG, FG, DIM, LIT, ROOT, OK, BAD, OFF = ("#101418", "#e8e8e8", "#7a8088", "#ffcc33", "#ff8a3d",
                                        "#3ecf6e", "#ff5a5a", "#2a3038")
SANS = 'font-family="sans-serif" text-anchor="middle"'
COLOR = {"note": LIT, "root": ROOT, "ok": OK, "bad": BAD, "dim": OFF, "next": FG}


def _t(x, y, text, size, fill=FG, weight="normal", anchor="middle"):
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" font-weight="{weight}" '
            f'font-family="sans-serif" text-anchor="{anchor}">{escape(str(text))}</text>')


def page(parts: list[str], title: str = "", heading: str = "", status: str = "", status_kind: str = "") -> str:
    """The frame every view shares: a small title, the big heading, and a
    status line at the bottom (listening, right, wrong)."""
    out = [f'<rect width="{W}" height="{H}" fill="{BG}"/>']
    if title:
        out.append(_t(W / 2, 60, title, 34, DIM))
    if heading:
        out.append(_t(W / 2, 170, heading, 96 if len(heading) < 14 else 64, LIT, "bold"))
    out += parts
    if status:
        col = {"listen": LIT, "ok": OK, "bad": BAD}.get(status_kind, FG)
        dot = "● " if status_kind == "listen" else "✓ " if status_kind == "ok" else "✗ " if status_kind == "bad" else ""
        out.append(_t(W / 2, H - 50, dot + status, 46, col, "bold"))
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">{"".join(out)}</svg>'
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


# ------------------------------------------------------------------ piano
_WHITE = (0, 2, 4, 5, 7, 9, 11)


def keyboard(keys: dict, top: float = 330, height: float = 400, low: int | None = None,
             high: int | None = None) -> list[str]:
    """`keys`: {MIDI note: (label, finger, kind)} - kind "root", "note",
    "ok", "bad". Two octaves at least, from a C."""
    notes = list(keys) or [60]
    lo = (min(notes) if low is None else low) // 12 * 12
    hi = max(max(notes) if high is None else high, lo + 23)
    hi = hi // 12 * 12 + 11
    whites = [n for n in range(lo, hi + 1) if n % 12 in _WHITE]
    margin = 30
    kw = (W - 2 * margin) / len(whites)
    out = []
    xs = {}
    for i, n in enumerate(whites):
        x = margin + i * kw
        xs[n] = x
        kind = keys.get(n, (None, None, None))[2]
        fill = COLOR.get(kind, "#f4f4f4") if kind else "#f4f4f4"
        out.append(f'<rect x="{x:.1f}" y="{top}" width="{kw - 3:.1f}" height="{height}" rx="8" fill="{fill}"/>')
        if n % 12 == 0:
            out.append(_t(x + kw / 2, top + height - 14, f"C{n // 12 - 1}", 20, "#888"))
    bw, bh = kw * 0.62, height * 0.6
    for n in range(lo, hi + 1):
        if n % 12 in _WHITE:
            continue
        x = xs[n - 1] + kw - bw / 2 - 1.5
        xs[n] = x - (kw - bw) / 2
        kind = keys.get(n, (None, None, None))[2]
        fill = COLOR.get(kind, "#1b1b1b") if kind else "#1b1b1b"
        out.append(f'<rect x="{x:.1f}" y="{top}" width="{bw:.1f}" height="{bh:.1f}" rx="6" fill="{fill}" '
                   f'stroke="#000" stroke-width="2"/>')
    for n, (label, finger, kind) in keys.items():
        if n not in xs:
            continue
        black = n % 12 not in _WHITE
        cx = xs[n] + kw / 2
        ly = top + bh - 26 if black else top + height - 50
        if label:
            out.append(_t(cx, ly, label, 30 if black else 36, "#101418", "bold"))
        if finger:                     # black keys' fingers a row higher: neighbours don't overlap
            fy = top - (104 if black else 40)
            r = min(30, kw * 0.48)
            out.append(f'<circle cx="{cx:.1f}" cy="{fy}" r="{r:.1f}" fill="{COLOR.get(kind, LIT)}"/>')
            out.append(_t(cx, fy + 12, finger, 34, "#101418", "bold"))
    return out


# ------------------------------------------------------------------ guitar and bass
def fretboard(dots: list, strings: list[str], top: float = 300, first: int = 0, frets: int = 6,
              height: float = 440) -> list[str]:
    """Horizontal, as tab is read: the highest string on top. `dots`:
    [(string from the lowest, fret, label, kind)]; `strings`: their names,
    lowest first. Shows frets first..first+frets (0: with the nut)."""
    n = len(strings)
    left, right = 130, W - 40
    fw = (right - left) / frets
    gap = height / (n - 1)
    out = []

    def y_of(s):
        return top + (n - 1 - s) * gap

    out.append(f'<rect x="{left}" y="{top - 20}" width="{right - left}" height="{height + 40}" rx="10" fill="#3a2a1c"/>')
    for k in range(frets + 1):
        x = left + k * fw
        width = 12 if first == 0 and k == 0 else 4
        out.append(f'<rect x="{x - width / 2:.1f}" y="{top - 20}" width="{width}" height="{height + 40}" '
                   f'fill="{"#e8e0d0" if width > 4 else "#9a9a9a"}"/>')
        fret = first + k
        if k < frets and fret + 1 in (3, 5, 7, 9, 15, 17):
            out.append(f'<circle cx="{x + fw / 2:.1f}" cy="{top + height / 2:.1f}" r="12" fill="#6b5640"/>')
        if k < frets and fret + 1 == 12:
            for dy in (-gap, gap):
                out.append(f'<circle cx="{x + fw / 2:.1f}" cy="{top + height / 2 + dy:.1f}" r="12" fill="#6b5640"/>')
        if k < frets:
            out.append(_t(x + fw / 2, top + height + 64, fret + 1, 26, DIM))
    for s in range(n):
        y = y_of(s)
        out.append(f'<line x1="{left}" y1="{y:.1f}" x2="{right}" y2="{y:.1f}" stroke="#d9d2c0" '
                   f'stroke-width="{1.5 + (n - 1 - (n - 1 - s)) * 0.0 + (n - s) * 0.7:.1f}"/>')
        out.append(_t(34, y + 12, strings[s], 34, FG, "bold"))
    for s, fret, label, kind in dots:
        y = y_of(s)
        if fret == 0:
            cx = left - 8
            out.append(f'<circle cx="{cx - 26:.1f}" cy="{y:.1f}" r="22" fill="none" stroke="{COLOR.get(kind, LIT)}" '
                       f'stroke-width="5"/>')
            if label:
                out.append(_t(cx - 26, y + 9, label, 24, COLOR.get(kind, LIT), "bold"))
            continue
        k = fret - first
        if not 1 <= k <= frets:
            continue
        cx = left + (k - 0.5) * fw
        out.append(f'<circle cx="{cx:.1f}" cy="{y:.1f}" r="30" fill="{COLOR.get(kind, LIT)}"/>')
        if label:
            out.append(_t(cx, y + 11, label, 30, "#101418", "bold"))
    return out


def chord_chart(strings_frets: tuple, barre: int, names: list[str], top: float = 250,
                marks: dict | None = None) -> list[str]:
    """A guitar chord as on a chord chart: the strings standing, the lowest
    on the left; X a string not played, O an open one; numbered fingers.
    `marks`: {string: "ok"/"bad"} - which strings rang right."""
    marks = marks or {}
    n = len(strings_frets)
    frets_shown = 5
    first = barre if barre > 1 else 1
    left, width = 230, 620
    gap = width / (n - 1)
    fh = 130
    out = []
    if first == 1:
        out.append(f'<rect x="{left - 6}" y="{top - 14}" width="{width + 12}" height="14" fill="{FG}"/>')
    else:
        out.append(_t(left - 70, top + fh / 2 + 14, f"{first}", 44, FG, "bold"))
    for k in range(frets_shown + 1):
        y = top + k * fh
        out.append(f'<line x1="{left}" y1="{y}" x2="{left + width}" y2="{y}" stroke="{DIM}" stroke-width="4"/>')
    for s in range(n):
        x = left + s * gap
        col = COLOR.get(marks.get(s), "#d9d2c0")
        out.append(f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{top + frets_shown * fh}" stroke="{col}" '
                   f'stroke-width="{6 - s * 0.6:.1f}"/>')
        out.append(_t(x, top + frets_shown * fh + 56, names[s], 34, DIM, "bold"))
    if barre:
        bs = [s for s, (f, g) in enumerate(strings_frets) if f == barre and g == 1]
        if len(bs) >= 2:
            y = top + (barre - first + 0.5) * fh
            x1, x2 = left + min(bs) * gap, left + max(bs) * gap
            out.append(f'<rect x="{x1 - 30:.1f}" y="{y - 30:.1f}" width="{x2 - x1 + 60:.1f}" height="60" rx="30" '
                       f'fill="{LIT}"/>')
    for s, (fret, finger) in enumerate(strings_frets):
        x = left + s * gap
        if fret is None:
            out.append(_t(x, top - 34, "✕", 44, BAD, "bold"))
            continue
        if fret == 0:
            out.append(f'<circle cx="{x:.1f}" cy="{top - 50}" r="20" fill="none" stroke="{OK}" stroke-width="5"/>')
            continue
        y = top + (fret - first + 0.5) * fh
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="40" fill="{LIT}"/>')
        out.append(_t(x, y + 14, finger, 42, "#101418", "bold"))
    return out


# ------------------------------------------------------------------ the notes in order
def note_row(labels: list[str], marks: list | None = None, y: float = 900, current: int | None = None) -> list[str]:
    """The notes to play, in order: `marks` a mark each (True right, False
    wrong, None not yet); `current` the one to play now."""
    if not labels:
        return []
    marks = marks or [None] * len(labels)
    per_row = 8 if len(labels) > 8 else len(labels)
    rows = math.ceil(len(labels) / per_row)
    out = []
    cw = min(128, (W - 80) / per_row)
    for i, label in enumerate(labels):
        r, c = divmod(i, per_row)
        in_row = min(per_row, len(labels) - r * per_row)
        x = W / 2 + (c - (in_row - 1) / 2) * cw
        yy = y + r * 96 - (rows - 1) * 48
        m = marks[i] if i < len(marks) else None
        fill = OK if m is True else BAD if m is False else OFF
        stroke = f' stroke="{LIT}" stroke-width="5"' if current == i else ""
        out.append(f'<rect x="{x - cw / 2 + 6:.1f}" y="{yy - 42:.1f}" width="{cw - 12:.1f}" height="78" rx="14" '
                   f'fill="{fill}"{stroke}/>')
        out.append(_t(x, yy + 12, label, 34 if len(label) < 4 else 26, "#101418" if m is not None else FG, "bold"))
    return out


# ------------------------------------------------------------------ the tuner
def tuner(string_name: str, cents: float | None, hint: str = "") -> list[str]:
    """A needle from -50 to +50 cents; green in the middle."""
    cx, cy, r = W / 2, 760, 400
    out = []
    for lo_c, hi_c, col in ((-50, -10, BAD), (-10, -4, LIT), (-4, 4, OK), (4, 10, LIT), (10, 50, BAD)):
        a1, a2 = math.radians(90 + 90 * lo_c / 50), math.radians(90 + 90 * hi_c / 50)
        x1, y1 = cx - r * math.cos(a1), cy - r * math.sin(a1)
        x2, y2 = cx - r * math.cos(a2), cy - r * math.sin(a2)
        out.append(f'<path d="M {x1:.1f} {y1:.1f} A {r} {r} 0 0 1 {x2:.1f} {y2:.1f}" stroke="{col}" '
                   f'stroke-width="36" fill="none" opacity="0.85"/>')
    for c in range(-50, 51, 10):
        a = math.radians(90 + 90 * c / 50)
        out.append(_t(cx - (r + 60) * math.cos(a), cy - (r + 60) * math.sin(a) + 10, f"{c:+d}" if c else "0", 26, DIM))
    out.append(_t(cx, cy - 120, string_name, 220, FG, "bold"))
    if cents is not None:
        c = max(-50.0, min(50.0, cents))
        a = math.radians(90 + 90 * c / 50)
        x, y = cx - (r - 30) * math.cos(a), cy - (r - 30) * math.sin(a)
        col = OK if abs(cents) <= 4 else LIT if abs(cents) <= 10 else BAD
        out.append(f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" stroke="{col}" stroke-width="12" '
                   f'stroke-linecap="round"/>')
        out.append(f'<circle cx="{cx}" cy="{cy}" r="24" fill="{col}"/>')
        out.append(_t(cx, cy + 90, f"{cents:+.0f} cent", 48, col, "bold"))
    if hint:
        out.append(_t(cx, cy + 170, hint, 46, FG))
    return out


def text_lines(lines: list[str], y: float = 300, size: int = 44) -> list[str]:
    return [_t(W / 2, y + i * (size * 1.5), line, size, FG) for i, line in enumerate(lines)]
