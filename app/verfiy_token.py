from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from jose import jwt, ExpiredSignatureError, JWTError
from app.tokens import create_access_token
import os
import json

class VerifyToken(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.secret_key = os.getenv("SECRET_KEY")
        self.algorithm = os.getenv("ALGORITHM")

    def decode_token(self, token):
        if not token:
            return None
        try:
            return jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
        except (ExpiredSignatureError, JWTError):
            return None

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if not path.startswith("/protected"):
            return await call_next(request)
        print(f'Cookies:{request.cookies}')
        token = request.cookies.get("token")
        refresh_token = request.cookies.get("refresh_token")
        print(f"Token:{token} and Refresh Token:{refresh_token}")

        payload = self.decode_token(token)
        if payload:
            request.state.user = payload.get("sub")
            return await call_next(request)

        payload_refresh = self.decode_token(refresh_token)
        if payload_refresh:
            user = payload_refresh.get("sub")
            new_token = create_access_token({"sub": user}, minutes=60)
            request.state.user = user

            # call endpoint
            response = await call_next(request)

            # حاول تعديل response إذا كان JSON
            if response.media_type == "application/json":
                original_body = b""
                async for chunk in response.body_iterator:
                    original_body += chunk
                data = json.loads(original_body)
                data["new_access_token"] = new_token
                response = JSONResponse(content=data, status_code=200)

            # set cookie for frontend
            
            return response

        return JSONResponse({"invalid_token": "/login"}, status_code=401)
