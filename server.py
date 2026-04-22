import json
import os
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, 'data', 'alphabet.json')
PUBLIC_DIR = os.path.join(BASE_DIR, 'public')

def read_data():
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def write_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=PUBLIC_DIR, **kwargs)

    def log_message(self, format, *args):
        pass  # Silent

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == '/api/alphabet':
            self.send_json(read_data())
        else:
            super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        length = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(length)) if length else {}

        if parsed.path == '/api/submit':
            self.handle_submit(body)
        elif parsed.path == '/api/vote':
            self.handle_vote(body)
        elif parsed.path == '/api/reset':
            self.handle_reset(body)
        else:
            self.send_error(404)

    def handle_submit(self, body):
        idx = body.get('letterIndex')
        word = (body.get('word') or '').strip()
        emoji = body.get('emoji', '✨')
        submitter = body.get('submitter', 'مجهول')

        data = read_data()
        if idx is None or idx < 0 or idx >= len(data['letters']):
            return self.send_json({'error': 'حرف غير صحيح'}, 400)

        letter = data['letters'][idx]
        if letter['status'] != 'empty':
            return self.send_json({'error': 'هذا الحرف مأخوذ بالفعل'}, 400)
        if not word or len(word) < 2:
            return self.send_json({'error': 'الكلمة قصيرة جداً'}, 400)

        letter.update({'status':'pending','word':word,'emoji':emoji,'submitter':submitter,'votes':0,'upvotes':0,'downvotes':0})
        data['activity'].insert(0, {'text': f'{submitter} اقترح كلمة "{word}" للحرف {letter["letter"]} 🟡','time':'منذ لحظة'})
        data['activity'] = data['activity'][:20]
        write_data(data)
        self.send_json({'success': True, 'letter': letter})

    def handle_vote(self, body):
        idx = body.get('letterIndex')
        vote = body.get('vote')
        data = read_data()

        if idx is None or idx < 0 or idx >= len(data['letters']):
            return self.send_json({'error': 'حرف غير صحيح'}, 400)

        letter = data['letters'][idx]
        if letter['status'] != 'pending':
            return self.send_json({'error': 'لا يوجد اقتراح للتصويت عليه'}, 400)

        if vote == 'up':
            letter['upvotes'] = letter.get('upvotes', 0) + 1
        else:
            letter['downvotes'] = letter.get('downvotes', 0) + 1

        if letter.get('upvotes', 0) >= 3:
            letter['status'] = 'approved'
            data['activity'].insert(0, {'text': f'تم اعتماد كلمة "{letter["word"]}" للحرف {letter["letter"]} ✅','time':'منذ لحظة'})

        if letter.get('downvotes', 0) >= 3:
            rejected = letter['word']
            letter.update({'status':'empty','word':'','emoji':'','submitter':'','votes':0,'upvotes':0,'downvotes':0})
            data['activity'].insert(0, {'text': f'تم رفض كلمة "{rejected}" ❌','time':'منذ لحظة'})

        data['activity'] = data['activity'][:20]
        write_data(data)
        self.send_json({'success': True, 'letter': letter})

    def handle_reset(self, body):
        if body.get('secret') != 'saudi2025':
            return self.send_json({'error': 'غير مصرح'}, 403)
        idx = body.get('letterIndex')
        data = read_data()
        letter = data['letters'][idx]
        letter.update({'status':'empty','word':'','emoji':'','submitter':'','votes':0,'upvotes':0,'downvotes':0})
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

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    print(f'\n🌴 الأبجدية السعودية: http://localhost:{port}\n')
    HTTPServer(('0.0.0.0', port), Handler).serve_forever()
