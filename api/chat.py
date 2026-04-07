import json
import os
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler

# Complexity keywords for auto-detection
SIMPLE_KEYWORDS = [
    'bonjour', 'salut', 'hello', 'hi', 'merci', 'ok', 'oui', 'non',
    'quelle heure', 'quel jour', 'meteo', 'blague', 'joke',
    'traduis', 'translate', 'definis', 'define', 'c est quoi', "c'est quoi",
    'simple', 'rapide', 'vite', 'resume', 'resume en', 'summarize',
    'liste', 'list', 'donne moi', 'give me', 'explique', 'explain simply'
]

COMPLEX_KEYWORDS = [
    'architecture', 'system design', 'analyse', 'analyze', 'refactor',
    'optimise', 'optimize', 'debug', 'performance', 'securite', 'security',
    'algorithme', 'algorithm', 'complexe', 'complex', 'avance', 'advanced',
    'integre', 'integrate', 'deploie', 'deploy', 'infrastructure',
    'machine learning', 'deep learning', 'neural', 'ia', 'ai model',
    'audit', 'review complet', 'full review', 'strategie', 'strategy'
]

def classify_task(message):
    msg_lower = message.lower()
    msg_len = len(message.split())

    # Check complex keywords first
    for kw in COMPLEX_KEYWORDS:
        if kw in msg_lower:
            return 'complex'

    # Check simple keywords
    for kw in SIMPLE_KEYWORDS:
        if kw in msg_lower:
            return 'simple'

    # Classify by length
    if msg_len <= 15:
        return 'simple'
    elif msg_len <= 60:
        return 'medium'
    else:
        return 'complex'

def get_suggested_model(complexity):
    if complexity == 'simple':
        return {
            'provider': 'groq',
            'model': 'llama-3.3-70b-versatile',
            'label': 'Llama 3.3 70B (Groq)',
            'reason': 'Tache simple — Llama 3 gratuit et rapide',
            'tier': 'free'
        }
    elif complexity == 'medium':
        return {
            'provider': 'openai',
            'model': 'gpt-4o-mini',
            'label': 'GPT-4o mini (OpenAI)',
            'reason': 'Tache moderee — GPT-4o mini offre un bon equilibre',
            'tier': 'low-cost'
        }
    else:
        return {
            'provider': 'anthropic',
            'model': 'claude-opus-4-5',
            'label': 'Claude Opus (Anthropic)',
            'reason': 'Tache complexe — Claude Opus pour la meilleure qualite',
            'tier': 'premium'
        }

def call_groq(api_key, model, messages, system, max_tokens):
    openai_messages = [{'role': 'system', 'content': system}] + messages
    payload = {
        'model': model,
        'messages': openai_messages,
        'max_tokens': max_tokens
    }
    req = urllib.request.Request(
        'https://api.groq.com/openai/v1/chat/completions',
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Authorization': 'Bearer ' + api_key,
            'Content-Type': 'application/json'
        },
        method='POST'
    )
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read().decode('utf-8'))
    reply = result['choices'][0]['message']['content']
    usage = result.get('usage', {})
    return reply, {'input_tokens': usage.get('prompt_tokens', 0), 'output_tokens': usage.get('completion_tokens', 0)}

def call_openai(api_key, model, messages, system, max_tokens):
    openai_messages = [{'role': 'system', 'content': system}] + messages
    payload = {
        'model': model,
        'messages': openai_messages,
        'max_tokens': max_tokens
    }
    req = urllib.request.Request(
        'https://api.openai.com/v1/chat/completions',
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Authorization': 'Bearer ' + api_key,
            'Content-Type': 'application/json'
        },
        method='POST'
    )
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read().decode('utf-8'))
    reply = result['choices'][0]['message']['content']
    usage = result.get('usage', {})
    return reply, {'input_tokens': usage.get('prompt_tokens', 0), 'output_tokens': usage.get('completion_tokens', 0)}

def call_anthropic(api_key, model, messages, system, max_tokens):
    payload = {
        'model': model,
        'max_tokens': max_tokens,
        'system': system,
        'messages': messages
    }
    req = urllib.request.Request(
        'https://api.anthropic.com/v1/messages',
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'x-api-key': api_key,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json'
        },
        method='POST'
    )
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read().decode('utf-8'))
    reply = result['content'][0]['text']
    usage = result.get('usage', {})
    return reply, usage


class handler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body)

            action = data.get('action', 'chat')

            # Action: classify only — return suggestion without calling LLM
            if action == 'classify':
                last_message = data.get('message', '')
                complexity = classify_task(last_message)
                suggestion = get_suggested_model(complexity)
                self._json_response(200, {
                    'complexity': complexity,
                    'suggestion': suggestion
                })
                return

            # Action: chat — call the chosen LLM
            provider = data.get('provider', 'groq')
            model = data.get('model', 'llama-3.3-70b-versatile')
            messages = data.get('messages', [])
            max_tokens = data.get('max_tokens', 4096)
            system = data.get('system', 'You are Claw Code, a helpful AI assistant. Answer in the same language as the user.')

            # Get API key: from request body or env
            keys = data.get('api_keys', {})
            api_key = ''
            if provider == 'groq':
                api_key = keys.get('groq', '') or os.environ.get('GROQ_API_KEY', '')
            elif provider == 'openai':
                api_key = keys.get('openai', '') or os.environ.get('OPENAI_API_KEY', '')
            elif provider == 'anthropic':
                api_key = keys.get('anthropic', '') or os.environ.get('ANTHROPIC_API_KEY', '')

            if not api_key:
                self._json_response(400, {'error': 'Cle API manquante pour le fournisseur: ' + provider})
                return

            reply = ''
            usage = {}

            try:
                if provider == 'groq':
                    reply, usage = call_groq(api_key, model, messages, system, max_tokens)
                elif provider == 'openai':
                    reply, usage = call_openai(api_key, model, messages, system, max_tokens)
                elif provider == 'anthropic':
                    reply, usage = call_anthropic(api_key, model, messages, system, max_tokens)
                else:
                    self._json_response(400, {'error': 'Fournisseur inconnu: ' + provider})
                    return
            except urllib.error.HTTPError as e:
                err_body = e.read().decode('utf-8')
                try:
                    err_json = json.loads(err_body)
                except Exception:
                    err_json = {'raw': err_body}
                self._json_response(e.code, {'error': err_json})
                return

            self._json_response(200, {
                'reply': reply,
                'model': model,
                'provider': provider,
                'usage': usage
            })

        except Exception as e:
            self._json_response(500, {'error': str(e)})

    def _json_response(self, status, data):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)
