from pydantic import BaseModel

class UserToSignUp(BaseModel):
    '''This class to validate inputs using Base Model class '''
    name: str
    password: str
    email: str


class UserToLogin(BaseModel):
    name: str
    password: str

