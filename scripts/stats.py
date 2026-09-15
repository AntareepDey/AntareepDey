import json, os, urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

Q = '''query($u:String!,$from:DateTime!,$after:String){user(login:$u){
  issues{totalCount}
  repositoriesContributedTo(contributionTypes:[COMMIT,PULL_REQUEST,ISSUE,PULL_REQUEST_REVIEW]){totalCount}
  contributionsCollection(from:$from){totalCommitContributions totalPullRequestContributions}
  repositories(first:100,after:$after,ownerAffiliations:OWNER,isFork:false){pageInfo{hasNextPage endCursor}
    nodes{stargazerCount languages(first:20){edges{size node{name}}}}}}}'''

W, PAD, CW, BAR = 900, 40, 10.2, 150
THEMES = {'dark': ('#ffffff', '#3d444d', '#39d353'), 'light': ('#1f2328', '#d1d9e0', '#1a7f37')}


def fetch(user, token):
    frm, after, repos = (datetime.now(timezone.utc) - timedelta(days=365)).isoformat(), None, []
    while True:
        body = json.dumps({'query': Q, 'variables': {'u': user, 'from': frm, 'after': after}}).encode()
        req = urllib.request.Request('https://api.github.com/graphql', body, {'Authorization': f'bearer {token}'})
        with urllib.request.urlopen(req) as r:
            res = json.load(r)
        if 'errors' in res:
            raise SystemExit(res['errors'])
        u = res['data']['user']
        repos += u['repositories']['nodes']
        if not (page := u['repositories']['pageInfo'])['hasNextPage']:
            break
        after = page['endCursor']
    langs = Counter()
    for r in repos:
        for e in r['languages']['edges']:
            langs[e['node']['name']] += e['size']
    cc = u['contributionsCollection']
    stats = {'total stars': sum(r['stargazerCount'] for r in repos),
             'commits (1y)': cc['totalCommitContributions'],
             'pull requests (1y)': cc['totalPullRequestContributions'],
             'total issues': u['issues']['totalCount'],
             'contributed to (repos)': u['repositoriesContributedTo']['totalCount']}
    return stats, langs


def render(stats, langs, ink, border, green):
    total = sum(langs.values()) or 1
    top = langs.most_common(4)
    top.append(('others', total - sum(v for _, v in top)))
    t = lambda x, y, s, a='', cw=CW: f'<text x="{x:.0f}" y="{y}" textLength="{len(s) * cw:.0f}"{a}>{s}</text>'
    R = W - PAD
    bx = R - 5 * CW - 14 - BAR
    rx = bx - 18 - max(len(n) for n, _ in top) * CW
    cell = lambda x: f'<rect x="{x:.0f}" y="34" width="12" height="12" rx="2.5" fill="{green}"/>'
    rows = [cell(PAD), t(PAD + 20, 46, 'activity', ' class="h"', 12), cell(rx), t(rx + 20, 46, 'languages', ' class="h"', 12)]
    bars = []
    for i, (k, v) in enumerate(stats.items()):
        y, v = 88 + i * 30, str(v)
        rows.append(f'<text x="{PAD}" y="{y}" textLength="{32 * CW:.0f}">{k} <tspan class="d">{"." * (30 - len(k) - len(v))}</tspan> {v}</text>')
    for i, (name, size) in enumerate(top):
        y, pct = 88 + i * 30, 100 * size / total
        box = f'x="{bx:.0f}" y="{y - 13}" height="14"'
        rows += [t(rx, y, name.lower()), f'<rect {box} width="{BAR}" class="s"/>',
                 f'<text x="{R}" y="{y}" text-anchor="end" textLength="{len(f"{pct:.1f}%") * CW:.0f}">{pct:.1f}%</text>']
        bars += [f'<rect {box} width="{BAR}" fill="url(#p)"/>'] + [f'<rect {box} width="{BAR * pct / 100:.1f}" fill="url(#{p})"/>' for p in 'ab']
    hatch = lambda i, w, a, c, sw, o: (f'<pattern id="{i}" width="{w}" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate({a})">'
                                       f'<path d="M0 0V4" stroke="{c}" stroke-width="{sw}" stroke-opacity="{o}"/></pattern>')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} 240" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace" font-size="17" font-weight="600">
<style>text{{fill:{ink};white-space:pre}}.h{{font-size:20px;font-weight:700}}.d{{fill-opacity:.35}}.s{{fill:none;stroke:{ink};stroke-width:1.1;stroke-opacity:.6;filter:url(#r)}}</style>
<defs><filter id="r"><feTurbulence type="fractalNoise" baseFrequency=".8" numOctaves="2" seed="7" result="n"/><feDisplacementMap in="SourceGraphic" in2="n" scale="2.2" xChannelSelector="R" yChannelSelector="G"/></filter>
{hatch("a", 2.8, 40, green, 1.7, 1)}{hatch("b", 4.5, -50, green, 1, .85)}{hatch("p", 6, 40, ink, .7, .3)}</defs>
<rect x="1" y="1" width="{W - 2}" height="238" rx="10" fill="none" stroke="{border}" stroke-width="1.5"/>
<g filter="url(#r)">{"".join(bars)}</g>{"".join(rows)}
</svg>'''


if __name__ == '__main__':
    data = fetch(os.environ['GH_USER'], os.environ['GH_TOKEN'])
    for name, colors in THEMES.items():
        Path(f'assets/stats-{name}.svg').write_text(render(*data, *colors), encoding='utf-8')
