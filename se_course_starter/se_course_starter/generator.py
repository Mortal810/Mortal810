"""Hugging Face 适配层 + 本地证据保存。生产入口没有模拟生成开关。"""
from __future__ import annotations
import hashlib
import json
import os
import re
import threading
import time
import uuid
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from typing import Any

import httpx
from huggingface_hub import InferenceClient
from huggingface_hub.errors import HfHubHTTPError, InferenceTimeoutError
from schemas import GenerateRequest

ROOT = Path(__file__).resolve().parent
MODEL_ID = "XLabs-AI/flux-RealismLora"
PROVIDER = "fal-ai"


class GenerationProblem(Exception):
    def __init__(self, detail: dict[str, Any], http_status: int = 502):
        super().__init__(detail["message"])
        self.detail = detail
        self.http_status = http_status


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def classify_error(exc: Exception) -> tuple[str, str, int | None]:
    response = getattr(exc, "response", None)
    code = getattr(response, "status_code", None)
    if isinstance(exc, (InferenceTimeoutError, httpx.TimeoutException, TimeoutError)):
        return "timeout", "上游请求超时；先检查用量记录，勿连续重试，超时不等于没有计费。", code
    messages = {
        401: "鉴权失败：检查 HF_TOKEN 是否有效或已撤销。",
        402: "上游要求付款：检查 Hugging Face 余额与计费设置。",
        403: "上游拒绝访问：检查推理权限、模型访问条件及账号限制。",
        404: "未找到上游模型或路由：重新检查模型页的服务商与 SDK 版本。",
        410: "上游接口已不可用：核对官方模型页和 SDK。",
        422: "上游不接受当前参数：可用简化模式排查，不要悄悄更换模型。",
        429: "上游限流或额度限制：查看账号用量，等待后再手动尝试。",
    }
    if code in messages:
        return "upstream_http", messages[code], code
    if code is not None and code >= 500:
        return "upstream_unavailable", "上游服务暂时异常；保存记录并稍后重试。", code
    if isinstance(exc, httpx.NetworkError):
        return "network", "网络连接失败：检查本机联网、DNS 和学校允许的网络设置。", code
    if isinstance(exc, ValueError):
        return "provider_or_parameters", "服务商映射或参数不兼容：运行 check_access.py，核对模型页。", code
    return "upstream_error", "生成未完成。检查异常类型、网络及账号设置；程序没有自动改用其他模型。", code


class GenerationService:
    def __init__(self, root: Path = ROOT):
        self.root = root
        self.output_dir = root / "outputs"
        self.log_dir = root / "logs"
        self.lock = threading.Lock()  # 本地单进程只允许一个推理任务，避免重复费用。
        self.log_lock = threading.Lock()

    def write_record(self, record: dict[str, Any]) -> None:
        self.log_dir.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, ensure_ascii=False)
        with self.log_lock:
            with (self.log_dir / "calls.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(line + "\n")
        print(line, flush=True)

    def generate(self, item: GenerateRequest) -> dict[str, Any]:
        token = os.getenv("HF_TOKEN", "").strip()
        if not token.startswith("hf_") or len(token) < 10:
            raise GenerationProblem({"message": "未配置有效格式的 HF_TOKEN；请编辑项目根目录 .env 并重启服务。", "category": "configuration"}, 503)
        if not self.lock.acquire(blocking=False):
            raise GenerationProblem({"message": "已有生成任务，请等待完成，勿重复提交。", "category": "busy"}, 409)
        try:
            return self._generate_locked(item, token)
        finally:
            self.lock.release()

    def _generate_locked(self, item: GenerateRequest, token: str) -> dict[str, Any]:
        local_id = uuid.uuid4().hex
        started = time.perf_counter()
        arguments: dict[str, Any] = {"model": MODEL_ID, "prompt": item.prompt}
        if item.parameter_mode == "explicit":
            arguments.update(width=item.width, height=item.height,
                             num_inference_steps=item.steps, guidance_scale=3.5,
                             seed=item.seed)
        record: dict[str, Any] = {
            "local_request_id": local_id,
            "started_at_utc": utc_now(),
            "experiment": item.experiment,
            "model": MODEL_ID,
            "provider": PROVIDER,
            "parameter_mode": item.parameter_mode,
            "requested_parameters": arguments.copy(),
            "sdk_version": version("huggingface_hub"),
            "upstream_http_status": None,
            "upstream_status_note": "SDK 的成功返回值为图像；未截获上游 HTTP 状态，不将本地 200 冒充上游状态。",
            "request_id_note": "local_request_id 由本程序生成，不是 Hugging Face 的官方请求编号。",
        }
        # 先验证本地目录可写，再调用可能计费的上游。
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            self.write_record({**record, "event": "generation_started"})
        except OSError as exc:
            raise GenerationProblem({"message": "本地输出或日志目录不可写，尚未发起推理请求。", "category": "local_storage"}, 500) from exc
        try:
            # hf_ 令牌经 Hugging Face 路由到 fal；不在浏览器中传递密钥。
            # timeout 是 SDK 的请求超时设置，不保证整个生成流程恰好在 180 秒终止。
            with InferenceClient(provider=PROVIDER, api_key=token, timeout=180) as client:
                image = client.text_to_image(**arguments)
        except Exception as exc:
            category, message, upstream_code = classify_error(exc)
            error_record = {
                **record, "event": "generation_failed", "finished_at_utc": utc_now(),
                "elapsed_seconds": round(time.perf_counter() - started, 3),
                "category": category, "message": message,
                "exception_type": type(exc).__name__, "upstream_http_status": upstream_code,
            }
            # 不输出原始异常字符串，避免 URL、令牌或服务响应中的敏感内容泄露。
            try:
                self.write_record(error_record)
            except OSError:
                pass
            raise GenerationProblem(error_record) from exc
        try:
            image_file = self.output_dir / f"{local_id}.png"
            image.save(image_file, format="PNG")
            record.update({
                "event": "generation_completed", "finished_at_utc": utc_now(),
                "elapsed_seconds": round(time.perf_counter() - started, 3),
                "image_file": image_file.name,
                "image_sha256": hashlib.sha256(image_file.read_bytes()).hexdigest(),
                "actual_size": {"width": image.width, "height": image.height},
                "image_url": f"/outputs/{local_id}.png",
                "record_url": f"/outputs/{local_id}.json",
            })
            (self.output_dir / f"{local_id}.json").write_text(
                json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
            self.write_record(record)
        except OSError as exc:
            raise GenerationProblem({"local_request_id": local_id, "category": "local_storage",
                                     "message": "上游已返回图像，但本地保存失败；可能已经计费，请先检查磁盘。"}, 500) from exc
        return record
