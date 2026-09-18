# Fluent Music AI 智能助手 5-Step 全流程实施规划书

> **项目定位**：基于现有 Fluent Music（Qt 6 / C++20 / QML）音乐播放器，构建一套包含**自然语言播放器控制、本地音乐精准检索、智能场景情绪歌单、多源网络音乐发现与下载入库**的高可用 AI Agent 系统。  
> **核心架构**：Qt/C++ 播放器客户端（原生 UI 与音频核心） + Python Agent 微服务（LangChain + FastAPI + Pydantic）。  
> **执行准则**：每完成一步，严格执行验收测试，由用户逐一核对确认后，再推进下一步。

---

## 一、 系统架构总览与九大核心要素映射

根据规格说明书 V1.4 及生产级 Agent 的架构要求，系统全要素分工如下：

```text
┌────────────────────────────────────────────────────────────────────────┐
│                   Qt 音乐播放器 (C++20 / Qt 6.8 / QML)                  │
│                                                                        │
│  [SideBar 导航] ──> [qml/agent/AgentPage 交互界面]                      │
│                           │                  ▲                         │
│                           ▼                  │ 状态/消息流             │
│                 MusicAgentClient (C++) ── AgentMessageModel            │
│                           │                                            │
│                 QtToolServer (127.0.0.1:8766)                          │
│                  ├── PlayerController (播放控制)                       │
│                  └── MusicLibraryModel (本地检索与歌单)                │
└───────────────────────────┬────────────────────────────────────────────┘
                            │ HTTP / SSE 异步回环 (127.0.0.1:8765)
                            ▼
┌────────────────────────────────────────────────────────────────────────┐
│             Python Agent 微服务 (agent_service/ Python 3.13)            │
│                                                                        │
│  ├── [1. LLM Adapter]     本地模型(Ollama/vLLM) + 云端(DeepSeek/Qwen等) │
│  ├── [2. Agent Loop]      意图理解 -> 决策 -> Tool -> 回传 -> 最终响应  │
│  ├── [3. Tool Registry]   Pydantic 强类型 Schema，只读/执行权限分级    │
│  ├── [4. State Engine]    播放器快照状态注入 + Agent UI 状态同步       │
│  ├── [5. Context Manager] Session 隔离 + 滑动窗口历史修剪              │
│  ├── [6. Guardrails]      参数范围拦截 + 敏感破坏性操作二次确认        │
│  ├── [7. Error Recovery]  超时重试 + JSON 兜底解析 + Tool 异常反馈修复  │
│  ├── [8. Observability]   DeepSeek-R1 <think> 提取 + ToolCard 结构化呈现│
│  └── [9. Evaluation]      自动化测试集，量化意图识别率与执行成功率     │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 二、 5-Step 分步实施计划

---

### 📍 Step 1：Qt 前端改造与智能助手 QML 页面

#### 1. 建设目标
在现有播放器界面中无缝集成「智能助手」页面，打造完全符合 Fluent Dark 视觉风格的聊天交互界面、思考状态指示器、操作执行卡片与模型设置面板，完成纯前端数据流驱动。

#### 2. 新增与修改文件清单
* **修改已有文件**：
  - `qml/components/SideBar.qml`：将第 6 项「下载管理」替换为「智能助手」，配备 Fluent 风格 Sparkles/Bot 图标。
  - `qml/Main.qml`：在 `StackLayout` 的 Index 6 位置挂载 `AgentPage.qml`，对接页面切换逻辑。
  - `CMakeLists.txt`：在 `appFluentWinUI_Musicplayer` 资源列表中注册新增的 QML 文件。
* **新建 QML 组件目录** `qml/agent/`：
  - `qml/agent/AgentPage.qml`：主页面容器，包含顶部标题、操作栏（新建对话、模型配置按钮）、聊天视图、底部输入栏。
  - `qml/agent/AgentChatView.qml`：消息流展示区，基于 ListView，支持消息自动滚底。
  - `qml/agent/AgentMessageDelegate.qml`：消息气泡渲染器（区分 User 右侧气泡、Assistant 左侧气泡、System 系统通知）。
  - `qml/agent/AgentToolCard.qml`：结构化操作卡片，展示工具名称、调用参数、执行中/成功/失败状态指示。
  - `qml/agent/AgentThinkingIndicator.qml`：思维链展示器，支持展开/收起 DeepSeek-R1 `<think>` 思考过程。
  - `qml/agent/AgentInputBar.qml`：输入区域，支持自适应高度、Enter 发送、Shift+Enter 换行、发送中禁用态。
  - `qml/agent/AgentSuggestionCard.qml`：快捷预置指令标签流（如“播放周杰伦”、“音量调到 30%”等）。
  - `qml/agent/AgentSettingsDialog.qml`：模型设置弹窗，支持选择模式（本地模型/在线 API）、填写 Base URL、API Key、Model Name 与连通性测试。

#### 3. 具体功能实现
1. 侧边栏原 Index 6 顺畅切换到智能助手页面。
2. 完整的视觉状态机渲染：`Idle`（空闲）、`Thinking`（思考中）、`CallingTool`（工具执行中）、`Streaming`（流式输出）、`Error`（错误提示）。
3. 纯前端数据绑定：点击快捷提示词自动填入并模拟生成对话卡片与 ToolCard。
4. 保证切换智能助手页面时，底部播放栏（PlayerBar）及当前播放音乐不受任何干扰。

#### 4. 验证方式与验收标准
- **编译测试**：运行 `mingw32-make`，确保 QML 预编译与 C++ 链接 100% 成功，无任何 QML 语法错误。
- **页面交互验证**：
  1. 启动播放器，点击左侧「智能助手」，页面平滑切换入智能助手。
  2. 点击快捷指令气泡（如“音量调到 30%”），验证输入栏与消息列表中立刻渲染出用户消息及模拟的 AI 回复与 ToolCard。
  3. 点击右上角「设置」图标，弹出 `AgentSettingsDialog`，可自由切换“本地模型”与“在线 API”并修改配置项。
  4. 播放器后台正在播放歌曲时，来回切换侧边栏各项与智能助手，音乐播放无中断、无卡顿。

---

### 📍 Step 2：Python Agent 微服务基础与 LLM 双模式抽象

#### 1. 建设目标
在项目根目录下创建标准的 `agent_service/` 独立工程，基于 Python 3.13 与 LangChain 搭建微服务骨架，完整实现「本地模型 API」与「在线商业 API」的统一抽象适配器，打通 Qt 客户端与 Python 服务之间的 HTTP/SSE 基础对话闭环。

#### 2. 新增与修改文件清单
* **新建 Python 服务目录** `agent_service/`：
  - `agent_service/main.py`：FastAPI 应用入口，挂载 `/health`、`/api/agent/chat`、`/api/agent/chat/stream`、`/api/config/llm`。
  - `agent_service/config.py`：使用 Pydantic 管理配置项（本地模型 URL/模式、云端 Key/URL、当前会话超时等）。
  - `agent_service/llm_adapter.py`：核心模型抽象，封装 `OllamaProvider` 与 `OpenAICompatibleProvider`（兼容 DeepSeek/通义千问/OpenAI）。
  - `agent_service/context_manager.py`：Session 会话管理，实现滑动窗口上下文修剪与 R1 `<think>` 标签剥离。
  - `agent_service/prompts/system_prompt.md`：音乐智能助手基础系统提示词。
  - `agent_service/requirements.txt`：明确锁定依赖版本。
* **C++ 客户端集成**（`src/agent/`）：
  - `src/agent/MusicAgentClient.h/.cpp`：基于 `QNetworkAccessManager` 与 Python 服务建立 HTTP REST 及 SSE 流式长连接。
  - `src/agent/AgentMessageModel.h/.cpp`：继承 `QAbstractListModel`，负责实时管理 QML 界面消息列表。
  - `src/main.cpp`：注册并初始化 `MusicAgentClient` 与 `AgentMessageModel`，暴露给 QML 上下文。

#### 3. 具体功能实现
1. 屏蔽全局废弃的 `PYTHONPATH` 干扰，使用 Python 3.13.15 稳定运行 FastAPI。
2. LLM 双模式抽象落地：
   - **Local Mode**：连接本地 Ollama（如 `http://127.0.0.1:11434/v1`）或 LM Studio，免 Key 认证。
   - **Online Mode**：连接 DeepSeek / 通义千问等商业 API，鉴权 Bearer Token。
3. Qt 客户端自动探测 Agent 服务健康状态（在线/离线指示器）。
4. 实现流式打字机输出（SSE）与 Thinking 状态同步。

#### 4. 验证方式与验收标准
- **服务启动验证**：运行 `python main.py`，访问 `http://127.0.0.1:8765/health`，返回 `{"status": "ok", "provider": ...}`。
- **对话闭环测试**：
  1. 打开 Qt 播放器，智能助手顶部显示“在线”绿点。
  2. 向输入框发送“你好，请问你是谁？”，界面出现“正在思考...”状态。
  3. 本地 LLM（或配置好的云端 API）成功返回回答，并在 QML 对话列表中逐字流式打字输出。
  4. 点击“新建对话”，验证上下文已清空重置。

---

### 📍 Step 3：播放器 Tool 闭环控制（自然语言操控）

#### 1. 建设目标
在 Qt 播放器端开设本地专用 Tool Server，并在 Python 端实现第一批播放器控制 Tool，构建完整的 ReAct 决策循环，让 Agent 真正能够通过自然语言执行硬件级/软件级播放器控制。

#### 2. 新增与修改文件清单
* **C++ 端 Tool Server 与映射**：
  - `src/agent/QtToolServer.h/.cpp`：在 Qt 进程内部启动专属轻量 TCP/HTTP 服务（绑定 `127.0.0.1:8766`，仅限本机访问）。
  - 映射绑定 `PlayerController` 现有接口：
    - `POST /tools/set_volume` -> `playerController.setVolume(value)`
    - `POST /tools/pause` -> `playerController.pause()`
    - `POST /tools/resume` -> `playerController.play()`
    - `POST /tools/next_track` -> `playerController.next()`
    - `POST /tools/previous_track` -> `playerController.previous()`
    - `POST /tools/seek` -> `playerController.seek(positionMs)`
    - `POST /tools/set_play_mode` -> `playerController.setPlayMode(mode)`
    - `GET /tools/get_player_state` -> 获取当前歌曲名、歌手、播放状态、当前音量。
* **Python 端 Agent 决策与工具库**：
  - `agent_service/tools/base.py`：定义 Tool 基类与 Pydantic Schema 校验规则。
  - `agent_service/tools/player_tools.py`：实现播放器常用工具，自动注入参数校验与越界护栏（如音量严格限制在 0~100）。
  - `agent_service/agent.py`：实现 Agent Loop 循环，装载 System Prompt、当前播放器快照状态，调用 LLM 进行工具决策，自动执行 Tool 并将结果回传给 LLM 形成回复。

#### 3. 具体功能实现
1. **状态感知**：Python 服务每次调用 LLM 前，自动获取播放器当前状态（正在播放什么、音量多大、是否在播），AI 能准确理解代词（如“这首歌叫什么”、“把声音调大点”）。
2. **决策闭环**：LLM 识别到操作指令 -> 触发 Tool Call -> Python 转发至 Qt Tool Server -> C++ 真正执行底层控制 -> 返回结构化 JSON 结果 -> Agent 给出最终确认回复。
3. **前端呈现**：聊天页面自动插入 `AgentToolCard`，清晰展示执行动作及参数变化（如 `✓ 调整音量 60% → 30%`）。

#### 4. 验证方式与验收标准
- **单项动作测试**：
  1. 对智能助手说：“把声音调到 25%”，底栏音量滑块真实滑到 25%，声音即刻变小，聊天列表出现音量调整成功卡片。
  2. 正在播放时说：“暂停播放”，音乐立即暂停；随后说：“继续”，音乐继续流畅播放。
  3. 说：“切到下一首”，播放器顺利跳至下一曲，底栏歌名封面随之切换。
- **复合与模糊意图测试**：
  - 说：“把声音调得特别大”，LLM 自动换算为合理值（如 85%）并提示。
  - 问：“当前在放什么歌？”，AI 能结合播放器状态准确报出歌名与歌手。

---

### 📍 Step 4：本地音乐自然语言检索与智能场景歌单

#### 1. 建设目标
让 Agent 拥有检索本地音乐库的能力，实现基于自然语言歌名/歌手的精准点歌与模糊查找；并在本地建立轻量 `AgentTagCache`，支持基于情绪、工作场景、语言风格的智能歌单生成。

#### 2. 新增与修改文件清单
* **C++ 端曲库检索接口暴露**：
  - 在 `src/agent/QtToolServer.cpp` 中挂载：
    - `POST /tools/search_local_music`：对接 `MusicLibraryModel`，执行毫秒级标题/歌手模糊匹配。
    - `POST /tools/play_local_track`：指定文件路径或索引直接加载播放。
    - `POST /tools/create_temp_playlist`：动态创建并加载一组歌曲为当前播放列表。
    - `GET /tools/get_library_summary`：获取本地音乐总数、全部歌手/曲目概览。
* **Python 端曲库工具与歌单规划器**：
  - `agent_service/tools/library_tools.py`：本地检索 Tool，包含结果去重与置信度排序。
  - `agent_service/tools/playlist_tools.py`：智能歌单生成器，实现多维标签过滤（心情、场景、语言、年代）。
  - `agent_service/tag_cache.py`：基于 SQLite / JSON 实现的轻量 `AgentTagCache`，仅缓存本地歌曲的标签分析，不破坏现有 INI/JSON 音乐配置。

#### 3. 具体功能实现
1. **精准与模糊搜歌点播**：
   - 用户输入“播放周杰伦的晴天” -> Agent 搜本地库 -> 找到唯一点播 -> 自动切换播放晴天。
   - 用户输入“放一首关于冬天的歌” -> Agent 提取关键词并智能匹配本地库相关歌曲。
2. **场景/情绪智能歌单**：
   - 用户输入“我准备写代码了，给我找点节奏轻松的中文歌” -> Agent 提取属性（Scene: Coding, Mood: Relaxing, Language: Chinese） -> 筛选本地库歌曲 -> 组建临时播放列表并启动连续播放。
3. **无结果优雅回退**：
   - 当本地确实没有检索到曲目时，明确告知用户“本地音乐库中未找到《XXX》，后续可通过网络搜索获取”。

#### 4. 验证方式与验收标准
- **搜歌播放验证**：
  1. 输入“播放本地的 [真实存在的歌名]”，验证播放器立刻选中该歌曲开播，左下角封面信息与歌词同步刷新。
  2. 输入不完整的歌名（如“播放夜曲”），验证 Agent 准确匹配出周杰伦的《夜曲》并播放。
- **歌单生成验证**：
  - 输入“给我推荐 5 首适合深夜听的慢歌”，验证 Agent 生成包含 5 首曲目的推荐列表并调用 `create_temp_playlist` 开播，界面卡片完整展示生成的歌单目录。

---

### 📍 Step 5：多来源网络音乐发现与下载管理（按需靠后执行）

#### 1. 建设目标
构建统一的多 Provider 网络音乐发现体系，让 Agent 具备跨源音乐检索能力；支持在特定音乐站点搜索直链解析与 P2P 接入；实现下载管理器，歌曲下载完成后自动导入本地音乐库。

#### 2. 新增与修改文件清单
* **Python 端多源架构**：
  - `agent_service/services/music_discovery_service.py`：网络资源发现调度中心。
  - `agent_service/providers/music/base.py`：统一 `TrackCandidate` 数据模型与 `MusicProvider` 抽象基类。
  - `agent_service/providers/music/manager.py`：统一调度、多源并发请求、结果归一化、去重与智能排序。
  - `agent_service/providers/music/web/xiageba_provider.py` / `web_search_provider.py`：指定音乐网站爬虫与网页直链解析器（利用 `requests` / `beautifulsoup4` / `DrissionPage`）。
  - `agent_service/providers/music/p2p/soulseek_provider.py`：调用 slskd HTTP API 实现 P2P 资源检索与下载。
  - `agent_service/services/download_manager.py`：统一多源下载任务管理、断点续传、下载进度通知。
* **C++ 端自动导入集成**：
  - 在 `src/agent/QtToolServer.cpp` 中挂载 `POST /tools/import_downloaded_track`，接收新下载的文件路径，自动刷新 `MusicLibraryModel` 并缓存封面。

#### 3. 具体功能实现
1. **本地优先原则**：搜歌请求先查本地；本地命中则直接播放，只有本地未找到时才触发网络搜索。
2. **多源候选归一化**：网络搜索结果聚合转换为统一的 `TrackCandidate` 列表（包含格式、码率、来源标签），并在界面呈现候选列表。
3. **安全操作二次确认（Human Confirmation）**：大文件下载或下载敏感曲目时，在界面弹出确认按钮，用户点击后再启动下载任务。
4. **下载后自动入库**：下载完成后，文件自动存入本地指定音乐文件夹，Qt 播放器动态追加该曲目，无需重启软件。

#### 4. 验证方式与验收标准
- **网络搜歌验证**：
  1. 检索一首本地曲库完全没有的歌曲，验证 Agent 自动调用 `search_network_music` 并返回多条候选资源。
  2. 候选卡片中清晰展示曲名、歌手、音质码率与 Provider 来源。
- **下载与导入闭环验证**：
  1. 点击候选结果的“下载”按钮，下载任务在后台启动，有明确进度反馈。
  2. 下载完毕后，本地音乐库总曲目数自动 +1，播放器可立即点击播放该下载好的音乐文件。

---

## 三、 实施执行守则

1. **单步交付与逐项核对**：严格按照 **Step 1 -> Step 2 -> Step 3 -> Step 4 -> Step 5** 的顺序开发。每做完一个 Step，先进行全量代码编译和场景实机验证，由您核对确认无误后，再启动下一步。
2. **非侵入性保护**：严格保证播放器现有的 8 大推荐模块、最近播放、我喜欢、歌单管理、歌词左右分栏等成熟功能不受任何破坏与回退。
3. **无缝平替**：左侧原本闲置的 Index 6 顺滑升级为「智能助手」，其他页面逻辑保持不变。
