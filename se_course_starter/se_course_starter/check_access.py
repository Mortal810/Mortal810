"""只验证账号与模型服务映射，不生成图片，不证明推理成功。"""
import json
import os
from pathlib import Path
from dataclasses import asdict, is_dataclass
from dotenv import load_dotenv
from huggingface_hub import HfApi
from generator import MODEL_ID, PROVIDER, classify_error


def main() -> int:
    load_dotenv(Path(__file__).resolve().parent / ".env")
    token = os.getenv("HF_TOKEN", "").strip()
    if not token.startswith("hf_") or len(token) < 10:
        print("请先复制 .env.example 为 .env，并填写自己的 Hugging Face Token。")
        return 1
    try:
        api = HfApi(token=token)
        me = api.whoami()
        print(json.dumps({"check": "identity", "username": me.get("name"), "ok": True}, ensure_ascii=False))
        model = api.model_info(MODEL_ID, expand=["inferenceProviderMapping"], timeout=30)
        mappings = model.inference_provider_mapping or {}
        for name, info in mappings.items():
            print(json.dumps({"provider": name, "mapping": asdict(info) if is_dataclass(info) else vars(info)}, ensure_ascii=False))
        if PROVIDER not in mappings:
            print("当前映射中未发现 fal-ai。请核对模型页，不要把其他模型的结果当成指定模型。")
            return 2
        print("账号和模型映射检查完成；仍需真实生成确认推理权限、余额和服务可用性。")
        return 0
    except Exception as exc:
        category, message, status = classify_error(exc)
        print(json.dumps({"ok": False, "exception_type": type(exc).__name__, "category": category,
                          "http_status": status, "message": message}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
