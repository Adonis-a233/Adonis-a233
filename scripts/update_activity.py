"""Render public GitHub activity. Fail rather than publish invented/empty data."""
import datetime as dt
import html
import json
import os
import re
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen

USER = 'Adonis-a233'
ROOT = Path(__file__).resolve().parents[1]

def fetch(url):
    headers = {'User-Agent': 'Adonis-profile-activity', 'Accept': 'application/vnd.github+json'}
    if url.startswith('https://api.github.com/') and os.environ.get('GITHUB_TOKEN'):
        headers['Authorization'] = 'Bearer ' + os.environ['GITHUB_TOKEN']
    with urlopen(Request(url, headers=headers), timeout=40) as response:
        return response.read().decode('utf-8')

class Calendar(HTMLParser):
    def __init__(self):
        super().__init__()
        self.days, self.counts = {}, {}
        self.target = None
        self.buffer = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'td' and 'data-date' in a:
            self.days[a['id']] = dt.date.fromisoformat(a['data-date'])
        if tag == 'tool-tip':
            self.target = a.get('for')
            self.buffer = []

    def handle_data(self, data):
        if self.target:
            self.buffer.append(data)

    def handle_endtag(self, tag):
        if tag == 'tool-tip' and self.target:
            match = re.search(r'(No|[\d,]+) contributions? on', ''.join(self.buffer))
            if match:
                self.counts[self.target] = 0 if match[1] == 'No' else int(match[1].replace(',', ''))
            self.target = None

cal = Calendar()
cal.feed(fetch(f'https://github.com/users/{USER}/contributions'))
assert len(cal.days) >= 365, 'Contribution calendar markup changed'
assert all(key in cal.counts for key in cal.days), 'Contribution counts missing'
today = dt.datetime.now(dt.timezone.utc).date()
values = {date: cal.counts[key] for key, date in cal.days.items() if today-dt.timedelta(days=364) <= date <= today}
assert len(values) >= 364, 'Incomplete public contribution calendar'
recent = [values.get(today-dt.timedelta(days=i), 0) for i in range(30)]
total = sum(values.values())
active = sum(v > 0 for v in values.values())
recent_active = sum(v > 0 for v in recent)
languages = Counter()
page = 1
repos = []
while True:
    batch = json.loads(fetch(f'https://api.github.com/users/{USER}/repos?type=owner&per_page=100&page={page}'))
    repos.extend(batch)
    if len(batch) < 100:
        break
    page += 1
for repo in repos:
    if repo['fork'] or repo['archived'] or repo['name'].lower() == USER.lower():
        continue
    languages.update(json.loads(fetch(repo['languages_url'])))
assert languages, 'No public language data'
top = languages.most_common(4)
if len(languages) > 4:
    top.append(('Other', sum(v for _, v in languages.most_common()[4:])))
language_total = sum(languages.values())

elements = []
def text(x, y, value, size=16, color='#b8becb', weight='400'):
    elements.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" font-weight="{weight}">{html.escape(str(value))}</text>')
def rect(x, y, width, height, color, rx=4):
    elements.append(f'<rect x="{x}" y="{y}" width="{width:.2f}" height="{height}" rx="{rx}" fill="{color}"/>')

rect(0, 0, 1200, 350, '#101217', 14)
text(36, 38, 'ACTIVITY.LOG / 我有在敲，真的。', 19, '#eeeae2', '700')
text(850, 38, f'SYNC / {today.isoformat()} UTC', 14, '#8e98aa')
rect(36, 57, 1128, 1, '#303541', 0)
text(36, 95, '过去 365 天 / 贡献次数', 15)
text(36, 153, f'{total:,}', 48, '#b0dc8a', '700')
text(315, 95, '最近 30 天 / 贡献次数', 15)
text(315, 153, f'{sum(recent):,}', 48, '#bba5ee', '700')

text(36, 203, f'近 30 天出没率  {recent_active}/30 天', 16)
rect(36, 218, 470, 12, '#262c37')
if recent_active: rect(36, 218, 470*recent_active/30, 12, '#bba5ee')
text(36, 270, f'全年出没率  {active}/{len(values)} 天', 16)
rect(36, 285, 470, 12, '#262c37')
if active: rect(36, 285, 470*active/len(values), 12, '#b0dc8a')

rect(557, 84, 1, 213, '#303541', 0)
text(606, 95, 'LANGUAGE LOOT / 公开代码成分', 16, '#eeeae2', '700')
colors = ['#bba5ee', '#b0dc8a', '#eed080', '#86cddb', '#c6c8d1']
for i, (language, amount) in enumerate(top):
    y = 133+i*34
    percent = amount/language_total*100
    text(606, y, language, 15)
    rect(760, y-12, 290, 12, '#262c37')
    rect(760, y-12, 290*percent/100, 12, colors[i])
    text(1070, y, f'{percent:.1f}%', 14, colors[i])

svg = '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="350" viewBox="0 0 1200 350" role="img"><title>GitHub public activity and language distribution</title><g font-family="Consolas, Microsoft YaHei, Noto Sans CJK SC, monospace">' + ''.join(elements) + '</g></svg>'
(ROOT/'assets/activity.svg').write_text(svg, encoding='utf-8')
print(json.dumps({'total_contributions':total,'active_days':active,'recent_30_days':sum(recent),'recent_active_days':recent_active,'language_bytes':dict(languages)},ensure_ascii=False))
