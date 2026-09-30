# 可选文档解析和 Agent 记忆

知页核心资料库不依赖以下项目。它们用于不同任务，数据不会自动互相同步。

## OmniDocs 文档解析

[OmniDocs](https://github.com/adithya-s-k/Omnidocs) 是文档解析项目，不是本仓库的问答前端。请按上游说明在独立 Python 环境安装，将扫描文档或图片转换为 Markdown，再把产物放进知页 `documents` 目录导入。

本版没有封装其 Python API 或自动安装模型，避免把上游依赖和不同模型许可证混入核心环境。

## OmniDocs-RAG 独立资料库

[OmniDocs-RAG](https://github.com/ElvinBayramov/OmniDocs-RAG) 是另一套独立资料库。本仓库不复制其源码，也不使用它的 Chroma 数据库。

安装后，可在 `services.json` 中的 `omnidocs-rag` 条目填写绝对启动程序和脚本路径、工作目录 `cwd`、就绪地址与网页地址，再启用。不要导入别人提供的未知启动命令：这些命令会以你的本机用户身份执行。

## Hindsight Agent 记忆

[Hindsight](https://github.com/vectorize-io/hindsight) 提供长期记忆，与文档资料库的作用不同。请按上游安装、数据库和 MCP 文档部署，再给自己的 Agent 客户端接入相应记忆库。

模板条目只提供状态与页面地址示例，不会安装 Hindsight 或为客户端改配置。若 API 和网页是独立进程，应配置两个服务条目，分别填 `command`。关系图、自动记忆策略、MCP 地址以你的上游版本和实际部署为准。

有数据库的服务应显式配置 `stop_command` 为参数数组，例如调用你自己的停库脚本。该脚本应先停止接收新任务、等待写入，再执行数据库正常关闭。启动台会等待这个命令，失败时不会继续强制杀掉该服务。**不要直接把 PostgreSQL 启动进程当普通模型服务管理。**

独立部署的 Hindsight 不会因为知页的“游戏模式”而停止，但如果使用同一组本地模型，相关记忆功能会暂时不可用。

## AstrBot 等调用方

本地重排序可通过兼容 Cohere 格式的提供商接入：

```json
{
  "model": "bge-reranker-v2-m3",
  "query": "问题",
  "documents": ["候选资料一", "候选资料二"],
  "top_n": 2
}
```

向实际 `/v1/rerank` 地址 POST，响应应含 `results`，各项包括 `index` 和 `relevance_score`。知页不会修改 AstrBot、Chatbox 或其他客户端的配置。共用模型关闭后，这些客户端也会失去该接口，重新启动模型即可恢复。
