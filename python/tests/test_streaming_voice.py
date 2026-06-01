"""Tests for the streaming-voice extensions on ``AgentSession``.

We can't use respx here — it's WebSocket, not HTTP — so we spin up a
tiny in-process ``websockets`` echo server, point the session at it,
and assert the wire shape (text JSON frames + binary PCM frames + the
order of sends). The server reads everything the client sends and
mirrors it back as JSON events so the client iterator can verify."""

from __future__ import annotations

import asyncio
import json

import pytest
import websockets

from vocence._streaming import AgentSession


async def _fake_voicechat_server(
    received: list,
    *,
    capabilities: dict | None = None,
    port_holder: dict,
) -> None:
    """Echo-style server that records every frame and offers a
    configurable ``capabilities`` block on the ``ready`` event."""
    async def handler(ws):
        # Send ready first so wait_ready() resolves.
        await ws.send(json.dumps({
            "type": "ready",
            "session_id": "sess_test",
            "capabilities": capabilities or {"voice_stream": True, "turn_detection": True},
        }))
        try:
            async for msg in ws:
                if isinstance(msg, (bytes, bytearray)):
                    received.append(("bin", len(msg)))
                else:
                    received.append(("text", msg))
                    # Once the client commits, echo a transcript + turn_end
                    # so the iterator can finish cleanly.
                    try:
                        data = json.loads(msg)
                    except Exception:
                        continue
                    if data.get("type") == "stream_commit":
                        await ws.send(json.dumps({"type": "transcript", "text": "(stream commit ack)"}))
                        await ws.send(json.dumps({"type": "turn_end"}))
                        break
        except websockets.ConnectionClosed:
            pass

    server = await websockets.serve(handler, "127.0.0.1", 0)
    port_holder["port"] = server.sockets[0].getsockname()[1]
    port_holder["server"] = server


@pytest.mark.asyncio
async def test_wait_ready_returns_capabilities() -> None:
    received: list = []
    holder: dict = {}
    await _fake_voicechat_server(received, port_holder=holder)
    try:
        url = f"ws://127.0.0.1:{holder['port']}/"
        async with AgentSession(url=url, api_key="voc_live_test") as sess:
            caps = await sess.wait_ready(timeout=2.0)
            assert caps == {"voice_stream": True, "turn_detection": True}
            assert sess.session_id == "sess_test"
    finally:
        holder["server"].close()
        await holder["server"].wait_closed()


@pytest.mark.asyncio
async def test_stream_lifecycle_sends_correct_wire_shape() -> None:
    """start_stream + send_pcm + commit_stream should ship:
    text JSON `stream_start` → N binary frames → text JSON `stream_commit`."""
    received: list = []
    holder: dict = {}
    await _fake_voicechat_server(received, port_holder=holder)
    try:
        url = f"ws://127.0.0.1:{holder['port']}/"
        async with AgentSession(url=url, api_key="voc_live_test") as sess:
            await sess.wait_ready(timeout=2.0)
            await sess.start_stream()
            for _ in range(3):
                await sess.send_pcm(b"\x00\x01" * 320)  # 20 ms @ 16 kHz
            await sess.commit_stream()
            # Drain remaining events so the server-side close completes.
            events: list = []
            async for ev in sess:
                events.append(ev)
                if getattr(ev, "type", None) == "turn_end":
                    break
        # Server-side recording: 1 stream_start, 3 binary, 1 stream_commit.
        kinds = [r[0] for r in received]
        assert kinds == ["text", "bin", "bin", "bin", "text"]
        first_text = json.loads(received[0][1])
        last_text = json.loads(received[-1][1])
        assert first_text["type"] == "stream_start"
        assert last_text["type"] == "stream_commit"
    finally:
        holder["server"].close()
        await holder["server"].wait_closed()


@pytest.mark.asyncio
async def test_send_pcm_outside_stream_raises() -> None:
    """``send_pcm`` MUST refuse if no stream is open — guards against
    quietly sending audio that the server has no turn to put it in."""
    from vocence._errors import VocenceError

    received: list = []
    holder: dict = {}
    await _fake_voicechat_server(received, port_holder=holder)
    try:
        url = f"ws://127.0.0.1:{holder['port']}/"
        async with AgentSession(url=url, api_key="voc_live_test") as sess:
            await sess.wait_ready(timeout=2.0)
            with pytest.raises(VocenceError):
                await sess.send_pcm(b"\x00\x00")
    finally:
        holder["server"].close()
        await holder["server"].wait_closed()


@pytest.mark.asyncio
async def test_capabilities_populated_via_iterator_too() -> None:
    """When the caller skips ``wait_ready`` and iterates the session
    directly, ``ready`` should STILL populate ``capabilities`` on the
    way through so later code can branch on the flag without having to
    parse the event itself."""
    received: list = []
    holder: dict = {}
    await _fake_voicechat_server(
        received, port_holder=holder,
        capabilities={"voice_stream": False, "turn_detection": False},
    )
    try:
        url = f"ws://127.0.0.1:{holder['port']}/"
        async with AgentSession(url=url, api_key="voc_live_test") as sess:
            it = sess.__aiter__()
            # First event off the wire is the ``ready`` frame the server
            # always sends. The session caches its capabilities as the
            # event passes through, then yields the event itself.
            first = await asyncio.wait_for(it.__anext__(), timeout=2.0)
            assert getattr(first, "type", None) == "ready"
            assert sess.capabilities == {"voice_stream": False, "turn_detection": False}
            assert sess.session_id == "sess_test"
    finally:
        holder["server"].close()
        await holder["server"].wait_closed()
