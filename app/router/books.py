from PIL import Image, ImageEnhance
import numpy as np
import os
import requests
from fastapi import APIRouter, Request, UploadFile, File, Form
import cloudinary
import cloudinary.uploader
import uuid
from openai import OpenAI
from openai import OpenAI
from app.db import create_connection
from dotenv import load_dotenv
import base64
from io import BytesIO

import json
from app.router.book_update import BookUpdate
from app.router import favourite, daily

router = APIRouter(prefix="/books")
router.include_router(favourite.router)
router.include_router(daily.router)

load_dotenv()

# ✅ إعداد عميل OpenAI
openai_api_key = os.getenv("API_KEY_FOR_OPEN_AI")
client = OpenAI(api_key=openai_api_key)

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True,
)

api_key = os.getenv("API_KEY_FOR_GOOGLE_BOOKS_API")

prompt = """
أنت متخصص OCR.
استخرج فقط عنوان الكتاب والتصنيف من الغلاف.
لو التصنيف غير موجود في الصورة، ابحث أونلاين باستخدام العنوان وحدد التصنيف.
أنت متخصص OCR.
استخرج فقط عنوان الكتاب والتصنيف من الغلاف.
لو التصنيف غير موجود في الصورة، ابحث أونلاين باستخدام العنوان وحدد التصنيف.
أرجع النتيجة في JSON فقط، هكذا:

{"book_name": "...", "category": "..."}
"""


@router.post("/upload-book")
async def extract_text(request: Request, user_id: str, file: UploadFile = File(...)):
    try:

        conn = create_connection()
        cursor = conn.cursor()

        # 1) قراءة الصورة

        # 1) قراءة الصورة
        raw_bytes = await file.read()
        image = Image.open(BytesIO(raw_bytes)).convert("RGB")

        image = ImageOps.exif_transpose(image)
        # تحسين الصورة قليلاً
        # تحسين الصورة قليلاً
        image = ImageEnhance.Brightness(image).enhance(1.02)
        image = ImageEnhance.Contrast(image).enhance(1.05)
        image = ImageEnhance.Sharpness(image).enhance(1.1)

        # تنظيف الخلفية البيضاء
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

        # تحويلها base64
        # تحويلها base64
        buffer = BytesIO()
        image.save(buffer, format="JPEG")
        processed_bytes = buffer.getvalue()
        image_b64 = base64.b64encode(processed_bytes).decode("utf-8")

        try:
            # 2️⃣ إرسال الصورة إلى OpenAI OCR
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
            return {"error": "Can not Upload book"}



        title_text = ""
        category_text = "غير معروف"

        try:
            raw_text_clean = raw_text.strip()
            if raw_text_clean.startswith("```"):
                raw_text_clean = raw_text_clean.strip("`")
                if raw_text_clean.lower().startswith("json"):
                    raw_text_clean = raw_text_clean[4:].strip()

            parsed = json.loads(raw_text_clean)
            title_text = parsed.get("book_name", "").strip()
            category_text = parsed.get("category", "")
        except json.JSONDecodeError:
            title_text = raw_text or "Unknown Title"
        except json.JSONDecodeError:
            title_text = raw_text or "Unknown Title"
            category_text = "غير معروف"

        result = cloudinary.uploader.upload(processed_bytes, folder="my_books")
        image_return = result.get("secure_url")

        # تحقق من وجود الكتاب مسبقاً
      
        # تحقق من وجود الكتاب مسبقاً
        cursor.execute("SELECT book_name FROM books WHERE user_id = %s", (user_id,))
        books = cursor.fetchall()
        for book_name in books:
            if title_text == book_name[0]:
                return {"error": "Book name already exists"}
                

        # استعلام Google Books API
        # استعلام Google Books API
        query = requests.utils.requote_uri(title_text or "")
        url = f"https://www.googleapis.com/books/v1/volumes?q={query}&key={api_key}"
        gres = requests.get(url, timeout=10)
        gdata = gres.json()

        if gdata.get("totalItems", 0) != 0:
            id = str(uuid.uuid4())
            authors = gdata.get("items", [{}])[0].get("volumeInfo", {}).get(
                "authors"
            ) or ["غير معروف"]
            writer = authors[0]
            publisher = (
                gdata.get("items", [{}])[0].get("volumeInfo", {}).get("publisher")
                or "غير معروف"
            )
            total_pages = (
                gdata.get("items", [{}])[0].get("volumeInfo", {}).get("pageCount") or 0
            )

            cursor.execute(
                """
                INSERT INTO books (
                    id, book_name, writer, book_type,
                    publisher, total_pages, image_url, user_id, category
                    
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    id,
                    title_text,
                    writer,
                    "كتاب نصي",
                    publisher,
                    total_pages,
                    image_return,
                    user_id,
                    category_text,
                ),
            )
            conn.commit()
            cursor.close()
            conn.close()

            return {
                "id": id,
                "book_name": title_text,
                "category": category_text,
                "image_url": image_return,
                "is_in_daily": False,
                "is_favourite": False,
            }

        else:
            return {"warning": "No books found"}

    except Exception as e:
        return {"error": f"Cannot add the book: {str(e)}"}


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

        # 2) افتح الصورة وحوّلها RGB
        image = Image.open(BytesIO(raw_bytes)).convert("RGB")

        image = ImageOps.exif_transpose(image)
        image = ImageEnhance.Brightness(image).enhance(1.02)
        image = ImageEnhance.Contrast(image).enhance(1.05)
        image = ImageEnhance.Sharpness(image).enhance(1.1)

        # 4) تنظيف الخلفية
        np_img = np.array(image)
        threshold = 240
        mask = (
            (np_img[:, :, 0] > threshold)
            & (np_img[:, :, 1] > threshold)
            & (np_img[:, :, 2] > threshold)
        )
        np_img[mask] = [255, 255, 255]
        image = Image.fromarray(np_img)

        # 5) حفظ الصورة في buffer
        buffer = BytesIO()
        image.save(buffer, format="JPEG")
        processed_bytes = buffer.getvalue()

        result = cloudinary.uploader.upload(processed_bytes, folder="my_books")
        image_return = result.get("secure_url")

        cursor.execute("select book_name from books where user_id = %s", (user_id,))
        books = cursor.fetchall()
        for name in books:
            if book_name == name[0]:
                return {"error": "Book name is already exists"}

        cursor.execute(
            """
            INSERT INTO books (
                id, book_name, writer,
                book_type,  publisher, total_pages,
                image_url, user_id, category
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
        return {"error": f"Can not add the book: {str(e)}"}


@router.get("/get-books")
async def get_books(user_id: str):
    try:

        conn = create_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT * FROM books WHERE user_id = %s",
            (user_id,),
        )
        books = cursor.fetchall()

        cursor.close()
        conn.close()
        # print(f"Books:{books}")
       

        if not books or books == []:
            return {"error": "No books found "}

        

        return {"books": books}

    except Exception as e:
        return {"error": "Can not get Books"}



@router.delete("/delete-book")
async def delete_book(user_id: str, id: str):
    try:

        conn = create_connection()
        cursor = conn.cursor()

        cursor.execute(
            "delete FROM books WHERE user_id = %s and id = %s", (user_id, id)
        )

        conn.commit()
        cursor.close()
        conn.close()
        return {"done": "Book Deleted Successfully"}

    except Exception as e:
        return {"error": "Can not delete the book"}


@router.put("/edit-book")
async def edit_book(new_book: BookUpdate, user_id: str, id: str):
    try:

        conn = create_connection()
        cursor = conn.cursor()

        
        cursor.execute("select book_name from books where user_id = %s", (user_id,))
        books = cursor.fetchall()
        for name in books:
            if new_book.book_name == name[0]:
                return {"error": "Book name is already exists"}
            
        cursor.execute(
            "update books set book_name = %s, writer = %s, publisher = %s, category = %s ,total_pages = %s WHERE user_id = %s and id = %s",
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
        return {"error": f"Can not Edit the book {str(e)} "}
