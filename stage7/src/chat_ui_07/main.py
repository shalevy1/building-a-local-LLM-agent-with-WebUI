"""
Stage 7: Slash commands as buttons (final version)
===================================================
Adds context/compact/tools control messages, exposed as buttons in the
sidebar. This is the complete final version of the agent.

Run:
    uvicorn main:app --reload
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


def read_text_file(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {str(e)}"


tools = [
    {'type': 'function', 'function': {
        'name': 'read_text_file',
        'description': 'Read the contents of a text file from the local disk.',
        'parameters': {'type': 'object', 'properties': {'path': {'type': 'string'}}, 'required': ['path']}}},
    {'type': 'function', 'function': {
        'name': 'get_current_datetime',
        'description': 'Get the current local date and time.',
        'parameters': {'type': 'object', 'properties': {}}}},
]


class Agent:
    def __init__(self, session_id=None):
        self.session_id = session_id or datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.history_file = os.path.join(HISTORY_DIR, f"{self.session_id}.json")
        self.messages = []
        self.active_skill_content = ""
        self._warned_thresholds = set()

        if os.path.exists(self.history_file):
            with open(self.history_file, 'r', encoding='utf-8') as f:
                self.messages = json.load(f)

    def estimate_tokens(self):
        text = "".join([str(m.get('content', '')) for m in self.messages])
        return len(text) // 4

    def save_history(self):
        serializable = []
        for m in self.messages:
            if hasattr(m, 'model_dump'):
                serializable.append(m.model_dump())
            elif isinstance(m, dict):
                m_copy = dict(m)
                if 'tool_calls' in m_copy and m_copy['tool_calls']:
                    m_copy['tool_calls'] = [
                        tc.model_dump() if hasattr(tc, 'model_dump') else tc
                        for tc in m_copy['tool_calls']
                    ]
                serializable.append(m_copy)
            else:
                serializable.append(dict(m))
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(serializable, f, indent=4)

    def build_messages_for_model(self):
        if self.active_skill_content:
            return [{'role': 'system', 'content': self.active_skill_content}] + self.messages
        return self.messages

    def _do_compact(self):
        """Blocking Ollama call — run via asyncio.to_thread."""
        split_idx = int(len(self.messages) * 0.7)
        to_summarize = self.messages[:split_idx]
        keep_fresh = self.messages[split_idx:]
        resp = ollama.chat(
            model=MODEL_NAME,
            messages=to_summarize + [{'role': 'user', 'content':
                "Summarize this conversation briefly, preserving key facts and active goals."}],
        )
        summary = resp['message']['content']
        self.messages = [{'role': 'system', 'content': f"PREVIOUS SUMMARY: {summary}"}] + keep_fresh
        self._warned_thresholds = set()

    async def compact_history(self):
        if len(self.messages) < 4:
            return
        import asyncio
        try:
            await asyncio.to_thread(self._do_compact)
        except Exception as e:
            print(f"[ERROR] Compaction failed: {e}")

    def handle_tools(self, tool_calls):
        for tool in tool_calls:
            name = tool.function.name
            args = tool.function.arguments or {}
            if name == 'read_text_file':
                res = read_text_file(args.get('path', ''))
            elif name == 'get_current_datetime':
                res = datetime.now().strftime("%A, %B %d, %Y - %H:%M:%S")
            else:
                res = "Unknown tool."
            if len(res) > 4000:
                res = res[:1000] + "\n...[TRUNCATED]..." + res[-1000:]
            self.messages.append({'role': 'tool', 'content': res})

        resp = ollama.chat(model=MODEL_NAME, messages=self.build_messages_for_model(), tools=tools)
        return {'role': 'assistant', 'content': resp['message']['content']}


async def stream_to_websocket(agent, websocket):
    tokens = agent.estimate_tokens()

    for threshold_pct, label in [(85, "15%"), (90, "10%"), (95, "5%")]:
        if tokens >= CONTEXT_THRESHOLD * threshold_pct // 100 and threshold_pct not in agent._warned_thresholds:
            agent._warned_thresholds.add(threshold_pct)
            await websocket.send_json({
                'type': 'system',
                'content': f"Warning: {label} context space remaining ({tokens}/{CONTEXT_THRESHOLD} tokens)",
            })

    if tokens > CONTEXT_THRESHOLD:
        await websocket.send_json({
            'type': 'system', 'content': f"Compacting context... ({tokens}/{CONTEXT_THRESHOLD} tokens)"})
        await agent.compact_history()
        await websocket.send_json({'type': 'system', 'content': 'Context compacted.'})

    response_stream = ollama.chat(
        model=MODEL_NAME, messages=agent.build_messages_for_model(), stream=True, tools=tools,
    )

    full_content = ""
    collected_tool_calls = []

    await websocket.send_json({'type': 'start'})

    for chunk in response_stream:
        msg = chunk.message
        if hasattr(msg, 'tool_calls') and msg.tool_calls:
            collected_tool_calls = msg.tool_calls
        if hasattr(msg, 'thinking') and msg.thinking:
            await websocket.send_json({'type': 'thinking', 'content': msg.thinking})
        elif msg.content:
            await websocket.send_json({'type': 'content', 'content': msg.content})
            full_content += msg.content

    if collected_tool_calls:
        agent.messages.append({'role': 'assistant', 'tool_calls': collected_tool_calls})
        for tc in collected_tool_calls:
            await websocket.send_json({
                'type': 'tool_call', 'name': tc.function.name, 'args': tc.function.arguments,
            })
        final_msg = agent.handle_tools(collected_tool_calls)
        await websocket.send_json({'type': 'tool_result'})
        await websocket.send_json({'type': 'content', 'content': final_msg['content']})
        agent.messages.append(final_msg)
    else:
        agent.messages.append({'role': 'assistant', 'content': full_content})

    tokens = agent.estimate_tokens()
    if tokens > CONTEXT_THRESHOLD:
        await websocket.send_json({'type': 'system', 'content': f"Compacting context... ({tokens}/{CONTEXT_THRESHOLD} tokens)"})
        await agent.compact_history()
        await websocket.send_json({'type': 'system', 'content': 'Context compacted.'})

    await websocket.send_json({'type': 'end'})


app = FastAPI()


@app.get("/")
async def root():
    return FileResponse("index.html")


@app.get("/sessions")
async def list_sessions():
    if not os.path.exists(HISTORY_DIR):
        return {'sessions': []}
    files = sorted(os.listdir(HISTORY_DIR), reverse=True)
    return {'sessions': [f.replace('.json', '') for f in files if f.endswith('.json')]}


@app.get("/skills")
async def list_skills():
    if not os.path.exists(SKILLS_DIR):
        return {'skills': []}
    skills = [f.replace('.md', '') for f in os.listdir(SKILLS_DIR) if f.endswith('.md')]
    return {'skills': skills}


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    agent = Agent(session_id=session_id)

    for m in agent.messages:
        if m.get('role') == 'user':
            await websocket.send_json({'type': 'replay_user', 'content': m['content']})
        elif m.get('role') == 'assistant' and m.get('content'):
            await websocket.send_json({'type': 'replay_assistant', 'content': m['content']})

    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)

            if 'control' in msg:
                ctrl = msg['control']
                if ctrl == 'load_skill':
                    path = os.path.join(SKILLS_DIR, f"{msg['name']}.md")
                    if os.path.exists(path):
                        with open(path, 'r', encoding='utf-8') as f:
                            agent.active_skill_content = f.read()
                        await websocket.send_json({
                            'type': 'system', 'content': f"Skill loaded: {msg['name']}"})
                    else:
                        await websocket.send_json({
                            'type': 'system', 'content': f"Skill not found: {msg['name']}"})
                elif ctrl == 'context':
                    tokens = agent.estimate_tokens()
                    await websocket.send_json({
                        'type': 'system',
                        'content': f"Context: {tokens}/{CONTEXT_THRESHOLD} tokens"})
                    if tokens > CONTEXT_THRESHOLD:
                        await websocket.send_json({
                            'type': 'system',
                            'content': f"Compacting context... ({tokens}/{CONTEXT_THRESHOLD} tokens)"})
                        await agent.compact_history()
                        await websocket.send_json({'type': 'system', 'content': 'Context compacted.'})
                elif ctrl == 'compact':
                    tokens = agent.estimate_tokens()
                    await websocket.send_json({
                        'type': 'system',
                        'content': f"Compacting context... ({tokens}/{CONTEXT_THRESHOLD} tokens)"})
                    await agent.compact_history()
                    await websocket.send_json({
                        'type': 'system', 'content': 'Context compacted.'})
                elif ctrl == 'tools':
                    names = [t['function']['name'] for t in tools]
                    await websocket.send_json({
                        'type': 'system', 'content': f"Tools: {', '.join(names)}"})
                continue

            user_input = msg.get('content', '')
            agent.messages.append({'role': 'user', 'content': user_input})
            await stream_to_websocket(agent, websocket)
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
        config = uvicorn.Config("chat_ui_07.main:app", host="127.0.0.1", port=8000)
        server = uvicorn.Server(config)
        await server.serve()

    try:
        asyncio.run(_serve())
    except KeyboardInterrupt:
        pass
