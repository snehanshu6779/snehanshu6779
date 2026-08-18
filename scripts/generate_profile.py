import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from html import escape

USER = "snehanshu6779"
API = "https://api.github.com"
TOKEN = os.environ["GITHUB_TOKEN"]
OUT = "generated"

os.makedirs(OUT, exist_ok=True)


def request(url, method="GET", payload=None):
    data = None
    if payload is not None:
        data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def graphql(query, variables=None):
    return request("https://api.github.com/graphql", "POST", {"query": query, "variables": variables or {}})


def fmt(n):
    if n >= 1000:
        return f"{n/1000:.1f}k"
    return str(n)


def card(x, y, w, h, title, value, subtitle):
    return f'''<g><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="18" fill="#0b1220" stroke="#24324a"/>
<text x="{x+22}" y="{y+31}" fill="#8fa3bf" font-family="Arial" font-size="14">{escape(title.upper())}</text>
<text x="{x+22}" y="{y+69}" fill="#e8f0ff" font-family="Arial" font-size="30" font-weight="700">{escape(value)}</text>
<text x="{x+22}" y="{y+94}" fill="#64748b" font-family="Arial" font-size="12">{escape(subtitle)}</text></g>'''


def svg_start(w, h, title):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#22d3ee"/><stop offset="0.55" stop-color="#60a5fa"/><stop offset="1" stop-color="#a78bfa"/></linearGradient></defs>
<rect width="{w}" height="{h}" rx="24" fill="#050816"/>
<text x="30" y="42" fill="url(#g)" font-family="Arial" font-size="24" font-weight="700">{escape(title)}</text>'''


def svg_end():
    return "</svg>"

# Public repositories only. Private work is intentionally not exposed by the profile.
repos = request(f"{API}/users/{USER}/repos?per_page=100&type=owner&sort=updated")
public_repos = [r for r in repos if not r.get("private") and not r.get("archived") and not r.get("fork") and r["name"] != USER]

profile = request(f"{API}/users/{USER}")

stars = sum(r.get("stargazers_count", 0) for r in public_repos)
forks = sum(r.get("forks_count", 0) for r in public_repos)

# Contribution calendar via GraphQL.
today = datetime.now(timezone.utc).date()
from_date = today - timedelta(days=365)
query = '''query($login:String!, $from:DateTime!, $to:DateTime!){ user(login:$login){ contributionsCollection(from:$from,to:$to){ contributionCalendar{totalContributions weeks{contributionDays{date contributionCount}}} } } }'''
try:
    gql = graphql(query, {"login": USER, "from": f"{from_date}T00:00:00Z", "to": f"{today}T23:59:59Z"})
    calendar = gql["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    days = [d for w in calendar["weeks"] for d in w["contributionDays"]]
    total_contributions = calendar["totalContributions"]
except Exception:
    days = []
    total_contributions = 0

# Current streak, counting today and backwards. GitHub's contribution calendar is the source.
streak = 0
if days:
    by_date = {d["date"]: d["contributionCount"] for d in days}
    d = today
    while by_date.get(str(d), 0) > 0:
        streak += 1
        d -= timedelta(days=1)

last_update = max((r.get("updated_at") for r in public_repos if r.get("updated_at")), default=datetime.now(timezone.utc).isoformat())
last_update_dt = datetime.fromisoformat(last_update.replace("Z", "+00:00"))
last_update_text = last_update_dt.strftime("%d %b %Y")
now_text = datetime.now(timezone(timedelta(hours=5, minutes=30))).strftime("%d %b %Y • %I:%M %p IST")

# Dashboard SVG
svg = svg_start(1100, 280, "⚡ LIVE GITHUB ANALYTICS")
svg += card(30, 70, 245, 115, "Public Repositories", fmt(profile.get("public_repos", len(public_repos))), "visible portfolio repositories")
svg += card(290, 70, 245, 115, "Followers", fmt(profile.get("followers", 0)), "GitHub followers")
svg += card(550, 70, 245, 115, "Stars", fmt(stars), "stars across public projects")
svg += card(810, 70, 245, 115, "Forks", fmt(forks), "forks across public projects")
svg += card(160, 200, 245, 60, "Contributions", fmt(total_contributions), "last 12 months")
svg += card(425, 200, 245, 60, "Current Streak", f"{streak} days", "consecutive contribution days")
svg += card(690, 200, 245, 60, "Profile Updated", now_text, "generated automatically")
svg += svg_end()
open(f"{OUT}/github-dashboard.svg", "w", encoding="utf-8").write(svg)

# Featured projects: strongest public repositories by stars, then recency.
featured = sorted(public_repos, key=lambda r: (r.get("stargazers_count", 0), r.get("updated_at", "")), reverse=True)[:6]
svg = svg_start(1100, 430, "🚀 FEATURED PUBLIC PROJECTS")
positions = [(30, 70), (560, 70), (30, 190), (560, 190), (30, 310), (560, 310)]
for r, (x, y) in zip(featured, positions):
    name = r["name"]
    desc = (r.get("description") or "Public project by Snehanshu Mandal").replace("&", "&amp;")[:70]
    lang = r.get("language") or "Open source"
    star = r.get("stargazers_count", 0)
    upd = r.get("updated_at", "")[:10]
    svg += f'''<a href="{escape(r['html_url'])}"><rect x="{x}" y="{y}" width="510" height="100" rx="16" fill="#0b1220" stroke="#24324a"/>
<text x="{x+20}" y="{y+30}" fill="#e8f0ff" font-family="Arial" font-size="18" font-weight="700">{escape(name)}</text>
<text x="{x+20}" y="{y+53}" fill="#7f91aa" font-family="Arial" font-size="12">{escape(desc)}</text>
<text x="{x+20}" y="{y+78}" fill="#22d3ee" font-family="Arial" font-size="12">{escape(lang)}</text>
<text x="{x+350}" y="{y+78}" fill="#a78bfa" font-family="Arial" font-size="12">★ {star}  •  {upd}</text></a>'''
svg += svg_end()
open(f"{OUT}/featured-projects.svg", "w", encoding="utf-8").write(svg)

# Recent activity from public repository updates.
recent = sorted(public_repos, key=lambda r: r.get("updated_at", ""), reverse=True)[:7]
svg = svg_start(1100, 360, "🛰️ RECENT PUBLIC REPOSITORY ACTIVITY")
for i, r in enumerate(recent):
    y = 78 + i * 38
    name = r["name"]
    when = r.get("updated_at", "")[:10]
    lang = r.get("language") or "Repository"
    svg += f'''<circle cx="40" cy="{y-5}" r="5" fill="#22d3ee"/><text x="60" y="{y}" fill="#e8f0ff" font-family="Arial" font-size="14" font-weight="700">{escape(name)}</text><text x="360" y="{y}" fill="#7f91aa" font-family="Arial" font-size="13">{escape(lang)}</text><text x="850" y="{y}" fill="#64748b" font-family="Arial" font-size="13">updated {escape(when)}</text>'''
svg += svg_end()
open(f"{OUT}/activity.svg", "w", encoding="utf-8").write(svg)

# Language distribution based on public repositories.
langs = {}
for r in public_repos:
    if r.get("language"):
        langs[r["language"]] = langs.get(r["language"], 0) + 1
langs = sorted(langs.items(), key=lambda x: x[1], reverse=True)[:8]
total_lang = max(sum(v for _, v in langs), 1)
svg = svg_start(1100, 330, "🛠️ PUBLIC REPOSITORY LANGUAGE MIX")
for i, (lang, count) in enumerate(langs):
    y = 80 + i * 29
    width = int(700 * count / total_lang)
    svg += f'''<text x="35" y="{y}" fill="#e8f0ff" font-family="Arial" font-size="13">{escape(lang)}</text><rect x="160" y="{y-13}" width="700" height="15" rx="7" fill="#101b2f"/><rect x="160" y="{y-13}" width="{width}" height="15" rx="7" fill="url(#g)"/><text x="885" y="{y}" fill="#7f91aa" font-family="Arial" font-size="13">{count} repo{'s' if count != 1 else ''}</text>'''
svg += svg_end()
open(f"{OUT}/languages.svg", "w", encoding="utf-8").write(svg)

# Machine-readable status used by README and future automations.
status = {
    "generated_at": now_text,
    "public_repositories": len(public_repos),
    "followers": profile.get("followers", 0),
    "stars": stars,
    "forks": forks,
    "contributions_last_12_months": total_contributions,
    "current_streak": streak,
    "latest_public_repo_update": last_update_text,
}
open(f"{OUT}/profile-status.json", "w", encoding="utf-8").write(json.dumps(status, indent=2))
print(json.dumps(status, indent=2))
