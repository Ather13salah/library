from jose import jwt, JWTError
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

# get the variables of dotenv 
secret_key = os.getenv('SECRET_KEY')
algorithm = os.getenv('ALGORITHM')   # ✅ مظبوط spelling

def create_access_token(data: dict, minutes: int):
    try:
        expire = datetime.utcnow() + timedelta(minutes=minutes)
        payload = data.copy()
        payload.update({'exp': expire})

        token = jwt.encode(
            payload,
            secret_key,
            algorithm=algorithm   # ✅ string مش list
        )
        return token

    except Exception as e:
        print("Error while creating token:", e)
        return False
