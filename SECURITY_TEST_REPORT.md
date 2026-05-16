# 安全测试报告 — Grain Counter v2.1.0

> 测试日期：2026-05-15
> 测试对象：http://localhost:8000 / http://[LAN_IP]:8000
> 测试方法：黑盒 + 源码审计（项目目录 `[PROJECT_DIR]`）

---

## 一、测试环境

| 项目 | 信息 |
|------|------|
| 框架 | FastAPI + uvicorn |
| 模型 | ONNX YOLO (grain_yolo26m_v1.onnx) |
| 认证 | Bearer Token (secrets.token_urlsafe) |
| 限速 | 60次/分钟（通用），30次/分钟（检测）|
| CORS | allow_origins=[]（已关闭跨域）|
| 保护 | ScanGuard 扫描防护 + 3次触发自动关机 |

---

## 二、漏洞清单

### 🔴 CRITICAL-1：`/api/select-model` 路径穿越 + 无认证

**涉及文件**：`graincounter/routes/models.py` 第 33-46 行

**问题描述**：
1. 接口未添加 `Depends(verify_api_key)`，任何人可直接调用
2. `model_name` 来自用户 JSON 输入，直接拼入 `os.path.join(models_dir, model_name)`，没有过滤 `../`

**测试过程**：
```bash
# 测试1：尝试读取 models 目录上级的 config.yaml
curl -X POST http://localhost:8000/api/select-model \
  -H "Content-Type: application/json" \
  -d '{"model": "../config.yaml"}'

# 测试2：尝试读取 .api_key 密钥文件
curl -X POST http://localhost:8000/api/select-model \
  -H "Content-Type: application/json" \
  -d '{"model": "../.api_key"}'

# 测试3：探索系统文件是否存在
curl -X POST http://localhost:8000/api/select-model \
  -H "Content-Type: application/json" \
  -d '{"model": "../../Windows/System32/drivers/etc/hosts"}'
```

**测试结果**：

| 测试 | 输入 | 返回 | 说明 |
|------|------|------|------|
| 1 | `../config.yaml` | 500 "模型加载失败: 'backbone'" | 文件存在，YOLO尝试加载失败 |
| 2 | `../.api_key` | **200 `{"ok": true}`** | API密钥文件被"成功"加载为模型 |
| 3 | `../../Windows/...` | 404 "模型文件不存在" | 文件不存在 |

**实际影响**：
- ✅ **模型被替换**：`.api_key` 文件被设为当前模型，`config.yaml` 中的 `model_path` 被持久化写入
- ✅ **文件存在性探测**：404 = 文件不存在，500/200 = 文件存在
- ✅ **检测功能瘫痪**：模型换成无效文件后，所有 `/api/detect` 请求报错
- ✅ **重启后仍生效**：因为写入了 `config.yaml`

**修复建议**：
```python
# models.py select-model 函数修改

# 1. 加上认证依赖
async def select_model(request: Request, _: str = Depends(verify_api_key)):
    ...

# 2. model_name 做安全校验
import os
model_name = data.get("model")
if not model_name:
    raise ...
# 禁止路径穿越
if os.path.basename(model_name) != model_name:
    raise HTTPException(400, detail={"error": True, "message": "无效的模型名称"})
# 只允许 .onnx 后缀
if not model_name.lower().endswith(".onnx"):
    raise HTTPException(400, detail={"error": True, "message": "仅支持 .onnx 模型文件"})
```

---

### 🔴 CRITICAL-2：ScanGuard 可被利用实现 DoS 关机

**涉及文件**：`graincounter/guard.py` 第 10-60 行

**问题描述**：
当前逻辑：5秒内 404/403/429 错误 > 20 次 → 5分钟保护模式 → 累计3次 → 服务器自杀

由于 X-Forwarded-For 伪造可绕过限速（见 HIGH-3），攻击者可以轻松触发。

**测试过程**：
```bash
# 用 XFF 伪造25个不同IP，同时发送25个404请求
for i in $(seq 1 25); do
  curl -s -o /dev/null -w "%{http_code} " \
    -H "X-Forwarded-For: 10.99.99.$i" \
    http://localhost:8000/api/nonexistent_$i &
done
wait

# 检查是否进入保护模式
curl http://localhost:8000/api/ping
```

**测试结果**：
```text
=== 发送25个请求 ===
404 404 404 404 404 404 404 404 404 404
404 404 404 404 404 404 404 404 404 404
503 503 503 503 503   ← 触发保护，后续请求被拒绝

=== 检查保护状态 ===
{"error":"服务器进入保护模式，请298秒后再试"}
```

**攻击路径**：
```
第1轮：25个404请求（5秒内）→ 保护模式5分钟
第2轮：25个404请求            → 保护模式5分钟
第3轮：25个404请求            → 服务器自杀（SIGTERM）

总计：~63个请求，约10分钟，无需认证，服务器永久下线
```

**修复建议**：见第四章 ScanGuard 改进方案。

---

### 🟡 HIGH-1：多个管理接口缺少认证

**涉及文件**：
- `graincounter/routes/models.py` 第 33 行 — `/api/select-model`
- `graincounter/routes/pages.py` 第 54-76 行 — `/api/valuable-toggle`、`/api/valuable-reset`、`/api/valuable-open-dir`

**测试过程**：
```bash
# 无需 API Key，直接调用
curl -X POST http://localhost:8000/api/valuable-toggle    # 切换优质照片保存
curl -X POST http://localhost:8000/api/valuable-reset      # 重置保存计数
curl -X POST http://localhost:8000/api/valuable-open-dir   # 打开服务器Explorer窗口
curl -X POST http://localhost:8000/api/select-model \
  -H "Content-Type: application/json" \
  -d '{"model": "../.api_key"}'                            # 切换模型
```

**测试结果**：

| 接口 | 认证要求 | 测试结果 |
|------|----------|----------|
| `/api/valuable-toggle` | ❌ 无 | `{"ok": true, "enable": false}` — 成功关闭 |
| `/api/valuable-reset` | ❌ 无 | `{"ok": true, "saved_count": 0}` — 成功重置 |
| `/api/valuable-open-dir` | ❌ 无 | `{"ok": true}` — 服务器弹出 Explorer 窗口 |
| `/api/select-model` | ❌ 无 | `{"ok": true}` — 成功切换模型 |

**修复建议**：
```python
# 给以下接口统一添加认证依赖
# pages.py
@router.post("/api/valuable-toggle")
async def valuable_toggle(_: str = Depends(verify_api_key)):  # 加这行
    ...

@router.post("/api/valuable-reset")
async def valuable_reset(_: str = Depends(verify_api_key)):   # 加这行
    ...

@router.post("/api/valuable-open-dir")
async def valuable_open_dir(_: str = Depends(verify_api_key)):  # 加这行
    ...

# models.py
@router.post("/api/select-model")
async def select_model(request: Request, _: str = Depends(verify_api_key)):  # 加这行
    ...
```

---

### 🟡 HIGH-2：文件名路径穿越（文件写入）

**涉及文件**：`graincounter/valuable.py` 第 76-78 行

**问题描述**：
`check_and_save()` 中 `file.filename` 直接参与文件保存路径拼接，可写入到 Valuable photos 目录之外。

```python
# 当前代码
base_name = os.path.splitext(filename)[0]  # filename 来自用户上传
save_name = f"{base_name}_{timestamp}.jpg"
save_path = os.path.join(self._valuable_dir, save_name)  # 危险：可穿越
cv2.imwrite(save_path, img_bgr, ...)
```

**攻击场景**：
上传文件时设 `filename="../../../AppData/Roaming/evil"`，则：
- `save_path` → `Valuable photos/../../../AppData/Roaming/evil_20260515_220000.jpg`
- 实际写入 → `../AppData/Roaming/evil_20260515_220000.jpg`

> 注：此漏洞需 API Key（通过 `/api/detect` 上传触发），且写入内容是 JPEG 图片，不能直接执行，但仍属于任意路径写入。

**修复建议**：
```python
# valuable.py check_and_save 方法中
base_name = os.path.splitext(os.path.basename(filename))[0]  # 只取文件名，丢掉路径
save_name = f"{base_name}_{timestamp}.jpg"
save_path = os.path.join(self._valuable_dir, save_name)
```

---

### 🟡 HIGH-3：X-Forwarded-For 伪造

**涉及文件**：`graincounter/middleware.py` 第 25-27 行

**问题描述**：
直接信任 HTTP 请求头 `X-Forwarded-For`，不做任何验证。

```python
# 当前代码
xff = request.headers.get("X-Forwarded-For")
if xff:
    client_ip = xff.split(",")[0].strip()  # 攻击者可随意伪造
```

**测试过程**：
```bash
# 每次换一个XFF值，获得全新限速配额
for i in $(seq 1 5); do
  curl -s -o /dev/null -w "%{http_code} " \
    -H "X-Forwarded-For: 10.0.0.$i" \
    http://localhost:8000/api/ping
done
# 结果：200 200 200 200 200 — 全部通过
```

**影响范围**：
- ✅ 限速绕过 — 每次换IP得全新配额
- ✅ 封禁绕过 — 被封禁了换IP即可
- ✅ 设备追踪污染 — 虚假设备出现在在线列表
- ✅ 辅助 ScanGuard DoS 攻击

**修复建议**：

方案A（你使用了反向代理时）：
```python
# 只信任已知代理的 XFF
KNOWN_PROXIES = {"127.0.0.1", "::1", "192.168.x.x"}  # 改成你隧道服务的IP

xff = request.headers.get("X-Forwarded-For")
if xff and request.client.host in KNOWN_PROXIES:
    client_ip = xff.split(",")[-1].strip()  # 取最右边的（最靠近源）
```

方案B（直连，没有代理时）：
```python
# 直接删除XFF信任逻辑，始终用真实IP
client_ip = request.client.host
```

---

### 🟠 MEDIUM-1：`/api/stats` 缺少认证

**涉及文件**：`graincounter/routes/admin.py` 第 56-62 行

**测试**：
```bash
curl http://localhost:8000/api/stats
# 返回：total、today、errors、uptime、top_ips、guard状态
```

返回了内部统计数据、客户端IP排名、Guard状态。外部攻击者可以用来监控服务器状态、判断保护模式是否过期。

**修复**：加上 `_: str = Depends(verify_api_key)`。

---

### 🟠 MEDIUM-2：信息公开接口泄露敏感信息

以下接口无需认证即可访问，泄露服务器内部信息：

| 接口 | 泄露内容 |
|------|----------|
| `/api/health` | 模型文件**完整绝对路径** `[PROJECT_DIR]/models/...` |
| `/api/config` | 版本号、上传限制、auth状态 |
| `/api/models` | 所有已安装模型的文件名和大小 |

**建议**：如果能接受前端也需要API Key，统一加上认证；或者减少返回内容（去掉绝对路径，只返回相对路径）。

---

## 三、ScanGuard 改进方案

### 3.1 当前问题

| 问题 | 说明 |
|------|------|
| 只看总错误数 | 正常误触和扫描攻击无法区分 |
| 触发门槛低 | 21次/5秒太容易达到 |
| 3次就关机 | 容错空间太小 |
| 保护时间太长 | 5分钟对个人使用来说偏长 |

### 3.2 新方案：双重检测机制

```
检测窗口：10秒
触发条件（满足任一即触发）：
  条件A（扫描检测）：≥ 15 个【不同路径】返回 404/403
  条件B（洪水检测）：≥ 50 个【总错误】  返回 404/403/429

触发后动作：
  进入保护模式 3 分钟（所有请求返回 503）
  累计触发 5 次 → 服务器关机

关机后不自动重启（保持现有行为）
```

### 3.3 为什么这样设计

| 攻击方式 | 触发条件 | 举例 |
|---------|---------|------|
| 指纹扫描 | 条件A（15个不同路径） | 扫 `/admin`、`/.env`、`/wp-admin`... |
| 单路径 DDoS | 条件B（50个总错误） | 肉鸡同时打 `/api/detect` |
| 混合扫描 | 两者都可能 | 真实扫描器既换路径又大量请求 |
| 正常误触 | **都不触发** | 同个URL重复404只计入条件B（门槛50够高） |

### 3.4 需要修改的代码

**文件**：`graincounter/guard.py`

改动点：
1. `__init__` 参数调整：
   - `window_seconds`: 5 → 10
   - `threshold`: 20 → 15（用于路径数检测）
   - 新增 `flood_threshold`: 50（用于总错误数检测）
   - `protect_minutes`: 5 → 3
   - `stop_after`: 3 → 5

2. `check_and_record` 逻辑改为双重检测：
   - 统计窗口内**不同路径**的 404/403 数量
   - 统计窗口内**总** 404/403/429 数量
   - 任一超过阈值 → 触发保护

3. 可选：新增 `get_detection_detail()` 返回触发原因，方便调试

### 3.5 参数对比

| 参数 | 旧值 | 新值 |
|------|------|------|
| 检测窗口 | 5秒 | 10秒 |
| 扫描阈值（不同路径） | 20（总错误） | 15（不同路径） |
| 洪水阈值（总错误） | — | 50 |
| 保护时长 | 5分钟 | 3分钟 |
| 关机前触发次数 | 3次 | 5次 |

---

## 四、修复优先级排序

| 优先级 | 问题 | 工作量 | 风险 |
|--------|------|--------|------|
| 🔴 P0 | ScanGuard 改进（防止被利用关机） | 中 | 不改的话攻击者能关你服务器 |
| 🔴 P0 | `/api/select-model` 加认证 + 防路径穿越 | 小 | 模型可被替换，检测瘫痪 |
| 🟡 P1 | 所有管理接口加认证 | 小 | 3-4个接口各加一行代码 |
| 🟡 P1 | X-Forwarded-For 伪造修复 | 小 | 去掉或限制 XFF 信任 |
| 🟡 P1 | 文件名路径穿越修复 | 极小 | 加一个 basename 调用 |
| 🟠 P2 | `/api/stats` 加认证 | 极小 | 一行代码 |
| 🟠 P2 | 信息公开接口收敛 | 小 | 看需求决定是否改动 |

---

## 五、未发现问题的区域

以下方面经检查未发现漏洞：

- ✅ CORS 配置：`allow_origins=[]` 正确拒绝所有跨域
- ✅ API Key 比较：使用 `secrets.compare_digest()` 防时序攻击
- ✅ API Key 存储：本地文件 `.api_key`（需本地访问才能读取）
- ✅ 文件上传大小限制：`max_upload_mb` 生效
- ✅ 检测参数校验：`conf`/`iou` 范围 `0.01-1.0`
- ✅ 模型加载：线程安全，使用 `asyncio.Semaphore(2)` 限制并发
- ✅ 日志脱敏：`PinHidingFilter` 隐藏 API Key / Token
- ✅ 无 SQL 注入风险（无数据库）
- ✅ 无命令注入（valuable-open-dir 路径来自配置，非用户输入）
- ✅ 日志系统：`RotatingFileHandler` 10MB/5备份，不会被打爆

---

*报告完毕，请交后端同学逐一修复。*
