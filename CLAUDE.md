# 🌾 Grain Counter — Claude Code 长时间运行框架

> 基于 [longtimerun/CLAUDE.md] 适配的小麦籽粒检测 Web 服务重构项目

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
├── web_server.py           # FastAPI 后端入口
├── server_panel.py         # Tkinter/CustomTkinter 管理面板
├── graincounter/           # 共享逻辑包
│   ├── __init__.py
│   ├── config.py           # 配置管理
│   ├── logger.py           # 日志系统
│   ├── rate_limiter.py     # 限速器
│   ├── user_agent.py       # UA 解析
│   ├── device_tracker.py   # 在线设备追踪
│   ├── detector.py         # YOLO 检测器
│   └── valuable.py         # 优质照片筛选
├── templates/
│   └── index.html          # 前端页面
├── models/                 # YOLO 模型文件
├── Valuable photos/        # 优质照片
├── prompts/                # Planner/Generator/Evaluator prompt
├── memory/                 # 进度日志 & handoff
├── tasks/                  # 任务定义
├── CLAUDE.md               # 本文件
└── CHANGELOG.md            # 变更日志
```
