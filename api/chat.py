import json
import os
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler

SIMPLE_KW = ['bonjour','salut','hello','hi','merci','ok','oui','non','quoi','what','who','when','where','how much','combien','quelle heure','quel jour','meteo','blague','joke','traduis','translate','definis','define','simple','rapide','resume','summarize','liste','list','donne moi','give me']
COMPLEX_KW = ['architecture','system design','analyse','analyze','refactor','optimise','optimize','debug','performance','securite','security','algorithme','algorithm','complexe','complex','avance','advanced','integre','integrate','deploie','deploy','infrastructure','machine learning','deep learning','neural','audit','review complet','full review','strategie','strategy','concurrent','threading','async','microservice']

def classify(msg):
    m = msg.lower()
    for kw in COMPLEX_KW:
        if kw in m:
            return 'complex'
    for kw in SIMPLE_KW:
        if kw in m:
            return 'simple'
    n = len(msg.split())
    if n <= 12:
        return 'simple'
    if n <= 50:
        return 'medium'
    return 'complex'

def suggestion(complexity):
    if complexity == 'simple':
        return {'provider':'groq','model':'llama-3.3-70b-versatile','label':'Llama 3.3 70B (Groq - gratuit)','reason':'Tache simple — rapide et gratuit','tier':'free'}
    if complexity == 'medium':
        return {'provider':'openai','model':'gpt-4o-mini','label':'GPT-4o mini (OpenAI)','reason':'Tache moderee — bon equilibre qualite/cout','tier':'low-cost'}
    return {'provider':'anthropic','model':'claude-opus-4-5','label':'Claude Opus (Anthropic)','reason':'Tache complexe — meilleure qualite disponible','tier':'premium'}

def call_api(provider, model, api_key, messages, system, max_tokens):
    if provider == 'anthropic':
        payload = {'model':model,'max_tokens':max_tokens,'system':system,'messages':messages}
        req = urllib.request.Request(
            'https://api.anthropic.com/v1/messages',
            data=json.dumps(payload).encode(),
            headers={'x-api-key':api_key,'anthropic-version':'2023-06-01','content-type':'application/json'},
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=25) as r:
            d = json.loads(r.read())
        return d['content'][0]['text'], d.get('usage',{})
    else:
        url = 'https://api.groq.com/openai/v1/chat/completions' if provider == 'groq' else 'https://api.openai.com/v1/chat/completions'
        msgs = [{'role':'system','content':system}] + messages
        payload = {'model':model,'messages':msgs,'max_tokens':max_tokens}
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={'Authorization':'Bearer '+api_key,'Content-Type':'application/json'},
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=25) as r:
            d = json.loads(r.read())
        c = d['choices'][0]['message']['content']
        u = d.get('usage',{})
        return c, {'input_tokens':u.get('prompt_tokens',0),'output_tokens':u.get('completion_tokens',0)}

class handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_POST(self):
        try:
            n = int(self.headers.get('Content-Length',0))
            data = json.loads(self.rfile.read(n))
        except Exception as e:
            self._resp(400, {'error': 'Invalid JSON: ' + str(e)})
            return

        try:
            action = data.get('action','chat')

            if action == 'classify':
                msg = data.get('message','')
                c = classify(msg)
                self._resp(200, {'complexity':c,'suggestion':suggestion(c)})
                return

            provider = data.get('provider','groq')
            model = data.get('model','llama-3.3-70b-versatile')
            messages = data.get('messages',[])
            max_tokens = min(int(data.get('max_tokens',2048)), 4096)
            system = data.get('system','You are Claw Code, a helpful AI assistant. Respond in the same language as the user.')
            keys = data.get('api_keys',{})

            key_map = {'groq': keys.get('groq','') or os.environ.get('GROQ_API_KEY',''),
                       'openai': keys.get('openai','') or os.environ.get('OPENAI_API_KEY',''),
                       'anthropic': keys.get('anthropic','') or os.environ.get('ANTHROPIC_API_KEY','')}
            api_key = key_map.get(provider,'')

            if not api_key:
                self._resp(400, {'error': 'Cle API manquante pour: ' + provider + '. Verifiez vos cles dans le champ API.'})
                return

            if not messages:
                self._resp(400, {'error': 'Aucun message fourni.'})
                return

            reply, usage = call_api(provider, model, api_key, messages, system, max_tokens)
            self._resp(200, {'reply':reply,'model':model,'provider':provider,'usage':usage})

        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8','replace')
            try:
                err = json.loads(body)
            except Exception:
                err = {'message': body[:300]}
            self._resp(e.code, {'error': err})
        except urllib.error.URLError as e:
            self._resp(502, {'error': 'Connexion impossible: ' + str(e.reason)})
        except Exception as e:
            self._resp(500, {'error': str(e)})

    def _cors(self):
        self.send_header('Access-Control-Allow-Origin','*')
        self.send_header('Access-Control-Allow-Methods','POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers','Content-Type')

    def _resp(self, status, data):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self._cors()
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)
