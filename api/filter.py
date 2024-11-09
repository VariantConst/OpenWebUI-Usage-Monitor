from typing import Optional
from pydantic import Field, BaseModel
import requests
import json
import math


class Filter:
    class Valves(BaseModel):
        API_ENDPOINT: str = Field(
            default="", description="The base URL for the API endpoint."
        )
        POST_USER_INFO_PATH: str = Field(
            default="/post_user_info",
            description="Single-level endpoint for posting user info.",
        )
        POST_RESULT_PATH: str = Field(
            default="/post_result",
            description="Single-level endpoint for posting LLM result.",
        )
        USE_ACCURATE_TOKENIZER: bool = Field(
            default=False,
            description="Whether to use accurate tokenizer calculation from backend",
        )

    def __init__(self):
        self.type = "filter"
        self.name = "OpenWebUI Monitor"
        self.valves = self.Valves()

    def calculate_tokens(self, messages: list[dict] | str, model: str) -> int:
        if not self.valves.USE_ACCURATE_TOKENIZER:
            # 使用原来的估算方法
            total = 0
            if isinstance(messages, list):
                for msg in messages:
                    total += len(msg["content"]) / 2.718 + 2
            else:
                total += len(json.dumps(messages)[1:-1].encode('unicode-escape').decode()) / 2.718 + 2
            return int(total)
        else:
            # 使用后端的精确计算
            try:
                post_url = f"{self.valves.API_ENDPOINT}/calculate_tokens"
                response = requests.post(
                    post_url,
                    json={
                        "messages": messages,
                        "type": "chat" if isinstance(messages, list) else "text",
                        "model": model
                    }
                )
                response.raise_for_status()
                return response.json()["tokens"]
            except Exception as e:
                print(f"Error calculating tokens accurately: {e}")
                # 如果精确计算失败，回退到估算方法
                return self.calculate_tokens(messages, model)

    def inlet(self, body: dict, user: Optional[dict] = None, __user__: dict = {}) -> dict:
        post_url = f"{self.valves.API_ENDPOINT}{self.valves.POST_USER_INFO_PATH}"
        self.input_tokens = self.calculate_tokens(body["messages"], body["model"])
        response = requests.post(post_url, json={"user": __user__})
        response.raise_for_status()
        return body

    def outlet(
        self, body: dict, user: Optional[dict] = None, __user__: dict = {}
    ) -> dict:
        post_url = f"{self.valves.API_ENDPOINT}{self.valves.POST_RESULT_PATH}"
        assistant_message = None
        if "messages" in body and isinstance(body["messages"], list):
            for msg in reversed(body["messages"]):
                if msg.get("role") == "assistant":
                    assistant_message = msg
                    break
            
        output_tokens = self.calculate_tokens(assistant_message["content"], body["model"])

        request_data = {
            "user": __user__,
            "model": body["model"],
            "input_tokens": self.input_tokens,
            "output_tokens": output_tokens,
        }
        response = requests.post(post_url, json=request_data)
        response.raise_for_status()
        result = response.json()

        # 在消息末尾添加统计信息和用户信息
        if assistant_message and result.get("stats_text"):
            assistant_message["content"] += result.get("stats_text", "")

        return body
