from fastapi.staticfiles import StaticFiles
from app.router import auth
from app.router import protected
from app.verfiy_token import VerifyToken

from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware




app = FastAPI() #this object from fast api to make 

origins = [
    "http://localhost:3000", 
    "https://maktabty-library.vercel.app/"
    
]

app.add_middleware(VerifyToken)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

app.mount('/uploads',StaticFiles(directory='uploads'),name='uploads')
app.include_router(auth.router)
app.include_router(protected.router)
