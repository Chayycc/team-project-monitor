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
DB_CALENDAR    = '1c18fd87ee6e8112940df29c43a1aca0'

# Notion user UUID prefix → team nick
USER_NICK_MAP = {
    '3f5a2fb4': 'เชย์',
    '63a73367': 'เช่',
    '55e1a95e': 'ทราย',
    '054f9bd7': 'หมิว',
    '1a0d872b': 'เอโกะ',
}


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

def parse_ms(s):
    """Parse ISO datetime string → UTC milliseconds. Assumes Bangkok UTC+7 if no tz."""
    from datetime import datetime, timezone, timedelta
    if not s: return 0
    try:
        if 'T' in s and ('+' in s[10:] or 'Z' in s[10:]):
            dt = datetime.fromisoformat(s.replace('Z', '+00:00'))
            return int(dt.astimezone(timezone.utc).timestamp() * 1000)
        elif 'T' in s:
            dt = datetime.fromisoformat(s[:19])
            return int((dt - timedelta(hours=7)).timestamp() * 1000)
        else:
            dt = datetime.fromisoformat(s)
            return int((dt - timedelta(hours=7)).timestamp() * 1000)
    except Exception:
        return 0


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

# ── Calendar ─────────────────────────────────────────────────
print("Fetching Calendar...")
pages_cal = fetch_all(DB_CALENDAR)
cal_data, cal_meta = [], []
for pg in pages_cal:
    pr = pg['properties']
    date_prop = next((v for v in pr.values() if v.get('type') == 'date' and v.get('date')), None)
    if not date_prop:
        continue
    start_str = date_prop['date'].get('start', '')
    end_str   = date_prop['date'].get('end') or start_str
    if not start_str:
        continue
    ts_ms = parse_ms(start_str)
    te_ms = parse_ms(end_str) if end_str != start_str else ts_ms + 3600000
    if not ts_ms:
        continue
    d_str = start_str[:10]
    # Title
    title_prop = next((v for v in pr.values() if v.get('type') == 'title'), {})
    name_raw = clean(gp(title_prop))
    if not name_raw:
        continue
    # Meeting type: look for select/status property with online/onsite value
    tp_raw = ''
    for v in pr.values():
        if v.get('type') in ('select', 'status'):
            val = gp(v)
            if any(x in val.lower() for x in ('online', 'onsite', 'office')):
                tp_raw = val
                break
    tp = 'S' if any(x in tp_raw.lower() for x in ('onsite', 'office')) else 'O'
    cal_data.append({'d': d_str, 'ts': ts_ms, 'te': te_ms, 'n': name_raw, 'tp': tp})
    # Location
    loc = ''
    for k in ('Location', 'สถานที่', 'Place', 'ห้อง'):
        if k in pr:
            loc = gp(pr[k])
            break
    # Persons
    persons_nicks = []
    for k in ('Person', 'Attendees', 'ผู้เข้าร่วม', 'Members', 'คนที่เข้าร่วม'):
        if k in pr and pr[k].get('type') == 'people':
            for u in pr[k].get('people', []):
                uid = u.get('id', '').replace('-', '')[:8]
                nick = USER_NICK_MAP.get(uid)
                if nick:
                    persons_nicks.append(nick)
            break
    if loc or persons_nicks:
        entry = {'ts': ts_ms, 'nf': name_raw[:20]}
        if loc: entry['loc'] = loc
        if persons_nicks: entry['persons'] = persons_nicks
        cal_meta.append(entry)

cal_data.sort(key=lambda x: x['ts'])
print(f"  → {len(cal_data)} calendar events, {len(cal_meta)} with metadata")

def replace_const(html, var_name, new_data):
    pattern = rf'const {re.escape(var_name)}\s*='
    m = re.search(pattern, html)
    if not m:
        print(f"  WARNING: const {var_name} not found in HTML")
        return html
    start = m.start()
    # Use JSON decoder to find the exact end — handles brackets inside string values
    json_start = m.end()
    while json_start < len(html) and html[json_start] in ' \t\n':
        json_start += 1
    try:
        _, consumed = json.JSONDecoder().raw_decode(html[json_start:])
    except json.JSONDecodeError as e:
        print(f"  ERROR: could not parse existing {var_name}: {e}")
        return html
    end = json_start + consumed
    if end < len(html) and html[end] == ';':
        end += 1
    new_json = json.dumps(new_data, ensure_ascii=False, separators=(',', ':'))
    html = html[:start] + f'const {var_name} ={new_json};' + html[end:]
    print(f"  ✓ const {var_name}: {len(new_data)} rows")
    return html

if cal_data:
    html = replace_const(html, 'CALENDAR_DATA', cal_data)
if cal_meta:
    html = replace_const(html, 'CALENDAR_META', cal_meta)

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
print(f"   User Request:  {len(user_req)} rows")
print(f"   Team Request:  {len(team_req)} rows")
print(f"   Survey:        {len(survey)} rows")
print(f"   Calendar:      {len(cal_data)} events")
