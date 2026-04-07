import json
import os
import requests
from http.server import BaseHTTPRequestHandler

SIMPLE_KW = ['bonjour','salut','hello','hi','merci','ok','oui','non','quoi','what','who','when','where','pourquoi','why','how','comment','est-ce','is it','define','definis','traduis','translate','resume','summarize','liste','list']
COMPLEX_KW = ['architecture','system design','analyse','analyze','refactor','optimise','optimize','securite','security','deploy','deployer','infrastructure','scalable','scalability','debug','debugger','microservice','kubernetes','docker','ci/cd','pipeline','algorithme','algorithm','complexite','complexity','performance','benchmark']

def classify(msg):
    m = msg.lower()
    for kw in COMPLEX_KW:
        if kw in m:
            return 'complex'
    for kw in SIMPLE_KW:
        if kw in m:
            return 'simple'
    if len(msg) > 300:
        return 'complex'
    if len(msg) > 80:
        return 'medium'
    return 'simple'

def call_groq(api_key, messages):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "ClawCode/1.0"
    }
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": messages,
        "max_tokens": 2048,
        "temperature": 0.7
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=25)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]

def call_openai(api_key, messages):
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "ClawCode/1.0"
    }
    payload = {
        "model": "gpt-4o-mini",
        "messages": messages,
        "max_tokens": 2048,
        "temperature": 0.7
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=25)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]

def call_anthropic(api_key, messages):
    url = "https://api.anthropic.com/v1/messages"
    system_msg = ""
    filtered = []
    for m in messages:
        if m["role"] == "system":
            system_msg = m["content"]
        else:
            filtered.append(m)
    if not filtered:
        filtered = messages
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
        "User-Agent": "ClawCode/1.0"
    }
    payload = {
        "model": "claude-opus-4-5",
        "messages": filtered,
        "max_tokens": 2048
    }
    if system_msg:
        payload["system"] = system_msg
    resp = requests.post(url, headers=headers, json=payload, timeout=25)
    resp.raise_for_status()
    return resp.json()["content"][0]["text"]

class handler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def send_json(self, status, obj):
        body = json.dumps(obj).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        try:
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            data = json.loads(body)
        except Exception:
            self.send_json(400, {"error": "Invalid JSON"})
            return

        action = data.get("action", "chat")

        if action == "classify":
            msg = data.get("message", "")
            level = classify(msg)
            model_map = {"simple": "llama3", "medium": "gpt4o", "complex": "claude"}
            label_map = {"llama3": "Llama 3.3 70B (Groq)", "gpt4o": "GPT-4o mini (OpenAI)", "claude": "Claude Opus (Anthropic)"}
            suggested = model_map.get(level, "gpt4o")
            self.send_json(200, {"level": level, "suggested_model": suggested, "label": label_map[suggested]})
            return

        messages = data.get("messages", [])
        model = data.get("model", "llama3")
        api_keys = data.get("api_keys", {})

        try:
            if model == "llama3":
                key = api_keys.get("groq") or os.environ.get("GROQ_API_KEY", "")
                if not key:
                    self.send_json(400, {"error": "Clé API Groq manquante. Configurez-la dans 'Clés API'."})
                    return
                reply = call_groq(key, messages)
            elif model == "gpt4o":
                key = api_keys.get("openai") or os.environ.get("OPENAI_API_KEY", "")
                if not key:
                    self.send_json(400, {"error": "Clé API OpenAI manquante. Configurez-la dans 'Clés API'."})
                    return
                reply = call_openai(key, messages)
            elif model == "claude":
                key = api_keys.get("anthropic") or os.environ.get("ANTHROPIC_API_KEY", "")
                if not key:
                    self.send_json(400, {"error": "Clé API Anthropic manquante. Configurez-la dans 'Clés API'."})
                    return
                reply = call_anthropic(key, messages)
            else:
                self.send_json(400, {"error": f"Modele inconnu: {model}"})
                return

            self.send_json(200, {"reply": reply, "model": model})

        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response else 0
            try:
                err_body = e.response.json()
                err_msg = err_body.get("error", {}).get("message", str(e))
            except Exception:
                err_msg = str(e)
            self.send_json(502, {"error": f"Erreur API ({status_code}): {err_msg}"})
        except requests.exceptions.Timeout:
            self.send_json(504, {"error": "Timeout: le modele n a pas repondu dans les 25 secondes."})
        except Exception as e:
            self.send_json(500, {"error": f"Erreur interne: {str(e)}"})
