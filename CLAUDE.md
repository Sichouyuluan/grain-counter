<!-- 用户全局规则（[USER_HOME]\.claude\CLAUDE.md）— 优先执行 -->
# CLAUDE.md — Karpathy 12 Rules

These rules apply to every task in this project unless explicitly overridden.
Bias: caution over speed on non-trivial work. Use judgment on trivial tasks.
（以下规则适用于本项目所有任务，除非明确覆盖。非简单任务：谨慎优先于速度。简单任务可自行判断。）

## 执行流程优先级

1. **先想再写，不确定就问** — 接到任务先理解全貌，有歧义的地方问清楚
2. **懂了再拆** — 确认理解正确后，将任务拆分为可执行步骤
3. **步骤多则并行** — 5步以上或预计超过30分钟，尽可能派多个子Agent并行执行
4. **简单任务不硬拆** — 明显无法拆分的事直接干，不用强行派子Agent

---

## Rule 1 — Think Before Coding（先想再写）
State assumptions explicitly. If uncertain, ask rather than guess.
Present multiple interpretations when ambiguity exists.
Push back when a simpler approach exists.
Stop when confused. Name what's unclear.
（明确陈述假设。不确定就问，不要猜。有歧义时列出多种可能的理解。有更简单的方案时要指出。卡住就停下来，说出哪里不清楚。）

## Rule 2 — Simplicity First（简单优先）
Minimum code that solves the problem. Nothing speculative.
No features beyond what was asked. No abstractions for single-use code.
Test: would a senior engineer say this is overcomplicated? If yes, simplify.
（用最少的代码解决问题。不加猜测的功能。不加没被要求的特性。不为只用一次的场景做抽象。自问：资深工程师会觉得这个写复杂了吗？如果是，简化。）

## Rule 3 — Surgical Changes（外科式修改）
Touch only what you must. Clean up only your own mess.
Don't "improve" adjacent code, comments, or formatting.
Don't refactor what isn't broken. Match existing style.
（只动必须动的。只清理自己弄乱的。不要"顺手改进"旁边的代码、注释或格式。没坏的东西不要重构。匹配现有代码风格。）

## Rule 4 — Goal-Driven Execution（目标驱动执行）
Define success criteria. Loop until verified.
Don't follow steps blindly. Define success and iterate.
Strong success criteria let you loop independently.
（先定义"怎样算做完了"。反复验证直到达标。不要盲目按步骤走。先定义成功长什么样，再迭代达成。清晰的成功标准让你能独立反复验证。）

## Rule 5 — Use the model only for judgment calls（只让 AI 做判断类任务）
Use me for: classification, drafting, summarization, extraction.
Do NOT use me for: routing, retries, deterministic transforms.
If code can answer, code answers.
（AI 适合：分类、起草、摘要、提取。不要用 AI 做：路由、重试、确定性转换。能用代码解决的问题，就用代码解决。）

## Rule 6 — Token budgets are not advisory（Token 预算不是建议）
Per-task: 4,000 tokens. Per-session: 30,000 tokens.
If approaching budget, summarize and start fresh.
Surface the breach. Do not silently overrun.
（每个任务上限 4000 token，每轮会话上限 30000 token。快超预算时，做摘要并重新开始。超了要明说，不要偷偷超限。）

## Rule 7 — Surface conflicts, don't average them（暴露冲突，不要取平均）
If two patterns contradict, pick one (more recent / more tested).
Explain why. Flag the other for cleanup.
Don't blend conflicting patterns.
（如果两种写法矛盾，选一种（更新或经过更多测试的）。解释为什么选这个，标记另一个待清理。不要混搭矛盾的写法。）

## Rule 8 — Read before you write（先读再写）
Before adding code, read exports, immediate callers, shared utilities.
"Looks orthogonal" is dangerous. If unsure why code is structured a way, ask.
（加代码前，先读导出接口、直接调用方、共用工具。"看起来不相关"是危险的想法。不确定某段代码为什么这么写，先问。）

## Rule 9 — Tests verify intent, not just behavior（测试验证意图，不只验证行为）
Tests must encode WHY behavior matters, not just WHAT it does.
A test that can't fail when business logic changes is wrong.
（测试必须编码"为什么这个行为重要"，不只是"它干了什么"。业务逻辑变了但测试仍然通过的测试，是错的。）

## Rule 10 — Checkpoint after every significant step（每步做检查点）
Summarize what was done, what's verified, what's left.
Don't continue from a state you can't describe back.
If you lose track, stop and restate.
（每完成一个重要步骤，总结：做了什么、验证了什么、还剩下什么。如果你说不清当前状态，就不要继续。如果跟丢了，停下来重新说一遍。）

## Rule 11 — Match the codebase's conventions, even if you disagree（匹配代码库的约定，即使你不同意）
Conformance over taste inside the codebase.
If you genuinely think a convention is harmful, surface it. Don't fork silently.
（在代码库内，一致性优先于个人偏好。如果你真的认为某个约定是有害的，提出来讨论。不要默默搞出两套风格。）

## Rule 12 — Fail loud（失败要大声）
"Completed" is wrong if anything was skipped silently.
"Tests pass" is wrong if any were skipped.
Default to surfacing uncertainty, not hiding it.
（如果有东西被静默跳过了，"已完成"就是假的。如果有测试被跳过了，"测试通过"就是假的。有不确定的事情，默认说出来，不要藏起来。）

---

# Long Time Run — 长时间运行框架

所有项目默认使用此框架。如果项目根目录没有框架文件，则创建它们。

## 框架结构

```
├── run.ps1              # 入口（接收任务描述，调用 harness）
├── harness.ps1          # 核心循环（不要手动修改）
├── prompts/
│   ├── planner.md       # Planner 阶段指令
│   ├── generator.md     # Generator 阶段指令
│   └── evaluator.md     # Evaluator 阶段指令
├── memory/
│   ├── progress.md      # 追加式进度日志
│   └── handoff.md       # 当前状态（跨迭代通信的唯一信道）
├── tasks/
│   ├── mission.md       # 原始任务定义
│   └── tasks.json       # 结构化任务列表
└── CLAUDE.md
```

- 模板文件从 `[LONGTIMERUN_DIR]/` 复制（如果目录不存在，根据本文件的描述自行重建框架文件）
- `harness.ps1` 和 `prompts/` 下的文件不要手动修改
- 用户说 "开始" 或给出明确的长任务描述时，初始化框架
- **触发条件**：5步以上 / 预计超过30分钟 / 涉及3个以上不相关模块 / 用户明确说"开始"

## 启动流程

1. **写入任务**：将用户需求写入 `tasks/mission.md`，描述越清晰越好
2. **判断起始阶段**：
   - 需求模糊或项目刚开始 → **Planner 阶段**
   - 已有明确任务列表 → **Generator 阶段**
   - 任务已实现需要验收 → **Evaluator 阶段**
   - 不确定时走 Planner
3. **创建任务列表**：在 Planner 阶段，将模糊需求分解为可执行任务，写入 `tasks/tasks.json`

## 三阶段工作流

### Planner 阶段
- 将模糊需求分解为结构化任务
- 每个任务包含：id、title、status（默认 pending）、dependencies、acceptance_criteria
- 写入 `tasks/tasks.json`
- 完成后推进到 Generator 阶段

### Generator 阶段
每轮迭代：
1. 读 `tasks/tasks.json`，找一个 `pending` 状态且依赖已满足的任务
2. 标记为 `in_progress`
3. 实现该任务
4. 按 acceptance_criteria 验证
5. 通过则标记 `completed`，失败则标记 `failed` 并记录原因
6. `git add -A && git commit -m "task N: title"`
7. 更新 `memory/handoff.md` 和 `memory/progress.md`
8. **每次迭代只做一个任务**

### Evaluator 阶段
- 所有 Generator 任务完成后**自动执行**，或用户说"检查/验证"时手动触发
- 检查所有已实现任务的代码是否存在、是否可运行
- 逐项核对 acceptance_criteria
- 输出评估报告到 `memory/evaluation.md`

## 核心约定

### 每轮迭代
- **第一件事**：读取 `memory/handoff.md`，了解当前状态和下一步
- **最后一件事**：更新 `memory/handoff.md` 和 `memory/progress.md`，让下一次迭代能接上

### 任务管理
- 任务列表格式：`{"id": 1, "title": "..", "status": "pending", "dependencies": [], "acceptance_criteria": []}`
- 状态流转：`pending` → `in_progress` → `completed` | `failed`

### Git 提交
- 每次完成一个任务后提交：`git add -A && git commit -m "task N: description"`
- 保持工作目录干净，提交前 `git status` 确认

## 最佳实践
- **不要假设前一轮的状态**。每次都是 fresh context，从文件读取所有信息
- **写清晰的 acceptance_criteria**。模糊的标准导致模糊的结果
- **遇到阻碍时标记 failed 并记录原因**，不要卡住
- **复杂项目走全流程**（Planner → Generator → Evaluator），简单任务可直接从 Generator 开始

---

## 子 Agent 使用规范

接到任务后，先想再写不确定就问 → 懂了之后拆步骤 → 步骤多则并行。

### 长任务 vs 简单任务

| 类型 | 特征 | 处理方式 |
|---|---|---|
| 简单任务 | 1-3步，改动量小 | 直接干，不派子Agent |
| 中等任务 | 4-8步，涉及多个方面但依赖性强 | 先规划，少量并行或不并行 |
| 复杂/长任务 | **5步以上**或**预计超过30分钟**或**涉及3个以上不相关模块** | 先规划，拆成独立子任务，尽可能并行派子Agent |

**明显无法拆分的简单任务，不硬拆。**

### 执行原则
- 将大任务拆解为多个互相独立的子任务
- 每个子任务派一个子 Agent 独立执行
- 互不依赖的子任务同时并行，减少总耗时
- 子 Agent 各司其职，每个只专注一件事
- 所有子 Agent 完成后，汇总结果

---

## 浏览器自动化规范

### 工具选择
- **优先用 CLI**（Python Playwright 脚本），一次 Bash 调用完成所有步骤，省 token
- 如果任务无法用固定脚本完成（需要边看边决策），**换 MCP 执行**

### 前台/后台
- **默认前台执行**（`headless=False`），弹出浏览器窗口让用户看到操作过程
- 只有用户明确说"后台执行"或"后台跑"时，才使用 `headless=True`
- 此规则同时适用于 CLI 脚本和 MCP 两种方式


<!-- 项目特定配置 -->
# 🌾 Grain Counter — 项目结构

> 基于 longtimerun 框架适配的小麦籽粒检测 Web 服务项目

## 核心约定

### 每次迭代的第一件事
**读取 `memory/handoff.md`** 了解当前状态和下一步要做什么。

### 每次迭代的最后一件事
更新 `memory/handoff.md` 和 `memory/progress.md`，让下一次迭代能接上。

### 任务管理
- 任务列表在 `tasks/tasks.json`
- 状态流转：`pending` → `in_progress` → `completed` | `failed`
- **每次迭代只做一个任务**

### Git 提交规范
每次完成一个任务后提交：
```
git add -A && git commit -m "task N: description"
```

### 文件结构
```
├── web_server.py               # FastAPI 入口 + lifespan + uvicorn 启动
├── server_panel.py             # Tkinter/CustomTkinter 管理面板
├── graincounter/
│   ├── __init__.py
│   ├── config.py               # 配置管理（支持持久化）
│   ├── logger.py               # 日志系统 (PinHidingFilter)
│   ├── middleware.py            # 认证 + 限速中间件
│   ├── state.py                # 集中应用状态 AppState
│   ├── guard.py                # ScanGuard 扫描防护 (双重检测)
│   ├── rate_limiter.py         # 限速器 (线程安全)
│   ├── stats.py                # DetectionStats 检测统计
│   ├── device_tracker.py       # 在线设备追踪
│   ├── detector.py             # YOLO ONNX 检测器
│   ├── valuable.py             # 优质照片筛选
│   ├── user_agent.py           # UA 解析
│   ├── theme.py                # 面板主题
│   ├── panel_ui.py             # 面板 UI (mixin)
│   ├── panel_controls.py       # 面板控制逻辑 (mixin)
│   └── routes/
│       ├── __init__.py
│       ├── admin.py            # /api/config /health /ping /stats /key
│       ├── models.py           # /api/models /select-model
│       ├── devices.py          # /api/online-devices /kick-device
│       ├── detect.py           # /api/detect /save-image
│       └── pages.py            # GET /, /api/valuable-*
├── templates/index.html        # 前端页面 (Tailwind replacement CSS)
├── models/                     # YOLO ONNX 模型文件
├── Valuable photos/            # 优质训练照片
├── prompts/                    # Planner/Generator/Evaluator prompt
├── memory/                     # 进度日志 & handoff
├── tasks/                      # 任务定义
├── SECURITY_TEST_REPORT.md     # 安全测试报告
├── CLAUDE.md                   # 本文件
└── CHANGELOG.md                # 变更日志
```
