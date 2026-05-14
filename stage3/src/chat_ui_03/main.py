"""
Stage 3: The HTML+JS frontend
==============================
The server now serves index.html on /. The page renders the layout
(sidebar + chat area) and connects a WebSocket on load, but the JS
just logs incoming messages to the browser console.

Run:
    uvicorn main:app --reload
    open http://localhost:8000/
    (then open browser dev tools to see the console)
"""

import ollama
import os
import json
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

MODEL_NAME = 'qwen3.5:9b'
HISTORY_DIR = "history"
SKILLS_DIR = "skills"
CONTEXT_THRESHOLD = 4000

for d in [HISTORY_DIR, SKILLS_DIR]:
    if not os.path.exists(d):
        os.makedirs(d)


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


app = FastAPI()


@app.get("/")
async def root():
    return FileResponse("index.html")


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    agent = Agent(session_id=session_id)

    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            user_input = msg.get('content', '')

            await websocket.send_json({'type': 'echo', 'received': user_input})

            agent.messages.append({'role': 'user', 'content': user_input})
            agent.save_history()
    except WebSocketDisconnect:
        pass


def chat():
    import asyncio
    import sys
    import uvicorn
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    async def _serve():
        config = uvicorn.Config("chat_ui_03.main:app", host="127.0.0.1", port=8000)
        server = uvicorn.Server(config)
        await server.serve()

    try:
        asyncio.run(_serve())
    except KeyboardInterrupt:
        pass
