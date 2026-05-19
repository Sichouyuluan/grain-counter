# Grain Counter — 功能测试计划

> 测试环境：`grain-counter/` 项目根目录
> 测试方法：Playwright 浏览器自动化 + CLI 命令 + API curl
> 测试日期：2026-05-19

---

## 一、Web 前端测试 (templates/index.html)

### 1.1 页面加载
- [ ] 页面正常加载，无 JS 错误
- [ ] 暗色主题渲染正确
- [ ] 上传区域可见（渐变边框动画）
- [ ] 心跳检测启动（/api/ping 每5秒）
- [ ] 响应式布局（移动端适配）

### 1.2 图片上传
- [ ] 点击上传区域触发文件选择
- [ ] 拖拽图片到上传区域
- [ ] 粘贴图片（Ctrl+V）
- [ ] 上传后显示预览图
- [ ] 客户端压缩（>500KB → 1920px）

### 1.3 检测功能
- [ ] 点击"检测"按钮发送请求
- [ ] Enter 键触发检测
- [ ] 检测结果显示：籽粒数量、耗时、尺寸
- [ ] 结果图片正常显示
- [ ] 置信度分布柱状图
- [ ] 加载骨架屏

### 1.4 参数调节
- [ ] Confidence 滑块 (0.01-1.0)
- [ ] IoU 滑块 (0.01-1.0)
- [ ] 滑块值实时显示

### 1.5 API Key 管理
- [ ] 输入 API Key 并保存到 localStorage
- [ ] 显示/隐藏 Key 切换
- [ ] 无 Key 时检测返回 403
- [ ] 错误 Key 时检测返回 403
- [ ] 正确 Key 时检测成功

### 1.6 其他按钮
- [ ] "清空"按钮清除结果
- [ ] "保存图片"按钮下载结果图
- [ ] 重试机制（最多3次）

---

## 二、API 端点测试

### 2.1 公开端点
- [ ] GET / — 返回 HTML 页面
- [ ] GET /api/health — 返回健康状态
- [ ] GET /api/ping — 返回 pong
- [ ] GET /api/config — 返回配置

### 2.2 认证端点
- [ ] GET /api/key — 需要认证，返回 API Key
- [ ] POST /api/key/regenerate — 重新生成 Key

### 2.3 检测端点
- [ ] POST /api/detect — 上传图片，返回检测结果
- [ ] POST /api/detect — 无图片时返回错误
- [ ] POST /api/detect — 无认证时返回 403

### 2.4 模型端点
- [ ] GET /api/models — 列出可用模型
- [ ] POST /api/select-model — 切换模型（需认证）
- [ ] POST /api/select-model — 路径穿越防护（../ 拒绝）

### 2.5 设备端点
- [ ] GET /api/online-devices — 列出在线设备
- [ ] POST /api/kick-device — 踢出设备（需认证）

### 2.6 管理端点
- [ ] POST /api/toggle-auth — 切换认证开关
- [ ] GET /api/stats — 检测统计

### 2.7 优质照片端点
- [ ] GET /api/valuable-stats — 照片统计
- [ ] POST /api/valuable-toggle — 切换筛选
- [ ] POST /api/valuable-reset — 重置计数
- [ ] POST /api/valuable-open-dir — 打开目录

---

## 三、CLI 工具测试 (agent-harness)

### 3.1 安装
- [ ] pip install -e agent-harness/ 成功
- [ ] grain --help 可用
- [ ] grainon --help 可用
- [ ] grainoff --help 可用
- [ ] grainkey 可用

### 3.2 grain CLI 命令
- [ ] grain detect <image> — 直接检测（无服务器）
- [ ] grain server start — 启动服务器
- [ ] grain server stop — 停止服务器
- [ ] grain server status — 服务器状态
- [ ] grain config show — 显示配置
- [ ] grain config set — 修改配置
- [ ] grain model list — 列出模型
- [ ] grain health — 健康检查
- [ ] grain stats — 统计信息

### 3.3 一键命令
- [ ] grainoff — 停止所有服务
- [ ] grainkey — 显示当前 API Key

---

## 四、管理面板测试 (server_panel.py)

- [ ] 面板启动（python server_panel.py）
- [ ] 服务器启停控制
- [ ] 状态指示灯
- [ ] API Key 显示/复制/重新生成
- [ ] 端口配置 + 认证开关
- [ ] 在线设备列表
- [ ] 实时日志面板
- [ ] 模型选择下拉框
- [ ] Cloudflared 状态检测
- [ ] Tailscale 状态检测

---

## 五、安全测试

- [ ] 路径穿越防护（../ 攻击）
- [ ] X-Forwarded-For 信任限制
- [ ] ScanGuard 双重检测
- [ ] CORS 限制
- [ ] 限速保护
- [ ] API Key 脱敏日志

---

## 六、回归验证

- [ ] test_verification.py 8/8
- [ ] 无敏感信息泄露
- [ ] .gitignore 覆盖所有生成文件
