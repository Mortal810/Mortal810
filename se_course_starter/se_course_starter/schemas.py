"""本地接口的输入约定：参数校验在产生推理费用之前执行。"""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class GenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    prompt: str = Field(min_length=1, max_length=1500)
    experiment: str = Field(default="v1", pattern=r"^[A-Za-z0-9_-]{1,24}$")
    parameter_mode: Literal["explicit", "minimal"] = "explicit"
    seed: int = Field(default=42, ge=0, le=4294967295, strict=True)
    width: Literal[512, 768, 1024] = 1024
    height: Literal[512, 768, 1024] = 768
    steps: int = Field(default=28, ge=10, le=40, strict=True)

    @field_validator("prompt")
    @classmethod
    def reject_secrets(cls, value: str) -> str:
        # 防止误把访问令牌粘贴到提示词并写入证据记录。
        if "hf_" in value or "Bearer " in value:
            raise ValueError("请勿在提示词中输入 API 密钥或 Authorization 内容")
        return value
