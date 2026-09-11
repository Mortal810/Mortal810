# 软件工程课程实践起步包

用途：Hugging Face 指定模型 API → 本机 Python 后端 → 交互网页；另附 GitHub 个人主页与博客园 Markdown 模板。

**这不是已经完成的个人作业。** 需要你填写真实个人内容、配置自己的账号，在本机实际调用并截图，再发布博文和完成课程提交。此包没有令牌、没有真实生成结果，也没有伪造的成功截图。

## 1. 先确认路径与平台

推荐先完成最小可交付：真实调用 1 次 → 前端生成并记录修改 → 个人资料 README → 博客发布。预算允许再增加第三版提示词；有余力再选 Pages。

三个位置的区别：edu.cnblogs.com 是教育/班级入口；个人公开博文在 www.cnblogs.com；博客编辑后台通常从 i.cnblogs.com 进入。登录后界面若不同，以“设置默认编辑器 / Markdown / 添加随笔”的功能名称寻找。

本次查阅的指定模型页列出 fal。代码使用 provider="fal-ai"，model="XLabs-AI/flux-RealismLora"，不会自动更换成基础模型。服务可用性可能变化，运行 check_access.py 并再次查看模型页。

## 2. 账号与密钥

注册 Hugging Face 并完成邮箱验证；在 Settings → Access Tokens 新建 fine-grained 令牌，开启 Make calls to Inference Providers。使用最小权限，不需要为了生成图像开启所有仓库写权限。

查看 Inference Providers / Billing 用量与余额。免费额度不是无限调用保证；费用依账号和服务商实际页面。默认 Hugging Face 路由方案通常不需要额外注册 fal 账号。不要混用自己的服务商密钥后仍宣称账单由 HF 统一结算。

将 .env.example 复制为 .env，在本地编辑 HF_TOKEN。不要在前端、README、截图、Git 提交、聊天消息中放真实密钥。若误提交，先在平台撤销并更换，不能只删当前文件而忽略 Git 历史。

## 3. Windows 从零运行

安装 Python 3.11 或更新的兼容版本；以下用 Windows PowerShell 演示。解压到 D:\se_course_starter（路径可自定）。在资源管理器进入文件夹，地址栏输入 powershell 打开终端，确认当前目录有 app.py。

```powershell
py --version
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
```

把 .env 中的文字替换为你自己的 hf_ 令牌，保存并关闭记事本。文件名必须是 .env，不是 .env.txt。若以前已经配过 .env，不要再次复制覆盖。环境变量 HF_TOKEN 优先于 .env；修改后重启服务。

命令直接使用虚拟环境解释器，不需要 Activate.ps1，不必修改系统 PowerShell 执行策略。若电脑没有 py 命令，用已安装的 python 创建虚拟环境；不要把两套 Python 的 pip 混在一起。

```powershell
.\.venv\Scripts\python.exe check_access.py
.\.venv\Scripts\python.exe -m pytest -q
```

check_access 只读取身份与模型映射，不生成图片，不证明推理权限、额度与服务整体都正常。pytest 使用模拟返回，不访问外部 API，不替代真实成功记录。

### 先跑命令行调用

打开 prompts/my_prompt.txt，把全部内容换成自己的提示词（UTF-8）。只想验证链路时，也可明确选择示范文件，但必须自己运行。

```powershell
.\.venv\Scripts\python.exe minimal_api.py --prompt-file prompts/my_prompt.txt --experiment v1 --seed 42
```

示范命令（可能产生费用，且题材只是示范）：

```powershell
.\.venv\Scripts\python.exe minimal_api.py --prompt-file prompts/example_v1.txt --experiment v1 --seed 42
```

成功后看 outputs/<本地编号>.png 与同名 .json，并截取真实终端记录。没有看到成功，不能拿模板结果替代。

### 启动交互网页

```powershell
.\.venv\Scripts\python.exe app.py
```

浏览器访问 http://127.0.0.1:8000。不要双击 web/index.html 或用 VS Code Live Server：此网页需要本项目的后端与同源接口。

输入提示词、实验编号及参数，点击生成。成功后可下载 PNG 与 JSON，网页显示本地请求编号、耗时、模型和实际尺寸。控制台与 logs/calls.jsonl 保存开始、失败或完成记录。每次修改提示词后更新 v1/v2/v3 编号；建议固定其他已提交参数。无需把刚在命令行成功的 v1 又生成一遍，前端可从修改版 v2 开始，以控制费用。

终端需保持打开；结束按 Ctrl+C。服务只监听本机，不要改成 0.0.0.0 公开借用自己的收费密钥。

若 8000 端口被占用：

```powershell
.\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8001
```

然后访问 http://127.0.0.1:8001。不要开多个 worker，否则当前内存锁不能保证跨进程只执行一个请求。

### Linux / macOS

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
# 用编辑器填写 .env
.venv/bin/python check_access.py
.venv/bin/python -m pytest -q
.venv/bin/python minimal_api.py --prompt-file prompts/my_prompt.txt --experiment v1
.venv/bin/python app.py
```

## 4. 代码结构与接口

| 文件 | 作用 |
| --- | --- |
| schemas.py | 约定提示词和参数，提前拒绝不合法输入 |
| generator.py | 官方 SDK 调用、异常分类、图片和记录保存 |
| minimal_api.py | 不依赖网页的首次真实调用入口 |
| check_access.py | 身份和模型映射检查 |
| app.py | 本地 HTTP 接口、页面和结果文件读取 |
| web/index.html / style.css / app.js | 前端表单、样式和交互 |
| tests/test_app.py | 24 项本地测试，全部外部生成都被模拟或阻止 |
| templates/blog_template.md | 可复制到博客园的完整待填写骨架 |
| templates/profile_README.md | 同名公开仓库个人介绍 |
| templates/ai_guide.md | 本次对话生成的简要学习指南与分析空位 |
| homepage/index.html | 可选 Pages 静态个人主页 |
| tools/count_loc.py | 辅助统计源码行数，不判定代码作者 |

本地接口：GET /api/config 只返回模型、服务商与是否存在格式正确的密钥；POST /api/generate 需要 application/json 与 X-Demo-Request: 1；GET /outputs/<32位本地编号>.png 或 .json 读取已生成结果。

```json
{"prompt":"由你填写场景","experiment":"v1","parameter_mode":"explicit","seed":42,"width":1024,"height":768,"steps":28}
```

收到正常本地响应时，数据在 record 中，包括 model/provider/requested_parameters/local_request_id/image_url/record_url/elapsed_seconds/actual_size。

**两层状态要分清：** 浏览器 Network 的 200 来自本地后端。SDK 成功直接返回 PIL 图像，本程序不捕获上游成功 HTTP 状态，也不捏造官方请求编号。发生上游错误且异常含状态码时，会另记录 upstream_http_status。哈希只能检查图片文件是否一致，并不是平台真实性证书。

“后端总耗时”含网络请求、可能等待和保存，不是模型纯推理耗时。SDK timeout=180 是请求超时配置，不是整个任务绝对截止时间。超时后先看平台用量，不要自动循环重试。

## 5. 参数兼容性和常见故障

先尝试默认明确参数；若上游提示参数不兼容，可在网页切到简化参数，或用：

```powershell
.\.venv\Scripts\python.exe minimal_api.py --prompt-file prompts/my_prompt.txt --experiment diagnostic --minimal
```

简化模式只提交 model/prompt，没有提交 seed、尺寸和步数。不能把这类记录写成固定条件实验。排查后再按模型当前文档恢复明确参数。

| 现象 | 检查顺序 |
| --- | --- |
| 401 | Token 是否正确、过期或已撤销；不要把令牌发给别人排查 |
| 403 | 推理权限、模型访问条件和账号限制；以实际响应为准 |
| 402 / 用量不足 | 检查余额与计费；先估计预算，不无限重试 |
| 404 / 410 / 模型服务商不存在 | 模型 ID 大小写、模型页当前服务商、SDK 版本；不是给模型换个名字 |
| 422 | 区分本地参数校验与上游参数不支持；必要时简化模式排查 |
| 429 | 限流或额度限制，查看账户用量和上游说明 |
| 502 / 503 / 超时 | 先分清本地/上游状态，检查服务与网络；可能已有计费 |
| 浏览器显示空白或接口找不到 | 用后端地址访问，不要 file:// 或另一个 Live Server 端口 |
| 缺少模块 | 确认使用 .venv 的 Python 并安装 requirements.txt |

如果指定模型当天完全没有可用服务，保留模型页与失败记录并向教师/助教确认部署或替代方案；不能偷偷换成 FLUX.1-schnell/FLUX.1-dev 并标成指定 LoRA。自部署模型与原始云端 API 方案的工作量不同，不建议临近截止盲目付费部署 GPU。

## 6. 个人主页：二选一即可

### 方案 A：同名仓库 README

打开自己的 GitHub 账号，记下用户名（不是显示昵称）。新建名称与用户名完全一致的公开仓库，勾选添加 README。在根目录 README.md 粘贴 templates/profile_README.md 并填写。保存提交后访问账号主页检查。

内容必须包括：个人介绍/兴趣/经历、作品/技能/专业实践、自我评估与技术兴趣、最想学的知识、未来三年规划。不要只在博客里写规划而在主页省略。

完善头像、简介和博客链接；项目展示优先给出源码、本人贡献与完成状态，而不是堆语言徽章。可以置顶真正完成的作品。

### 方案 B：GitHub Pages

新建公开仓库 USERNAME.github.io（将 USERNAME 替换为自己的真实 GitHub 用户名）。将 homepage/index.html 上传到仓库根目录，也可同时放入 .nojekyll。编辑 HTML 中全部【待填写】、标题、页面描述与链接；不用 HTML 构建工具。

进入仓库 Settings → Pages → Build and deployment → Source: Deploy from a branch → Branch: main → /(root) → Save。等待部署完成，访问 https://USERNAME.github.io/。更新可能需要几分钟，以实际部署状态为准。查看 Actions 定位构建失败。

可使用 GitHub 内置 Create new file，把文件名填 index.html 并粘贴 HTML；或 Add file → Upload files 上传现成文件。避免把整个 homepage 文件夹嵌套到发布目录导致根路径没有 index.html。

GitHub Pages 只托管静态网页，不能运行本包 Python 后端。主页可以放作品链接、截图和复现说明；不必在线公开图像生成器，不买域名也能完成任务。

## 7. 博客园 Markdown 发布

在博客园完成注册、开通博客和课程班级关联，按教师要求填写班级身份信息。开通/审核规则、截止时间和提交按钮以你登录后的页面为准。

进入后台 → 设置默认编辑器 → Markdown → 保存 → 添加随笔。不能只在富文本编辑器里粘贴 Markdown 就当作切换完成。

把 templates/blog_template.md 的内容复制到 Markdown 编辑区。页面标题单独填写；正文最前面保留四行课程信息表。不要把整篇文章再包在一个 markdown 代码围栏中。

代码块用三反引号并标注 python/javascript/powershell；图片通过后台上传功能插入，得到在线图片地址。粘贴本地 C:\路径或 localhost 图片路径，别人无法看到。相对路径可用于仓库文档，但复制到博客园需要重新上传并替换。

先预览表格、图片、代码和链接。文章接近完成时截取后台的文章标题与 Markdown 内容，然后上传这张截图，插入“Markdown 编辑”章节，再最终保存发布。截图里看不到后来新增的那张截图不影响证明编辑方式，不需要递归截图。

用未登录窗口打开公开博文，检查主页链接、仓库链接与图片。返回 edu.cnblogs.com 对应作业页面，按要求提交公开博文 URL 并确认成功；不要提交后台编辑 URL。保存本地 Markdown 与提交确认记录。

## 8. 代码量与个人内容

把可统计的本人课程代码整理到目录，排除依赖、第三方模板、重复备份以及无权计入的团队代码。工具统计物理行和非空行（均含注释），按完整文件内容去重，不知道哪些代码属于你或 AI。

```powershell
.\.venv\Scripts\python.exe tools/count_loc.py "D:\my-own-code" --output docs/my_loc.json
```

以上 D:\my-own-code 必须改为自己的实际代码目录。博客中说明统计日期、项目范围、口径与误差。当前存量不等于历史累计，Git 提交次数或 AI token 用量也不能直接换算成代码行数。模板代码不应直接冒充本人的历史练习量。

本学期目标由自己制定：已有可核对代码量 + 计划新增，并写出对应任务。技术评价用“能独立完成什么—证据—尚不能完成什么—下一步”，不编造熟练度、奖项或经历。

## 9. Git 提交建议

初学者可先用 GitHub 的网页创建个人 README。网页上传项目时也要手动核对文件清单，不要因为有 .gitignore 就把包含 .env 或 .venv 的整个目录拖入上传区。公开证据应先检查隐私，再挑选复制到 evidence/。实践项目建议用 Git 提交，确保 .gitignore 存在，再操作：

```powershell
git init
git add .
git diff --cached --name-only
git diff --cached
git commit -m "feat: add local Flux demo and documentation"
git branch -M main
git remote add origin https://github.com/USERNAME/se-practice-01.git
git push -u origin main
```

远程仓库先创建为空，不另加 README，避免与本地初始化冲突。Git 首次使用须按自己的信息配置 user.name / user.email，使用 GitHub 支持的浏览器/凭据管理器或 SSH 认证，不把 Token 嵌进远程 URL。命令中的 USERNAME 必须替换。每做完一个真实功能再提交，不伪造开发历史。

选中的公开结果放 evidence/ 并检查后再提交。不要只传压缩包；仓库中应能直接阅读源码与运行说明。

## 10. 测试状态与限制

起步包作者环境已执行 24 项测试并全部通过。覆盖：首页配置、非法输入、无密钥、跨站请求、重复任务、成功返回合同、上游失败脱敏、文件访问限制。

**测试是本地模拟测试，不是实际 Hugging Face 生成。** 未使用你的账号，未验证你的网络、余额或平台权限，也未替你创建 GitHub/博客园账户。依赖在本地安装后可用 pip freeze 记录；所有真实截图由你运行后获得。

```powershell
.\.venv\Scripts\python.exe -m pip freeze > requirements-local.txt
```

更多：docs/evidence_checklist.md、docs/prompt_lab.md、docs/sources.md。
