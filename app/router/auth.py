from fastapi import APIRouter, Response, Request
from jose import jwt, JWTError, ExpiredSignatureError
from fastapi.responses import JSONResponse
from app.router.user import UserToLogin, UserToSignUp
from app.db import create_connection
import bcrypt
from app.tokens import create_access_token
import uuid
import os
from dotenv import load_dotenv


load_dotenv()
router = APIRouter(prefix="/auth")

@router.post("/signup")
async def signup(user: UserToSignUp, response: Response):
    try:
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute("select * from users where username=%s", (user.name,))
        name = cursor.fetchone()
        if name:
            return {"error": "Username already exists"}

        token = create_access_token({"sub": user.name}, 60)
        refresh_token = create_access_token({"sub": user.name}, 43200)

        if not token or not refresh_token:
            return {"error": "Cannot create user"}

        hashed_password = bcrypt.hashpw(user.password.encode("utf-8"), bcrypt.gensalt()).decode('utf-8')
        user_id = str(uuid.uuid4())

        cursor.execute(
            "INSERT INTO users (id, username, user_password, user_email) VALUES (%s, %s, %s, %s)",
            (user_id, user.name, hashed_password, user.email),
        )
        conn.commit()
        cursor.close()
        conn.close()

        response.set_cookie(
            key="token",
            value=token,
            httponly=True,
            secure=True,
            samesite="None",
            max_age=3600,
        )
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=True,
            samesite="None",
            max_age=43200,
        )

        return {"id": user_id, "message": "Loggedin"}

    except Exception as e:
        return {"error": f"Cannot create user:"}


@router.post("/login")
async def login(user: UserToLogin, response: Response):
    try:
        conn = create_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("select * from users where username=%s", (user.name,))
        current_user = cursor.fetchone()
        if not current_user:
            return {"error": "Username not found"}

        if not bcrypt.checkpw(
            user.password.encode("utf-8"), current_user["user_password"].encode("utf-8")
        ):
            return {"error": "Invalid username or password"}

        token = create_access_token({"sub": user.name}, 60)
        refresh_token = create_access_token({"sub": user.name}, 43200)

        if not token or not refresh_token:
            return {"error": "Cannot create token"}

        response.set_cookie(
            key="token",
            value=token,
            httponly=True,
            secure=True,
            samesite="None",
            max_age=3600,
        )
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=True,
            samesite="None",
            max_age=43200,
        )

        return {"id": current_user["id"], "message": "Loggedin"}

    except Exception as e:
        return {"error": f"Cannot login"}

def check_refresh(refresh_token):
    refresh_payload = jwt.decode(
        refresh_token,
        os.getenv("SECRET_KEY"),
        algorithms=[os.getenv("ALGORITHM")],
    )
    new_token = create_access_token(
        {"sub": refresh_payload.get("sub")}, minutes=60
    )
    response = JSONResponse(
        {"user": refresh_payload.get("sub"), "new_token": new_token}
        )
    response.set_cookie(
        key="token",
        value=new_token,
        httponly=True,
        samesite="None",
        secure=True,
    )
    return response

@router.get("/me") 
async def get_me(request: Request):
    token = request.cookies.get("token")
    refresh_token = request.cookies.get("refresh_token")

    if not token and not refresh_token:
        return JSONResponse({"detail": "Not authenticated"}, status_code=401)

    try:
        if token is None:
            return check_refresh(refresh_token)
        payload = jwt.decode(
            token, os.getenv("SECRET_KEY"), algorithms=[os.getenv("ALGORITHM")]
        )
        return {"user": payload.get("sub"), "status": "active"}
    except ExpiredSignatureError:
        # انتهت صلاحية الـ access token → نحاول نستخدم refresh
        try:
           return check_refresh(refresh_token)
        except Exception:
            return JSONResponse({"detail": "Session expired"}, status_code=401)
    except JWTError:
        return JSONResponse({"detail": "Invalid token"}, status_code=401)


@router.post("/logout")
async def logout(response: Response):
    try:
        response = JSONResponse(content={'message':"Logged out Successfully"})
        response.delete_cookie(
            key="token",
            httponly=True,
            secure=True,
            samesite="None",
        )
        response.delete_cookie(
            key="refresh_token",
            httponly=True,
            secure=True,
            samesite="None",
        )
        return response
    except:
        return {"error":"Can not logout "}
    
