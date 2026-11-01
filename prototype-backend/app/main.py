"""
ZhiQingYu - AI情绪陪伴应用后端主入口
"""
import logging
import os
os.umask(0o077)
from urllib.parse import urlsplit
from fastapi.responses import JSONResponse
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from app.db import engine, Base
from app.api import chat, daily, stats, ai_config
from app.middleware.error_handler import validation_exception_handler, general_exception_handler

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# 创建数据库表
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="ZhiQingYu API",
    description="AI情绪陪伴应用后端API",
    version="0.1.0"
)

# 配置CORS
prototype_origins = [o.strip().rstrip('/') for o in os.getenv("PROTOTYPE_ALLOWED_ORIGINS", "http://localhost:5525,http://127.0.0.1:5525,http://localhost:3000,http://127.0.0.1:3000").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=prototype_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Protect the single-user local API from hostile websites and DNS rebinding.
@app.middleware("http")
async def restrict_local_api(request: Request, call_next):
    allowed_hosts = {h.strip().lower() for h in os.getenv("PROTOTYPE_ALLOWED_HOSTS", "localhost,127.0.0.1,::1").split(",")}
    allowed_origins = {o.strip().rstrip('/') for o in os.getenv("PROTOTYPE_ALLOWED_ORIGINS", "http://localhost:5525,http://127.0.0.1:5525,http://localhost:3000,http://127.0.0.1:3000").split(",")}
    try:
        host = urlsplit("//" + request.headers.get("host", "")).hostname
    except ValueError:
        host = None
    origin = request.headers.get("origin", "").rstrip('/')
    own_origin = str(request.base_url).rstrip('/')
    if host not in allowed_hosts or (origin and origin != own_origin and origin not in allowed_origins):
        return JSONResponse(status_code=403, content={"data": None, "error": {"code": "ORIGIN_DENIED", "message": "Request origin denied"}})
    if not origin and request.headers.get("sec-fetch-site") == "cross-site":
        return JSONResponse(status_code=403, content={"data": None, "error": {"code": "ORIGIN_DENIED", "message": "Request origin denied"}})
    return await call_next(request)


# 注册错误处理器
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

# 注册路由
app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(daily.router, prefix="/api", tags=["daily"])
app.include_router(stats.router, prefix="/api", tags=["stats"])
app.include_router(ai_config.router, prefix="/api", tags=["ai-config"])


@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {"status": "ok", "service": "ZhiQingYu"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=os.getenv("PROTOTYPE_HOST", "127.0.0.1"), port=8000)

