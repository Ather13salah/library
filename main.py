import pytesseract
from PIL import Image
import requests
import mysql.connector as sql
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from jose import jwt
import os
import bcrypt
from dotenv import load_dotenv
from datetime import datetime, timedelta
from user import UserToLogin,UserToSignUp
app = FastAPI() #this object from fast api to make 

origins = [
    "http://localhost:3000", 
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

env = load_dotenv() 
# get the variables of dotenv 
SECRET_KEY = os.getenv('SECRET_KEY')
ALGROTHEM = os.getenv('ALGROTHEM')
EXPIRE = os.getenv('EXPIRE_AFTER')


def create_connection():
    """Create Connection with database"""
    return sql.connect(
        host = 'localhost',
        user = 'root',
        password = 'ather2010',
        database = 'library',
        auth_plugin = 'mysql_native_password'
    )

def create_acsses_token(data: dict):
    try:
        
        expire = datetime.now() + timedelta(minutes = int(EXPIRE))
        data.update({'exp':expire})
        token = jwt.encode(
            data,
            SECRET_KEY,
            algorithm = ALGROTHEM

        )
        return token

    except:
        return False
    

@app.post('/signup')
async def signup(user:UserToSignUp):
    try:
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute(
            'select * from users where username=%s',(user.name,)
        )
        name = cursor.fetchone()
        if name: 
            return{
                "error":"Username is already exists"
            }
        else:
           
            token = create_acsses_token({"sub":user.name})
            hashed_password = bcrypt.hashpw('ather2010'.encode('utf-8'),bcrypt.gensalt())
            if  not token:
                return {

                    "error":"Can not create user"
                }
            else:
                cursor.execute(
                    'Insert into users (username, user_password,user_email, token) values(%s,%s,%s, %s)',
                    (user.name,hashed_password,user.email,token)
                )
                conn.commit()
            cursor.close()
            conn.close()
            return{"acsses_token":token}

    except:
        return {"error":"Can not create user"}

@app.post('/login')
async def login(user:UserToLogin):
    '''This function for making the login and check the password '''
    try:
        conn = create_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            'select * from users where username=%s',(user.name,)
        )
        current_user = cursor.fetchone()
        if not current_user: 
            return{
                "error":"Username is not found"
            }
        
        else:
            if current_user['username'] == user.name and \
            bcrypt.checkpw(user.password.encode("utf-8"), current_user['user_password'].encode("utf-8")) :
                return{
                    'succses':True,
                    "acsses_token":current_user['token']
                }
            else:
                return{
                    "error":"Invalid Username or Password"
                }      

    except :
        return {"error":"Can not Login"}
    

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
# this to set the path of app to run it 
@app.post('/upload-book')
async def extract_text(file: UploadFile = File(...)):
    API_KEY = 'AIzaSyCcX--GAdN4QxckDrMxSFNkhWUhsQldMsQ'
   
    try:
        img = Image.open(file.file)
        query = pytesseract.image_to_string(img, lang='en+ara').replace("\n", "+")
        # url = f"https://www.googleapis.com/books/v1/volumes?q={query}:keyes&key={API_KEY}"        

        # request = requests.get(url)
        # data = request.json()
        return{
            "text":query
        }

    except :
        ...
    
