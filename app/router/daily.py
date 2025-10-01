from app.db import create_connection
from fastapi import APIRouter

router = APIRouter(prefix='/daily')


@router.patch("/set-in-daily-books")
async def setInDaily(user_id: str, id: str):
    try:

        conn = create_connection("library")
        cursor = conn.cursor()

        cursor.execute(
            "update books set is_in_daily = True WHERE user_id = %s and id = %s",
            (user_id, id),
        )
        conn.commit()
        cursor.close()
        conn.close()

        return {"done": "Set the book in daily  "}

    except Exception as e:
        return {"error": "Can not add the book in daily"}


@router.get("/get-daily-books")
async def get_books(user_id: str):
    try:

        conn = create_connection("library")
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT id, book_name, image_url FROM books WHERE user_id = %s and is_in_daily = True",
            (user_id,),
        )
        books = cursor.fetchall()

        cursor.close()
        conn.close()

        if not books:
            return {"error": "No daily books found "}

        return {"books": books}

    except Exception as e:
        return {"error": "Can not get Books"}
    
    
@router.patch('/delete-from-daily')
async def delete_from_daily(user_id: str, id: str):
    try:
        
        conn = create_connection("library")
        cursor = conn.cursor()

        cursor.execute(
            "update books set is_in_daily = False WHERE user_id = %s and id = %s", (user_id, id)
        )

        conn.commit()
        cursor.close()
        conn.close()
        return {"done": "Book Deleted from daily Successfully"}

    except Exception as e:
        return {"error": "Can not delete the book from daily"}