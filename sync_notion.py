"""
sync_notion.py — ดึง Notion data และ inject เข้า index.html
รันโดย GitHub Actions ทุกวัน 7:00 น. (Bangkok)
"""
import os, re, json, time, requests
from datetime import datetime

TOKEN = os.environ.get('NOTION_TOKEN', '')
if not TOKEN:
    raise ValueError("NOTION_TOKEN env var not set")

HEADERS = {
    'Authorization': f'Bearer {TOKEN}',
    'Notion-Version': '2022-06-28',
    'Content-Type': 'application/json',
}

DB_USER_REQUEST = '817d901464a84f24bffe480ed2158983'
DB_TEAM_REQUEST = '2b68fd87ee6e804f88f8f252850ed099'
DB_SURVEY      = '30a8fd87ee6e80d48e10d227ebfcc0a4'


def fetch_all(db_id):
    rows = []
    cursor = None
    while True:
        body = {'page_size': 100}
        if cursor:
            body['start_cursor'] = cursor
        r = requests.post(
            f'https://api.notion.com/v1/databases/{db_id}/query',
            headers=HEADERS, json=body, timeout=30
        )
        r.raise_for_status()
        data = r.json()
        rows.extend(data.get('results', []))
        if not data.get('has_more'):
            break
        cursor = data.get('next_cursor')
        time.sleep(0.3)  # rate limit
    return rows


def gp(p):
    if not p: return ''
    t = p.get('type', '')
    if t == 'title':       return ''.join(x['plain_text'] for x in p.get('title', []))
    if t == 'rich_text':   return ''.join(x['plain_text'] for x in p.get('rich_text', []))[:200]
    if t == 'select':      return (p.get('select') or {}).get('name', '')
    if t == 'status':      return (p.get('status') or {}).get('name', '')
    if t == 'date':        return (p.get('date') or {}).get('start', '')
    if t == 'people':      return ', '.join(u.get('name', '') for u in p.get('people', []))
    if t == 'multi_select': return ', '.join(s.get('name', '') for s in p.get('multi_select', []))
    if t == 'url':         return p.get('url', '') or ''
    return ''


def ms(s):
    s = (s or '').lower()
    if 'done' in s or 'complet' in s: return 'done'
    if 'progress' in s: return 'progress'
    if 'pending' in s or 'wait' in s: return 'pending'
    if 'cancel' in s: return 'cancel'
    return 'todo'


def clean(t):
    if not t: return ''
    t = str(t).strip()
    t = re.sub(r"^'[^']*'![A-Z]+\d+\s*↳?\s*", '', t).strip()
    t = re.sub(r'^↳\s*', '', t).strip()
    t = t.replace('\n', ' ').replace('\r', ' ').strip()
    return t


# ── User Request ─────────────────────────────────────────────
print("Fetching User Request...")
pages_ur = fetch_all(DB_USER_REQUEST)
user_req = []
for pg in pages_ur:
    pr = pg['properties']
    sr = gp(pr.get('Status', ''))
    t1 = gp(pr.get('Request by Name', ''))
    t2 = gp(pr.get('Project Title', ''))
    title = t1 if t1 else (t2 if t2 else '(ไม่มีชื่อ)')
    user_req.append({
        'id':        pg['id'].replace('-', ''),
        'title':     clean(title),
        'status':    ms(sr),
        'statusRaw': sr,
        'priority':  gp(pr.get('Priority', '')),
        'output':    gp(pr.get('Output Type', '')),
        'owner':     gp(pr.get('Project Owner', '')),
        'deadline':  gp(pr.get('Deadline', '')),
        'dept':      gp(pr.get('Request by Dep.', '')),
        'type':      gp(pr.get('ประเภทของงาน Request', '')),
        'topic':     gp(pr.get('เรื่องที่ต้องการ Data', '')),
        'submitted': gp(pr.get('Submitted date', '')),
        'desc':      clean(gp(pr.get('Work description', ''))),
        'company':   gp(pr.get('เครือบริษัท', '')),
        'actual':    gp(pr.get('Actual Date', '')),
        'note':      clean(gp(pr.get('Note', ''))),
        'link':      gp(pr.get('Link งานที่ทำ', '')),
    })
print(f"  → {len(user_req)} rows")

# ── Team Request ─────────────────────────────────────────────
print("Fetching Team Request...")
pages_tr = fetch_all(DB_TEAM_REQUEST)
team_req = []
for pg in pages_tr:
    pr = pg['properties']
    sr = gp(pr.get('Status', ''))
    title = gp(pr.get('Project Title', ''))
    if not title: continue
    team_req.append({
        'id':        pg['id'].replace('-', ''),
        'title':     clean(title),
        'status':    ms(sr),
        'statusRaw': sr,
        'priority':  gp(pr.get('Priority ', '')),
        'owner':     gp(pr.get('Project Owner', '')),
        'member':    gp(pr.get('Member Assign', '')),
        'type':      gp(pr.get('Type of work ', '')),
        'company':   gp(pr.get('เครือบริษัท', '')),
        'submitter': gp(pr.get('Submitted by', '')),
        'start':     gp(pr.get('Start Date', '')),
        'deadline':  gp(pr.get('Due dates ', '')),
        'actual':    gp(pr.get('Complete Date', '')),
        'desc':      clean(gp(pr.get('Project/Task Detail', ''))),
        'link':      gp(pr.get('Online Link', '')),
    })
print(f"  → {len(team_req)} rows")

# ── Survey ───────────────────────────────────────────────────
print("Fetching Survey...")
pages_sv = fetch_all(DB_SURVEY)
survey = []
for pg in pages_sv:
    pr = pg['properties']
    survey.append({
        'id':           pg['id'].replace('-', ''),
        'note':         clean(gp(pr.get('Note', ''))),
        'staff':        gp(pr.get('คนที่ทำ', '')),
        'score':        gp(pr.get('ความพึงพอใจ', '')),
        'dept':         gp(pr.get('ฝ่าย', '')),
        'type':         gp(pr.get('ประเภทการใช้บริการ', '')),
        's_output':     gp(pr.get('แบบประเมินบริการ : output', '')),
        's_accuracy':   gp(pr.get('แบบประเมินบริการ : ความถูกต้อง', '')),
        's_consult':    gp(pr.get('แบบประเมินบริการ : คำปรึกษา', '')),
        's_time':       gp(pr.get('แบบประเมินบริการ : ระยะเวลา', '')),
        's_practical':  gp(pr.get('แบบประเมินบริการ : ใช้ได้จริง', '')),
        'date':         (pg.get('created_time', '') or '')[:10],
    })
print(f"  → {len(survey)} rows")

# ── Inject into HTML ─────────────────────────────────────────
print("Updating index.html...")

with open('index.html', 'r', encoding='utf-8') as f:
    html = f.read()

def replace_var(html, var_name, new_data):
    opn = '[' if isinstance(new_data, list) else '{'
    clo = ']' if isinstance(new_data, list) else '}'
    pattern = rf'var {re.escape(var_name)}\s*=\s*[{re.escape(opn)}]'
    m = re.search(pattern, html)
    if not m:
        print(f"  WARNING: {var_name} not found in HTML")
        return html
    start = m.start()
    depth = 0
    i = m.end() - 1
    while i < len(html):
        if html[i] == opn:   depth += 1
        elif html[i] == clo:
            depth -= 1
            if depth == 0:
                end = i + 1
                if end < len(html) and html[end] == ';':
                    end += 1
                break
        i += 1
    new_json = json.dumps(new_data, ensure_ascii=False, separators=(',', ':'))
    html = html[:start] + f'var {var_name} ={new_json};' + html[end:]
    print(f"  ✓ {var_name}: {len(new_data)} rows")
    return html

html = replace_var(html, 'NOTION_DATA', user_req)
html = replace_var(html, 'TEAM_REQ_DATA', team_req)
html = replace_var(html, 'SURVEY_DATA', survey)

# ── KPI Data from Google Apps Script ─────────────────────────────
print("Fetching KPI data from Google Apps Script...")
NICK_MAP = {
    'วรภพ':'โตโต้','อัญชนา':'หมิว','ทรายทอง':'ทราย','พลอยพรรณ':'พลอย',
    'กมลชนก':'โบว์','ภัทรวดี':'เอโกะ','ธีรนาถ':'ต้า','ณัฏฐา':'ฟ้าใส',
    'ศิริพร':'เซ่','อธิษฐาน':'โอม',
    'โตโต้':'โตโต้','หมิว':'หมิว','ทราย':'ทราย','พลอย':'พลอย',
    'โบว์':'โบว์','เอโกะ':'เอโกะ','ต้า':'ต้า','ฟ้าใส':'ฟ้าใส','เซ่':'เซ่','โอม':'โอม',
}
kpi_data = []
try:
    kpi_resp = requests.get(
        'https://script.google.com/macros/s/AKfycbzL5pUQ3bnxmZ--QGVxn-D5XXqM8euDGQUL1HYS7Jl7iBo0g1uYPilm00dwST1v1CgLkQ/exec?action=all',
        timeout=30
    )
    kpi_raw = kpi_resp.json().get('data', [])
    for r in kpi_raw:
        owner = r.get('owner', '')
        nick_raw = r.get('nickname', '') or ''
        nick = NICK_MAP.get(nick_raw, '')
        if not nick:
            for k, v in NICK_MAP.items():
                if k in owner:
                    nick = v; break
        if not nick:
            nick = nick_raw or owner.split()[0]
        kpi_data.append({
            'nick': nick, 'name': owner,
            'role': r.get('role', 'DA/DS'), 'pos': r.get('position', ''),
            'no': r.get('kpi_no', 0), 'persp': r.get('perspective', ''),
            'kname': r.get('kpi_name', ''), 'w': r.get('weight', 0),
            'tgt': r.get('target', ''), 'prog': r.get('progress', 0),
            'status': 'ล่าช้า' if 'ล่าช้า' in (r.get('status','')) else 'ตามแผน',
            'risk': r.get('risk_level', 'Medium')
        })
    print(f"  ✓ KPI_DATA: {len(kpi_data)} rows")
except Exception as e:
    print(f"  ⚠ KPI fetch failed: {e} — keeping existing data")
if kpi_data:
    html = replace_var(html, 'KPI_DATA', kpi_data)

# Add sync timestamp comment
ts = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
html = re.sub(r'<!-- Last synced:.*?-->', '', html)
html = html.replace('</title>', f'</title>\n<!-- Last synced: {ts} -->', 1)

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(html)

print(f"\n✅ Done! Synced at {ts}")
print(f"   User Request: {len(user_req)} rows")
print(f"   Team Request: {len(team_req)} rows")
print(f"   Survey:       {len(survey)} rows")
