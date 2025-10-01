
from pydantic import BaseModel

class BookUpdate(BaseModel):
    book_name: str
    writer: str
    publisher: str
    category: str
    total_pages: str