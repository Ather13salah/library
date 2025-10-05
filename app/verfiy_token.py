from fastapi import Request
from fastapi.responses import JSONResponse
from jose import jwt, JWTError, ExpiredSignatureError
from starlette.middleware.base import BaseHTTPMiddleware
from app.tokens import create_access_token
import os


class VerifyToken(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.secret_key = os.getenv("SECRET_KEY")
        self.algorithm = os.getenv("ALGORITHM")

    def decode_token(self, token):
        """Decode JWT token safely"""
        if not token:
            return None
        try:
            return jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
        except (ExpiredSignatureError, JWTError):
            return None

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # ✅ 1) Allow all OPTIONS requests to pass (for CORS preflight)
        if request.method == "OPTIONS":
            return await call_next(request)

        # ✅ 2) Allow public endpoints (not protected)
        if not path.startswith("/protected"):
            return await call_next(request)

        # ✅ 3) Get cookies
        token = request.cookies.get("token")
        refresh_token = request.cookies.get("refresh_token")

        # ✅ 4) Verify access token
        payload = self.decode_token(token)
        if payload:
            request.state.user = payload.get("sub")
            return await call_next(request)

        # ✅ 5) If access expired, try refresh
        payload_refresh = self.decode_token(refresh_token)
        if payload_refresh:
            user = payload_refresh.get("sub")

            # create a new access token
            new_token = create_access_token({"sub": user}, minutes=60)
            request.state.user = user

            # continue request
            response = await call_next(request)

            # set new cookie
            response.set_cookie(
                key="token",
                value=new_token,
                httponly=True,
                max_age=3600,
                samesite="None",
                secure=True,
                path="/",
            )
            return response

        # ✅ 6) If both invalid
        return JSONResponse({"invalid_token": "/login"}, status_code=401)
