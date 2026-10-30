"""Builds the animated SVG cards for the profile README from live GitHub data.

Run by .github/workflows/refresh.yml on a schedule. Locally:
    GITHUB_TOKEN=$(gh auth token) python scripts/build_profile.py
"""

import json
import math
import os
import urllib.parse
import urllib.request
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from html import escape
from pathlib import Path

USER = os.environ.get("PROFILE_USER", "samranahmad09")
GPU_REPO = "WhateverXe-RaptorLakeP"
TOKEN = os.environ["GITHUB_TOKEN"]
OUT = Path(__file__).resolve().parent.parent / "assets"
PKT = timezone(timedelta(hours=5))

BG0, BG1 = "#05070d", "#0a1222"
LINE = "#16243d"
CYAN, VIOLET, MAGENTA = "#22d3ee", "#a78bfa", "#f472b6"
GREEN, AMBER, GOLD, SILVER = "#34d399", "#fbbf24", "#fcd34d", "#cbd5e1"
TEXT, MUTED, DIM = "#e6f1ff", "#7f8ea8", "#2a3a55"
SANS = "'Segoe UI', Inter, -apple-system, Helvetica, Arial, sans-serif"
MONO = "'JetBrains Mono', 'Cascadia Code', ui-monospace, SFMono-Regular, Consolas, monospace"
LANG_COLORS = [CYAN, VIOLET, MAGENTA, GREEN, AMBER]


# ---------------------------------------------------------------- data

def rest(path, token=TOKEN, **params):
    url = f"https://api.github.com/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def graphql(query, **variables):
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request("https://api.github.com/graphql", data=body,
                                 headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if "errors" in data:
        raise RuntimeError(data["errors"])
    return data["data"]


def collect():
    cal = graphql("""query($u:String!){user(login:$u){contributionsCollection{contributionCalendar{
        totalContributions weeks{contributionDays{date contributionCount}}}}}}""", u=USER)
    cal = cal["user"]["contributionsCollection"]["contributionCalendar"]
    days = [(date.fromisoformat(d["date"]), d["contributionCount"]) for w in cal["weeks"] for d in w["contributionDays"]]
    today = datetime.now(PKT).date()
    days = [d for d in days if d[0] <= today]

    streak = 0
    for i, (d, n) in enumerate(reversed(days)):
        if n:
            streak += 1
        elif i:  # today may still be empty without breaking the streak
            break

    repos = [r for r in rest(f"users/{USER}/repos", per_page=100, type="owner") if not r["private"]]
    langs = Counter()
    for r in repos:
        if not r["fork"]:
            langs.update(rest(f"repos/{USER}/{r['name']}/languages"))
    # private repos need LANG_TOKEN: a fine-grained token with read-only Metadata on just those repos
    private = [n for n in os.environ.get("PRIVATE_LANG_REPOS", "").split(",") if n]
    lang_token = os.environ.get("LANG_TOKEN")
    for name in private if lang_token else []:
        langs.update(rest(f"repos/{USER}/{name}/languages", token=lang_token))
    if private and not lang_token:
        print(f"LANG_TOKEN not set, languages skip {', '.join(private)}")

    gpu = rest(f"repos/{USER}/{GPU_REPO}")
    commits = []
    for page in range(1, 11):
        batch = rest(f"repos/{USER}/{GPU_REPO}/commits", author=USER, per_page=100, page=page)
        commits += batch
        if len(batch) < 100:
            break
    commit_days = [datetime.fromisoformat(c["commit"]["author"]["date"].replace("Z", "+00:00")).astimezone(PKT).date()
                   for c in commits]
    weekly = [sum(1 for d in commit_days if 7 * (11 - i) <= (today - d).days < 7 * (12 - i)) for i in range(12)]

    return {
        "total": cal["totalContributions"],
        "last30": sum(n for d, n in days if (today - d).days < 30),
        "streak": streak,
        "weeks": [sum(w) for w in _chunks([n for _, n in days][-364:], 7)],
        "repos": len(repos),
        "langs": langs.most_common(5),
        "langs_private": bool(private and lang_token),
        "gpu_commits": len(commits),
        "gpu_weekly": weekly,
        "gpu_stars": gpu["stargazers_count"],
        "gpu_pushed": gpu["pushed_at"][:10],
        "gpu_latest": commits[0]["commit"]["message"].split("\n")[0] if commits else "",
        "synced": datetime.now(PKT).strftime("%Y-%m-%d %H:%M PKT"),
    }


def _chunks(xs, n):
    return [xs[i:i + n] for i in range(0, len(xs), n)]


# ---------------------------------------------------------------- shared pieces

def svg(w, h, body, extra_css="", label=""):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-label="{escape(label)}">
<style>
  .mono {{ font-family: {MONO}; }}
  .sans {{ font-family: {SANS}; }}
  .drift {{ animation: drift 6s linear infinite; }}
  .scan {{ animation: scan 7s linear infinite; }}
  .blink {{ animation: blink 1.1s steps(1) infinite; }}
  .pulse {{ animation: pulse 2.4s ease-in-out infinite; }}
  @keyframes drift {{ to {{ transform: translate(-32px, -32px); }} }}
  @keyframes scan {{ from {{ transform: translateY(-120px); }} to {{ transform: translateY({h + 40}px); }} }}
  @keyframes blink {{ 50% {{ opacity: 0; }} }}
  @keyframes pulse {{ 0%, 100% {{ opacity: .35; }} 50% {{ opacity: 1; }} }}
  {extra_css}
  @media (prefers-reduced-motion: reduce) {{ * {{ animation: none !important; }} }}
</style>
<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{BG0}"/><stop offset="1" stop-color="{BG1}"/></linearGradient>
  <pattern id="grid" width="32" height="32" patternUnits="userSpaceOnUse"><path d="M32 0H0V32" fill="none" stroke="{LINE}" stroke-width="1"/></pattern>
  <linearGradient id="scanline" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="{CYAN}" stop-opacity="0"/><stop offset=".85" stop-color="{CYAN}" stop-opacity=".07"/>
    <stop offset="1" stop-color="{CYAN}" stop-opacity=".25"/></linearGradient>
  <radialGradient id="vignette" cx=".5" cy=".5" r=".75"><stop offset=".55" stop-color="{BG0}" stop-opacity="0"/><stop offset="1" stop-color="{BG0}" stop-opacity=".85"/></radialGradient>
  <filter id="glow" x="-20%" y="-40%" width="140%" height="180%"><feGaussianBlur stdDeviation="5" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
  <filter id="softglow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="2.2" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
  <clipPath id="frame"><rect width="{w}" height="{h}" rx="18"/></clipPath>
</defs>
<g clip-path="url(#frame)">
  <rect width="{w}" height="{h}" fill="url(#bg)"/>
  <g class="drift"><rect width="{w + 64}" height="{h + 64}" fill="url(#grid)"/></g>
  <rect width="{w}" height="{h}" fill="url(#vignette)"/>
  {body}
  <rect class="scan" width="{w}" height="120" fill="url(#scanline)"/>
</g>
<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="18" fill="none" stroke="{LINE}"/>
{brackets(w, h)}
</svg>
"""


def brackets(w, h, c=CYAN, s=22, m=10):
    p = [f"M{m} {m + s}V{m}H{m + s}", f"M{w - m - s} {m}H{w - m}V{m + s}",
         f"M{m} {h - m - s}V{h - m}H{m + s}", f"M{w - m - s} {h - m}H{w - m}V{h - m - s}"]
    return "".join(f'<path d="{d}" fill="none" stroke="{c}" stroke-width="2.5" opacity=".9"/>' for d in p)


def header(x, y, title, right=""):
    out = f'<text x="{x}" y="{y}" class="mono" font-size="15" fill="{CYAN}" letter-spacing="2">◆ {escape(title)}</text>'
    if right:
        out += f'<text x="{1200 - x}" y="{y}" text-anchor="end" class="mono" font-size="13" fill="{MUTED}">{escape(right)}</text>'
    return out


def wrap(text, width):
    lines, cur = [], ""
    for word in text.split():
        if cur and len(cur) + 1 + len(word) > width:
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    return lines + [cur] if cur else lines


# ---------------------------------------------------------------- hero

PHRASES = [
    "bringing up an Intel GPU on macOS, from scratch",
    "building AI agents that do real work",
    "shipping winning builds on a 24-hour clock",
    "BS Artificial Intelligence @ FAST-NUCES Islamabad",
]


def typing(x, y, size=22):
    cw, type_s, hold_s, del_s = size * 0.6, 0.06, 1.6, 0.022
    slots, t = [], 0.0
    for p in PHRASES:
        n = len(p)
        slots.append((t, p))
        t += n * type_s + hold_s + n * del_s + 0.4
    total = t

    def frames(start, n):
        f = [(start, 0)]
        f += [(start + k * type_s, k) for k in range(1, n + 1)]
        end_type = start + n * type_s + hold_s
        f += [(end_type + (n - k) * del_s, k) for k in range(n - 1, -1, -1)]
        return f

    out, cursor = [], [(0.0, 0)]
    for i, (start, p) in enumerate(slots):
        f = frames(start, len(p))
        cursor += f
        f = [(0.0, 0)] + f if start > 0 else f
        kt = ";".join(f"{a / total:.5f}" for a, _ in f)
        vals = ";".join(f"{k * cw:.1f}" for _, k in f)
        out.append(f'<clipPath id="type{i}"><rect x="{x}" y="{y - size}" height="{size + 10}" width="0">'
                   f'<animate attributeName="width" values="{vals}" keyTimes="{kt}" dur="{total:.2f}s" calcMode="discrete" repeatCount="indefinite"/></rect></clipPath>'
                   f'<text x="{x}" y="{y}" class="mono" font-size="{size}" fill="{TEXT}" textLength="{len(p) * cw:.1f}" lengthAdjust="spacing" clip-path="url(#type{i})">{escape(p)}</text>')
    dedup = {}
    for a, k in cursor:
        dedup[round(a / total, 5)] = k
    kt = ";".join(f"{a:.5f}" for a in dedup)
    vals = ";".join(f"{x + k * cw + 2:.1f}" for k in dedup.values())
    out.append(f'<rect class="blink" y="{y - size + 2}" width="{size * 0.55:.1f}" height="{size + 2}" fill="{CYAN}" x="{x}">'
               f'<animate attributeName="x" values="{vals}" keyTimes="{kt}" dur="{total:.2f}s" calcMode="discrete" repeatCount="indefinite"/></rect>')
    return "".join(out)


def chip(cx, cy):
    size, eu = 176, 15
    x0, y0 = cx - size / 2, cy - size / 2
    parts = [
        f'<circle class="spin" cx="{cx}" cy="{cy}" r="142" fill="none" stroke="{CYAN}" stroke-opacity=".35" stroke-width="1.5" stroke-dasharray="3 9"/>',
        f'<circle class="spin-rev" cx="{cx}" cy="{cy}" r="126" fill="none" stroke="{VIOLET}" stroke-opacity=".5" stroke-width="2" stroke-dasharray="60 40 10 40"/>',
    ]
    for i in range(6):
        p = 28 + i * 24
        for j, (x1, y1, x2, y2) in enumerate([(x0 + p, y0, x0 + p, y0 - 44), (x0 + p, y0 + size, x0 + p, y0 + size + 44),
                                              (x0, y0 + p, x0 - 44, y0 + p), (x0 + size, y0 + p, x0 + size + 44, y0 + p)]):
            parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{DIM}" stroke-width="3" stroke-linecap="round"/>')
            parts.append(f'<line class="trace" style="animation-delay:{(i * 4 + j) * 0.17:.2f}s" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
                         f'stroke="{CYAN}" stroke-width="3" stroke-linecap="round" stroke-dasharray="8 60"/>')
    parts.append(f'<rect x="{x0}" y="{y0}" width="{size}" height="{size}" rx="16" fill="#0b1426" stroke="{CYAN}" stroke-opacity=".6" stroke-width="1.5"/>')
    gx, gy = x0 + 18, y0 + 16
    for r in range(8):
        for c in range(8):
            parts.append(f'<rect class="eu" style="animation-delay:{(r + c) * 0.11:.2f}s" x="{gx + c * 18.2:.1f}" y="{gy + r * 16.6:.1f}" '
                         f'width="{eu}" height="{eu - 2}" rx="2.5" fill="{CYAN}"/>')
    parts.append(f'<text x="{cx}" y="{y0 + size + 70}" text-anchor="middle" class="mono" font-size="13" fill="{MUTED}" letter-spacing="2">A7A8 // Xe-LP // 64 EU</text>')
    return "".join(parts)


def hero(d):
    css = f"""
  .spin {{ transform-box: fill-box; transform-origin: center; animation: spin 40s linear infinite; }}
  .spin-rev {{ transform-box: fill-box; transform-origin: center; animation: spin 24s linear infinite reverse; }}
  @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
  .trace {{ stroke-dashoffset: 68; animation: trace 2.6s linear infinite; }}
  @keyframes trace {{ to {{ stroke-dashoffset: 0; }} }}
  .eu {{ opacity: .15; animation: eu 2.6s ease-in-out infinite; }}
  @keyframes eu {{ 0%, 100% {{ opacity: .15; }} 45% {{ opacity: .95; }} }}
  .glitch-a {{ animation: glitch 7s steps(1) infinite; }}
  .glitch-b {{ animation: glitch 7s steps(1) infinite .12s; }}
  @keyframes glitch {{ 0%, 88%, 100% {{ opacity: 0; }} 89% {{ opacity: .8; }} 90% {{ opacity: 0; }} 92% {{ opacity: .7; }} 93% {{ opacity: 0; }} }}
  .tag {{ animation: pulse 3.2s ease-in-out infinite; }}
"""
    tags = ["GPU DRIVERS", "AI AGENTS", "FULL-STACK", "HACKATHONS"]
    tag_svg, x = [], 64
    for i, t in enumerate(tags):
        w = len(t) * 9.6 + 34
        tag_svg.append(f'<rect class="tag" style="animation-delay:{i * 0.8}s" x="{x}" y="276" width="{w:.0f}" height="32" rx="4" fill="{CYAN}" fill-opacity=".06" stroke="{CYAN}" stroke-opacity=".7"/>'
                       f'<text x="{x + w / 2:.0f}" y="297" text-anchor="middle" class="mono" font-size="14" fill="{TEXT}" letter-spacing="1.5">{t}</text>')
        x += w + 14
    name = "SAMRAN AHMAD"
    body = f"""
  <defs>
    <linearGradient id="namegrad" x1="0" y1="0" x2="520" y2="0" gradientUnits="userSpaceOnUse" spreadMethod="reflect">
      <stop offset="0" stop-color="{CYAN}"/><stop offset=".5" stop-color="{VIOLET}"/><stop offset="1" stop-color="{MAGENTA}"/>
      <animateTransform attributeName="gradientTransform" type="translate" values="0 0;1040 0" dur="9s" repeatCount="indefinite"/>
    </linearGradient>
  </defs>
  <text x="64" y="52" class="mono" font-size="14" fill="{CYAN}" letter-spacing="2">◢ ~/samranahmad09 :: profile.sys</text>
  <circle class="pulse" cx="560" cy="47" r="5" fill="{GREEN}" filter="url(#softglow)"/>
  <text x="573" y="52" class="mono" font-size="13" fill="{GREEN}" letter-spacing="2">SYS ONLINE</text>
  <text x="710" y="52" class="mono" font-size="13" fill="{MUTED}">ISB // UTC+5</text>
  <text class="glitch-a" x="67" y="150" font-family="{SANS}" font-size="68" font-weight="800" letter-spacing="5" fill="{MAGENTA}">{name}</text>
  <text class="glitch-b" x="61" y="148" font-family="{SANS}" font-size="68" font-weight="800" letter-spacing="5" fill="{CYAN}">{name}</text>
  <text x="64" y="150" font-family="{SANS}" font-size="68" font-weight="800" letter-spacing="5" fill="url(#namegrad)" filter="url(#glow)">{name}</text>
  <text x="66" y="221" class="mono" font-size="22" fill="{CYAN}">&gt;</text>
  {typing(92, 221)}
  {''.join(tag_svg)}
  <text x="64" y="356" class="mono" font-size="12" fill="{MUTED}" letter-spacing="1">LAST SYNC {d['synced']} // AUTO-REFRESHED BY GITHUB ACTIONS</text>
  {chip(1000, 196)}
"""
    return svg(1200, 380, body, css, "Samran Ahmad: GPU drivers, AI agents, full-stack, hackathons")


# ---------------------------------------------------------------- GPU mission panel

SUBSYSTEMS = [
    ("Internal panel, native framebuffer", "ONLINE"),
    ("Metal acceleration", "ONLINE"),
    ("OpenGL apps + hardware video", "ONLINE"),
    ("Brightness slider + keys", "ONLINE"),
    ("Display sleep / wake", "ONLINE"),
    ("System sleep / wake", "IN PROGRESS"),
    ("External displays, 144 Hz", "QUEUED"),
]
STATE_COLOR = {"ONLINE": GREEN, "IN PROGRESS": AMBER, "QUEUED": MUTED}


def gpu_panel(d):
    css = """
  .seg { opacity: 0; animation: segin .25s ease-out forwards; }
  @keyframes segin { to { opacity: 1; } }
  .wave { animation: wave 1.6s ease-in-out infinite; }
  @keyframes wave { 0%, 100% { opacity: .15; } 50% { opacity: 1; } }
  .shine { animation: shine 3.5s ease-in-out infinite; }
  @keyframes shine { 0% { transform: translateX(-120px); } 60%, 100% { transform: translateX(380px); } }
  .grow { transform-box: fill-box; transform-origin: bottom; transform: scaleY(0); animation: grow .8s cubic-bezier(.2,.8,.2,1) forwards; }
  @keyframes grow { to { transform: scaleY(1); } }
  .wavefm { animation: fm 2.2s linear infinite; }
  @keyframes fm { to { transform: translateX(-80px); } }
"""
    rows = []
    for i, (label, state) in enumerate(SUBSYSTEMS):
        y = 140 + i * 44
        col = STATE_COLOR[state]
        rows.append(f'<text x="60" y="{y}" class="sans" font-size="17" fill="{TEXT if state != "QUEUED" else MUTED}">{escape(label)}</text>')
        pw = len(state) * 8 + 20
        rows.append(f'<rect x="372" y="{y - 15}" width="{pw}" height="21" rx="10.5" fill="{col}" fill-opacity=".12" stroke="{col}" stroke-opacity=".8"/>'
                    f'<text x="{372 + pw / 2}" y="{y}" text-anchor="middle" class="mono" font-size="11.5" fill="{col}" letter-spacing="1">{state}</text>')
        lit = {"ONLINE": 20, "IN PROGRESS": 12, "QUEUED": 0}[state]
        segs = []
        for s in range(20):
            sx = 512 + s * 13
            if s < lit:
                segs.append(f'<rect class="seg" style="animation-delay:{i * 0.12 + s * 0.035:.2f}s" x="{sx}" y="{y - 13}" width="10" height="16" rx="1.5" fill="{col}"/>')
            elif state == "IN PROGRESS":
                segs.append(f'<rect class="wave" style="animation-delay:{(s - lit) * 0.12:.2f}s" x="{sx}" y="{y - 13}" width="10" height="16" rx="1.5" fill="{col}"/>')
            else:
                segs.append(f'<rect x="{sx}" y="{y - 13}" width="10" height="16" rx="1.5" fill="{DIM}" fill-opacity=".6"/>')
        rows.append("".join(segs))
        if state == "ONLINE":
            rows.append(f'<g clip-path="url(#bar{i})"><rect class="shine" style="animation-delay:{1.4 + i * 0.3:.1f}s" x="512" y="{y - 13}" width="60" height="16" fill="url(#shinegrad)"/></g>'
                        f'<clipPath id="bar{i}"><rect x="512" y="{y - 13}" width="257" height="16"/></clipPath>')

    # telemetry box
    bx, by, bw, bh = 820, 104, 330, 318
    peak = max(d["gpu_weekly"]) or 1
    bars = []
    for i, n in enumerate(d["gpu_weekly"]):
        h = max(2, 56 * n / peak)
        bars.append(f'<rect class="grow" style="animation-delay:{0.6 + i * 0.06:.2f}s" x="{bx + 20 + i * 25}" y="{by + 216 - h:.1f}" width="17" height="{h:.1f}" rx="2" fill="{CYAN if i < 11 else MAGENTA}"/>')
    latest = wrap(d["gpu_latest"], 40)[:2]
    if len(wrap(d["gpu_latest"], 40)) > 2:
        latest[1] = latest[1][:37] + "..."
    latest_svg = "".join(f'<text x="{bx + 20}" y="{by + 270 + k * 18}" class="mono" font-size="12" fill="{TEXT}">{escape(t)}</text>' for k, t in enumerate(latest))
    wave = " ".join(f"{'M' if k == 0 else 'L'}{bx + 20 + k * 4} {by + 120 + 9 * math.sin(k * 0.8) * (1 if k % 7 else 1.6):.1f}" for k in range(95))
    tele = f"""
  <rect x="{bx}" y="{by}" width="{bw}" height="{bh}" rx="10" fill="#08101e" fill-opacity=".85" stroke="{CYAN}" stroke-opacity=".35"/>
  <text x="{bx + 20}" y="{by + 30}" class="mono" font-size="12" fill="{CYAN}" letter-spacing="2">LIVE TELEMETRY</text>
  <circle class="pulse" cx="{bx + bw - 24}" cy="{by + 26}" r="4.5" fill="{MAGENTA}" filter="url(#softglow)"/>
  <text x="{bx + 20}" y="{by + 64}" class="mono" font-size="12" fill="{MUTED}">MY COMMITS</text>
  <text x="{bx + 20}" y="{by + 96}" class="sans" font-size="32" font-weight="700" fill="{TEXT}">{d['gpu_commits']}</text>
  <text x="{bx + 130}" y="{by + 64}" class="mono" font-size="12" fill="{MUTED}">LAST PUSH</text>
  <text x="{bx + 130}" y="{by + 92}" class="mono" font-size="17" fill="{TEXT}">{d['gpu_pushed']}</text>
  <text x="{bx + 260}" y="{by + 64}" class="mono" font-size="12" fill="{MUTED}">STARS</text>
  <text x="{bx + 260}" y="{by + 96}" class="sans" font-size="32" font-weight="700" fill="{TEXT}">{d['gpu_stars']}</text>
  <clipPath id="fmclip"><rect x="{bx + 20}" y="{by + 104}" width="{bw - 40}" height="34"/></clipPath>
  <g clip-path="url(#fmclip)"><path class="wavefm" d="{wave}" fill="none" stroke="{VIOLET}" stroke-width="1.6" opacity=".8"/></g>
  <text x="{bx + 20}" y="{by + 152}" class="mono" font-size="12" fill="{MUTED}">COMMITS / WEEK, LAST 12</text>
  <line x1="{bx + 20}" y1="{by + 216.5}" x2="{bx + bw - 20}" y2="{by + 216.5}" stroke="{DIM}"/>
  {''.join(bars)}
  <text x="{bx + 20}" y="{by + 250}" class="mono" font-size="12" fill="{MUTED}">LATEST COMMIT</text>
  {latest_svg}
"""
    body = f"""
  <defs><linearGradient id="shinegrad" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".5" stop-color="#fff" stop-opacity=".55"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient></defs>
  {header(60, 46, "MISSION // macOS ON INTEL RAPTOR LAKE-P", "SYNC " + d['synced'])}
  <text x="60" y="80" class="sans" font-size="15" fill="{MUTED}">13th-gen Intel laptop iGPUs have no macOS driver. Bringing one up natively, subsystem by subsystem.</text>
  {''.join(rows)}
  {tele}
  <text x="60" y="452" class="mono" font-size="12" fill="{MUTED}">REF RIG: ASUS TUF F15 // i7-13620H // UHD GRAPHICS A7A8 // EXPERIMENTAL, TESTED ON ONE MACHINE</text>
"""
    return svg(1200, 476, body, css, "macOS on Intel Raptor Lake-P: subsystem status and live commit telemetry")


# ---------------------------------------------------------------- trophy cards

WINS = [
    ("01", "1ST", GOLD, "SOVENTURE 2025", "FIRST PLACE", "prompt-play",
     "ChromeForge: describe a Chrome extension in plain words, get a working one."),
    ("02", "1ST", GOLD, "NaSCon '26 APP DEV", "TIED 1ST OF 12 TEAMS", "nascon26-appdev",
     "League platform plus offline-first Flutter app in two days. 1,246 tests."),
    ("03", "2ND", SILVER, "AGENTHACK 2026", "NATIONAL RUNNER-UP", "autosdr",
     "An autonomous 11-agent sales team, built in 24 hours."),
]


def win_card(i, w):
    num, place, col, event, result, repo, blurb = w
    W, H = 400, 236
    css = f"""
  .shimmer {{ animation: shimmer 5s ease-in-out infinite {i * 0.9}s; }}
  @keyframes shimmer {{ 0% {{ transform: translateX(-260px) skewX(-20deg); }} 45%, 100% {{ transform: translateX(520px) skewX(-20deg); }} }}
  .twinkle {{ animation: twinkle 2.8s ease-in-out infinite; }}
  @keyframes twinkle {{ 0%, 100% {{ opacity: 0; transform: scale(.4); }} 50% {{ opacity: 1; transform: scale(1); }} }}
  .twinkle {{ transform-box: fill-box; transform-origin: center; }}
"""
    hexagon = " ".join(f"{330 + 34 * math.cos(a):.1f},{62 + 34 * math.sin(a):.1f}"
                       for a in [k * 3.14159 / 3 + 3.14159 / 6 for k in range(6)])
    stars = "".join(f'<path class="twinkle" style="animation-delay:{k * 0.7 + i * 0.3:.1f}s" d="M{x} {y - 6}L{x + 1.5} {y - 1.5}L{x + 6} {y}L{x + 1.5} {y + 1.5}L{x} {y + 6}L{x - 1.5} {y + 1.5}L{x - 6} {y}L{x - 1.5} {y - 1.5}Z" fill="{col}"/>'
                    for k, (x, y) in enumerate([(282, 30), (372, 100), (296, 104)]))
    lines = wrap(blurb, 44)[:2]
    blurb_svg = "".join(f'<text x="24" y="{186 + k * 20}" class="sans" font-size="14" fill="{MUTED}">{escape(t)}</text>' for k, t in enumerate(lines))
    body = f"""
  <defs>
    <linearGradient id="border" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="{W}" y2="{H}">
      <stop offset="0" stop-color="{col}"/><stop offset=".4" stop-color="{CYAN}" stop-opacity=".2"/><stop offset=".7" stop-color="{VIOLET}"/><stop offset="1" stop-color="{col}"/>
      <animateTransform attributeName="gradientTransform" type="rotate" values="0 {W / 2} {H / 2};360 {W / 2} {H / 2}" dur="6s" repeatCount="indefinite"/>
    </linearGradient>
    <linearGradient id="sh" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".5" stop-color="#fff" stop-opacity=".09"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
    <linearGradient id="numgrad" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{col}"/><stop offset="1" stop-color="{col}" stop-opacity=".25"/></linearGradient>
  </defs>
  <rect x="3" y="3" width="{W - 6}" height="{H - 6}" rx="15" fill="none" stroke="url(#border)" stroke-width="2.5"/>
  <text x="24" y="70" class="mono" font-size="56" font-weight="700" fill="url(#numgrad)">{num}</text>
  <polygon points="{hexagon}" fill="{col}" fill-opacity=".1" stroke="{col}" stroke-width="2" filter="url(#softglow)"/>
  <text x="330" y="70" text-anchor="middle" class="mono" font-size="20" font-weight="700" fill="{col}">{place}</text>
  {stars}
  <text x="24" y="118" class="sans" font-size="21" font-weight="700" fill="{TEXT}" letter-spacing="1">{escape(event)}</text>
  <text x="24" y="142" class="mono" font-size="13" fill="{col}" letter-spacing="1.5">{escape(result)}</text>
  <text x="24" y="164" class="mono" font-size="13" fill="{CYAN}">&gt; {escape(repo)}</text>
  {blurb_svg}
  <rect class="shimmer" x="0" y="0" width="120" height="{H}" fill="url(#sh)"/>
"""
    return svg(W, H, body, css, f"{event}: {result}, {repo}")


# ---------------------------------------------------------------- telemetry

def telemetry(d):
    css = """
  .draw { stroke-dasharray: 1600; stroke-dashoffset: 1600; animation: draw 3s ease-out forwards; }
  @keyframes draw { to { stroke-dashoffset: 0; } }
  .fade { opacity: 0; animation: fade 1.5s ease-out 1.8s forwards; }
  @keyframes fade { to { opacity: 1; } }
  .bar { transform-box: fill-box; transform-origin: left; transform: scaleX(0); animation: barx 1.2s cubic-bezier(.2,.8,.2,1) forwards; }
  @keyframes barx { to { transform: scaleX(1); } }
  .ping { transform-box: fill-box; transform-origin: center; animation: ping 1.8s ease-out infinite; }
  @keyframes ping { from { transform: scale(.6); opacity: .9; } to { transform: scale(3); opacity: 0; } }
"""
    tiles = [("CONTRIBUTIONS // 12M", d["total"], CYAN), ("LAST 30 DAYS", d["last30"], VIOLET),
             ("CURRENT STREAK", f"{d['streak']}d", MAGENTA), ("PUBLIC REPOS", d["repos"], GREEN)]
    t_svg = []
    for k, (label, val, col) in enumerate(tiles):
        x, y = 50 + (k % 2) * 262, 84 + (k // 2) * 112
        t_svg.append(f'<rect x="{x}" y="{y}" width="244" height="96" rx="10" fill="#08101e" fill-opacity=".85" stroke="{col}" stroke-opacity=".35"/>'
                     f'<rect x="{x}" y="{y + 18}" width="3" height="60" fill="{col}"/>'
                     f'<text x="{x + 20}" y="{y + 30}" class="mono" font-size="12" fill="{MUTED}" letter-spacing="1">{label}</text>'
                     f'<text x="{x + 20}" y="{y + 76}" class="sans" font-size="40" font-weight="700" fill="{TEXT}" filter="url(#softglow)">{val}</text>')

    cx, cy, cw, ch = 610, 92, 540, 150
    weeks = d["weeks"]
    peak = max(weeks) or 1
    pts = [(cx + k * cw / (len(weeks) - 1), cy + ch - ch * math.sqrt(n / peak)) for k, n in enumerate(weeks)]
    line = "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts)
    area = line + f" L{cx + cw} {cy + ch} L{cx} {cy + ch} Z"
    lx, ly = pts[-1]

    total_bytes = sum(b for _, b in d["langs"]) or 1
    lang_svg, x = [], cx
    for k, (name, b) in enumerate(d["langs"]):
        w = cw * b / total_bytes
        lang_svg.append(f'<rect class="bar" style="animation-delay:{0.4 + k * 0.15:.2f}s" x="{x:.1f}" y="290" width="{max(w - 2, 1):.1f}" height="10" rx="2" fill="{LANG_COLORS[k]}"/>')
        x += w
    lx2 = cx
    for k, (name, b) in enumerate(d["langs"]):
        label = f"{name} {100 * b / total_bytes:.0f}%"
        lang_svg.append(f'<circle cx="{lx2 + 5}" cy="321" r="4.5" fill="{LANG_COLORS[k]}"/><text x="{lx2 + 15}" y="325" class="mono" font-size="12" fill="{MUTED}">{escape(label)}</text>')
        lx2 += len(label) * 7.4 + 30

    body = f"""
  <defs><linearGradient id="area" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{CYAN}" stop-opacity=".35"/><stop offset="1" stop-color="{CYAN}" stop-opacity="0"/></linearGradient>
  <linearGradient id="linegrad" x1="0" x2="1"><stop offset="0" stop-color="{VIOLET}"/><stop offset="1" stop-color="{CYAN}"/></linearGradient></defs>
  {header(50, 50, "TELEMETRY // LAST 12 MONTHS", "SYNC " + d['synced'])}
  {''.join(t_svg)}
  <text x="{cx}" y="{cy - 8}" class="mono" font-size="12" fill="{MUTED}" letter-spacing="1">CONTRIBUTIONS PER WEEK</text>
  {''.join(f'<line x1="{cx}" y1="{cy + ch * f:.1f}" x2="{cx + cw}" y2="{cy + ch * f:.1f}" stroke="{DIM}" stroke-dasharray="2 6"/>' for f in (0.25, 0.5, 0.75))}
  <line x1="{cx}" y1="{cy + ch}" x2="{cx + cw}" y2="{cy + ch}" stroke="{DIM}"/>
  <path class="fade" d="{area}" fill="url(#area)"/>
  <path class="draw" d="{line}" fill="none" stroke="url(#linegrad)" stroke-width="2.5" stroke-linejoin="round" filter="url(#softglow)"/>
  <circle class="ping" cx="{lx:.1f}" cy="{ly:.1f}" r="5" fill="none" stroke="{MAGENTA}" stroke-width="2"/>
  <circle cx="{lx:.1f}" cy="{ly:.1f}" r="4.5" fill="{MAGENTA}"/>
  <text x="{cx}" y="278" class="mono" font-size="12" fill="{MUTED}" letter-spacing="1">LANGUAGES // {'OWN REPOS, INCL. PRIVATE GPU KIT' if d['langs_private'] else 'OWN PUBLIC REPOS'}</text>
  {''.join(lang_svg)}
"""
    return svg(1200, 350, body, css, f"{d['total']} contributions in the last year, {d['streak']}-day streak")


# ---------------------------------------------------------------- loadout

STACK = ["Python", "C++", "TypeScript", "Dart / Flutter", "FastAPI", "PostgreSQL",
         "Redis", "Docker", "OpenCore / ACPI", "macOS kexts", "LLM agents + RAG", "x86 assembly"]


def loadout():
    css = """
  .led { animation: pulse 2.4s ease-in-out infinite; }
  .tile { animation: tile 4.8s ease-in-out infinite; }
  @keyframes tile { 0%, 100% { stroke-opacity: .25; } 50% { stroke-opacity: .9; } }
"""
    tiles = []
    for k, name in enumerate(STACK):
        x, y = 50 + (k % 6) * 186, 76 + (k // 6) * 58
        col = [CYAN, VIOLET, MAGENTA][k % 3]
        tiles.append(f'<rect class="tile" style="animation-delay:{k * 0.4:.1f}s" x="{x}" y="{y}" width="172" height="42" rx="6" fill="#08101e" fill-opacity=".85" stroke="{col}"/>'
                     f'<circle class="led" style="animation-delay:{k * 0.2:.1f}s" cx="{x + 18}" cy="{y + 21}" r="4" fill="{col}" filter="url(#softglow)"/>'
                     f'<text x="{x + 32}" y="{y + 26}" class="mono" font-size="13.5" fill="{TEXT}">{escape(name)}</text>')
    body = header(50, 50, "LOADOUT") + "".join(tiles)
    return svg(1200, 210, body, css, "Stack: " + ", ".join(STACK))


# ---------------------------------------------------------------- main

def main():
    d = collect()
    OUT.mkdir(exist_ok=True)
    files = {"hero.svg": hero(d), "gpu.svg": gpu_panel(d), "telemetry.svg": telemetry(d), "loadout.svg": loadout()}
    for i, w in enumerate(WINS):
        files[f"win-{i + 1}.svg"] = win_card(i, w)
    for name, content in files.items():
        (OUT / name).write_text(content, encoding="utf-8")
    print(json.dumps({k: v for k, v in d.items() if k not in ("weeks",)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
