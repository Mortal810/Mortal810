"""课程演示应用。仅在本机运行；不具备公开付费服务的身份认证与配额管理。"""
from pathlib import Path
import os
import re
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from generator import GenerationProblem, GenerationService, MODEL_ID, PROVIDER, ROOT
from schemas import GenerateRequest

load_dotenv(ROOT / ".env", override=False)
app = FastAPI(title="Flux 写实图像生成 · 课程实践", version="1.0.0", docs_url=None, redoc_url=None)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])
app.mount("/assets", StaticFiles(directory=ROOT / "web"), name="assets")
service = GenerationService()


@app.middleware("http")
async def local_security(request: Request, call_next):
    if request.method == "POST":
        origin = request.headers.get("origin")
        local_origin = str(request.base_url).rstrip("/")
        if origin and origin != local_origin:
            return JSONResponse({"detail": {"message": "不接受跨站生成请求。"}}, status_code=403)
        if request.headers.get("content-type", "").split(";")[0] != "application/json":
            return JSONResponse({"detail": {"message": "请使用 application/json。"}}, status_code=415)
        if request.headers.get("x-demo-request") != "1":
            return JSONResponse({"detail": {"message": "缺少本地演示请求标识。"}}, status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; object-src 'none'; frame-ancestors 'none'"
    return response


@app.exception_handler(RequestValidationError)
async def input_error(request: Request, exc: RequestValidationError):
    # 默认错误对象可能回显输入；此处只返回字段和说明，不回显误粘贴的令牌。
    errors = [{"field": ".".join(str(v) for v in e["loc"]), "message": e["msg"]} for e in exc.errors()]
    return JSONResponse({"detail": {"message": "输入不符合要求，请检查提示词与参数。", "errors": errors}}, status_code=422)


@app.get("/")
def home():
    return FileResponse(ROOT / "web" / "index.html")


@app.get("/api/config")
def config():
    token = os.getenv("HF_TOKEN", "").strip()
    return {"model": MODEL_ID, "provider": PROVIDER,
            "token_configured": token.startswith("hf_") and len(token) >= 10,
            "note": "已配置不代表权限或余额验证成功；请运行 check_access.py。"}


@app.post("/api/generate")
def generate(item: GenerateRequest):
    try:
        return {"ok": True, "record": service.generate(item)}
    except GenerationProblem as exc:
        return JSONResponse({"ok": False, "detail": exc.detail}, status_code=exc.http_status)


@app.get("/outputs/{filename}")
def output(filename: str):
    # 只开放本次生成的 PNG/JSON，不开放项目根目录，更不会暴露 .env。
    if not re.fullmatch(r"[a-f0-9]{32}\.(png|json)", filename):
        raise HTTPException(status_code=404, detail="文件不存在")
    target = service.output_dir / filename
    if not target.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(target, media_type="image/png" if filename.endswith(".png") else "application/json")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
