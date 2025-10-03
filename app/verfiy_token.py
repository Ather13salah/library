from fastapi import Request
from fastapi.responses import JSONResponse
from jose import jwt, JWTError, ExpiredSignatureError
from starlette.middleware.base import BaseHTTPMiddleware
from app.tokens import create_access_token
import os
from dotenv import load_dotenv

load_dotenv()

class VerifyToken(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.secret_key = os.getenv("SECRET_KEY")
        self.algorithm = os.getenv("ALGORITHM")

    def check_refresh(self, refresh_token: str):
        try:
            payload = jwt.decode(refresh_token, self.secret_key, algorithms=[self.algorithm])
            user = payload.get("sub")
            return create_access_token({"sub": user}, minutes=60)
        except (ExpiredSignatureError, JWTError):
            return None

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # استثناء المسارات الغير محمية
        if not path.startswith("/protected"):
            return await call_next(request)

        token = request.cookies.get("token")
        refresh_token = request.cookies.get("refresh_token")

        def set_new_token(response, new_token):
            response.set_cookie(
                key="token",
                value=new_token,
                httponly=True,
                max_age=3600,
                samesite="None",
                secure=True,
            )
            return response

        try:
            if token:
                jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
                return await call_next(request)

            if refresh_token:
                new_token = self.check_refresh(refresh_token)
                if new_token:
                    response = await call_next(request)
                    return set_new_token(response, new_token)

            return JSONResponse({"invalid_token": "/login"}, status_code=401)

        except ExpiredSignatureError:
            if refresh_token:
                new_token = self.check_refresh(refresh_token)
                if new_token:
                    response = await call_next(request)
                    return set_new_token(response, new_token)

            return JSONResponse({"invalid_token": "/login"}, status_code=401)

        except JWTError:
            return JSONResponse({"invalid_token": "/login"}, status_code=401)
