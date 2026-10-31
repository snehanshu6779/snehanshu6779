"""Neon contribution snake.

Reads generated/contributions.json (written by generate_profile_v2.py from the
same GraphQL call that feeds the dashboard) and writes an animated SVG in two
themes. Because both graphics come from one data pull, the snake, the
contribution count and the streak on the dashboard always agree.

The snake walks a serpentine path through every day of the last year. Body,
head, eaten cells, burst rings and the progress bar are all driven by SMIL
timings derived from one clock, so everything stays in lock-step and loops
cleanly. No JavaScript, so it renders inside GitHub READMEs.
"""
import json
import os
import sys
from datetime import date
from html import escape

OUT = 'generated'
SRC = os.path.join(OUT, 'contributions.json')

PITCH = 15          # distance between cell centres
CELL = 11           # cell size
LEFT, TOP = 46, 104 # grid origin
STEP = 0.085        # seconds the head needs to cross one cell in an active week
EMPTY_FACTOR = 0.3  # empty weeks are crossed this much faster
SNAKE_CELLS = 9     # body length in cells
PAUSE = 3.2         # seconds between laps (cells regrow here)

THEMES = {
    'dark': {
        'bg': '#050816', 'border': '#1e293b', 'panel': '#0b1220',
        'text': '#e8f0ff', 'muted': '#7f91aa', 'faint': '#3b4a63',
        'empty': '#111a2e',
        'levels': ['#111a2e', '#0e4f63', '#0891b2', '#3b82f6', '#a78bfa'],
        'tail': '#6366f1', 'mid': '#60a5fa', 'front': '#22d3ee', 'head': '#ecfeff',
        'glow': '#22d3ee', 'burst': '#67e8f9', 'track': '#101b2f',
    },
    'light': {
        'bg': '#ffffff', 'border': '#d0d7de', 'panel': '#f6f8fa',
        'text': '#0f172a', 'muted': '#57606a', 'faint': '#afb8c1',
        'empty': '#ebedf0',
        'levels': ['#ebedf0', '#bae6fd', '#38bdf8', '#2563eb', '#7c3aed'],
        'tail': '#7c3aed', 'mid': '#2563eb', 'front': '#0891b2', 'head': '#0e7490',
        'glow': '#38bdf8', 'burst': '#0ea5e9', 'track': '#eaeef2',
    },
}

FONT = "font-family=\"'Segoe UI',Ubuntu,Arial,sans-serif\""


def f(x):
    """Compact number formatting for SVG attributes."""
    return f'{x:.4f}'.rstrip('0').rstrip('.') if isinstance(x, float) else str(x)


def load():
    if not os.path.exists(SRC):
        sys.exit(f'{SRC} missing - run generate_profile_v2.py first')
    data = json.load(open(SRC, encoding='utf-8'))
    weeks = data.get('weeks') or []
    if not weeks:
        sys.exit('No contribution data - keeping the previous snake.')
    return data, weeks


def stats(weeks, today):
    days = [d for w in weeks for d in w]
    counts = [d['count'] for d in days]
    by = {d['date']: d['count'] for d in days}

    longest = run = 0
    for c in counts:
        run = run + 1 if c > 0 else 0
        longest = max(longest, run)

    # Current streak: today may have no commits yet, so start from yesterday
    # in that case instead of reporting a broken streak.
    ordered = sorted(by)
    idx = len(ordered) - 1
    while idx >= 0 and ordered[idx] > today:
        idx -= 1
    if idx >= 0 and by[ordered[idx]] == 0:
        idx -= 1
    current = 0
    while idx >= 0 and by[ordered[idx]] > 0:
        current += 1
        idx -= 1

    best = max(days, key=lambda d: d['count']) if days else {'count': 0, 'date': ''}
    return {
        'total': sum(counts),
        'active': sum(1 for c in counts if c > 0),
        'current': current,
        'longest': longest,
        'best': best,
    }


def build(theme_name, data, weeks, st):
    t = THEMES[theme_name]
    cols = len(weeks)
    grid_w = (cols - 1) * PITCH + CELL
    width = LEFT + grid_w + 34
    height = TOP + 7 * PITCH + 70

    def centre(c, r):
        return LEFT + c * PITCH + CELL / 2, TOP + r * PITCH + CELL / 2

    # ---- path: lead-in, serpentine through every slot, lead-out ----
    order = []
    for c in range(cols):
        rows = range(7) if c % 2 == 0 else range(6, -1, -1)
        order += [(c, r) for r in rows]
    x0, y0 = centre(0, 0)
    pts = [(x0 - 2 * PITCH, y0)] + [centre(c, r) for c, r in order]
    lx, ly = pts[-1]
    lead_out = (SNAKE_CELLS + 2) * PITCH
    pts.append((lx + lead_out, ly))

    seg = [abs(pts[i + 1][0] - pts[i][0]) + abs(pts[i + 1][1] - pts[i][1]) for i in range(len(pts) - 1)]
    pos = [0.0]
    for s in seg:
        pos.append(pos[-1] + s)
    path_len = pos[-1]
    slot_pos = {order[i]: pos[i + 1] for i in range(len(order))}

    L = SNAKE_CELLS * PITCH
    d_attr = 'M' + ' L'.join(f'{f(float(x))} {f(float(y))}' for x, y in pts)

    # ---- one clock for everything: piecewise-linear position -> time map.
    # The snake sprints through empty weeks and slows down to feast on
    # active ones, so long quiet stretches don't stall the animation.
    active_col = [any(d.get('level', 0) > 0 for d in w) for w in weeks]

    def seg_speed(i):
        target = i  # segment i ends at pts[i + 1] == order[i] for grid slots
        if 0 <= target < len(order):
            return STEP if active_col[order[target][0]] else STEP * EMPTY_FACTOR
        return STEP

    knots = [(0.0, 0.0)]
    t_acc = 0.0
    for i, s_len in enumerate(seg):
        t_acc += s_len / PITCH * seg_speed(i)
        if i == len(seg) - 1 or seg_speed(i + 1) != seg_speed(i):
            knots.append((pos[i + 1], t_acc))
    knots.append((path_len + L, t_acc + L / PITCH * STEP))  # tail clears the board
    t_move = knots[-1][1]
    cycle = t_move + PAUSE
    m = t_move / cycle
    dur = f'{cycle:.2f}s'

    def time_at(s):
        for (s0, t0), (s1, t1) in zip(knots, knots[1:]):
            if s <= s1:
                return t0 + (t1 - t0) * ((s - s0) / (s1 - s0) if s1 > s0 else 0)
        return knots[-1][1]

    def frac(s):
        return min(max(time_at(s) / cycle, 0.0), 0.999)

    key_times = ';'.join(f(tk / cycle) for _, tk in knots) + ';1'

    regrow_a = m + (1 - m) * 0.15
    regrow_b = m + (1 - m) * 0.75

    o = []
    o.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="Contribution snake: {st["total"]} contributions in the last year">')
    o.append(f'<title>{st["total"]} contributions in the last year</title>')
    o.append('<defs>'
             f'<linearGradient id="tg" x1="0" x2="1"><stop stop-color="{t["front"]}"/><stop offset=".55" stop-color="{t["mid"]}"/><stop offset="1" stop-color="{t["tail"]}"/></linearGradient>'
             '<filter id="glow" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="4"/></filter>'
             '<filter id="soft" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="1.6"/></filter>'
             f'<clipPath id="board"><rect x="{LEFT - 14}" y="{TOP - 6}" width="{grid_w + 28}" height="{7 * PITCH + 10}" rx="8"/></clipPath>'
             '</defs>')
    o.append(f'<rect x=".5" y=".5" width="{width - 1}" height="{height - 1}" rx="18" fill="{t["bg"]}" stroke="{t["border"]}"/>')

    # ---- header ----
    o.append(f'<text x="{LEFT}" y="36" fill="url(#tg)" {FONT} font-size="20" font-weight="700" letter-spacing="1">🐍 CONTRIBUTION SNAKE</text>')
    o.append(f'<text x="{width - 30}" y="36" text-anchor="end" fill="{t["muted"]}" {FONT} font-size="13">'
             f'<tspan fill="{t["text"]}" font-weight="700">{st["total"]:,}</tspan> contributions · last 12 months</text>')

    chips = [
        ('CURRENT STREAK', f'{st["current"]} day{"s" if st["current"] != 1 else ""}'),
        ('LONGEST STREAK', f'{st["longest"]} day{"s" if st["longest"] != 1 else ""}'),
        ('ACTIVE DAYS', f'{st["active"]}'),
        ('BEST DAY', f'{st["best"]["count"]} on {fmt_day(st["best"]["date"])}' if st['best']['count'] else '—'),
    ]
    cw = (width - LEFT - 30 - 3 * 10) / 4
    for i, (k, val) in enumerate(chips):
        x = LEFT + i * (cw + 10)
        o.append(f'<rect x="{f(x)}" y="50" width="{f(cw)}" height="30" rx="9" fill="{t["panel"]}" stroke="{t["border"]}"/>')
        o.append(f'<text x="{f(x + 12)}" y="69" fill="{t["muted"]}" {FONT} font-size="9.5" letter-spacing=".6">{k}</text>')
        o.append(f'<text x="{f(x + cw - 12)}" y="69.5" text-anchor="end" fill="{t["text"]}" {FONT} font-size="12" font-weight="700">{escape(val)}</text>')

    # ---- month + weekday labels ----
    last_label = -10
    for c, w in enumerate(weeks):
        first = next((d for d in w if int(d['date'][8:]) <= 7), None)
        if first and c - last_label >= 3 and c < cols - 1:
            mon = date.fromisoformat(first['date']).strftime('%b')
            o.append(f'<text x="{LEFT + c * PITCH}" y="{TOP - 8}" fill="{t["muted"]}" {FONT} font-size="10">{mon}</text>')
            last_label = c
    for r, lab in ((1, 'Mon'), (3, 'Wed'), (5, 'Fri')):
        o.append(f'<text x="{LEFT - 8}" y="{TOP + r * PITCH + 9}" text-anchor="end" fill="{t["muted"]}" {FONT} font-size="9.5">{lab}</text>')

    # ---- empty grid ----
    o.append(f'<g fill="{t["empty"]}">')
    for c, w in enumerate(weeks):
        for d in w:
            r = weekday(d['date'])
            o.append(f'<rect x="{LEFT + c * PITCH}" y="{TOP + r * PITCH}" width="{CELL}" height="{CELL}" rx="2.5"/>')
    o.append('</g>')

    # ---- coloured cells that get eaten, plus burst rings ----
    cells, bursts = [], []
    for c, w in enumerate(weeks):
        for d in w:
            lvl = d.get('level', 0)
            if lvl <= 0:
                continue
            r = weekday(d['date'])
            fe = frac(slot_pos[(c, r)])
            e1 = min(fe + 0.004, 0.999)
            cells.append(
                f'<rect x="{LEFT + c * PITCH}" y="{TOP + r * PITCH}" width="{CELL}" height="{CELL}" rx="2.5" fill="{t["levels"][lvl]}">'
                f'<title>{d["count"]} on {d["date"]}</title>'
                f'<animate attributeName="opacity" dur="{dur}" repeatCount="indefinite" '
                f'values="1;1;0;0;1;1" keyTimes="0;{f(fe)};{f(e1)};{f(regrow_a)};{f(regrow_b)};1"/></rect>')
            if lvl >= 2:
                cx, cy = centre(c, r)
                b1 = min(fe + 0.03, 0.999)
                bursts.append(
                    f'<circle cx="{f(cx)}" cy="{f(cy)}" r="0" fill="none" stroke="{t["burst"]}" stroke-width="1.6" opacity="0">'
                    f'<animate attributeName="r" dur="{dur}" repeatCount="indefinite" values="0;0;{4 + 2.5 * lvl};{4 + 2.5 * lvl}" keyTimes="0;{f(fe)};{f(b1)};1"/>'
                    f'<animate attributeName="opacity" dur="{dur}" repeatCount="indefinite" values="0;0;.95;0;0" keyTimes="0;{f(fe)};{f(e1)};{f(b1)};1"/></circle>')
    o += cells
    o += bursts

    # ---- snake: layered dashes sharing one clock => tapered, glowing body ----
    def layer(length, width_, colour, extra=''):
        # head position = length - dashoffset; keep every layer's head on the same clock
        offs = [length - sk for sk, _ in knots]
        offs.append(offs[-1])
        vals = ';'.join(f(float(x)) for x in offs)
        return (f'<path d="{d_attr}" fill="none" stroke="{colour}" stroke-width="{width_}" stroke-linecap="round" '
                f'stroke-linejoin="round" stroke-dasharray="{f(float(length))} {f(path_len + L + 50)}" '
                f'stroke-dashoffset="{f(float(length))}" {extra}>'
                f'<animate attributeName="stroke-dashoffset" dur="{dur}" repeatCount="indefinite" '
                f'values="{vals}" keyTimes="{key_times}"/></path>')

    o.append('<g clip-path="url(#board)">')
    o.append(layer(L, 16, t['glow'], 'opacity=".45" filter="url(#glow)"'))
    o.append(layer(L, 6.5, t['tail']))
    o.append(layer(L * 0.7, 8.5, t['mid']))
    o.append(layer(L * 0.38, 10, t['front']))
    o.append(layer(0.01, 13, t['head'], 'filter="url(#soft)"'))
    o.append(layer(0.01, 9, t['head']))
    o.append('</g>')

    # ---- progress bar synced to the head ----
    py = TOP + 7 * PITCH + 12
    o.append(f'<rect x="{LEFT}" y="{py}" width="{grid_w}" height="4" rx="2" fill="{t["track"]}"/>')
    # bar tip tracks the head's column: one keyframe per column end
    bvals, btimes = ['0'], ['0']
    for c in range(cols):
        bvals.append(f(float(min(LEFT + c * PITCH + CELL, LEFT + grid_w) - LEFT)))
        btimes.append(f(frac(slot_pos[order[c * 7 + 6]])))
    bvals += [f(float(grid_w)), '0', '0']
    btimes += [f(regrow_a), f(regrow_b), '1']
    o.append(f'<rect x="{LEFT}" y="{py}" width="0" height="4" rx="2" fill="url(#tg)">'
             f'<animate attributeName="width" dur="{dur}" repeatCount="indefinite" '
             f'values="{";".join(bvals)}" keyTimes="{";".join(btimes)}"/></rect>')

    # ---- legend + footer ----
    fy = height - 20
    o.append(f'<text x="{LEFT}" y="{fy}" fill="{t["muted"]}" {FONT} font-size="10">Updated {escape(data.get("generated_at", ""))} · synced with profile dashboard</text>')
    lx0 = LEFT + grid_w - 5 * 15 - 34
    o.append(f'<text x="{lx0 - 6}" y="{fy}" text-anchor="end" fill="{t["muted"]}" {FONT} font-size="10">Less</text>')
    for i, col in enumerate(t['levels']):
        o.append(f'<rect x="{lx0 + i * 15}" y="{fy - 9}" width="{CELL}" height="{CELL}" rx="2.5" fill="{col}"/>')
    o.append(f'<text x="{lx0 + 5 * 15 + 2}" y="{fy}" fill="{t["muted"]}" {FONT} font-size="10">More</text>')

    o.append('</svg>')
    return '\n'.join(o)


def weekday(iso):
    # GitHub rows start on Sunday.
    return (date.fromisoformat(iso).weekday() + 1) % 7


def fmt_day(iso):
    return date.fromisoformat(iso).strftime('%d %b') if iso else ''


def main():
    data, weeks = load()
    today = data.get('today') or max(d['date'] for w in weeks for d in w)
    st = stats(weeks, today)
    if data.get('total'):
        st['total'] = data['total']  # identical to the dashboard's figure
    os.makedirs(OUT, exist_ok=True)
    for name in THEMES:
        svg = build(name, data, weeks, st)
        open(os.path.join(OUT, f'snake-{name}.svg'), 'w', encoding='utf-8').write(svg)
        print(f'snake-{name}.svg  {len(svg) / 1024:.0f} KB')
    print(json.dumps({k: v for k, v in st.items() if k != 'best'}))


if __name__ == '__main__':
    main()
