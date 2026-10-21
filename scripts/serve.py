"""
Servidor local para desenvolver/visualizar o painel no navegador.

    python scripts/serve.py [porta]

Envia "Cache-Control: no-store" para que uma alteracao no JS/CSS apareca
imediatamente (o painel tambem funciona abrindo o arquivo .html direto, sem
servidor — e esse e o modo de uso oficial).
"""

from __future__ import annotations

import http.server
import os
import socketserver
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORTA = int(sys.argv[1]) if len(sys.argv) > 1 else 8777


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        super().end_headers()

    def log_message(self, fmt, *args):
        sys.stderr.write("  %s\n" % (fmt % args))


if __name__ == "__main__":
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", PORTA), Handler) as httpd:
        print("Painel ODS em http://127.0.0.1:%d/prototipo.html  (Ctrl+C para parar)" % PORTA)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nencerrado.")
