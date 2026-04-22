import json
import os
import urllib.request
import urllib.error
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.join(BASE_DIR, 'public')
DATA_FILE  = os.path.join(BASE_DIR, 'data', 'alphabet.json')

JSONBIN_KEY = os.environ.get('JSONBIN_KEY', '')
JSONBIN_BIN = os.environ.get('JSONBIN_BIN', '')
USE_JSONBIN = bool(JSONBIN_KEY and JSONBIN_BIN)

LETTERS = [
    ("أ","الألف"),("ب","الباء"),("ت","التاء"),("ث","الثاء"),
    ("ج","الجيم"),("ح","الحاء"),("خ","الخاء"),("د","الدال"),
    ("ذ","الذال"),("ر","الراء"),("ز","الزاي"),("س","السين"),
    ("ش","الشين"),("ص","الصاد"),("ض","الضاد"),("ط","الطاء"),
    ("ظ","الظاء"),("ع","العين"),("غ","الغين"),("ف","الفاء"),
    ("ق","القاف"),("ك","الكاف"),("ل","اللام"),("م","الميم"),
    ("ن","النون"),("هـ","الهاء"),("و","الواو"),("ي","الياء")
]

def default_data():
    return {
        "letters": [{"letter": l, "name": n, "candidates": []} for l, n in LETTERS],
        "activity": []
    }

# ── JSONBin helpers ──────────────────────────────────────────────

def jsonbin_read():
    url = f'https://api.jsonbin.io/v3/b/{JSONBIN_BIN}/latest'
    req = urllib.request.Request(url, headers={'X-Master-Key': JSONBIN_KEY})
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            body = json.loads(r.read())
            data = body.get('record', {})
            if not data.get('letters'):
                return default_data()
            return data
    except Exception as e:
        print(f'JSONBin read error: {e}')
        return default_data()

_last_write_error = ''

def jsonbin_write(data):
    global _last_write_error
    url     = f'https://api.jsonbin.io/v3/b/{JSONBIN_BIN}'
    payload = json.dumps(data, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(
        url, data=payload, method='PUT',
        headers={
            'X-Master-Key':    JSONBIN_KEY,
            'Content-Type':    'application/json',
            'X-Bin-Versioning':'false'
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            _last_write_error = ''
            return r.status == 200
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='ignore')
        _last_write_error = f'HTTP {e.code}: {body[:200]}'
        print(f'JSONBin HTTPError: {_last_write_error}')
        return False
    except Exception as e:
        _last_write_error = str(e)
        print(f'JSONBin write error: {e}')
        return False

# ── File helpers (local fallback) ────────────────────────────────

def file_read():
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default_data()

def file_write(data):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ── Unified read/write ───────────────────────────────────────────

def read_data():
    return jsonbin_read() if USE_JSONBIN else file_read()

def write_data(data):
    if USE_JSONBIN:
        return jsonbin_write(data)
    else:
        file_write(data)
        return True

# ── HTTP Handler ─────────────────────────────────────────────────

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=PUBLIC_DIR, **kwargs)

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if urlparse(self.path).path == '/api/alphabet':
            self.send_json(read_data())
        else:
            super().do_GET()

    def do_POST(self):
        path   = urlparse(self.path).path
        length = int(self.headers.get('Content-Length', 0))
        body   = json.loads(self.rfile.read(length)) if length else {}

        if   path == '/api/submit': self.handle_submit(body)
        elif path == '/api/vote':   self.handle_vote(body)
        elif path == '/api/reset':  self.handle_reset(body)
        else: self.send_error(404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def handle_submit(self, body):
        idx       = body.get('letterIndex')
        word      = (body.get('word') or '').strip()
        emoji     = body.get('emoji', '✨')
        submitter = body.get('submitter', 'مجهول')

        data = read_data()
        if idx is None or not (0 <= idx < len(data['letters'])):
            return self.send_json({'error': 'حرف غير صحيح'}, 400)
        if not word or len(word) < 2:
            return self.send_json({'error': 'الكلمة قصيرة جداً'}, 400)

        letter     = data['letters'][idx]
        candidates = letter.get('candidates', [])

        if any(c['word'].strip() == word for c in candidates):
            return self.send_json({'error': 'هذه الكلمة مقترحة بالفعل'}, 400)

        candidates.append({'word': word, 'emoji': emoji, 'submitter': submitter, 'votes': 0})
        letter['candidates'] = candidates

        data['activity'].insert(0, {
            'text': f'{submitter} اقترح "{word}" للحرف {letter["letter"]} 🟡',
            'time': 'منذ لحظة'
        })
        data['activity'] = data['activity'][:20]
        ok = write_data(data)
        if not ok:
            return self.send_json({'error': f'فشل الحفظ: {_last_write_error}'}, 500)
        self.send_json({'success': True, 'letter': letter})

    def handle_vote(self, body):
        idx   = body.get('letterIndex')
        c_idx = body.get('candidateIndex')
        data  = read_data()

        if idx is None or not (0 <= idx < len(data['letters'])):
            return self.send_json({'error': 'حرف غير صحيح'}, 400)

        letter     = data['letters'][idx]
        candidates = letter.get('candidates', [])

        if c_idx is None or not (0 <= c_idx < len(candidates)):
            return self.send_json({'error': 'اقتراح غير صحيح'}, 400)

        candidates[c_idx]['votes'] = candidates[c_idx].get('votes', 0) + 1

        data['activity'].insert(0, {
            'text': f'صوّت لـ "{candidates[c_idx]["word"]}" في حرف {letter["letter"]} ❤️',
            'time': 'منذ لحظة'
        })
        data['activity'] = data['activity'][:20]
        ok = write_data(data)
        if not ok:
            return self.send_json({'error': f'فشل الحفظ: {_last_write_error}'}, 500)
        self.send_json({'success': True, 'letter': letter})

    def handle_reset(self, body):
        if body.get('secret') != 'saudi2025':
            return self.send_json({'error': 'غير مصرح'}, 403)
        idx  = body.get('letterIndex')
        data = read_data()
        if idx is not None and 0 <= idx < len(data['letters']):
            data['letters'][idx]['candidates'] = []
        else:
            for l in data['letters']:
                l['candidates'] = []
            data['activity'] = []
        write_data(data)
        self.send_json({'success': True})

    def send_json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    mode = 'JSONBin ☁️' if USE_JSONBIN else 'ملف محلي 💾'
    print(f'\n🌴 ألفبائية السعودية: http://localhost:{port}  [{mode}]\n')
    HTTPServer(('0.0.0.0', port), Handler).serve_forever()
