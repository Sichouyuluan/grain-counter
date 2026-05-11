# 🌾 小麦籽粒检测 Web 服务

基于 YOLOv8 的小麦灌浆期籽粒自动检测与计数 Web 服务。

## 功能

- **AI 检测**：YOLOv8 ONNX 自动识别小麦籽粒
- **Web 界面**：支持手机/平板/桌面浏览器
- **API Key 认证**：安全访问控制，支持热切换
- **在线设备追踪**：实时查看连接设备，支持踢出
- **限速保护**：防止滥用
- **优质照片筛选**：自动保存低置信度图片用于模型优化
- **Tailscale 穿墙**：支持远程访问
- **响应压缩**：低带宽优化

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动管理面板（推荐）
python server_panel.py

# 3. 或直接启动 Web 服务器
python web_server.py --port 8000

# 4. 浏览器访问
http://localhost:8000
```

## 项目结构

```
├── web_server.py           # FastAPI 后端入口
├── server_panel.py         # 桌面管理面板
├── graincounter/           # 共享逻辑包
├── templates/
│   └── index.html          # 前端页面
├── models/                 # YOLO 模型
├── Valuable photos/        # 优质训练照片
└── config.yaml             # 配置文件
```

## API 接口

| 路由 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 首页 |
| `/api/health` | GET | 健康检查 |
| `/api/ping` | GET | 心跳检测 |
| `/api/detect` | POST | 图片检测 |
| `/api/key` | GET | 获取 API Key |
| `/api/toggle-auth` | POST | 切换认证 |
| `/api/online-devices` | GET | 在线设备 |
| `/api/kick-device` | POST | 踢出设备 |
| `/api/valuable-stats` | GET | 优质照片统计 |
| `/api/valuable-toggle` | POST | 切换筛选 |
| `/api/valuable-reset` | POST | 重置计数 |
| `/api/valuable-open-dir` | POST | 打开目录 |

## 启动参数

```bash
python web_server.py --port 8080 --no-auth --api-key mykey123
```

## 技术栈

- Python 3.8+ / FastAPI / Uvicorn
- YOLOv8 (Ultralytics)
- Tailwind CSS
- OpenCV
