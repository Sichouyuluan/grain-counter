# Changelog / 更新日志

All notable changes to the Grain Counter project.

---

## [4.1.0] — 2026-05-19

### Added / 新增
- Cross-platform CLI tools: `grain`, `grainon`, `grainoff`, `grainkey` / 跨平台 CLI 工具
- `config.local.yaml` for local config overrides / 本地配置覆盖文件
- Cloudflared tunnel URL auto-detection from `~/.cloudflared/config.yml` / Cloudflared 隧道 URL 自动检测
- `TEST_PLAN.md` for structured testing / 结构化测试计划
- Agent-harness test suite (unit + E2E) / CLI 工具测试套件

### Changed / 改进
- Full README rewrite for GitHub public release / README 全面重写
- Agent-harness CLI with cross-platform explorer support / CLI 跨平台文件浏览器支持
- `tunnel_url` added to DEFAULT_CONFIG / 默认配置增加 tunnel_url

### Fixed / 修复
- Auth config persistence (`--no-auth` overriding config.yaml) / 认证配置持久化覆盖问题
- CLI import path resolution in agent-harness backends / CLI 导入路径解析
- Cross-platform explorer indentation in `pages.py` / 跨平台 explorer 缩进错误
- `config.local.yaml` support in `lifecycle.py` / lifecycle.py 本地配置读取

---

## [4.0.0] — 2026-05-19

### Added / 新增
- **Agent-Harness CLI**: pip-installable package / 可 pip 安装的 CLI 工具包
- CLI commands: `grain`, `grainon`, `grainoff`, `grainkey`
- Core backends: detector, server, config, HTTP client / 核心后端模块
- Cross-platform `start_panel.sh` / Linux/macOS 启动脚本
- `models/.gitkeep` for preserving directory / 模型目录占位文件

### Changed / 改进
- `.gitignore` expanded with 12 new patterns / 忽略规则扩展
- `config.yaml` model detection adjustments / 模型检测配置调整

### Removed / 移除
- Legacy `harness.ps1` and `run.ps1` (replaced by agent-harness) / 旧版 PowerShell 脚本

---

## [3.1.0] — 2026-05-18

### Added / 新增
- Auto-start mode with PID file management / 自动启动模式 + PID 文件管理
- Cloudflared auto-cleanup on graceful shutdown / 退出时自动清理 Cloudflared
- YOLO `max_det` raised from 300 to 1000 / 最大检测数 300→1000
- Responsive UI polish / 响应式 UI 打磨

---

## [3.0.0] — 2026-05-17

### Added / 新增
- **Cloudflared Tunnel** for secure public access / Cloudflared 隧道远程访问
- Multi-model warmup on startup / 多模型启动预热
- Scan configuration UI in management panel / 扫描防护配置 UI
- Application state tracking (`state.py`) / 应用状态追踪模块

---

## [2.1.0] — 2026-05-16

### Added / 新增
- **Security hardening**: 7 vulnerability fixes / 安全加固，修复 7 个漏洞
- ScanGuard dual-detection mechanism / ScanGuard 双重检测机制
- Attack log for security events / 攻击日志记录
- Inline CSS (Tailwind CDN replaced) / 内联 CSS 替代 Tailwind CDN
- `SECURITY_TEST_REPORT.md` / 安全测试报告

### Fixed / 修复
- Path traversal in model file serving / 模型文件路径穿越
- API key brute-force via rate limiting / API Key 暴力破解防护
- CORS origin validation / 跨域来源验证

---

## [2.0.0] — 2026-05-15

### Added / 新增
- **Modular refactoring**: `graincounter/` package with separate modules / 模块化重构
- Route modules: admin, detect, devices, models, pages / 路由模块拆分
- Graceful shutdown handler / 优雅退出处理
- Config hot-reload support / 配置热加载

---

## [1.1.0] — 2026-05-14

### Added / 新增
- **ScanGuard v1**: UvicornSafeFilter + anti-scan / 扫描防护 v1
- Runtime statistics (`stats.py`) / 运行时统计模块
- Model folder shortcut in panel / 面板模型文件夹快捷入口
- `test_verification.py` automated tests / 自动化验证测试

---

## [1.0.0] — 2026-05-13

### Added / 新增
- Config persistence across restarts / 配置持久化
- Model selection dropdown / 模型选择下拉框
- Image zoom up to 1000% / 图片缩放至 1000%
- Panel UI/Controls/Theme modules / 面板 UI/控制/主题模块

---

## [0.9.0] — 2026-05-12

### Added / 新增
- Auth checkbox toggle in panel / 面板认证开关
- Mobile responsive design / 移动端响应式设计
- Confidence distribution bar chart / 置信度分布柱状图

---

## [0.8.0] — 2026-05-11

### Added / 新增
- Project refactoring: modular architecture / 项目重构为模块化架构
- FastAPI entry point with startup/shutdown events / FastAPI 入口 + 生命周期事件
- Initial route system / 初始路由系统
- Centralized config, logger, middleware modules / 配置/日志/中间件模块

---

## [0.7.0] — 2026-05-03

### Added / 新增
- Low-bandwidth optimization / 低带宽优化
- Skeleton loading screens / 骨架屏加载
- Keyboard shortcuts (Enter to detect) / 键盘快捷键 Enter 检测
- Mobile adaptation / 移动端适配

---

## [0.6.0] — 2026-05-02

### Added / 新增
- Tailscale integration / Tailscale VPN 集成
- Response compression (gzip/brotli) / 响应压缩
- Heartbeat detection / 心跳检测

---

## [0.5.0] — 2026-05-01

### Added / 新增
- Online device management / 在线设备管理
- Confidence / IoU threshold controls / 置信度/IoU 参数调节
- Real-time parameter adjustment / 实时参数调整

---

## [0.4.0] — 2026-04-30

### Added / 新增
- Valuable photo filtering / 优质照片筛选
- Tailwind CSS frontend redesign / Tailwind CSS 前端重设计

---

## [0.3.0] — 2026-04-29

### Added / 新增
- API Key authentication / API Key 认证
- Device tracking with unique IDs / 设备唯一标识追踪
- Rate limiting for API protection / API 限速保护

---

## [0.2.0] — 2026-04-28

### Added / 新增
- Management panel / 管理面板
- Port configuration UI / 端口配置界面
- Auth toggle (enable/disable) / 认证开关
- Real-time server logs / 实时日志

---

## [0.1.0] — 2026-04-27

### Added / 新增
- Initial prototype / 初始原型
- FastAPI web server with async handling / FastAPI 异步 Web 服务
- YOLO ONNX grain detection / YOLO ONNX 籽粒检测
- Basic Web UI / 基础 Web 界面
