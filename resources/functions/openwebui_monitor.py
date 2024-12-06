from typing import Optional, Callable, Any, Awaitable
from pydantic import Field, BaseModel
import requests
import time
from open_webui.utils.misc import get_last_assistant_message


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
        show_tokens: bool = Field(default=True, description="Display token usage")
        show_tokens_per_sec: bool = Field(
            default=True, description="Display tokens per second"
        )

    def __init__(self):
        self.type = "filter"
        self.name = "OpenWebUI Monitor"
        self.valves = self.Valves()
        self.outage = False
        self.start_time = None

    def _prepare_user_dict(self, __user__: dict) -> dict:
        """将 __user__ 对象转换为可序列化的字典"""
        user_dict = dict(__user__)  # 创建副本以避免修改原始对象
        
        # 如果存在 valves 且是 BaseModel 的实例，将其转换为字典
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
            
            # 使用 _prepare_user_dict 处理 __user__ 对象
            user_dict = self._prepare_user_dict(__user__)
            
            response = requests.post(
                post_url, headers=headers, json={"user": user_dict, "body": body}
            )

            if response.status_code == 401:
                return body

            response.raise_for_status()
            response_data = response.json()

            if not response_data.get("success"):
                error_msg = response_data.get("error", "未知错误")
                error_type = response_data.get("error_type", "UNKNOWN_ERROR")
                raise Exception(f"请求失败: [{error_type}] {error_msg}")

            self.outage = response_data.get("balance", 0) <= 0
            if self.outage:
                raise Exception(f"余额不足: 当前余额 `{response_data['balance']:.4f}`")

            return body

        except requests.exceptions.RequestException as e:
            if (
                isinstance(e, requests.exceptions.HTTPError)
                and e.response.status_code == 401
            ):
                return body
            raise Exception(f"网络请求失败: {str(e)}")
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
            
            # 使用 _prepare_user_dict 处理 __user__ 对象
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

            # 获取统计数据
            input_tokens = result["inputTokens"]
            output_tokens = result["outputTokens"]
            total_cost = result["totalCost"]
            new_balance = result["newBalance"]

            # 构建状态栏显示的统计信息
            stats_array = []

            if self.valves.show_cost:
                stats_array.append(f"费用: ${total_cost:.4f}")
            if self.valves.show_balance:
                stats_array.append(f"余额: ${new_balance:.4f}")
            if self.valves.show_tokens:
                stats_array.append(f"Token: {input_tokens}+{output_tokens}")

            # 计算耗时（如果有start_time）
            if self.start_time:
                elapsed_time = time.time() - self.start_time
                stats_array.append(f"耗时: {elapsed_time:.2f}s")
                
                # 计算每秒输出速度
                if self.valves.show_tokens_per_sec:
                    stats_array.append(f"{(output_tokens/elapsed_time):.2f} T/s")

            stats = " | ".join(stat for stat in stats_array)

            # 发送状态更新
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
