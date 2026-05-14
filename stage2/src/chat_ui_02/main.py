"""
Stage 2: A minimal FastAPI server with a WebSocket endpoint
============================================================
Adds the FastAPI app and a WebSocket route. The WebSocket simply echoes
messages back for now, so we can confirm the wiring without HTML.

Run:
    pip install fastapi uvicorn websockets ollama
    uvicorn main:app --reload

Test the WebSocket:
    pip install websockets
    python -c "
    import asyncio, websockets, json
    async def main():
        async with websockets.connect('ws://localhost:8000/ws/test') as ws:
            await ws.send(json.dumps({'content': 'hello'}))
            print(await ws.recv())
    asyncio.run(main())
    "
"""

import ollama
import os
import json
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

MODEL_NAME = 'qwen3.5:9b'
HISTORY_DIR = "history"
SKILLS_DIR = "skills"
CONTEXT_THRESHOLD = 4000

for d in [HISTORY_DIR, SKILLS_DIR]:
    if not os.path.exists(d):
        os.makedirs(d)


# ----- Agent class (same as Stage 1) -----

class Agent:
    def __init__(self, session_id=None):
        self.session_id = session_id or datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.history_file = os.path.join(HISTORY_DIR, f"{self.session_id}.json")
        self.messages = []
        self.active_skill_content = ""

        if os.path.exists(self.history_file):
            with open(self.history_file, 'r', encoding='utf-8') as f:
                self.messages = json.load(f)

    def save_history(self):
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(self.messages, f, indent=4)


# ----- FastAPI server -----

app = FastAPI()


@app.get("/")
async def root():
    return {"status": "Server up. Connect via WebSocket at /ws/{session_id}"}


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    agent = Agent(session_id=session_id)
    print(f"[SYSTEM] Client connected to session {session_id}")

    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            user_input = msg.get('content', '')

            # Echo for now. We will replace this with real streaming in Stage 4.
            await websocket.send_json({
                'type': 'echo',
                'received': user_input,
                'session_id': session_id,
            })

            agent.messages.append({'role': 'user', 'content': user_input})
            agent.save_history()
    except WebSocketDisconnect:
        print(f"[SYSTEM] Client disconnected from session {session_id}")


def chat():
    import asyncio
    import sys
    import uvicorn
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    async def _serve():
        config = uvicorn.Config("chat_ui_02.main:app", host="127.0.0.1", port=8000)
        server = uvicorn.Server(config)
        await server.serve()

    try:
        asyncio.run(_serve())
    except KeyboardInterrupt:
        pass
