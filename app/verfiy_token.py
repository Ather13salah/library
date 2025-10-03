from fastapi import Request
from fastapi.responses import JSONResponse
from jose import jwt, JWTError, ExpiredSignatureError
from starlette.middleware.base import BaseHTTPMiddleware
from app.tokens import create_access_token
import os
import logging

logger = logging.getLogger("uvicorn.error")

class VerifyToken(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.secret_key = os.getenv("SECRET_KEY")
        self.algorithm = os.getenv("ALGORITHM")
        self.is_prod = os.getenv("ENV") == "production"

    def decode_token(self, token: str, token_type="access"):
        if not token:
            logger.warning(f"{token_type} token missing")
            return None
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except ExpiredSignatureError:
            logger.warning(f"{token_type} token expired")
            return None
        except JWTError as e:
            logger.error(f"{token_type} token invalid: {e}")
            return None

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # لا تعمل تحقق على كل الـ endpoints
        if not path.startswith("/protected"):
            return await call_next(request)

        token = request.cookies.get("token")
        refresh_token = request.cookies.get("refresh_token")

        logger.info(f"Request path: {path}")
        logger.info(f"Cookies received: token={'yes' if token else 'no'}, refresh={'yes' if refresh_token else 'no'}")

        # 1) جرّب access token
        payload = self.decode_token(token, "access")
        if payload:
            request.state.user = payload.get("sub")
            return await call_next(request)

        # 2) لو access فشل، جرّب refresh
        payload_refresh = self.decode_token(refresh_token, "refresh")
        if payload_refresh:
            user = payload_refresh.get("sub")
            new_token = create_access_token({"sub": user}, minutes=60)
            request.state.user = user

            response = await call_next(request)
            response.set_cookie(
                key="token",
                value=new_token,
                httponly=True,
                max_age=3600,
                samesite="None" if self.is_prod else "Lax",
                secure=self.is_prod,
                path="/",
            )
            logger.info("Issued new access token via refresh")
            return response

        # 3) مفيش أي توكين
        logger.error("Unauthorized request: no valid tokens")
        return JSONResponse({"invalid_token": "/login"}, status_code=401)
