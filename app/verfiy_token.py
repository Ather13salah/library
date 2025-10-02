from fastapi import Request, Response
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

    def check_refresh(self, refresh_token):
        try:
            payload = jwt.decode(
                refresh_token, self.secret_key, algorithms=[self.algorithm]
            )
            user = payload.get("sub")

            # اعمل توكين جديد
            new_token = create_access_token({"sub": user}, minutes=60)
            return new_token
        except (ExpiredSignatureError,JWTError):
            return None

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # السماح بالمسارات العامة
        if not path.startswith("/protected"):
            return await call_next(request)

        token = request.cookies.get("token")
        refresh_token = request.cookies.get("refresh_token")


        try:
            if token is None:
                new_token =  self.check_refresh(refresh_token)
                if not new_token:
                    return JSONResponse({"invalid_token": "/login"}, status_code=401)
                response = await call_next(request)
                response.set_cookie(
                    key="token",
                    value=new_token,
                    httponly=True,
                    max_age=3600,
                    samesite="none",
                    secure=True,
                )
                return response
            
            else:
                jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
                return await call_next(request)
        except ExpiredSignatureError:
            new_token =  self.check_refresh(refresh_token)
            if not new_token:
                return JSONResponse({"invalid_token": "/login"}, status_code=401)
            response = await call_next(request)
            response.set_cookie(
                key="token",
                value=new_token,
                httponly=True,
                max_age=3600,
                samesite="none",
                secure=True,
            )
            return response
        except JWTError:
            return JSONResponse({"invalid_token": "/login"}, status_code=401)
