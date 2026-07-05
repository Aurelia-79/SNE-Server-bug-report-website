#!/usr/bin/env python3
"""远程命令执行 — 纯 HTTP，不依赖浏览器。

启动后，Claude 通过 HTTP 请求直接执行命令并返回结果。
GET http://<ip>:17254/?token=xxx&cmd=dir
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse


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
        print(f"[remote-cmd] Token: {token}")
    return token


TOKEN = get_token()
TIMEOUT = int(os.getenv("CMD_TIMEOUT", "30"))


class CmdHandler(BaseHTTPRequestHandler):
    def _handle(self, cmd: str) -> bytes:
        """执行命令并返回响应体（字节）。"""
        print(f"[remote-cmd] 执行: {cmd[:120]}")
        # -EncodedCommand 保证输入的 UTF-16LE 编码正确
        encoded = base64.b64encode(cmd.encode("utf-16-le")).decode("ascii")
        try:
            clean_env = {k: v for k, v in os.environ.items() if v is not None}
            clean_env["POWERSHELL_TELEMETRY_OPTOUT"] = "1"
            # 不指定 encoding，拿原始字节
            result = subprocess.run(
                ["powershell.exe", "-NoLogo", "-NoProfile", "-EncodedCommand", encoded],
                capture_output=True,
                timeout=TIMEOUT,
                cwd=str(Path.home()),
                env=clean_env,
            )
            # PowerShell 输出到管道时仍用系统默认编码 (GBK/cp936)
            # stderr 可能混入 CLIXML 进度消息，优先解码 stdout
            raw_stdout = result.stdout or b""
            raw_stderr = result.stderr or b""
            output = raw_stdout.decode("gbk", errors="replace")
            if raw_stderr:
                stderr_text = raw_stderr.decode("gbk", errors="replace")
                # 过滤掉 CLIXML 进度噪音
                if "<Objs" in stderr_text or "<CLIXML" in stderr_text:
                    stderr_text = "(PowerShell progress messages omitted)"
                if stderr_text.strip():
                    output += "\n[STDERR]\n" + stderr_text
            if not output.strip():
                output = "(no output)"
        except subprocess.TimeoutExpired:
            output = f"[ERROR] 命令超时 ({TIMEOUT}s)"
        except Exception as e:
            output = f"[ERROR] {e}"
        return output.encode("utf-8", errors="replace")

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        if qs.get("token", [""])[0] != TOKEN:
            self.send_error(403, "Forbidden: token mismatch")
            return
        cmd = qs.get("cmd", [""])[0]
        if not cmd:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "message": "Remote CMD ready"}, ensure_ascii=False).encode("utf-8"))
            return
        body = self._handle(cmd)
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        """支持 POST，方便 curl --data-urlencode。"""
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length).decode("utf-8", errors="replace")
        from urllib.parse import parse_qs as _pqs
        qs = _pqs(raw)
        if qs.get("token", [""])[0] != TOKEN:
            self.send_error(403, "Forbidden: token mismatch")
            return
        cmd = qs.get("cmd", [""])[0]
        if not cmd:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "message": "Remote CMD ready"}, ensure_ascii=False).encode("utf-8"))
            return
        body = self._handle(cmd)
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args) -> None:
        pass


def main() -> None:
    PORT = int(os.getenv("CMD_PORT", "17254"))
    server = HTTPServer(("0.0.0.0", PORT), CmdHandler)
    print(f"[remote-cmd] 命令执行接口: http://0.0.0.0:{PORT}/?token={TOKEN}&cmd=dir")
    print(f"[remote-cmd] 用法: curl \"http://IP:{PORT}/?token={TOKEN}&cmd=whoami\"")
    print(f"[remote-cmd] 已就绪... (Ctrl+C 停止)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[remote-cmd] 已停止。")


if __name__ == "__main__":
    main()
