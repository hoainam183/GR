import json
from openai import OpenAI  # LM Studio dùng OpenAI-compatible endpoint
from .state import AgentState
from .tools import TOOL_DEFINITIONS
from .tool_adapters import execute_tool
from .prompts import AGENT_SYSTEM_PROMPT, SYNTHESIS_PROMPT

class ReActAgent:
    def __init__(self, settings):
        self.client = OpenAI(
            base_url=settings.lm_studio_url,  # "http://localhost:1234/v1"
            api_key="lm-studio"
        )
        self.model = settings.agent_model  # "qwen2.5-8b-instruct"

    def run(self, query: str) -> tuple[str, list]:
        """Returns (answer, tool_call_history) cho logging."""
        state = AgentState(query=query)
        state.messages = [
            {"role": "system", "content": AGENT_SYSTEM_PROMPT},
            {"role": "user", "content": query}
        ]

        while not state.is_done():
            state.iteration += 1
            action = self._think(state)

            if action["type"] == "final_answer":
                state.final_answer = action["content"]
            elif action["type"] == "tool_call":
                result = execute_tool(action["tool"], action["args"])
                state.add_tool_result(action["tool"], result)
                # Append vào messages để model biết kết quả
                state.messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [action["raw_tool_call"]]
                })
                state.messages.append({
                    "role": "tool",
                    "tool_call_id": action["raw_tool_call"]["id"],
                    "content": result
                })
            else:  # parse_error — fallback
                state.final_answer = self._fallback_answer(state)

        return state.final_answer, state.tool_call_history

    def _think(self, state: AgentState) -> dict:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=state.messages,
                tools=TOOL_DEFINITIONS,
                tool_choice="auto",
                temperature=0.1,   # Thấp cho reasoning nhất quán
                max_tokens=1000
            )
            msg = response.choices[0].message

            if msg.tool_calls:
                tc = msg.tool_calls[0]
                return {
                    "type": "tool_call",
                    "tool": tc.function.name,
                    "args": json.loads(tc.function.arguments),
                    "raw_tool_call": {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name,
                                     "arguments": tc.function.arguments}
                    }
                }
            else:
                return {"type": "final_answer", "content": msg.content}

        except (json.JSONDecodeError, Exception):
            return {"type": "parse_error"}

    def _fallback_answer(self, state: AgentState) -> str:
        """Nếu agent loop thất bại, synthesize từ tool results đã có."""
        if not state.tool_results:
            return "Xin lỗi, tôi không thể tìm thấy thông tin phù hợp."
        context = "\n\n".join(r["result"] for r in state.tool_results)
        # Gọi LLM một lần nữa để tổng hợp, không dùng tools
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYNTHESIS_PROMPT},
                {"role": "user", "content": f"Câu hỏi: {state.query}\n\nThông tin:\n{context}"}
            ],
            temperature=0.2,
            max_tokens=800
        )
        return resp.choices[0].message.content