from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse
from app.router.user import UserToLogin, UserToSignUp
from app.db import create_connection
import bcrypt
from app.tokens import create_access_token
import uuid

router = APIRouter(prefix="/auth")

@router.post("/signup")
async def signup(user: UserToSignUp):
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

        hashed_password = bcrypt.hashpw(user.password.encode("utf-8"), bcrypt.gensalt())
        user_id = str(uuid.uuid4())

        cursor.execute(
            "INSERT INTO users (id, username, user_password, user_email) VALUES (%s, %s, %s, %s)",
            (user_id, user.name, hashed_password, user.email),
        )
        conn.commit()
        cursor.close()
        conn.close()

        response = JSONResponse(
            content={
                "id": user_id,
                "access_token": token,
                "refresh_token": refresh_token,
            },
            status_code=200
        )
        # ✅ Set cookies
        cookie_opts = {"httponly": True, "secure": True, "samesite": "None", "path": "/"}
        response.set_cookie(key="token", value=token, **cookie_opts)
        response.set_cookie(key="refresh_token", value=refresh_token, **cookie_opts)
        response.set_cookie(
            key="user_id",
            value=user_id,
            httponly=False,
            secure=True,
            samesite="None",
            path="/",
        )


        return response

    except Exception as e:
        return {"error": f"Cannot create user: {str(e)}"}


@router.post("/login")
async def login(user: UserToLogin, response: Response):
    try:
        conn = create_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("select * from users where username=%s", (user.name,))
        current_user = cursor.fetchone()
        if not current_user:
            return {"error": "Username not found"}

        if not bcrypt.checkpw(user.password.encode("utf-8"), current_user["user_password"].encode("utf-8")):
            return {"error": "Invalid username or password"}

        token = create_access_token({"sub": user.name}, 60)
        refresh_token = create_access_token({"sub": user.name}, 43200)

        if not token or not refresh_token:
            return {"error": "Cannot create token"}

        response = JSONResponse(
            content={
                "id": current_user["id"],
                "access_token": token,
                "refresh_token": refresh_token,
            },
            status_code=200
        )
        # ✅ Set cookies
        cookie_opts = {"httponly": True, "secure": True, "samesite": "None", "path": "/"}
        response.set_cookie(key="token", value=token, **cookie_opts)
        response.set_cookie(key="refresh_token", value=refresh_token, **cookie_opts)
        response.set_cookie(
            key="user_id",
            value=current_user["id"],
            httponly=False,
            secure=True,
            samesite="None",
            path="/",
        )
        print(f"Response is: {response}")
        return response

    except Exception as e:
        return {"error": f"Cannot login: {str(e)}"}


@router.post("/logout")
async def logout(response: Response):
    try:
        cookie_opts = {"httponly": True, "samesite": "None", "secure": True, "path": "/"}
        response.delete_cookie("token", **cookie_opts)
        response.delete_cookie("refresh_token", **cookie_opts)
        response.delete_cookie("user_id", **cookie_opts)
        return {"message": "Logged out successfully"}
    except Exception as e:
        return {"error": f"Cannot log out: {str(e)}"}
