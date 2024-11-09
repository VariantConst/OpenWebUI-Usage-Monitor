from typing import Optional
from pydantic import Field, BaseModel
import requests
import json


class Filter:
    class Valves(BaseModel):
        priority: int = Field(
            default=0, description="Priority level for the filter operations."
        )
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
        MODEL_NAME: str = Field(
            default="default-model",
            description="The model name used in the OpenWebUI session.",
        )

    def __init__(self):
        self.type = "filter"
        self.name = "OpenWebUI Filter"
        self.valves = self.Valves()
        self.session_id = None

    def inlet(self, body: dict, user: Optional[dict] = None, __user__: dict = {}) -> dict:
        post_url = f"{self.valves.API_ENDPOINT}{self.valves.POST_USER_INFO_PATH}"
        try:
            request_data = {"body": body, "user": __user__}
            response = requests.post(post_url, json=request_data)
            response.raise_for_status()
            self.session_id = body.get("metadata", {}).get("chat_id")
        except requests.RequestException as e:
            if "messages" in body and body["messages"]:
                last_msg = body["messages"][-1]
                if last_msg["role"] == "user":
                    last_msg["content"] += f"\n\n[Debug: API Error - {str(e)}]"
        return body

    def outlet(
        self, body: dict, user: Optional[dict] = None, __user__: dict = {}
    ) -> dict:
        if self.session_id:
            post_url = f"{self.valves.API_ENDPOINT}{self.valves.POST_RESULT_PATH}"
            try:
                assistant_message = None
                if "messages" in body and isinstance(body["messages"], list):
                    for msg in reversed(body["messages"]):
                        if msg.get("role") == "assistant":
                            assistant_message = msg
                            break

                request_data = {
                    "session_id": self.session_id,
                    "body": body,
                    "user": __user__,
                    "llm_response": (
                        assistant_message["content"] if assistant_message else ""
                    ),
                }
                response = requests.post(post_url, json=request_data)
                response.raise_for_status()
                result = response.json()

                # 在消息末尾添加统计信息和用户信息
                if assistant_message and result.get("llm_response"):
                    assistant_message["content"] = (
                        result["llm_response"]
                        + result.get("stats_text", "")
                    )

            except requests.RequestException as e:
                error_message = str(e)
                print(f"Error posting result to API: {error_message}")
                if assistant_message:
                    assistant_message[
                        "content"
                    ] += f"\n\n[Debug: API Error - {error_message}]"

        return body
