import json
import os
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler


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

            api_key = os.environ.get('ANTHROPIC_API_KEY', '')
            if not api_key:
                self._json_response(500, {'error': 'ANTHROPIC_API_KEY not configured'})
                return

            messages = data.get('messages', [])
            model = data.get('model', 'claude-opus-4-5')
            max_tokens = data.get('max_tokens', 8096)
            system = data.get('system', 'You are Claw Code, a helpful AI assistant powered by Claude.')

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

            self._json_response(200, {
                'reply': reply,
                'model': result.get('model', model),
                'usage': usage
            })

        except urllib.error.HTTPError as e:
            err_body = e.read().decode('utf-8')
            try:
                err_json = json.loads(err_body)
            except Exception:
                err_json = {'raw': err_body}
            self._json_response(e.code, {'error': err_json})
        except Exception as e:
            self._json_response(500, {'error': str(e)})

    def _json_response(self, status, data):
        body = json.dumps(data).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)
