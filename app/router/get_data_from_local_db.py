from app.db import create_connection
import uuid


def get_data(database: str, text: str, image, user_id):
    try:
        id = uuid.uuid4()
        conn = create_connection(database)
        cursor = conn.cursor(dictionary=True)

        cursor.execute("select * from book where book_name = %s", (text,))
        book = cursor.fetchone()

        if not book:
            return False

        cursor.execute(
            "select category_name from category where category_id = %s",
            (book["book_category"]),
        )
        category = cursor.fetchone()

        cursor.execute(
            "select author_name from author where author_id = %s", (book["main_author"])
        )
        author = cursor.fetchone()

        conn = create_connection("library")
        cursor = conn.cursor()
        cursor.execute(
            """
                INSERT INTO books (
                    id, book_name, writer, book_description,
                    book_type
                    image_url, user_id, category
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                """,
            (id, book["book_name"], author, "كتاب نصي", image, user_id, category),
        )
        conn.commit()
        cursor.close()
        conn.close()

        # 12) الرد للعميل
        return {
            "id": id,
            "book_name": book["book_name"],
            "category": category,
            "image_url": image,
            "is_in_daily": False,
            "is_favourite": False,
        }

    except Exception:
        return False
