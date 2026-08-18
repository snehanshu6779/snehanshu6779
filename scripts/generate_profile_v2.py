import json, os, urllib.request
from datetime import datetime, timedelta, timezone
from html import escape

USER = 'snehanshu6779'
OUT = 'generated'
API = 'https://api.github.com'
TOKEN = os.environ['GITHUB_TOKEN']
os.makedirs(OUT, exist_ok=True)


def api(url, method='GET', body=None):
    data = None if body is None else json.dumps(body).encode()
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header('Authorization', f'Bearer {TOKEN}')
    r.add_header('Accept', 'application/vnd.github+json')
    r.add_header('X-GitHub-Api-Version', '2022-11-28')
    with urllib.request.urlopen(r, timeout=30) as x:
        return json.loads(x.read().decode())


def gql(q, v):
    return api('https://api.github.com/graphql', 'POST', {'query': q, 'variables': v})


def n(v):
    return f'{v / 1000:.1f}k' if v >= 1000 else str(v)


def start(w, h, title):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#22d3ee"/><stop offset=".55" stop-color="#60a5fa"/><stop offset="1" stop-color="#a78bfa"/></linearGradient></defs>
<rect width="100%" height="100%" rx="24" fill="#050816"/>
<text x="32" y="42" fill="url(#g)" font-family="Arial,sans-serif" font-size="24" font-weight="700">{escape(title)}</text>'''


def end():
    return '</svg>'


def card(x, y, w, title, value, sub=''):
    return f'''<rect x="{x}" y="{y}" width="{w}" height="108" rx="18" fill="#0b1220" stroke="#24324a"/>
<text x="{x + 18}" y="{y + 27}" fill="#8fa3bf" font-family="Arial,sans-serif" font-size="12">{escape(title.upper())}</text>
<text x="{x + 18}" y="{y + 64}" fill="#e8f0ff" font-family="Arial,sans-serif" font-size="27" font-weight="700">{escape(value)}</text>
<text x="{x + 18}" y="{y + 88}" fill="#64748b" font-family="Arial,sans-serif" font-size="10">{escape(sub)}</text>'''


profile = api(f'{API}/users/{USER}')
all_repos = api(f'{API}/users/{USER}/repos?per_page=100&type=owner&sort=updated')
repos = [
    r for r in all_repos
    if not r.get('private') and not r.get('archived') and r['name'] != USER and not r.get('fork')
]

stars = sum(r.get('stargazers_count', 0) for r in repos)
forks = sum(r.get('forks_count', 0) for r in repos)
today = datetime.now(timezone.utc).date()
frm = today - timedelta(days=365)

q = '''query($login:String!,$from:DateTime!,$to:DateTime!){user(login:$login){contributionsCollection(from:$from,to:$to){contributionCalendar{totalContributions weeks{contributionDays{date contributionCount}}}}}}'''
try:
    cal = gql(q, {'login': USER, 'from': f'{frm}T00:00:00Z', 'to': f'{today}T23:59:59Z'})['data']['user']['contributionsCollection']['contributionCalendar']
    days = [d for w in cal['weeks'] for d in w['contributionDays']]
    contrib = cal['totalContributions']
except Exception:
    days = []
    contrib = 0

by = {d['date']: d['contributionCount'] for d in days}
streak = 0
d = today
while by.get(str(d), 0) > 0:
    streak += 1
    d -= timedelta(days=1)

now = datetime.now(timezone(timedelta(hours=5, minutes=30))).strftime('%d %b %Y')

# Live dashboard: fixed 1100x340 canvas with safe margins and no overflow.
s = start(1100, 340, '⚡ LIVE GITHUB ANALYTICS')
card_w = 245
xs = [30, 290, 550, 810]
s += card(xs[0], 70, card_w, 'Public repositories', str(len(repos)), 'owned public repositories')
s += card(xs[1], 70, card_w, 'Followers', n(profile.get('followers', 0)), 'GitHub followers')
s += card(xs[2], 70, card_w, 'Stars', n(stars), 'stars on owned repos')
s += card(xs[3], 70, card_w, 'Forks', n(forks), 'forks on owned repos')
s += card(160, 208, 245, 'Contributions', n(contrib), 'last 12 months')
s += card(427, 208, 245, 'Current streak', f'{streak} days', 'consecutive contribution days')
s += card(694, 208, 245, 'Updated', now, 'automatic refresh • IST date')
s += end()
open(f'{OUT}/github-dashboard.svg', 'w', encoding='utf-8').write(s)

# Featured projects: owned repositories only, newest first.
featured = sorted(repos, key=lambda r: r.get('updated_at', ''), reverse=True)[:6]
s = start(1100, 430, '🚀 MY PROJECTS')
positions = [(30, 70), (560, 70), (30, 190), (560, 190), (30, 310), (560, 310)]
for i, r in enumerate(featured):
    x, y = positions[i]
    lang = r.get('language') or 'Repository'
    desc = (r.get('description') or 'Public project')[:62]
    date = r.get('updated_at', '')[:10]
    s += f'''<a href="{escape(r['html_url'])}"><rect x="{x}" y="{y}" width="510" height="100" rx="16" fill="#0b1220" stroke="#24324a"/>
<text x="{x + 18}" y="{y + 29}" fill="#e8f0ff" font-family="Arial,sans-serif" font-size="18" font-weight="700">{escape(r['name'])}</text>
<text x="{x + 18}" y="{y + 52}" fill="#7f91aa" font-family="Arial,sans-serif" font-size="12">{escape(desc)}</text>
<text x="{x + 18}" y="{y + 78}" fill="#22d3ee" font-family="Arial,sans-serif" font-size="12">{escape(lang)}</text>
<text x="{x + 350}" y="{y + 78}" fill="#a78bfa" font-family="Arial,sans-serif" font-size="12">★ {r.get('stargazers_count', 0)} · {date}</text></a>'''
s += end()
open(f'{OUT}/featured-projects.svg', 'w', encoding='utf-8').write(s)

# Recent activity: owned repositories only.
recent = sorted(repos, key=lambda r: r.get('updated_at', ''), reverse=True)[:7]
s = start(1100, 360, '🛰️ RECENT PUBLIC ACTIVITY')
for i, r in enumerate(recent):
    y = 78 + i * 38
    s += f'''<circle cx="40" cy="{y - 5}" r="5" fill="#22d3ee"/>
<text x="60" y="{y}" fill="#e8f0ff" font-family="Arial,sans-serif" font-size="14" font-weight="700">{escape(r['name'])}</text>
<text x="360" y="{y}" fill="#7f91aa" font-family="Arial,sans-serif" font-size="13">{escape(r.get('language') or 'Repository')}</text>
<text x="850" y="{y}" fill="#64748b" font-family="Arial,sans-serif" font-size="13">updated {r.get('updated_at', '')[:10]}</text>'''
s += end()
open(f'{OUT}/activity.svg', 'w', encoding='utf-8').write(s)

# Language mix: owned repositories only.
langs = {}
for r in repos:
    if r.get('language'):
        langs[r['language']] = langs.get(r['language'], 0) + 1
langs = sorted(langs.items(), key=lambda x: x[1], reverse=True)[:8]
total = max(sum(v for _, v in langs), 1)
s = start(1100, 330, '🛠️ PUBLIC REPOSITORY LANGUAGE MIX')
for i, (lang, count) in enumerate(langs):
    y = 80 + i * 29
    w = int(700 * count / total)
    s += f'''<text x="35" y="{y}" fill="#e8f0ff" font-family="Arial,sans-serif" font-size="13">{escape(lang)}</text>
<rect x="160" y="{y - 13}" width="700" height="15" rx="7" fill="#101b2f"/>
<rect x="160" y="{y - 13}" width="{w}" height="15" rx="7" fill="url(#g)"/>
<text x="885" y="{y}" fill="#7f91aa" font-family="Arial,sans-serif" font-size="13">{count} repo{'s' if count != 1 else ''}</text>'''
s += end()
open(f'{OUT}/languages.svg', 'w', encoding='utf-8').write(s)

status = {
    'generated_at': now,
    'public_repositories': len(repos),
    'followers': profile.get('followers', 0),
    'stars': stars,
    'forks': forks,
    'contributions_last_12_months': contrib,
    'current_streak': streak,
}
open(f'{OUT}/profile-status.json', 'w', encoding='utf-8').write(json.dumps(status, indent=2))
print(json.dumps(status, indent=2))
