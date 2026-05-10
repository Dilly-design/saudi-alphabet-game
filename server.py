import json
import os
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse
from datetime import datetime, timezone

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.join(BASE_DIR, 'public')
DATA_FILE  = os.path.join(BASE_DIR, 'data', 'alphabet.json')

UPSTASH_URL   = os.environ.get('UPSTASH_REDIS_REST_URL', '')
UPSTASH_TOKEN = os.environ.get('UPSTASH_REDIS_REST_TOKEN', '')
USE_UPSTASH   = bool(UPSTASH_URL and UPSTASH_TOKEN)
REDIS_KEY_V1  = 'alphabet_data'
REDIS_KEY_V2  = 'alphabet_data_v2'
RESET_SECRET  = os.environ.get('RESET_SECRET', 'saudi2025')

LETTERS = [
    ("أ","الألف"),("ب","الباء"),("ت","التاء"),("ث","الثاء"),
    ("ج","الجيم"),("ح","الحاء"),("خ","الخاء"),("د","الدال"),
    ("ذ","الذال"),("ر","الراء"),("ز","الزاي"),("س","السين"),
    ("ش","الشين"),("ص","الصاد"),("ض","الضاد"),("ط","الطاء"),
    ("ظ","الظاء"),("ع","العين"),("غ","الغين"),("ف","الفاء"),
    ("ق","القاف"),("ك","الكاف"),("ل","اللام"),("م","الميم"),
    ("ن","النون"),("هـ","الهاء"),("و","الواو"),("ي","الياء")
]

# ── V2 seed data (word, emoji, votes) ───────────────────────────
V2_SEEDS = {
    "أ": [("آيسكريم العاصمة","🍦",3), ("أبشر","📱",0)],
    "ب": [("بلوت","🃏",2), ("بشت","🧥",0)],
    "ت": [("966+","📞",2), ("تمر","🌴",0)],
    "ث": [("ثمانية","🎙️",0), ("ثور الله في برسيمه","🐂",0)],
    "ج": [("جلال","👑",3), ("جنبية","⚔️",0)],
    "ح": [("حمضيات","🍊",4), ("حنيذ","🍖",0)],
    "خ": [("خزامى","💜",0), ("خثاريد","🦎",0)],
    "د": [("الديرة","🏙️",3), ("دلة قهوة","☕",0), ("درباوي","🌿",0)],
    "ذ": [("ذهب","💛",0), ("ذبيحة","🐑",0)],
    "ر": [("رؤية","🔮",1), ("رياض","🏙️",0)],
    "ز": [("زعفران","🌸",3), ("زبيب","🍇",0), ("زمزم","💧",0)],
    "س": [("سعود","👑",3), ("سيفين","⚔️",1), ("سامري","🎵",0), ("سبحة","📿",0),
          ("سُمرة","🌅",0), ("سِدرة","🌳",0), ("سدو","🧶",0), ("سهيل","⭐",0)],
    "ش": [("شوال","🌙",3), ("شماغ","🧣",0), ("شاهي","🍵",0), ("شاص","🚙",0),
          ("شواية الخليج","🔥",0)],
    "ص": [("صامولي","🍞",3), ("صاروخ","🚀",1), ("صبّة","🫙",1),
          ("صقر","🦅",0), ("صملة","🪨",0)],
    "ض": [("ضبّ","🦎",2)],
    "ط": [("طن ططن","🥁",4), ("طعس","🎯",1), ("طيّب","🌸",0),
          ("طراطيع","🎭",0), ("طاق طاق طاقية","🎩",0), ("طويق","⛰️",0),
          ("طاش ما طاش","📺",0)],
    "ظ": [("ظبي","🦌",0), ("خالي من العيوب","⭐",0)],
    "ع": [("عصفر","🌺",3), ("عرضة","⚔️",2), ("عزبة","🏡",0)],
    "غ": [("غسال","🧺",4), ("غضى","🌳",0), ("غيبوبة العيد","💤",0)],
    "ف": [("فازلين","💆",4), ("فورد","🚗",1), ("فُلَّة","🌹",0), ("فوّال الطائف","🫘",0)],
    "ق": [("قلعة وادرين","🏰",2), ("قيظ","☀️",2), ("قايلة","😴",0)],
    "ك": [("كاسة جبن","🧀",2), ("كيرم","🎲",2)],
    "ل": [("لبيه","💛",2), ("لو قمت ولقيته","🚶",2)],
    "م": [("مخمّس","🎵",2), ("ماكنتوش","🍎",2), ("مربعانية","❄️",2),
          ("مقلط","🔑",2), ("مكة","🕌",0)],
    "ن": [("نعال","👡",3), ("نفط","🛢️",0), ("نخلة","🌴",0),
          ("نجد","🏜️",0), ("النيدو","🥛",0)],
    "هـ": [("هيل","🌿",0), ("هايلوكس","🚗",0), ("هبوب","💨",0)],
    "و": [("والله ما تدفع","💸",2), ("وانيت","🚌",1), ("ورع","🙏",0), ("ورد طائفي","🌹",0)],
    "ي": [("يصير خير","🌟",3), ("يُمّه","💛",1), ("يالالاه","🎵",0)],
}

# ── Default data builders ────────────────────────────────────────

def default_data():
    return {
        "letters": [{"letter": l, "name": n, "candidates": []} for l, n in LETTERS],
        "activity": []
    }

def v2_default_data():
    letters = []
    for letter, name in LETTERS:
        seeds = V2_SEEDS.get(letter, [])
        cands = [{"word": w, "emoji": e, "submitter": "seed", "votes": v}
                 for w, e, v in seeds]
        letters.append({"letter": letter, "name": name, "candidates": cands})
    return {"letters": letters, "activity": []}

# ── Upstash Redis REST ───────────────────────────────────────────

def upstash_cmd(command):
    body = json.dumps(command).encode('utf-8')
    req  = urllib.request.Request(
        UPSTASH_URL, data=body,
        headers={'Authorization': f'Bearer {UPSTASH_TOKEN}', 'Content-Type': 'application/json'}
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())

def redis_get(key):
    try:
        resp = upstash_cmd(["GET", key])
        val  = resp.get('result')
        return json.loads(val) if val else None
    except Exception as e:
        print(f'Redis GET error ({key}): {e}')
        return None

def redis_set(key, data):
    try:
        resp = upstash_cmd(["SET", key, json.dumps(data, ensure_ascii=False)])
        return resp.get('result') == 'OK'
    except Exception as e:
        print(f'Redis SET error ({key}): {e}')
        return False

# ── Unified read/write (game = 'v1' | 'v2') ─────────────────────

def read_data(game='v1'):
    if not USE_UPSTASH:
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return default_data()
    key  = REDIS_KEY_V2 if game == 'v2' else REDIS_KEY_V1
    data = redis_get(key)
    if not data or not data.get('letters'):
        seed = v2_default_data() if game == 'v2' else default_data()
        redis_set(key, seed)
        return seed
    return data

def write_data(data, game='v1'):
    if not USE_UPSTASH:
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    key = REDIS_KEY_V2 if game == 'v2' else REDIS_KEY_V1
    return redis_set(key, data)

# ── HTTP Handler ─────────────────────────────────────────────────

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=PUBLIC_DIR, **kwargs)

    def log_message(self, format, *args):
        pass

    def handle_error(self, request, client_address):
        import sys
        exc = sys.exc_info()[1]
        if isinstance(exc, (BrokenPipeError, ConnectionResetError, OSError)):
            pass
        else:
            super().handle_error(request, client_address)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == '/api/alphabet':
            self.send_json(read_data('v1'))
        elif path == '/api/v2/alphabet':
            self.send_json(read_data('v2'))
        else:
            super().do_GET()

    def do_POST(self):
        raw_path = urlparse(self.path).path
        length   = int(self.headers.get('Content-Length', 0))
        body     = json.loads(self.rfile.read(length)) if length else {}

        # Route game version from path prefix
        if raw_path.startswith('/api/v2/'):
            game = 'v2'
            path = '/api/' + raw_path[len('/api/v2/'):]
        else:
            game = 'v1'
            path = raw_path

        if   path == '/api/submit': self.handle_submit(body, game)
        elif path == '/api/vote':   self.handle_vote(body, game)
        elif path == '/api/reset':  self.handle_reset(body, game)
        else: self.send_error(404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def handle_submit(self, body, game='v1'):
        idx       = body.get('letterIndex')
        word      = (body.get('word') or '').strip()
        emoji     = body.get('emoji', '✨')
        submitter = body.get('submitter', 'مجهول')

        data = read_data(game)
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
            'time': datetime.now(timezone.utc).isoformat()
        })
        data['activity'] = data['activity'][:20]

        if not write_data(data, game):
            return self.send_json({'error': 'فشل الحفظ — حاول مرة أخرى'}, 500)
        self.send_json({'success': True, 'letter': letter})

    def handle_vote(self, body, game='v1'):
        idx   = body.get('letterIndex')
        c_idx = body.get('candidateIndex')
        data  = read_data(game)

        if idx is None or not (0 <= idx < len(data['letters'])):
            return self.send_json({'error': 'حرف غير صحيح'}, 400)

        letter     = data['letters'][idx]
        candidates = letter.get('candidates', [])

        if c_idx is None or not (0 <= c_idx < len(candidates)):
            return self.send_json({'error': 'اقتراح غير صحيح'}, 400)

        candidates[c_idx]['votes'] = candidates[c_idx].get('votes', 0) + 1

        data['activity'].insert(0, {
            'text': f'صوّت لـ "{candidates[c_idx]["word"]}" في حرف {letter["letter"]} ❤️',
            'time': datetime.now(timezone.utc).isoformat()
        })
        data['activity'] = data['activity'][:20]

        if not write_data(data, game):
            return self.send_json({'error': 'فشل الحفظ — حاول مرة أخرى'}, 500)
        self.send_json({'success': True, 'letter': letter})

    def handle_reset(self, body, game='v1'):
        if body.get('secret') != RESET_SECRET:
            return self.send_json({'error': 'غير مصرح'}, 403)
        idx  = body.get('letterIndex')
        data = read_data(game)
        if idx is not None and 0 <= idx < len(data['letters']):
            if game == 'v2':
                letter = data['letters'][idx]
                seeds  = V2_SEEDS.get(letter['letter'], [])
                data['letters'][idx]['candidates'] = [
                    {"word": w, "emoji": e, "submitter": "seed", "votes": v}
                    for w, e, v in seeds
                ]
            else:
                data['letters'][idx]['candidates'] = []
        else:
            seed = v2_default_data() if game == 'v2' else default_data()
            write_data(seed, game)
            return self.send_json({'success': True})
        write_data(data, game)
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
    mode = 'Upstash Redis ☁️' if USE_UPSTASH else 'ملف محلي 💾'
    print(f'\n🌴 ألفبائية السعودية → http://localhost:{port}  [{mode}]\n')
    ThreadingHTTPServer(('0.0.0.0', port), Handler).serve_forever()
