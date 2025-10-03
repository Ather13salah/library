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
        # Guard: don't try to decode None
        if not refresh_token:
            return None
        try:
            # decode will raise ExpiredSignatureError or JWTError if invalid/expired
            payload = jwt.decode(
                refresh_token, self.secret_key, algorithms=[self.algorithm]
            )
            user = payload.get("sub")
            # create new access token
            new_token = create_access_token({"sub": user}, minutes=60)
            return new_token
        except (ExpiredSignatureError, JWTError):
            return None
        except Exception:
            # unexpected error: return None so caller treats it as missing/invalid
            return None

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # allow public routes
        if not path.startswith("/protected"):
            return await call_next(request)

        token = request.cookies.get("token")
        refresh_token = request.cookies.get("refresh_token")

        try:
            if not token:
                # only attempt refresh if refresh_token is present
                new_token = self.check_refresh(refresh_token)
                if not new_token:
                    return JSONResponse({"invalid_token": "/login"}, status_code=401)

                response = await call_next(request)
                response.set_cookie(
                    key="token",
                    value=new_token,
                    httponly=True,
                    max_age=3600,
                    samesite="None",  # ensure 'None' and secure=True are used together in production
                    secure=True,
                )
                return response
            else:
                # token present -> validate it
                jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
                return await call_next(request)

        except ExpiredSignatureError:
            new_token = self.check_refresh(refresh_token)
            if not new_token:
                return JSONResponse({"invalid_token": "/login"}, status_code=401)
            response = await call_next(request)
            response.set_cookie(
                key="token",
                value=new_token,
                httponly=True,
                max_age=3600,
                samesite="None",
                secure=True,
            )
            return response
        except JWTError:
            return JSONResponse({"invalid_token": "/login"}, status_code=401)
        except Exception as e:
            # Catch-all to avoid crashing middleware on unexpected errors
            return JSONResponse({"error": "internal_server_error"}, status_code=500)
