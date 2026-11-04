#!/usr/bin/env python3
"""
Grimoire generator: turns your GitHub stats into animated, RPG-themed SVGs.

  python scripts/grimoire.py                 # live data (needs GITHUB_TOKEN)
  python scripts/grimoire.py --sample        # fake data, for previewing

Env:
  GITHUB_TOKEN   token for the GraphQL API (Actions' built-in token works;
                 a PAT with read:user also counts private contributions)
  GH_USER        username (default: abhi-jithb)
  OUT_DIR        output folder (default: dist)

Pure stdlib. Writes: hero.svg, mage-card.svg, affinity.svg, mana.svg,
battle.svg, divider.svg
"""
import base64, datetime as dt, json, math, os, random, sys, urllib.request
from xml.sax.saxutils import escape

USER = os.environ.get("GH_USER", "abhi-jithb")
OUT = os.environ.get("OUT_DIR", "dist")
TOKEN = os.environ.get("GITHUB_TOKEN", "")

# ---------- palette ----------
BG, PANEL, EDGE = "#0b0710", "#150d1f", "#2a1838"
CRIMSON, GOLD, VIOLET = "#ff3b5c", "#f5c451", "#9b6bff"
INK, MUTED = "#f1e8da", "#9a8cae"
SERIF = "'Cinzel','Trajan Pro',Georgia,'Times New Roman',serif"
SANS = "'Segoe UI',Ubuntu,'Helvetica Neue',Arial,sans-serif"
MONO = "'Fira Code','JetBrains Mono',Consolas,monospace"

ELEMENTS = {  # language -> (element, glyph)
    "TypeScript": ("Lightning", "⚡"), "JavaScript": ("Flame", "🔥"),
    "Go": ("Wind", "🌪"), "Python": ("Serpent", "🐍"), "HTML": ("Earth", "⛰"),
    "CSS": ("Water", "🌊"), "SCSS": ("Water", "🌊"), "Rust": ("Iron", "⚙"),
    "Java": ("Ember", "☕"), "C": ("Stone", "🪨"), "C++": ("Steel", "🗡"),
    "Shell": ("Shadow", "🌑"), "Dart": ("Arrow", "🏹"), "Kotlin": ("Frost", "❄"),
    "Vue": ("Leaf", "🍃"), "Svelte": ("Blaze", "✴"), "Jupyter Notebook": ("Star", "✨"),
    "Dockerfile": ("Tide", "🐋"), "Lua": ("Moon", "🌙"), "PHP": ("Mist", "🌫"),
}

RANKS = [  # lifetime contributions threshold, title
    (0, "Apprentice Mage"), (100, "Junior Magic Knight"), (300, "Magic Knight"),
    (700, "Senior Magic Knight"), (1500, "Vice Captain"), (3000, "Squad Captain"),
    (6000, "Archmage"), (12000, "Grand Archmage"),
]


# ---------- data ----------
def gql(query, variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "User-Agent": "grimoire-readme"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        body = json.load(r)
    if body.get("errors"):
        raise SystemExit(f"GraphQL error: {body['errors']}")
    return body["data"]


def fetch_live():
    if not TOKEN:
        raise SystemExit("GITHUB_TOKEN is not set (or run with --sample).")
    base = gql("""
    query($login:String!){ user(login:$login){
      name login avatarUrl createdAt followers{totalCount}
      pullRequests{totalCount} merged:pullRequests(states:MERGED){totalCount}
      issues{totalCount}
      contributionsCollection{ contributionYears
        contributionCalendar{ totalContributions
          weeks{ contributionDays{ date contributionCount } } } }
    }}""", {"login": USER})["user"]

    # repos (paginated) for stars + languages
    repos, cursor = [], None
    while True:
        page = gql("""
        query($login:String!,$after:String){ user(login:$login){
          repositories(ownerAffiliations:OWNER,isFork:false,first:100,after:$after){
            totalCount pageInfo{hasNextPage endCursor}
            nodes{ stargazerCount
              languages(first:10,orderBy:{field:SIZE,direction:DESC}){
                edges{ size node{ name color } } } } } }}""",
            {"login": USER, "after": cursor})["user"]["repositories"]
        repos += page["nodes"]
        total_repos = page["totalCount"]
        if not page["pageInfo"]["hasNextPage"]:
            break
        cursor = page["pageInfo"]["endCursor"]

    # every contribution year, for lifetime totals + longest streak
    days, lifetime = {}, 0
    for y in base["contributionsCollection"]["contributionYears"]:
        cal = gql("""
        query($login:String!,$from:DateTime!,$to:DateTime!){ user(login:$login){
          contributionsCollection(from:$from,to:$to){ contributionCalendar{
            totalContributions weeks{ contributionDays{ date contributionCount } } } } }}""",
            {"login": USER, "from": f"{y}-01-01T00:00:00Z", "to": f"{y}-12-31T23:59:59Z"},
        )["user"]["contributionsCollection"]["contributionCalendar"]
        lifetime += cal["totalContributions"]
        for w in cal["weeks"]:
            for d in w["contributionDays"]:
                days[d["date"]] = d["contributionCount"]

    langs, lcolor = {}, {}
    for r in repos:
        for e in r["languages"]["edges"]:
            n = e["node"]["name"]
            langs[n] = langs.get(n, 0) + e["size"]
            lcolor[n] = e["node"]["color"] or VIOLET

    avatar = ""
    try:
        with urllib.request.urlopen(base["avatarUrl"] + "&s=240", timeout=30) as r:
            avatar = "data:image/png;base64," + base64.b64encode(r.read()).decode()
    except Exception:
        pass

    weeks = base["contributionsCollection"]["contributionCalendar"]["weeks"]
    year_total = base["contributionsCollection"]["contributionCalendar"]["totalContributions"]
    return dict(
        name=base["name"] or base["login"], login=base["login"], avatar=avatar,
        lifetime=lifetime, year=year_total, days=days,
        calendar=[[d["contributionCount"] for d in w["contributionDays"]] for w in weeks],
        prs=base["pullRequests"]["totalCount"], merged=base["merged"]["totalCount"],
        issues=base["issues"]["totalCount"], followers=base["followers"]["totalCount"],
        stars=sum(r["stargazerCount"] for r in repos), repos=total_repos,
        langs=langs, lcolor=lcolor,
    )


def fetch_sample():
    rnd = random.Random(7)
    today = dt.date.today()
    days, cal = {}, []
    start = today - dt.timedelta(days=370)
    week = []
    for i in range(371):
        d = start + dt.timedelta(days=i)
        c = 0 if rnd.random() < 0.35 else int(rnd.expovariate(0.3)) + 1
        if i > 362:
            c = max(c, 1)
        days[d.isoformat()] = c
        week.append(c)
        if len(week) == 7:
            cal.append(week); week = []
    return dict(
        name="Abhijith B", login=USER, avatar="", lifetime=1840, year=sum(days.values()),
        days=days, calendar=cal[-53:], prs=142, merged=118, issues=57, followers=96,
        stars=73, repos=48,
        langs={"TypeScript": 41, "JavaScript": 27, "Go": 12, "HTML": 8, "CSS": 7, "Python": 3, "Shell": 2},
        lcolor={"TypeScript": "#3178c6", "JavaScript": "#f1e05a", "Go": "#00ADD8", "HTML": "#e34c26",
                "CSS": "#663399", "Python": "#3572A5", "Shell": "#89e051"},
    )


def derive(s):
    ordered = sorted(s["days"].items())
    longest = run = 0
    for _, c in ordered:
        run = run + 1 if c > 0 else 0
        longest = max(longest, run)
    today = dt.date.today()
    cur, d = 0, today
    if s["days"].get(d.isoformat(), 0) == 0:
        d -= dt.timedelta(days=1)
    while s["days"].get(d.isoformat(), 0) > 0:
        cur += 1; d -= dt.timedelta(days=1)
    total = s["lifetime"]
    level = int(math.sqrt(total / 5)) + 1
    lo, hi = 5 * (level - 1) ** 2, 5 * level ** 2
    rank = [t for th, t in RANKS if total >= th][-1]
    nxt = next(((th, t) for th, t in RANKS if th > total), None)
    s.update(streak=cur, longest=longest, level=level, xp_pct=(total - lo) / (hi - lo),
             xp_lo=lo, xp_hi=hi, rank=rank, next_rank=nxt)
    return s


# ---------- svg helpers ----------
def fmt(n):
    return f"{n:,}"


def svg(w, h, body, style="", defs=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
            f'role="img" font-family="{SANS}">\n<defs>{GLOW}{defs}</defs>\n<style>{BASE_CSS}{style}</style>\n'
            f'{body}\n</svg>\n')


GLOW = """
<filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
  <feGaussianBlur stdDeviation="4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
<filter id="bigglow" x="-80%" y="-80%" width="260%" height="260%">
  <feGaussianBlur stdDeviation="12" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
<linearGradient id="goldgrad" x1="0" x2="1"><stop offset="0" stop-color="#fff1c4"/><stop offset=".5" stop-color="#f5c451"/><stop offset="1" stop-color="#ff7a3d"/></linearGradient>
<linearGradient id="bloodgrad" x1="0" x2="1"><stop offset="0" stop-color="#ff3b5c"/><stop offset="1" stop-color="#9b6bff"/></linearGradient>
<radialGradient id="halo"><stop offset="0" stop-color="#ff3b5c" stop-opacity=".28"/><stop offset=".6" stop-color="#9b6bff" stop-opacity=".08"/><stop offset="1" stop-color="#9b6bff" stop-opacity="0"/></radialGradient>
<radialGradient id="vignette" cx=".5" cy=".5" r=".75"><stop offset="0" stop-color="#1d1029"/><stop offset="1" stop-color="#07040b"/></radialGradient>
"""

BASE_CSS = """
.spin{transform-box:fill-box;transform-origin:center;animation:spin 40s linear infinite}
.spinr{transform-box:fill-box;transform-origin:center;animation:spin 28s linear infinite reverse}
.pulse{animation:pulse 2.6s ease-in-out infinite}
.fade{opacity:0;animation:fadein .7s ease-out forwards}
.twinkle{animation:twinkle 3s ease-in-out infinite}
@keyframes spin{to{transform:rotate(360deg)}}
@keyframes pulse{0%,100%{opacity:.55}50%{opacity:1}}
@keyframes fadein{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
@keyframes twinkle{0%,100%{opacity:.15}50%{opacity:.9}}
"""


def rot(cx, cy, dur, rev=False):
    a, b = (360, 0) if rev else (0, 360)
    return (f'<animateTransform attributeName="transform" type="rotate" from="{a} {cx} {cy}" '
            f'to="{b} {cx} {cy}" dur="{dur}s" repeatCount="indefinite"/>')


def frame(w, h, title=None):
    """Panel with gold corner filigree and an optional banner title."""
    c = 22
    corners = "".join(
        f'<path d="M{x} {y+sy*c} L{x} {y} L{x+sx*c} {y}" stroke="{GOLD}" stroke-width="2.5" fill="none" filter="url(#glow)"/>'
        f'<circle cx="{x}" cy="{y}" r="3.5" fill="{GOLD}"/>'
        for x, y, sx, sy in [(10, 10, 1, 1), (w-10, 10, -1, 1), (10, h-10, 1, -1), (w-10, h-10, -1, -1)])
    t = ""
    if title:
        t = (f'<text x="{w/2}" y="40" text-anchor="middle" font-family="{SERIF}" font-size="17" '
             f'letter-spacing="5" fill="{GOLD}" font-weight="700">{escape(title)}</text>'
             f'<path d="M{w/2-230} 34 H{w/2-170} M{w/2+170} 34 H{w/2+230}" stroke="{GOLD}" stroke-opacity=".5"/>')
    return (f'<rect width="{w}" height="{h}" rx="16" fill="url(#vignette)"/>'
            f'<rect x="10" y="10" width="{w-20}" height="{h-20}" rx="10" fill="none" stroke="{EDGE}" stroke-width="1.5"/>'
            f'{corners}{t}')


def stars(w, h, n, seed):
    r = random.Random(seed)
    return "".join(
        f'<circle cx="{r.uniform(20,w-20):.0f}" cy="{r.uniform(20,h-20):.0f}" r="{r.choice([.8,1,1.3,1.7])}" '
        f'fill="{r.choice([INK,GOLD,VIOLET])}" class="twinkle" style="animation-delay:{r.uniform(0,3):.2f}s"/>'
        for _ in range(n))


def embers(w, h, n, seed):
    r = random.Random(seed)
    out = []
    for _ in range(n):
        x, dur, delay = r.uniform(0, w), r.uniform(5, 10), r.uniform(0, 8)
        out.append(f'<circle cx="{x:.0f}" cy="{h+10}" r="{r.uniform(1.2,2.8):.1f}" fill="{r.choice([CRIMSON,GOLD,"#ff7a3d"])}" '
                   f'filter="url(#glow)" style="animation:rise {dur:.1f}s linear {delay:.1f}s infinite"/>')
    return "".join(out) + f"<style>@keyframes rise{{0%{{transform:translateY(0);opacity:0}}10%{{opacity:1}}100%{{transform:translateY(-{h+40}px) translateX(30px);opacity:0}}}}</style>"


def magic_circle(cx, cy, R, runes):
    """Layered rotating sigil with code-runes on a text path."""
    oct_pts = lambda r, off: " ".join(
        f"{cx+r*math.cos(math.radians(a+off)):.1f},{cy+r*math.sin(math.radians(a+off)):.1f}" for a in range(0, 360, 90))
    return f"""
<g filter="url(#glow)">
  <circle cx="{cx}" cy="{cy}" r="{R*1.1}" fill="url(#halo)"/>
  <g>{rot(cx, cy, 40)}
    <path id="runepath" d="M{cx-R*.86},{cy} a{R*.86},{R*.86} 0 1,1 {R*1.72},0 a{R*.86},{R*.86} 0 1,1 {-R*1.72},0" fill="none"/>
    <circle cx="{cx}" cy="{cy}" r="{R}" fill="none" stroke="{GOLD}" stroke-width="2"/>
    <circle cx="{cx}" cy="{cy}" r="{R*.76}" fill="none" stroke="{GOLD}" stroke-width="1" stroke-opacity=".6"/>
    <text font-family="{MONO}" font-size="{R*.095:.0f}" fill="{GOLD}" letter-spacing="2"><textPath href="#runepath">{escape(runes)}</textPath></text>
  </g>
  <g>{rot(cx, cy, 28, True)}
    <circle cx="{cx}" cy="{cy}" r="{R*.66}" fill="none" stroke="{CRIMSON}" stroke-width="1.5" stroke-dasharray="6 9"/>
    <polygon points="{oct_pts(R*.64, 0)}" fill="none" stroke="{CRIMSON}" stroke-width="1.6"/>
    <polygon points="{oct_pts(R*.64, 45)}" fill="none" stroke="{CRIMSON}" stroke-width="1.6"/>
  </g>
  <g>{rot(cx, cy, 14)}
    <circle cx="{cx}" cy="{cy}" r="{R*.38}" fill="none" stroke="{VIOLET}" stroke-width="1.4" stroke-dasharray="2 6"/>
  </g>
</g>"""


def grimoire_book(cx, cy, s=1.0):
    return f"""
<g transform="translate({cx} {cy}) scale({s})" filter="url(#bigglow)">
  <g style="animation:hover 4s ease-in-out infinite">
    <rect x="-46" y="-32" width="92" height="64" rx="6" fill="#2b0f1c" stroke="{GOLD}" stroke-width="2"/>
    <rect x="-40" y="-26" width="38" height="52" rx="2" fill="#f3e3c3"/>
    <rect x="2" y="-26" width="38" height="52" rx="2" fill="#efdcb6"/>
    <g style="transform-box:fill-box;transform-origin:left center;animation:flip 3.2s ease-in-out infinite">
      <rect x="2" y="-26" width="38" height="52" rx="2" fill="#fff4d8"/>
    </g>
    <text x="-21" y="6" text-anchor="middle" font-family="{MONO}" font-size="15" font-weight="700" fill="#7a1530">&lt;/&gt;</text>
    <path d="M10 -14 h22 M10 -6 h18 M10 2 h24 M10 10 h14" stroke="#7a1530" stroke-width="2" stroke-linecap="round" opacity=".55"/>
    <circle cx="0" cy="-52" r="6" fill="{GOLD}" class="pulse"/>
  </g>
</g>
<style>@keyframes hover{{0%,100%{{transform:translateY(0)}}50%{{transform:translateY(-8px)}}}}
@keyframes flip{{0%,40%{{transform:scaleX(1)}}60%,100%{{transform:scaleX(-1)}}}}</style>"""


# ---------- cards ----------
def hero(s):
    W, H = 1200, 400
    lines = ["Full Stack Mage", "Open Source Knight", "Summoner of Bugs (unintentional)",
             "Captain of the 2 AM Deploy Squad"]
    n = len(lines); cyc = n * 3.2
    cycling = "".join(
        f'<text x="80" y="268" font-family="{MONO}" font-size="24" fill="{INK}" '
        f'style="opacity:0;animation:cyc {cyc}s linear {i*3.2}s infinite">'
        f'<tspan fill="{CRIMSON}">&gt;</tspan> cast <tspan fill="{GOLD}">{escape(l)}</tspan><tspan class="caret">▌</tspan></text>'
        for i, l in enumerate(lines))
    p = 100 / n
    body = f"""
{frame(W, H)}
{stars(W, H, 70, 1)}
{magic_circle(930, 200, 150, " ✦ git commit -m 'spell' ✦ npm run build ✦ go run . ✦ git push --force ✦ sudo make magic ✦ ")}
{grimoire_book(930, 200, 1.05)}
{embers(W, H, 26, 2)}
<text x="80" y="100" font-family="{SERIF}" font-size="15" letter-spacing="6" fill="{MUTED}" class="fade">GRIMOIRE OF THE MIDNIGHT COMMIT SQUAD</text>
<text x="76" y="188" font-family="{SERIF}" font-size="88" font-weight="700" fill="url(#shimmer)" filter="url(#glow)" class="fade" style="animation-delay:.2s">{escape(s['name'].upper())}</text>
<path d="M80 212 H560" stroke="url(#bloodgrad)" stroke-width="3" stroke-linecap="round" style="stroke-dasharray:480;stroke-dashoffset:480;animation:draw 1.4s ease-out .5s forwards"/>
{cycling}
<g class="fade" style="animation-delay:.9s">
  <rect x="80" y="304" width="360" height="40" rx="20" fill="{PANEL}" stroke="{GOLD}" stroke-opacity=".6"/>
  <text x="100" y="330" font-family="{SERIF}" font-size="16" fill="{GOLD}" letter-spacing="2">✦ {escape(s['rank'].upper())} · LV {s['level']}</text>
</g>
<text x="460" y="330" font-family="{MONO}" font-size="14" fill="{MUTED}" class="fade" style="animation-delay:1.1s">@{escape(s['login'])} · Kerala, IN</text>"""
    style = f"""
@keyframes cyc{{0%{{opacity:0}}{p*0.08:.1f}%{{opacity:1}}{p*0.9:.1f}%{{opacity:1}}{p:.1f}%,100%{{opacity:0}}}}
@keyframes draw{{to{{stroke-dashoffset:0}}}}
@keyframes sh{{0%{{stop-color:{GOLD}}}50%{{stop-color:#fff1c4}}100%{{stop-color:{GOLD}}}}}
.caret{{animation:pulse 1s steps(1) infinite}}"""
    defs = f"""<linearGradient id="shimmer" x1="0" x2="1"><stop offset="0" stop-color="{CRIMSON}"/>
<stop offset=".5" stop-color="{GOLD}" style="animation:sh 3s ease-in-out infinite"/><stop offset="1" stop-color="{VIOLET}"/></linearGradient>"""
    return svg(W, H, body, style, defs)


def mage_card(s):
    W, H = 1000, 330
    av = (f'<clipPath id="avc"><circle cx="150" cy="150" r="68"/></clipPath>'
          f'<image href="{s["avatar"]}" x="82" y="82" width="136" height="136" clip-path="url(#avc)"/>'
          if s["avatar"] else
          f'<circle cx="150" cy="150" r="68" fill="#2b0f1c"/><text x="150" y="168" text-anchor="middle" '
          f'font-family="{SERIF}" font-size="52" fill="{GOLD}">{escape(s["name"][:1])}</text>')
    xp_w = 420
    nr = s["next_rank"]
    nr_txt = f"{fmt(nr[0]-s['lifetime'])} more contributions to {nr[1]}" if nr else "Max rank reached"
    tiles = [
        ("⚔", "Lifetime contributions", fmt(s["lifetime"])),
        ("📜", f"Contributions in {dt.date.today().year}", fmt(s["year"])),
        ("🔥", "Current streak", f"{s['streak']} days"),
        ("🏔", "Longest streak", f"{s['longest']} days"),
        ("🗡", "Pull requests (merged)", f"{fmt(s['prs'])} ({fmt(s['merged'])})"),
        ("⭐", "Stars earned", fmt(s["stars"])),
    ]
    tg = ""
    for i, (ic, label, val) in enumerate(tiles):
        x, y = 640 + (i % 2) * 170, 74 + (i // 2) * 78
        tg += (f'<g class="fade" style="animation-delay:{.5+i*.15:.2f}s">'
               f'<rect x="{x}" y="{y}" width="158" height="66" rx="10" fill="{PANEL}" stroke="{EDGE}"/>'
               f'<text x="{x+12}" y="{y+26}" font-size="13" fill="{MUTED}">{ic} {escape(label)}</text>'
               f'<text x="{x+12}" y="{y+52}" font-family="{SERIF}" font-size="22" font-weight="700" fill="{INK}">{escape(val)}</text></g>')
    body = f"""
{frame(W, H, "MAGE LICENSE")}
{stars(W, H, 30, 3)}
<g>{rot(150, 150, 20)}<circle cx="150" cy="150" r="80" fill="none" stroke="{GOLD}" stroke-width="2" stroke-dasharray="4 8" filter="url(#glow)"/></g>
<circle cx="150" cy="150" r="72" fill="none" stroke="{CRIMSON}" stroke-width="3" class="pulse" filter="url(#glow)"/>
{av}
<text x="150" y="262" text-anchor="middle" font-family="{SERIF}" font-size="20" font-weight="700" fill="{INK}">{escape(s['name'])}</text>
<text x="150" y="286" text-anchor="middle" font-family="{MONO}" font-size="13" fill="{MUTED}">@{escape(s['login'])}</text>

<text x="270" y="96" font-size="13" letter-spacing="3" fill="{MUTED}">RANK</text>
<text x="270" y="134" font-family="{SERIF}" font-size="32" font-weight="700" fill="url(#goldgrad)" filter="url(#glow)" class="fade">{escape(s['rank'])}</text>
<text x="270" y="186" font-family="{SERIF}" font-size="44" font-weight="700" fill="{INK}">LV {s['level']}</text>
<text x="390" y="184" font-family="{MONO}" font-size="13" fill="{MUTED}">{fmt(s['lifetime'])} / {fmt(s['xp_hi'])} XP</text>
<rect x="270" y="204" width="{xp_w}" height="16" rx="8" fill="#22152e" stroke="{EDGE}"/>
<rect x="270" y="204" width="{max(8, xp_w*s['xp_pct']):.0f}" height="16" rx="8" fill="url(#bloodgrad)" filter="url(#glow)"
      style="transform-box:fill-box;transform-origin:left;transform:scaleX(0);animation:grow 1.6s cubic-bezier(.2,.8,.2,1) .4s forwards"/>
<text x="270" y="246" font-size="13" fill="{MUTED}">{escape(nr_txt)}</text>
<text x="270" y="282" font-size="13" fill="{MUTED}">🛡 {fmt(s['repos'])} repos · 👥 {fmt(s['followers'])} followers · 🪶 {fmt(s['issues'])} issues opened</text>
{tg}"""
    return svg(W, H, body, "@keyframes grow{to{transform:scaleX(1)}}")


def affinity(s):
    total = sum(s["langs"].values()) or 1
    top = sorted(s["langs"].items(), key=lambda kv: -kv[1])[:8]
    W, rowh = 1000, 44
    H = 90 + rowh * len(top)
    rows = ""
    for i, (name, size) in enumerate(top):
        pct = size / total
        el, gl = ELEMENTS.get(name, ("Arcane", "✦"))
        y, col = 80 + i * rowh, s["lcolor"].get(name, VIOLET)
        bw = max(6, 520 * pct / (top[0][1] / total))
        rows += f"""
<g class="fade" style="animation-delay:{i*.12:.2f}s">
  <text x="44" y="{y+20}" font-size="20">{gl}</text>
  <text x="80" y="{y+14}" font-family="{SERIF}" font-size="17" font-weight="700" fill="{INK}">{escape(name)}</text>
  <text x="80" y="{y+32}" font-size="12" fill="{MUTED}" letter-spacing="1">{escape(el.upper())} MAGIC</text>
  <rect x="300" y="{y+8}" width="520" height="14" rx="7" fill="#22152e"/>
  <rect x="300" y="{y+8}" width="{bw:.0f}" height="14" rx="7" fill="{col}" filter="url(#glow)"
        style="transform-box:fill-box;transform-origin:left;transform:scaleX(0);animation:grow 1.3s cubic-bezier(.2,.8,.2,1) {.3+i*.12:.2f}s forwards"/>
  <circle cx="{300+bw:.0f}" cy="{y+15}" r="4" fill="#fff" class="pulse" style="animation-delay:{i*.3:.1f}s"/>
  <text x="850" y="{y+21}" font-family="{MONO}" font-size="15" fill="{GOLD}">{pct*100:.1f}%</text>
</g>"""
    return svg(W, H, frame(W, H, "MAGIC AFFINITY") + stars(W, H, 25, 4) + rows,
               "@keyframes grow{to{transform:scaleX(1)}}")


def mana(s):
    cal = s["calendar"][-53:]
    W, H, cell, gap = 1000, 230, 14, 3
    x0 = (W - len(cal) * (cell + gap)) / 2
    mx = max([c for w in cal for c in w] + [1])
    shades = ["#1d1328", "#4a1530", "#8c1d3c", "#d72f55", "#ff8a4c", GOLD]
    cells = ""
    for wi, week in enumerate(cal):
        for di, c in enumerate(week):
            lvl = 0 if c == 0 else min(5, 1 + int(4 * c / mx))
            delay = wi * 0.035 + di * 0.02
            glow = ' filter="url(#glow)"' if lvl >= 4 else ""
            cells += (f'<rect x="{x0+wi*(cell+gap):.1f}" y="{62+di*(cell+gap)}" width="{cell}" height="{cell}" rx="3" '
                      f'fill="{shades[lvl]}"{glow} style="opacity:0;animation:pop .5s ease-out {delay:.2f}s forwards'
                      f'{",pulse 3s ease-in-out " + format(2+delay, ".2f") + "s infinite" if lvl >= 4 else ""}"/>')
    legend = "".join(f'<rect x="{770+i*18}" y="{H-42}" width="13" height="13" rx="3" fill="{c}"/>' for i, c in enumerate(shades))
    body = f"""{frame(W, H, "MANA FLOW · LAST 12 MONTHS")}{cells}
<text x="{x0:.0f}" y="{H-31}" font-size="14" fill="{MUTED}"><tspan fill="{GOLD}" font-weight="700">{fmt(s['year'])}</tspan> spells cast this year · current streak <tspan fill="{CRIMSON}" font-weight="700">{s['streak']}d</tspan></text>
<text x="740" y="{H-31}" font-size="12" fill="{MUTED}" text-anchor="end">less</text>{legend}
<text x="{770+6*18+6}" y="{H-31}" font-size="12" fill="{MUTED}">more</text>"""
    return svg(W, H, body, "@keyframes pop{from{opacity:0;transform:scale(.3)}to{opacity:1;transform:none}}"
               "rect{transform-box:fill-box;transform-origin:center}")


def battle(s):
    W, H = 1000, 360
    boss_hp = 1000
    dmg = s["year"]
    cleared, rem = divmod(dmg, boss_hp)
    hp_pct = 1 - rem / boss_hp
    bx, by = 760, 205
    orbs = "".join(
        f'<circle r="9" fill="{c}" filter="url(#bigglow)" style="animation:shoot 2.4s cubic-bezier(.5,0,.8,.6) {i*0.6:.1f}s infinite;'
        f'offset-path:path(\'M300 170 Q {520} {60+i*25} {bx-30} {by-10}\')"/>'
        for i, c in enumerate([CRIMSON, GOLD, VIOLET, "#ff7a3d"]))
    hits = "".join(
        f'<text x="{bx+165}" y="{by-75+dx}" text-anchor="middle" font-family="{SERIF}" font-size="20" font-weight="700" '
        f'fill="{c}" style="opacity:0;animation:dmg 2.4s ease-out {1.9+i*0.6:.1f}s infinite">-{v}</text>'
        for i, (dx, c, v) in enumerate([(0, CRIMSON, fmt(s['year'])), (60, GOLD, fmt(s['merged'])),
                                         (30, VIOLET, fmt(s['issues'])), (90, "#ff7a3d", f"{s['streak']}d")]))
    log = [
        f"⚔ Commit Barrage hits for {fmt(s['year'])} this year!",
        f"🗡 Pull Request Lance: {fmt(s['prs'])} casts, {fmt(s['merged'])} merged",
        f"🪶 Issue Seal binds {fmt(s['issues'])} bugs",
        f"🔥 Streak Aura burning for {s['streak']} days",
    ]
    logs = "".join(f'<text x="44" y="{258+i*22}" font-family="{MONO}" font-size="14" fill="{INK}" class="fade" '
                   f'style="animation-delay:{.6+i*.5:.1f}s">{escape(l)}</text>' for i, l in enumerate(log))
    status = (f"DEFEATED ×{cleared} · now fighting NG+{cleared}" if cleared else "BATTLE IN PROGRESS")
    body = f"""
{frame(W, H, "BOSS RAID · THE LEGACY CODE BEHEMOTH")}
{stars(W, H, 30, 5)}
<path d="M30 236 H970" stroke="{EDGE}" stroke-width="2"/>
<ellipse cx="230" cy="236" rx="70" ry="10" fill="{CRIMSON}" opacity=".25" class="pulse"/>
<ellipse cx="{bx}" cy="236" rx="120" ry="14" fill="{VIOLET}" opacity=".2" class="pulse"/>

<!-- mage -->
<g style="animation:bob 2.4s ease-in-out infinite">
  <path d="M195 232 L230 150 L265 232 Z" fill="#3a0f22" stroke="{CRIMSON}" stroke-width="2"/>
  <path d="M212 200 L248 200" stroke="{GOLD}" stroke-width="3"/>
  <circle cx="230" cy="138" r="16" fill="#f1d3b3"/>
  <path d="M206 132 L230 84 L256 132 Z" fill="#1d0b30" stroke="{VIOLET}" stroke-width="2"/>
  <path d="M206 132 Q230 140 256 132" stroke="{GOLD}" stroke-width="3" fill="none"/>
  <circle cx="236" cy="140" r="2" fill="#000"/>
  <path d="M262 232 L292 150" stroke="#8a5a2b" stroke-width="5" stroke-linecap="round"/>
  <circle cx="296" cy="166" r="11" fill="{GOLD}" filter="url(#bigglow)" class="pulse"/>
  <g>{rot(296, 166, 6)}<circle cx="296" cy="166" r="22" fill="none" stroke="{GOLD}" stroke-dasharray="3 5"/></g>
</g>
<text x="230" y="70" text-anchor="middle" font-family="{SERIF}" font-size="14" fill="{GOLD}" letter-spacing="2">{escape(s['name'].split()[0].upper())} · LV {s['level']}</text>

{orbs}

<!-- boss -->
<g style="animation:shake 2.4s ease-in-out 1.8s infinite">
  <path d="M{bx-110} 232 C{bx-120} 140 {bx-70} 92 {bx} 92 C{bx+70} 92 {bx+120} 140 {bx+110} 232
           L{bx+80} 214 L{bx+55} 234 L{bx+25} 214 L{bx} 234 L{bx-25} 214 L{bx-55} 234 L{bx-80} 214 Z"
        fill="#1b0f27" stroke="{VIOLET}" stroke-width="2.5" filter="url(#glow)"/>
  <path d="M{bx-62} 104 L{bx-90} 58 L{bx-40} 96 M{bx+62} 104 L{bx+90} 58 L{bx+40} 96" fill="#1b0f27" stroke="{VIOLET}" stroke-width="2.5"/>
  <ellipse cx="{bx-35}" cy="150" rx="14" ry="10" fill="{CRIMSON}" filter="url(#glow)" class="pulse"/>
  <ellipse cx="{bx+35}" cy="150" rx="14" ry="10" fill="{CRIMSON}" filter="url(#glow)" class="pulse"/>
  <path d="M{bx-40} 188 Q{bx} 172 {bx+40} 188" stroke="{CRIMSON}" stroke-width="3" fill="none"/>
  <text x="{bx}" y="132" text-anchor="middle" font-family="{MONO}" font-size="11" fill="{MUTED}">// TODO: refactor</text>
  <text x="{bx-80}" y="206" font-family="{MONO}" font-size="12" fill="{VIOLET}" opacity=".7">null</text>
  <text x="{bx+52}" y="206" font-family="{MONO}" font-size="12" fill="{VIOLET}" opacity=".7">any</text>
</g>
{hits}

<!-- hp bar -->
<text x="{bx-150}" y="262" font-size="12" fill="{MUTED}" letter-spacing="2">BEHEMOTH HP</text>
<rect x="{bx-150}" y="268" width="300" height="12" rx="6" fill="#22152e" stroke="{EDGE}"/>
<rect x="{bx-150}" y="268" width="300" height="12" rx="6" fill="url(#bloodgrad)" filter="url(#glow)"
      style="transform-box:fill-box;transform-origin:left;animation:drain 2.5s ease-out 1s forwards"/>
<text x="{bx+150}" y="262" text-anchor="end" font-family="{MONO}" font-size="12" fill="{GOLD}">{boss_hp-rem}/{boss_hp}</text>

{logs}
<text x="{W-44}" y="{H-36}" text-anchor="end" font-family="{SERIF}" font-size="16" letter-spacing="3"
      fill="{GOLD if cleared else CRIMSON}" class="pulse">{escape(status)}</text>
<text x="{W-44}" y="{H-52}" text-anchor="end" font-size="12" fill="{MUTED}">1 contribution = 1 damage · boss respawns every {boss_hp} hits</text>"""
    style = f"""
@keyframes shoot{{0%{{offset-distance:0%;opacity:0}}10%{{opacity:1}}85%{{opacity:1}}100%{{offset-distance:100%;opacity:0}}}}
@keyframes dmg{{0%{{opacity:0;transform:translateY(0)}}10%{{opacity:1}}60%{{opacity:1;transform:translateY(-30px)}}100%{{opacity:0;transform:translateY(-40px)}}}}
@keyframes shake{{0%,70%,100%{{transform:translateX(0)}}75%{{transform:translateX(-6px)}}80%{{transform:translateX(6px)}}85%{{transform:translateX(-4px)}}90%{{transform:translateX(3px)}}}}
@keyframes bob{{0%,100%{{transform:translateY(0)}}50%{{transform:translateY(-6px)}}}}
@keyframes drain{{from{{transform:scaleX(1)}}to{{transform:scaleX({hp_pct:.3f})}}}}"""
    return svg(W, H, body, style)


def divider():
    W, H = 1000, 40
    body = f"""
<path d="M40 20 H440 M560 20 H960" stroke="url(#bloodgrad)" stroke-width="1.5" opacity=".7"/>
<g filter="url(#glow)">
  <g>{rot(500, 20, 10)}<rect x="488" y="8" width="24" height="24" fill="none" stroke="{GOLD}" stroke-width="1.6" transform="rotate(45 500 20)"/></g>
  <circle cx="500" cy="20" r="5" fill="{CRIMSON}" class="pulse"/>
  <circle cx="460" cy="20" r="2.5" fill="{GOLD}" class="pulse" style="animation-delay:.4s"/>
  <circle cx="540" cy="20" r="2.5" fill="{GOLD}" class="pulse" style="animation-delay:.8s"/>
</g>
<circle r="3" fill="{GOLD}" filter="url(#glow)" style="offset-path:path('M40 20 H960');animation:run 5s linear infinite"/>"""
    return svg(W, H, body, "@keyframes run{from{offset-distance:0%}to{offset-distance:100%}}")


def main():
    s = derive(fetch_sample() if "--sample" in sys.argv else fetch_live())
    os.makedirs(OUT, exist_ok=True)
    for name, fn in [("hero", hero), ("mage-card", mage_card), ("affinity", affinity),
                     ("mana", mana), ("battle", battle)]:
        with open(os.path.join(OUT, f"{name}.svg"), "w", encoding="utf-8") as f:
            f.write(fn(s))
    with open(os.path.join(OUT, "divider.svg"), "w", encoding="utf-8") as f:
        f.write(divider())
    print(f"{s['name']}: {s['rank']} LV{s['level']} · lifetime {s['lifetime']} · year {s['year']} "
          f"· streak {s['streak']}/{s['longest']} → {OUT}/")


if __name__ == "__main__":
    main()
