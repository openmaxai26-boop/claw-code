import json
import os
import requests

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

def handler(request):
    if request.method == "OPTIONS":
        return Response("", headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type"
        })

    try:
        data = json.loads(request.body)
    except Exception:
        return Response(json.dumps({"error": "Invalid JSON"}), status=400, headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"})

    action = data.get("action", "chat")

    if action == "classify":
        msg = data.get("message", "")
        level = classify(msg)
        model_map = {"simple": "llama3", "medium": "gpt4o", "complex": "claude"}
        label_map = {"llama3": "Llama 3.3 70B (Groq)", "gpt4o": "GPT-4o mini (OpenAI)", "claude": "Claude Opus (Anthropic)"}
        suggested = model_map.get(level, "gpt4o")
        return Response(
            json.dumps({"level": level, "suggested_model": suggested, "label": label_map[suggested]}),
            headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
        )

    messages = data.get("messages", [])
    model = data.get("model", "llama3")
    api_keys = data.get("api_keys", {})

    try:
        if model == "llama3":
            key = api_keys.get("groq") or os.environ.get("GROQ_API_KEY", "")
            if not key:
                return Response(json.dumps({"error": "Clé API Groq manquante. Configurez-la dans 'Clés API'."}), status=400, headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"})
            reply = call_groq(key, messages)
        elif model == "gpt4o":
            key = api_keys.get("openai") or os.environ.get("OPENAI_API_KEY", "")
            if not key:
                return Response(json.dumps({"error": "Clé API OpenAI manquante. Configurez-la dans 'Clés API'."}), status=400, headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"})
            reply = call_openai(key, messages)
        elif model == "claude":
            key = api_keys.get("anthropic") or os.environ.get("ANTHROPIC_API_KEY", "")
            if not key:
                return Response(json.dumps({"error": "Clé API Anthropic manquante. Configurez-la dans 'Clés API'."}), status=400, headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"})
            reply = call_anthropic(key, messages)
        else:
            return Response(json.dumps({"error": f"Modèle inconnu: {model}"}), status=400, headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"})

        return Response(
            json.dumps({"reply": reply, "model": model}),
            headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
        )

    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code if e.response else 0
        try:
            err_body = e.response.json()
            err_msg = err_body.get("error", {}).get("message", str(e))
        except Exception:
            err_msg = str(e)
        return Response(
            json.dumps({"error": f"Erreur API ({status_code}): {err_msg}"}),
            status=502,
            headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
        )
    except requests.exceptions.Timeout:
        return Response(
            json.dumps({"error": "Timeout: le modèle n'a pas répondu dans les 25 secondes."}),
            status=504,
            headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
        )
    except Exception as e:
        return Response(
            json.dumps({"error": f"Erreur interne: {str(e)}"}),
            status=500,
            headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
        )
