from PIL import Image, ImageEnhance
import numpy as np
import os
import requests
from fastapi import APIRouter, Request, UploadFile, File, Form
import cloudinary
import cloudinary.uploader
import uuid
from openai import OpenAI
from app.db import create_connection
from dotenv import load_dotenv
import base64
from io import BytesIO
import json
from app.router.book_update import BookData, BookUpdate
from app.router import favourite, daily

# -----------------------------
# إعداد الراوتر والتهيئة
# -----------------------------
router = APIRouter(prefix="/books")
router.include_router(favourite.router)
router.include_router(daily.router)

load_dotenv()

openai_api_key = os.getenv("API_KEY_FOR_OPEN_AI")
client = OpenAI(api_key=openai_api_key)

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True,
)
api_key = os.getenv("GOOGLE_BOOKS_API_KEY")
# -----------------------------
# الـ Prompt الخاص بـ OCR
# -----------------------------
prompt = """
أنت متخصص OCR.
استخرج فقط عنوان الكتاب والتصنيف من الغلاف.
لو التصنيف غير موجود في الصورة، ابحث أونلاين باستخدام العنوان وحدد التصنيف.
أرجع النتيجة في JSON فقط، هكذا:
{"book_name": "...", "category": "..."}
"""


# -----------------------------
# رفع صورة الكتاب وتحليلها
# -----------------------------
@router.post("/upload-book")
async def extract_text(file: UploadFile = File(...)):
    try:
        raw_bytes = await file.read()
        image = Image.open(BytesIO(raw_bytes)).convert("RGB")

        # تحسين الصورة
        image = ImageEnhance.Brightness(image).enhance(1.02)
        image = ImageEnhance.Contrast(image).enhance(1.05)
        image = ImageEnhance.Sharpness(image).enhance(1.1)

        # تنظيف الخلفية البيضاء
        np_img = np.array(image)
        threshold = 240
        mask = (
            (np_img[:, :, 0] > threshold)
            & (np_img[:, :, 1] > threshold)
            & (np_img[:, :, 2] > threshold)
        )
        np_img[mask] = [255, 255, 255]
        image = Image.fromarray(np_img)

        # تحويل الصورة إلى base64
        buffer = BytesIO()
        image.save(buffer, format="JPEG")
        processed_bytes = buffer.getvalue()
        image_b64 = base64.b64encode(processed_bytes).decode("utf-8")

        # إرسال إلى OpenAI OCR
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": prompt},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_b64}"
                                },
                            },
                        ],
                    },
                ],
            )
            raw_text = response.choices[0].message.content.strip()
        except:
            return {"error": "Cannot upload book"}

        # تحليل الرد
        title_text = ""
        category_text = "غير معروف"

        try:
           
            parsed = json.loads(raw_text)
            title_text = parsed.get("book_name", "").strip()
            category_text = parsed.get("category", "")
        except json.JSONDecodeError:
            title_text = raw_text or "Unknown Title"

        # رفع الصورة إلى Cloudinary
        result = cloudinary.uploader.upload(processed_bytes, folder="my_books")
        image_return = result.get("secure_url")

        # البحث في Google Books API

        query = requests.utils.requote_uri(title_text or "")
        url = f"https://www.googleapis.com/books/v1/volumes?q={query}&key={api_key}"
        gres = requests.get(url, timeout=10)
        gdata = gres.json()
         id = str(uuid.uuid4())
        if gdata.get("totalItems", 0) != 0:

            volume_info = gdata.get("items", [{}])[0].get("volumeInfo", {})
            authors = volume_info.get("authors") or ["غير معروف"]
            writer = authors[0]
            publisher = volume_info.get("publisher", "غير معروف")
            total_pages = volume_info.get("pageCount", 0)

            return {
                "id": id,
                "book_name": title_text,
                "category": category_text,
                "image_url": image_return,
                "publisher": publisher,
                "total_pages": total_pages,
                "writer": writer,
                "is_in_daily": False,
                "is_favourite": False,
            }
        else:
            return {
                "id": id,
                "book_name": title_text,
                "category": category_text,
                "image_url": image_return,
                "publisher": "غير معروف",
                "total_pages": 0,
                "writer": "غير معروف",
                "is_in_daily": False,
                "is_favourite": False,
            }

    except Exception as e:
        return {"error": f"Cannot add the book: {str(e)}"}


# -----------------------------
# إضافة بيانات الكتاب يدويًا
# -----------------------------

@router.post("/add-book-data")
async def add_data(user_id: str, book: BookData):
    try:
        conn = create_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT book_name FROM books WHERE user_id = %s", (user_id,))
        books = cursor.fetchall()
        for name in books:
            if book.book_name == name[0]:
                return {"error": "Book name already exists"}

        cursor.execute(
            """
            INSERT INTO books (
                id, book_name, writer, book_type,
                publisher, total_pages, image_url, user_id, category
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                book.id,
                book.book_name,
                book.writer,
                "كتاب نصي",
                book.publisher,
                book.total_pages,
                book.image_return,
                user_id,
                book.category,
            ),
        )
        conn.commit()
        cursor.close()
        conn.close()
        return {"done": "Book added successfully"}
    except Exception as e:
        return {"error":"Can not add the book"}

# -----------------------------
# رفع كتاب يدويًا مع صورة
# -----------------------------
@router.post("/add-book")
async def add_book(
    request: Request,
    user_id: str,
    book_name: str = Form(...),
    writer: str = Form(...),
    publisher: str = Form(...),
    category: str = Form(...),
    total_pages: int = Form(...),
    file: UploadFile = File(...),
):
    try:
        conn = create_connection()
        cursor = conn.cursor()
        id = str(uuid.uuid4())
        raw_bytes = await file.read()

        image = Image.open(BytesIO(raw_bytes)).convert("RGB")
        image = ImageEnhance.Brightness(image).enhance(1.02)
        image = ImageEnhance.Contrast(image).enhance(1.05)
        image = ImageEnhance.Sharpness(image).enhance(1.1)

        np_img = np.array(image)
        threshold = 240
        mask = (
            (np_img[:, :, 0] > threshold)
            & (np_img[:, :, 1] > threshold)
            & (np_img[:, :, 2] > threshold)
        )
        np_img[mask] = [255, 255, 255]
        image = Image.fromarray(np_img)

        buffer = BytesIO()
        image.save(buffer, format="JPEG")
        processed_bytes = buffer.getvalue()

        result = cloudinary.uploader.upload(processed_bytes, folder="my_books")
        image_return = result.get("secure_url")

        cursor.execute("SELECT book_name FROM books WHERE user_id = %s", (user_id,))
        books = cursor.fetchall()
        for name in books:
            if book_name == name[0]:
                return {"error": "Book name already exists"}

        cursor.execute(
            """
            INSERT INTO books (
                id, book_name, writer, book_type, publisher,
                total_pages, image_url, user_id, category
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                id,
                book_name,
                writer,
                "كتاب نصي",
                publisher,
                total_pages,
                image_return,
                user_id,
                category,
            ),
        )
        conn.commit()
        cursor.close()
        conn.close()

        return {
            "id": id,
            "book_name": book_name,
            "category": category,
            "image_url": image_return,
            "is_in_daily": False,
            "is_favourite": False,
            "is_read": False,
        }

    except Exception as e:
        return {"error": f"Cannot add the book: {str(e)}"}


# -----------------------------
# جلب جميع الكتب
# -----------------------------
@router.get("/get-books")
async def get_books(user_id: str):
    try:
        conn = create_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM books WHERE user_id = %s", (user_id,))
        books = cursor.fetchall()

        cursor.close()
        conn.close()

        if not books:
            return {"error": "No books found"}
        return {"books": books}

    except Exception:
        return {"error": "Cannot get Books"}


# -----------------------------
# حذف كتاب
# -----------------------------
@router.delete("/delete-book")
async def delete_book(user_id: str, id: str):
    try:
        conn = create_connection()
        cursor = conn.cursor()

        cursor.execute(
            "DELETE FROM books WHERE user_id = %s AND id = %s", (user_id, id)
        )
        conn.commit()
        cursor.close()
        conn.close()
        return {"done": "Book Deleted Successfully"}

    except Exception:
        return {"error": "Cannot delete the book"}


# -----------------------------
# تعديل بيانات كتاب
# -----------------------------
@router.put("/edit-book")
async def edit_book(new_book: BookUpdate, user_id: str, id: str):
    try:
        conn = create_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT book_name FROM books WHERE user_id = %s", (user_id,))
        books = cursor.fetchall()
        for name in books:
            if new_book.book_name == name[0]:
                return {"error": "Book name already exists"}

        cursor.execute(
            """
            UPDATE books
            SET book_name = %s, writer = %s, publisher = %s, category = %s, total_pages = %s
            WHERE user_id = %s AND id = %s
            """,
            (
                new_book.book_name,
                new_book.writer,
                new_book.publisher,
                new_book.category,
                new_book.total_pages,
                user_id,
                id,
            ),
        )
        conn.commit()
        cursor.close()
        conn.close()
        return {"done": "Book Edited"}

    except Exception as e:
        return {"error": f"Cannot edit the book: {str(e)}"}
