from __future__ import annotations

import json
from typing import Any
from urllib import error, parse, request

from fastapi import HTTPException, status

from server.core.config import settings


class ServerBridgeClient:
    def __init__(self) -> None:
        self.base_url = settings.game_bridge_base_url
        self.token = settings.game_bridge_token
        self.timeout = settings.game_bridge_timeout_seconds

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return self._request("GET", path, params=params)

    def post(self, path: str, payload: dict[str, Any] | None = None) -> Any:
        return self._request("POST", path, payload=payload or {})

    def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self.base_url}{path}"
        if params:
            url = f"{url}?{parse.urlencode(params)}"
        body = None
        headers = {"X-Bridge-Token": self.token, "Accept": "application/json"}
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = request.Request(url, data=body, headers=headers, method=method)
        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            if exc.code == 401:
                detail = (
                    "游戏服务器桥接插件认证失败：X-Bridge-Token 不匹配。"
                    "请确认 .env 中的 GAME_BRIDGE_TOKEN 与 SL 插件配置的 BridgeToken 一致，"
                    "然后重启后端服务。"
                )
            elif not detail:
                detail = "游戏服务器桥接插件返回错误。"
            raise HTTPException(
                status_code=exc.code if exc.code >= 400 else status.HTTP_502_BAD_GATEWAY,
                detail=detail,
            ) from exc
        except (error.URLError, TimeoutError) as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"无法连接游戏服务器桥接插件：{exc}",
            ) from exc


bridge_client = ServerBridgeClient()
