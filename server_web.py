"""Serveur Web FastAPI pour visualisation temps reel."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

app = FastAPI(title="Acquisition Rivetage")


class WsHub:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def register(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._clients.add(ws)

    async def unregister(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)

    async def broadcast_point(self, t: float, force_n: float, pos_mm: float) -> None:
        payload = json.dumps(
            {
                "t": t,
                "force_n": force_n,
                "pos_mm": pos_mm,
                "x": pos_mm,
                "y": force_n,
            }
        )
        async with self._lock:
            clients = list(self._clients)

        for ws in clients:
            try:
                await ws.send_text(payload)
            except Exception:
                await self.unregister(ws)

    async def stream_points(self, points: AsyncIterator[tuple[float, float, float]]) -> None:
        async for t, force_n, pos_mm in points:
            await self.broadcast_point(t=t, force_n=force_n, pos_mm=pos_mm)


hub = WsHub()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.websocket("/ws/live")
async def ws_live(ws: WebSocket) -> None:
    await hub.register(ws)
    try:
        while True:
            # Connexion maintenue active; ignore les commandes cliente.
            await ws.receive_text()
    except WebSocketDisconnect:
        await hub.unregister(ws)
