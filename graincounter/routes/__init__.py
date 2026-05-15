"""路由注册 — 将拆分后的路由模块统一注册到 FastAPI app"""
from graincounter.routes import admin, models, devices, detect, pages


def register_all_routes(app):
    """将所有路由模块注册到 app（模块导入即注册，此函数用于显式导入触发）"""
    # 各模块在导入时已通过 app.include_router 或直接 @app 装饰注册
    # 此处保持各模块独立：调用方只需 import graincounter.routes 触发所有子模块导入
    pass
