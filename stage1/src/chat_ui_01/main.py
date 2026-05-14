"""
Stage 1: The Agent class
========================
This stage refactors the state from Part 1 into a reusable Agent class.
We then drive it with a small CLI loop, just to prove the class works
before we wire it up to a WebSocket in Stage 2.

Run:
    python main.py
"""

import ollama
import os
import json
from datetime import datetime

MODEL_NAME = 'qwen3.5:9b'   # change to whatever model you have pulled
HISTORY_DIR = "history"
SKILLS_DIR = "skills"
CONTEXT_THRESHOLD = 4000

for d in [HISTORY_DIR, SKILLS_DIR]:
    if not os.path.exists(d):
        os.makedirs(d)


# ----- Tools -----

def read_text_file(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {str(e)}"


tools = [
    {
        'type': 'function',
        'function': {
            'name': 'read_text_file',
            'description': 'Read the contents of a text file from the local disk.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'path': {'type': 'string', 'description': 'The path to the file'},
                },
                'required': ['path'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'get_current_datetime',
            'description': 'Get the current local date and time.',
            'parameters': {'type': 'object', 'properties': {}},
        },
    },
]


class Agent:
    def __init__(self, session_id=None):
        self.session_id = session_id or datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.history_file = os.path.join(HISTORY_DIR, f"{self.session_id}.json")
        self.messages = []
        self.active_skill_content = ""

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

    def compact_history(self):
        if len(self.messages) < 4:
            return
        print(f"\n[SYSTEM] Compacting context ({self.estimate_tokens()} tokens)...")
        split_idx = int(len(self.messages) * 0.7)
        to_summarize = self.messages[:split_idx]
        keep_fresh = self.messages[split_idx:]

        summary_prompt = "Summarize this conversation briefly, preserving key facts and active goals."
        try:
            resp = ollama.chat(
                model=MODEL_NAME,
                messages=to_summarize + [{'role': 'user', 'content': summary_prompt}],
            )
            summary = resp['message']['content']
            new_history = [{'role': 'system', 'content': f"PREVIOUS SUMMARY: {summary}"}]
            if self.active_skill_content:
                new_history.insert(0, {'role': 'system', 'content': f"Active Skill: {self.active_skill_content}"})
            new_history.extend(keep_fresh)
            self.messages = new_history
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

        resp = ollama.chat(model=MODEL_NAME, messages=self.messages, tools=tools)
        return {'role': 'assistant', 'content': resp['message']['content']}


# ----- A small CLI driver to prove the class works -----

def chat():
    agent = Agent()
    print(f"--- Agent session: {agent.session_id} ---")
    print("Type 'quit' to exit.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not user_input or user_input.lower() in ('quit', 'exit'):
            break

        agent.messages.append({'role': 'user', 'content': user_input})

        if agent.estimate_tokens() > CONTEXT_THRESHOLD:
            agent.compact_history()

        resp = ollama.chat(model=MODEL_NAME, messages=agent.messages, tools=tools)
        msg = resp['message']

        if hasattr(msg, 'tool_calls') and msg.tool_calls:
            agent.messages.append({'role': 'assistant', 'tool_calls': msg.tool_calls})
            final = agent.handle_tools(msg.tool_calls)
            print(f"Assistant: {final['content']}\n")
            agent.messages.append(final)
        else:
            print(f"Assistant: {msg.content}\n")
            agent.messages.append({'role': 'assistant', 'content': msg.content})

        agent.save_history()

if __name__ == "__main__":
    chat()

