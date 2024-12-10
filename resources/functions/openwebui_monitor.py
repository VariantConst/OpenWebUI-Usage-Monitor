from typing import Optional, Callable, Any, Awaitable
from pydantic import Field, BaseModel
import requests
import time


TRANSLATIONS = {
    "en": {
        "network_request_failed": "Network request failed: {error}",
        "request_failed": "Request failed: [{error_type}] {error_msg}",
        "insufficient_balance": "Insufficient balance: Current balance `{balance:.4f}`",
        "unknown_error": "Unknown error",
        "api_key_invalid": "API key validation failed",
        "cost": "Cost: ${cost:.4f}",
        "balance": "Balance: ${balance:.4f}",
        "tokens": "Tokens: {input}+{output}",
        "time_spent": "Time: {time:.2f}s",
        "tokens_per_sec": "{tokens_per_sec:.2f} T/s"
    },
    "zh": {
        "network_request_failed": "网络请求失败: {error}",
        "request_failed": "请求失败: [{error_type}] {error_msg}",
        "insufficient_balance": "余额不足: 当前余额 `{balance:.4f}`",
        "unknown_error": "未知错误",
        "api_key_invalid": "API密钥验证失败",
        "cost": "费用: ¥{cost:.4f}",
        "balance": "余额: ¥{balance:.4f}",
        "tokens": "Token: {input}+{output}",
        "time_spent": "耗时: {time:.2f}s",
        "tokens_per_sec": "{tokens_per_sec:.2f} T/s"
    }
}

class Filter:
    class Valves(BaseModel):
        API_ENDPOINT: str = Field(
            default="", description="The base URL for the API endpoint."
        )
        API_KEY: str = Field(default="", description="API key for authentication.")
        priority: int = Field(
            default=5, description="Priority level for the filter operations."
        )
        show_cost: bool = Field(default=True, description="Display cost information")
        show_balance: bool = Field(
            default=True, description="Display balance information"
        )
        show_spend_time: bool = Field(default=True, description="Display spend time")
        show_tokens: bool = Field(default=True, description="Display token usage")
        show_tokens_per_sec: bool = Field(
            default=True, description="Display tokens per second"
        )
        language: str = Field(
            default="en", 
            description="Language for messages (en/zh)"
        )

    def __init__(self):
        self.type = "filter"
        self.name = "OpenWebUI Monitor"
        self.valves = self.Valves()
        self.outage = False
        self.start_time = None
        self.translations = TRANSLATIONS

    def get_text(self, key: str, **kwargs) -> str:
        """获取指定语言的文本"""
        lang = self.valves.language
        if lang not in self.translations:
            lang = "en"
        text = self.translations[lang].get(key, self.translations["en"][key])
        return text.format(**kwargs) if kwargs else text

    def _prepare_user_dict(self, __user__: dict) -> dict:
        """将 __user__ 对象转换为可序列化的字典"""
        user_dict = dict(__user__)
        if "valves" in user_dict and hasattr(user_dict["valves"], "model_dump"):
            user_dict["valves"] = user_dict["valves"].model_dump()
        
        return user_dict

    def inlet(
        self, body: dict, user: Optional[dict] = None, __user__: dict = {}
    ) -> dict:
        self.start_time = time.time()

        try:
            post_url = f"{self.valves.API_ENDPOINT}/api/v1/inlet"
            headers = {"Authorization": f"Bearer {self.valves.API_KEY}"}
            
            user_dict = self._prepare_user_dict(__user__)
            
            response = requests.post(
                post_url, headers=headers, json={"user": user_dict, "body": body}
            )

            if response.status_code == 401:
                return body

            response.raise_for_status()
            response_data = response.json()

            if not response_data.get("success"):
                error_msg = response_data.get("error", self.get_text("unknown_error"))
                error_type = response_data.get("error_type", "UNKNOWN_ERROR")
                raise Exception(self.get_text("request_failed", error_type=error_type, error_msg=error_msg))

            self.outage = response_data.get("balance", 0) <= 0
            if self.outage:
                raise Exception(self.get_text("insufficient_balance", balance=response_data['balance']))

            return body

        except requests.exceptions.RequestException as e:
            if (
                isinstance(e, requests.exceptions.HTTPError)
                and e.response.status_code == 401
            ):
                return body
            raise Exception(self.get_text("network_request_failed", error=str(e)))
        except Exception as e:
            raise Exception(f"处理请求时发生错误: {str(e)}")

    async def outlet(
        self,
        body: dict,
        user: Optional[dict] = None,
        __user__: dict = {},
        __event_emitter__: Callable[[Any], Awaitable[None]] = None,
    ) -> dict:
        if self.outage:
            return body

        try:
            post_url = f"{self.valves.API_ENDPOINT}/api/v1/outlet"
            headers = {"Authorization": f"Bearer {self.valves.API_KEY}"}
            
            user_dict = self._prepare_user_dict(__user__)
            
            request_data = {
                "user": user_dict,
                "body": body,
            }

            response = requests.post(post_url, headers=headers, json=request_data)

            if response.status_code == 401:
                if __event_emitter__:
                    await __event_emitter__(
                        {
                            "type": "status",
                            "data": {
                                "description": "API密钥验证失败",
                                "done": True,
                            },
                        }
                    )
                return body

            response.raise_for_status()
            result = response.json()

            if not result.get("success"):
                error_msg = result.get("error", "未知错误")
                error_type = result.get("error_type", "UNKNOWN_ERROR")
                raise Exception(f"请求失败: [{error_type}] {error_msg}")

            input_tokens = result["inputTokens"]
            output_tokens = result["outputTokens"]
            total_cost = result["totalCost"]
            new_balance = result["newBalance"]

            stats_array = []

            if self.valves.show_cost:
                stats_array.append(self.get_text("cost", cost=total_cost))
            if self.valves.show_balance:
                stats_array.append(self.get_text("balance", balance=new_balance))
            if self.valves.show_tokens:
                stats_array.append(self.get_text("tokens", input=input_tokens, output=output_tokens))

            if self.start_time and self.valves.show_spend_time:
                elapsed_time = time.time() - self.start_time
                stats_array.append(self.get_text("time_spent", time=elapsed_time))
                
                if self.valves.show_tokens_per_sec:
                    stats_array.append(self.get_text("tokens_per_sec", tokens_per_sec=output_tokens/elapsed_time))

            stats = " | ".join(stat for stat in stats_array)

            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "description": stats,
                            "done": True,
                        },
                    }
                )

            return body

        except requests.exceptions.RequestException as e:
            if (
                isinstance(e, requests.exceptions.HTTPError)
                and e.response.status_code == 401
            ):
                if __event_emitter__:
                    await __event_emitter__(
                        {
                            "type": "status",
                            "data": {
                                "description": "API密钥验证失败",
                                "done": True,
                            },
                        }
                    )
                return body
            raise Exception(f"网络请求失败: {str(e)}")
        except Exception as e:
            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "description": f"错误: {str(e)}",
                            "done": True,
                        },
                    }
                )
            raise Exception(f"处理请求时发生错误: {str(e)}")
