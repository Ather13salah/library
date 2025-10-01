from fastapi import APIRouter
from app.router import books
router = APIRouter(prefix="/protected")

router.include_router(books.router)