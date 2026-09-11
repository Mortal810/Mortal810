"""所有图像返回均为临时目录中的模拟数据；不访问 HF，不构成作业的真实调用证据。"""
import json
import httpx
import pytest
from PIL import Image
from fastapi.testclient import TestClient
import app as webapp
import generator

HEADERS = {"X-Demo-Request": "1"}
VALID = {"prompt": "A bicycle beside a wet campus walkway.", "experiment": "test"}


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("HF_TOKEN", "hf_TEST_ONLY_NOT_A_REAL_TOKEN")
    monkeypatch.setattr(webapp, "service", generator.GenerationService(tmp_path))
    class ForbiddenClient:
        def __init__(self, **kwargs):
            raise AssertionError("测试禁止真实外部推理调用")
    monkeypatch.setattr(generator, "InferenceClient", ForbiddenClient)
    with TestClient(webapp.app) as client:
        yield client


def test_home_and_config_hide_token(client):
    assert client.get("/").status_code == 200
    reply = client.get("/api/config")
    assert reply.json()["token_configured"]
    assert "hf_TEST" not in reply.text


@pytest.mark.parametrize("patch", [
    {"prompt": ""}, {"prompt": "  "}, {"prompt": "x"*1501},
    {"seed": -1}, {"seed": True}, {"steps": 100}, {"width": 600},
    {"experiment": "../../x"}, {"parameter_mode": "unknown"},
    {"prompt": "hf_DO_NOT_LEAK_THIS_TOKEN"}, {"extra": "unexpected"}
])
def test_invalid_inputs_do_not_reach_provider(client, patch):
    response = client.post("/api/generate", json={**VALID, **patch}, headers=HEADERS)
    assert response.status_code == 422
    assert "hf_DO_NOT_LEAK_THIS_TOKEN" not in response.text


def test_no_key(client, monkeypatch):
    monkeypatch.delenv("HF_TOKEN")
    assert client.post("/api/generate", json=VALID, headers=HEADERS).status_code == 503


def test_cross_origin_blocked(client):
    reply = client.post("/api/generate", json=VALID, headers={**HEADERS, "Origin": "https://other.invalid"})
    assert reply.status_code == 403


def test_header_required(client):
    assert client.post("/api/generate", json=VALID).status_code == 403


def test_non_json_blocked(client):
    assert client.post("/api/generate", content="prompt=x", headers={**HEADERS, "Content-Type": "text/plain"}).status_code == 415


def test_busy(client):
    webapp.service.lock.acquire()
    try:
        assert client.post("/api/generate", json=VALID, headers=HEADERS).status_code == 409
    finally:
        webapp.service.lock.release()


@pytest.mark.parametrize("mode", ["explicit", "minimal"])
def test_success_contract_with_mock_only(client, monkeypatch, mode):
    seen = {}
    class FakeClient:
        def __init__(self, **kwargs): seen.update(kwargs)
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def text_to_image(self, **kwargs):
            seen["arguments"] = kwargs
            return Image.new("RGB", (16, 12))  # 仅供自动化测试的纯色临时图。
    monkeypatch.setattr(generator, "InferenceClient", FakeClient)
    response = client.post("/api/generate", json={**VALID, "parameter_mode": mode}, headers=HEADERS)
    assert response.status_code == 200
    record = response.json()["record"]
    assert seen["provider"] == "fal-ai"
    assert seen["arguments"]["model"] == "XLabs-AI/flux-RealismLora"
    assert ("seed" in seen["arguments"]) == (mode == "explicit")
    assert record["upstream_http_status"] is None
    assert len(record["image_sha256"]) == 64
    assert client.get(record["image_url"]).headers["content-type"] == "image/png"
    assert client.get(record["record_url"]).json()["local_request_id"] == record["local_request_id"]
    assert "hf_TEST" not in (webapp.service.log_dir / "calls.jsonl").read_text(encoding="utf-8")
    assert not webapp.service.lock.locked()


def test_upstream_error_redacted(client, monkeypatch):
    class FailingClient:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def text_to_image(self, **kwargs):
            request = httpx.Request("POST", "https://example.invalid")
            response = httpx.Response(401, request=request)
            raise httpx.HTTPStatusError("hf_TEST_ONLY_NOT_A_REAL_TOKEN", request=request, response=response)
    monkeypatch.setattr(generator, "InferenceClient", FailingClient)
    response = client.post("/api/generate", json=VALID, headers=HEADERS)
    assert response.status_code == 502  # 本地502与上游401分开记录。
    assert response.json()["detail"]["upstream_http_status"] == 401
    assert "hf_TEST" not in response.text
    assert not webapp.service.lock.locked()


@pytest.mark.parametrize("path", ["/.env", "/outputs/.env", "/outputs/secret.py", "/outputs/"+"0"*32+".png"])
def test_private_or_missing_files_not_served(client, path):
    assert client.get(path).status_code == 404
