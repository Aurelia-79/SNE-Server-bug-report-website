#!/usr/bin/env python3
"""Web 终端服务器 v2 — 纯文本界面，兼容 websockets 所有版本。
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HTML = r"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Web Terminal</title>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body {
    background: #1e1e1e; color: #d4d4d4; height: 100vh;
    display: flex; flex-direction: column;
    font: 14px/1.5 Consolas, "Courier New", "Microsoft YaHei", monospace;
  }
  #output {
    flex: 1; overflow-y: auto; padding: 12px;
    white-space: pre-wrap; word-break: break-all;
    background: #1e1e1e; border: none; outline: none;
  }
  #input-line {
    display: flex; border-top: 1px solid #444; background: #252526;
  }
  #prompt { color: #6a9955; padding: 8px 4px 8px 12px; user-select: none; }
  #cmd {
    flex: 1; background: transparent; color: #d4d4d4;
    border: none; outline: none; font: inherit; padding: 8px 4px;
  }
  #cmd::placeholder { color: #666; }
  #status-bar {
    display: flex; justify-content: space-between; align-items: center;
    padding: 4px 12px; background: #007acc; color: #fff;
    font-size: 12px; font-family: "Segoe UI", sans-serif;
  }
  .connected { background: #1a7f37; }
  .disconnected { background: #cf222e; }
  #hint {
    color: #888; font-size: 12px; padding: 8px 12px;
    background: #2d2d2d; border-top: 1px solid #444;
  }
  kbd {
    background: #444; border: 1px solid #666; border-radius: 3px;
    padding: 0 4px; font-family: inherit; font-size: 12px;
  }
</style>
</head>
<body>
<div id="status-bar"><span id="status-text">connecting...</span><span id="cwd"></span></div>
<div id="output" aria-live="polite" aria-label="Terminal output"></div>
<div id="hint">按 <kbd>Enter</kbd> 发送命令 &nbsp;|&nbsp; <kbd>Ctrl+L</kbd> 清屏 &nbsp;|&nbsp; <kbd>&uarr;</kbd><kbd>&darr;</kbd> 历史命令</div>
<div id="input-line">
  <span id="prompt">PS&gt;</span>
  <input id="cmd" type="text" placeholder="输入命令..."
         autofocus autocomplete="off" spellcheck="false"
         aria-label="Command input">
</div>
<script>
const OUTPUT = document.getElementById('output');
const CMD = document.getElementById('cmd');
const STATUS_TEXT = document.getElementById('status-text');
const STATUS_BAR = document.getElementById('status-bar');
const CWD_DISPLAY = document.getElementById('cwd');
const PROMPT = document.getElementById('prompt');

const TOKEN = new URLSearchParams(location.search).get('token') || '';
const WS_PORT = parseInt(location.port || '80') + 1;
const WS_URL = (location.protocol === 'https:' ? 'wss:' : 'ws:') +
               '//' + location.hostname + ':' + WS_PORT + '/ws?token=' + encodeURIComponent(TOKEN);

let ws = null;
let history = [];
let historyIdx = -1;

function setStatus(connected) {
  if (connected) {
    STATUS_TEXT.textContent = 'connected';
    STATUS_BAR.className = 'connected';
    CMD.disabled = false;
    CMD.focus();
  } else {
    STATUS_TEXT.textContent = 'disconnected';
    STATUS_BAR.className = 'disconnected';
    CMD.disabled = true;
  }
}

function appendOutput(text) {
  const clean = text.replace(/\x1b\[[0-9;]*[a-zA-Z]/g, '');
  OUTPUT.textContent += clean;
  OUTPUT.scrollTop = OUTPUT.scrollHeight;
  const lines = OUTPUT.textContent.split('\n');
  if (lines.length > 5000) {
    OUTPUT.textContent = lines.slice(-3000).join('\n');
  }
}

function connect() {
  setStatus(false);
  ws = new WebSocket(WS_URL);

  ws.onopen = () => { setStatus(true); };

  ws.onmessage = (evt) => {
    try {
      const obj = JSON.parse(evt.data);
      if (obj.type === 'output') appendOutput(obj.data);
      else if (obj.type === 'cwd') {
        CWD_DISPLAY.textContent = obj.data;
        PROMPT.textContent = 'PS ' + obj.data + '>';
      } else if (obj.type === 'error') {
        appendOutput('[ERROR] ' + obj.data + '\r\n');
      }
    } catch {
      appendOutput(evt.data);
    }
  };

  ws.onclose = () => {
    setStatus(false);
    setTimeout(connect, 2000);
  };
  ws.onerror = () => { ws.close(); };
}

CMD.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') {
    e.preventDefault();
    const cmd = CMD.value;
    if (!cmd.trim()) return;
    history.push(cmd);
    historyIdx = history.length;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'cmd', data: cmd + '\r\n' }));
    }
    CMD.value = '';
  } else if (e.key === 'ArrowUp') {
    e.preventDefault();
    if (history.length === 0) return;
    if (historyIdx === history.length) historyIdx = history.length - 1;
    else if (historyIdx > 0) historyIdx--;
    CMD.value = history[historyIdx];
  } else if (e.key === 'ArrowDown') {
    e.preventDefault();
    if (historyIdx < history.length - 1) {
      historyIdx++;
      CMD.value = history[historyIdx];
    } else {
      historyIdx = history.length;
      CMD.value = '';
    }
  } else if (e.ctrlKey && e.key === 'l') {
    e.preventDefault();
    OUTPUT.textContent = '';
  }
});

connect();
CMD.focus();
</script>
</body>
</html>"""


def get_token() -> str:
    token = os.getenv("TERMINAL_TOKEN", "").strip()
    if not token:
        token_file = Path(__file__).with_name(".terminal_token")
        if token_file.exists():
            token = token_file.read_text().strip()
            if len(token) != 32 or not all(c in "0123456789abcdef" for c in token):
                token = ""
    if not token:
        import secrets
        token = secrets.token_hex(16)
        Path(__file__).with_name(".terminal_token").write_text(token)
        print(f"[terminal-server] 已生成随机 token: {token}")
    return token


def ensure_deps() -> None:
    try:
        import websockets  # noqa: F401
    except ImportError:
        print("[terminal-server] 缺少依赖 websockets，正在安装...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "websockets"])
        print("[terminal-server] 安装完成，请重新运行。")
        sys.exit(1)


# ============================================================
#  简单的 HTTP 服务器，只返回 HTML 页面
# ============================================================
class TerminalHTTPHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        qs_token = parse_qs(parsed.query).get("token", [""])[0]
        if qs_token != TOKEN:
            self.send_response(403)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Forbidden: token mismatch")
            return
        if parsed.path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML.encode("utf-8"))
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args) -> None:
        pass  # 静默 HTTP 日志


def start_http_server(port: int) -> HTTPServer:
    server = HTTPServer(("0.0.0.0", port), TerminalHTTPHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


# ============================================================
#  WebSocket 处理
# ============================================================
async def handle_ws(websocket) -> None:
    """验证 token 后桥接 PowerShell。"""
    # 从 WebSocket 路径中提取 token
    path = websocket.request.path if hasattr(websocket, 'request') else websocket.path
    parsed = urlparse(path)
    qs_token = parse_qs(parsed.query).get("token", [""])[0]
    if qs_token != TOKEN:
        await websocket.send(json.dumps({"type": "error", "data": "token 不匹配"}))
        await websocket.close()
        return

    print(f"[terminal-server] 客户端已连接: {websocket.remote_address}")

    proc = subprocess.Popen(
        ["powershell.exe", "-NoLogo", "-NoExit", "-Command", "-"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=str(Path.home()),
        env={**os.environ, "TERM": "xterm-256color", "CLICOLOR": "1", "POWERSHELL_TELEMETRY_OPTOUT": "1"},
    )
    loop = asyncio.get_event_loop()
    pending = b""

    async def read_stdout() -> None:
        nonlocal pending
        try:
            while True:
                data = await loop.run_in_executor(None, proc.stdout.read, 4096)
                if not data:
                    break
                pending += data
                try:
                    text = pending.decode("utf-8")
                    pending = b""
                except UnicodeDecodeError:
                    continue
                if text:
                    await websocket.send(json.dumps({"type": "output", "data": text}))
            if pending:
                try:
                    await websocket.send(json.dumps({"type": "output", "data": pending.decode("utf-8", errors="replace")}))
                except Exception:
                    pass
        except Exception:
            pass
        finally:
            try:
                await websocket.close()
            except Exception:
                pass

    async def read_ws() -> None:
        try:
            async for msg in websocket:
                try:
                    obj = json.loads(msg)
                    if obj.get("type") == "cmd":
                        proc.stdin.write(obj["data"].encode("utf-8"))
                        proc.stdin.flush()
                except json.JSONDecodeError:
                    if isinstance(msg, str):
                        proc.stdin.write(msg.encode("utf-8"))
                        proc.stdin.flush()
        except Exception:
            pass
        finally:
            try:
                proc.kill()
            except Exception:
                pass

    await asyncio.gather(read_stdout(), read_ws())


# ============================================================
#  主入口
# ============================================================
async def main() -> None:
    global TOKEN
    TOKEN = get_token()
    import websockets
    from websockets.asyncio.server import serve as ws_serve

    HTTP_PORT = int(os.getenv("TERMINAL_HTTP_PORT", "17252"))
    WS_PORT = int(os.getenv("TERMINAL_WS_PORT", "17253"))

    # HTTP 服务器：返回 HTML 页面
    start_http_server(HTTP_PORT)
    print(f"[terminal-server] 页面地址: http://0.0.0.0:{HTTP_PORT}/?token={TOKEN}")

    # WebSocket 服务器：桥接 PowerShell
    print(f"[terminal-server] WebSocket: ws://0.0.0.0:{WS_PORT}/ws")
    print(f"[terminal-server] 在 Chrome 中打开页面地址即可。")

    async with ws_serve(handle_ws, "0.0.0.0", WS_PORT):
        print("[terminal-server] 已就绪，等待连接... (Ctrl+C 停止)")
        await asyncio.get_running_loop().create_future()


if __name__ == "__main__":
    ensure_deps()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[terminal-server] 已停止。")
