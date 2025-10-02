from fastapi import APIRouter
from app.db import create_connection

router = APIRouter(prefix='/favourite')
@router.patch("/set-in-favourate-books")
async def setInFavourite(user_id: str, id: str):
    try:

        conn = create_connection("library")
        cursor = conn.cursor()

        cursor.execute(
            "update books set is_favourite = True WHERE user_id = %s and id = %s",
            (user_id, id),
        )
        conn.commit()
        cursor.close()
        conn.close()
        return {"done": "Set the book in favourite "}

    except Exception as e:
        return {"error": "Can not add the book in favourite"}
    
@router.get("/get-favourite-books")
async def get_books(user_id: str):
    try:

        conn = create_connection("library")
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT id, book_name, image_url FROM books WHERE user_id = %s and is_favourite = True",
            (user_id,),
        )
        books = cursor.fetchall()

        cursor.close()
        conn.close()

        if not books:
            return {"error": "No favourite books found "}

        return {"books": books}

    except Exception as e:
        return {"error": "Can not get Books"}
    
@router.patch('/delete-from-favourite')
async def delete_from_favourite(user_id: str, id: str):
    try:
        
        conn = create_connection("library")
        cursor = conn.cursor()

        cursor.execute(
            "update books set is_favourite = False WHERE user_id = %s and id = %s", (user_id, id)
        )

        conn.commit()
        cursor.close()
        conn.close()
        
        return {"done": "Book Deleted from favourite Successfully"}

    except Exception as e:
        return {"error": "Can not delete the book from favourite"}