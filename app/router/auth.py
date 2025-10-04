from fastapi import APIRouter, Response
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
            return {"error": "Username is already exists"}
        else:

            token = create_access_token({"sub": user.name}, 60)
            refresh_token = create_access_token({"sub": user.name}, 43200)
            if token == False or refresh_token == False:
                return {"error": "Can not create user"}
            
            
            else:
                hashed_password = bcrypt.hashpw(
                user.password.encode("utf-8"), bcrypt.gensalt()
                )
                id = str(uuid.uuid4())
                cursor.execute(
                    "Insert into users (id,username, user_password,user_email) values(%s,%s,%s,%s)",
                    (id, user.name, hashed_password, user.email),
                )
                conn.commit()
            cursor.close()
            conn.close()

        return {"id":id,"acsses_token": token, "refresh_token": refresh_token}

    except Exception as e:
        return {"error": f"Can not create user {str(e)}"}


@router.post("/login")
async def login(user: UserToLogin):
    """This function for making the login and check the password"""
    try:
        conn = create_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("select * from users where username=%s", (user.name,))
        current_user = cursor.fetchone()
        if not current_user:
            return {"error": "Username is not found"}

        else:
            if current_user["username"] == user.name and bcrypt.checkpw(
                user.password.encode("utf-8"),
                current_user["user_password"].encode("utf-8"),
            ):
                token = create_access_token({"sub": user.name}, 60)
                refresh_token = create_access_token({"sub": user.name}, 43200)
                if token == False or refresh_token == False:
                    return {"error": "Can not create user"}

            else:
                return {"error": "Invalid Username or Password"}
        return {"id":current_user['id'],"acsses_token": token, "refresh_token": refresh_token}

    except Exception as e:
        return {"error": f"Can not Login{str(e)} "}
    
    
 
@router.post('/logout')
async def logout(response: Response):
    try:
        cookie_options = {
            "httponly": True,
            "samesite": "None",
            "secure": True,
            "path": "/"
        }

        response.delete_cookie("token", **cookie_options)
        response.delete_cookie("refresh_token", **cookie_options)
        response.delete_cookie("user_id", **cookie_options)

        return {"message": "Logged out successfully"}
    except Exception as e:
        return {"error": f"Can not log out: "}

