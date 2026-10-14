from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from utils.agent_logger import get_logger
import os
from dotenv import load_dotenv

load_dotenv()

logger = get_logger("webapp")

USER_ID = os.getenv("USER_ID")
USER_PASSWORD = os.getenv("USER_PASSWORD")
USER_TOKEN = os.getenv("USER_TOKEN")
USER_EXTERNAL_ID = os.getenv("USER_EXTERNAL_ID")

# 生命周期管理器
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting application...")
    yield
    logger.info("Shutting down application...")

app = FastAPI(lifespan=lifespan)

# 中间件

class HeaderMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        logger.debug("custom header for request url: %s", request.url)
        
        response = await call_next(request)
        response.headers["X-custom-header"] = "by Sagt Agent"
        return response

app.add_middleware(HeaderMiddleware)


# 路由
@app.get("/sagt/health")
async def health():
    logger.info("sagt health check")
    return {"status": "ok"}

@app.post("/sagt/get_token")
async def get_token(request: Request):
    logger.info("sagt get_token")
    body = await request.json()
    password = body.get("password")
    uid = body.get("user_id")

    if not uid or not password:
        return Response(status_code=403)

    if uid == USER_ID and password == USER_PASSWORD:
        logger.info("sagt get_token success: %s", uid)
        return {
            "status": "ok",
            "token": USER_TOKEN,
            "user_id": USER_ID,
            "external_id": USER_EXTERNAL_ID
        }
    else:
        logger.info("sagt get_token failed: %s", uid)
        return Response(status_code=403)