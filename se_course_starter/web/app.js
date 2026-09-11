"use strict";
const byId = (id) => document.getElementById(id);
const form = byId("generate-form");
const button = byId("generate-button");
const promptBox = byId("prompt");
let inFlight = false;

function updateCount() { byId("count").textContent = `${promptBox.value.length} / 1500`; }
promptBox.addEventListener("input", updateCount);
function updateMode() {
  const minimal = byId("mode").value === "minimal";
  ["seed", "steps", "width", "height"].forEach(id => { byId(id).disabled = minimal; });
  byId("mode-note").textContent = minimal
    ? "简化模式只提交 model 与 prompt，未固定 seed；不适合声称控制变量比较。"
    : "固定 seed 便于比较；服务商升级等因素仍可能影响复现。";
}
byId("mode").addEventListener("change", updateMode);

fetch("/api/config").then(r => r.json()).then(data => {
  byId("config").textContent = data.token_configured
    ? "Token 已配置 · 权限与余额待实际验证" : "Token 未配置 · 请编辑 .env 后重启";
}).catch(() => { byId("config").textContent = "本地服务连接失败"; });

function addHistory(experiment, result, seconds, localId) {
  const row = document.createElement("tr");
  [new Date().toLocaleTimeString(), experiment, result, seconds, localId].forEach(value => {
    const cell = document.createElement("td");
    cell.textContent = String(value); // 不用 innerHTML 处理提示词或上游信息。
    row.appendChild(cell);
  });
  byId("history-body").prepend(row);
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (inFlight) return;
  const prompt = promptBox.value.trim();
  if (!prompt) {
    byId("status").textContent = "请填写非空提示词。";
    byId("status").className = "error";
    return;
  }
  if (prompt.includes("hf_") || prompt.includes("Bearer ")) {
    byId("status").textContent = "提示词中疑似包含密钥，请删除后重试。";
    byId("status").className = "error";
    return;
  }
  const payload = {
    prompt, experiment: byId("experiment").value,
    parameter_mode: byId("mode").value,
    seed: Number(byId("seed").value), steps: Number(byId("steps").value),
    width: Number(byId("width").value), height: Number(byId("height").value)
  };
  inFlight = true;
  button.disabled = true;
  button.textContent = "生成中，请勿重复提交…";
  byId("status").className = "";
  byId("status").textContent = "已向本地后端提交，等待上游返回…";
  // 清除旧图，避免失败时旧结果被误认成本次成功。
  byId("result-image").hidden = true;
  byId("result-image").removeAttribute("src");
  byId("downloads").hidden = true;
  byId("result-meta").textContent = "";
  byId("empty").hidden = false;
  const started = performance.now();
  const timer = setInterval(() => {
    byId("status").textContent = `正在等待上游 · 已经过 ${Math.floor((performance.now() - started) / 1000)} 秒（不是完成进度）`;
  }, 1000);
  let status = "未取得响应";
  try {
    const response = await fetch("/api/generate", {
      method: "POST", headers: {"Content-Type": "application/json", "X-Demo-Request": "1"},
      body: JSON.stringify(payload)
    });
    clearInterval(timer);
    status = response.status;
    const data = await response.json();
    byId("raw-record").textContent = JSON.stringify(data, null, 2);
    if (!response.ok || !data.ok) {
      const detail = data.detail || {};
      const error = new Error(detail.message || "请求未完成，请查看本地控制台。");
      error.localId = detail.local_request_id;
      throw error;
    }
    const record = data.record;
    byId("result-image").src = record.image_url;
    byId("result-image").hidden = false;
    byId("empty").hidden = true;
    byId("downloads").hidden = false;
    byId("image-link").href = record.image_url;
    byId("image-link").download = `${record.experiment}-${record.local_request_id}.png`;
    byId("record-link").href = record.record_url;
    byId("record-link").download = `${record.experiment}-${record.local_request_id}.json`;
    byId("status").textContent = `生成完成 · 本地 HTTP ${status} · 后端总耗时 ${record.elapsed_seconds} 秒`;
    const submittedSeed = record.requested_parameters.seed ?? "未提交（服务商默认）";
    byId("result-meta").textContent = `${record.model} | ${record.provider} | seed: ${submittedSeed} | 实际 ${record.actual_size.width} × ${record.actual_size.height} | 本地请求编号：${record.local_request_id}`;
    addHistory(record.experiment, `成功 / ${status}`, `${record.elapsed_seconds}s`, record.local_request_id);
  } catch (error) {
    clearInterval(timer);
    byId("status").className = "error";
    byId("status").textContent = error.message + " 请勿连续重试，先确认账号用量。";
    addHistory(payload.experiment, `失败 / ${status}`, `${((performance.now()-started)/1000).toFixed(1)}s`, error.localId || "—");
  } finally {
    clearInterval(timer);
    inFlight = false;
    button.disabled = false;
    button.textContent = "生成图像 ↗";
  }
});
