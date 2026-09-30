# 知页 Zhiye Local KB

一个面向个人电脑的中文本地知识库，带来源引用的资料问答界面，以及可以启动、关闭模型的桌面工作台。

把资料放进本地文件夹，导入索引，然后向资料提问。知页会组合向量检索、中文与英文关键词检索、重排序，最后调用你配置的模型生成带 `[S1]` 等来源编号的答案。点击编号即可核对原文。

这是从个人使用工具整理的 **v0.1 实验版**，不是生产级多用户平台。Windows 是主要使用环境；服务端可以在其他系统运行，桌面启动台需要 Python 的 Tk 支持。

## 包含什么

- 中文问答前端、知识库集合、原文引用侧栏。
- TXT、Markdown、代码、HTML、CSV、可提取文本的 PDF、DOCX、PPTX、XLSX 导入。
- SQLite 持久化、文件哈希增量更新、向量与 BM25 检索、RRF 合并及重排序。
- OpenAI-compatible 生成与嵌入接口、Cohere-compatible `/rerank` 接口。
- 桌面启动台：服务状态、单独启动和关闭、游戏模式释放已管理模型。
- OmniDocs 和 Hindsight 的可选集成说明。第三方项目不随本仓库分发或自动安装。

模型权重、私人资料、聊天记忆、API Key 均不包含在仓库里。

## Windows 快速开始

需要 Python 3.11（安装时包含 Tcl/Tk 与 Python Launcher）和可用的模型接口。若要启动 GGUF 模型，还需要自行安装 [llama.cpp](https://github.com/ggml-org/llama.cpp) 并准备兼容权重。

```powershell
git clone https://github.com/TIPSONG/zhiye-local-kb.git
cd zhiye-local-kb
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1
```

1. 编辑 `.env`，填写生成、嵌入、重排序接口。如果它们已经由其他软件启动，可跳过模型启动配置。
2. 编辑 `services.json`。模型条目默认禁用；把 `command` 中的程序和模型路径改成自己的实际路径，再设 `enabled: true`。不要求指定聊天模型品牌。
3. 双击 `launch.cmd`，点击“启动已启用服务”。模型加载可能需要等待，状态变为“已就绪”后打开知页网页。
4. 把资料复制进仓库的 `documents` 文件夹；网页点“导入资料”，输入 `documents` 或其中的文件路径。
5. 导入完成后提问，点击回答中的来源编号查看依据。

可先把 `examples/welcome.txt` 复制到 `documents` 测试。默认网页是 `http://127.0.0.1:8090/`。

只运行知识库后端，不使用启动台：

```powershell
.\.venv\Scripts\python.exe -m uvicorn rag_server:app --host 127.0.0.1 --port 8090
```

Linux 或 macOS 可使用 `python3 -m venv .venv`、激活环境、`pip install -r requirements.txt`，复制 `.env.example` 为 `.env` 后运行相同的 uvicorn 命令。Tk 是否可用取决于系统 Python 安装；本版未做这些平台的桌面人工验收。

## 配置接口

| 用途 | 默认地址 | 配置项 |
| --- | --- | --- |
| 生成 | `http://127.0.0.1:8080/v1` | `RAG_LLM_URL` |
| 嵌入 | `http://127.0.0.1:8081/v1` | `RAG_EMBED_URL` |
| 重排序 | `http://127.0.0.1:8082/v1` | `RAG_RERANK_URL` |

URL 填 Base URL，程序追加 `/chat/completions`、`/embeddings`、`/rerank`。如需认证，在 `.env` 填对应的 `RAG_LLM_API_KEY`、`RAG_EMBED_API_KEY`、`RAG_RERANK_API_KEY`。

BGE-M3 和 BGE-reranker-v2-m3 是配置示例，不自动下载。权重来源和许可证由使用者自行确认。生成接口默认发送 `chat_template_kwargs.enable_thinking=false`；若服务商不兼容该 llama.cpp 扩展，可在 `rag_server.py` 的请求参数中移除该字段。

嵌入模型更换后应使用新集合重新导入，即使新旧模型维度相同也不能混用已有向量。

## 关闭与游戏模式

“游戏模式”停止 `group: model` 的已登记进程。“关闭全部”先停止应用，再停止模型；不删除文件。

启动台只管理自己启动的进程，停止前核对 PID、创建时间、程序路径和参数。检测到外部模型接口时只显示状态，不会接管或结束它。外部程序应在原启动工具中关闭。

启动日志直接写进 `runtime` 文件夹，启动过程不会等待长期运行服务关闭标准输出。启动尚未完成时，关闭按钮仍可用，会取消剩余启动操作。关闭过程中不要重复打开多个启动台。

Windows 普通进程关闭可能中断当前请求。索引、文档转换和记忆写入完成后再关闭；数据库类外部服务必须配置自己的优雅停库命令，见 [第三方集成](docs/integrations.md)。

## 隐私与边界

- 默认只监听 `127.0.0.1`，没有用户账号或多用户权限。**不要映射端口到公网，也不要改成对外监听。**
- 只允许导入 `RAG_DOCUMENTS_DIR` 范围内的文件；不会扫描整块硬盘。支持格式与单文件大小检查不等于恶意文件沙箱，只导入可信文档。
- 默认模型接口都是本机地址。改成远程 API 后，问题和相关文档内容会发送给该服务；不能再视为完全离线。
- 前端将模型输出当作文本显示，不执行回答中的 HTML。文档内容仍可能包含提示注入，引用不能保证答案正确。
- 本地数据库与日志未加密，不要在公开 Issue 中上传个人数据库、完整日志或 `.env`。
- 默认 `.gitignore` 排除数据、权重、运行记录和私人配置；贡献前仍应检查暂存文件。

## 当前限制

检索会将一个集合的向量读入内存，适合个人规模数据，不适合百万级文档；没有后台任务队列、权限系统或文档版本管理。索引可能部分成功，网页会列出失败文件。删除原文件不会自动删除库内旧片段。

网页对话仅在当前页面保留，每次问题独立检索；刷新会清空对话，但保留数据库。扫描 PDF 需要先 OCR 或用 OmniDocs 解析。自带前端没有文档关系图；Hindsight 展示的是独立的 Agent 记忆关系图。

## 开发与验证

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

测试使用临时数据库和模拟模型返回，不需要下载权重，也不会调用真实云端模型。进程管理测试仅启动自己的短测试进程。GitHub Actions 在 Windows 与 Ubuntu、Python 3.11 上运行同一测试集。

欢迎通过 Issue 反馈可复现问题，通过 Pull Request 改进代码。请提供系统、Python 版本、脱敏错误和复现步骤，不要提交私人配置和资料。

## 许可证

本项目原创代码采用 [MIT License](LICENSE)。Python 依赖、模型权重和可选第三方项目各自遵循自己的许可证，不因接入知页而改变。项目没有附带模型，也不代表任何上游项目的官方发行版。
