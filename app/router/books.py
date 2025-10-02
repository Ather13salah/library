from PIL import Image, ImageEnhance
import numpy as np
import os
import requests
from fastapi import APIRouter, Request, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
import uuid
import google.generativeai as genai
from app.db import create_connection
from dotenv import load_dotenv
import base64
from io import BytesIO
from pathlib import Path
import json
from app.router.get_data_from_local_db import get_data
from app.router.book_update import BookUpdate
from app.router import favourite, daily


router = APIRouter(prefix="/books")
router.include_router(favourite.router)
router.include_router(daily.router)


UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# إضافة static route
router.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
load_dotenv()
genai.configure(api_key=os.getenv("API_KEY_FOR_GEMINI_AI"))
api_key = os.getenv("API_KEY_FOR_GOOGLE_BOOKS_API")

prompt = """
أنت OCR متخصص.  
استخرج فقط عنوان الكتاب والتصنيف من الغلاف.  
لو التصنيف غير موجود في الصورة، ابحث أونلاين باستخدام العنوان وحدد التصنيف.  
أرجع النتيجة في JSON فقط، هكذا:

{"book_name": "...", "category": "..."}

"""
 

@router.post("/upload-book")
async def extract_text(request: Request, file: UploadFile = File(...)):
    try:
        user_id = request.cookies.get("id")  # get the user id
        conn = create_connection("library")
        cursor = conn.cursor()
        # 1) قراءة الملف كـ bytes
        raw_bytes = await file.read()

        # 2) افتح الصورة وحوّلها RGB
        image = Image.open(BytesIO(raw_bytes)).convert("RGB")

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

        # 6) إرسال الصورة إلى Gemini OCR
        image_b64 = base64.b64encode(processed_bytes).decode("utf-8")
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(
            [prompt, {"mime_type": file.content_type, "data": image_b64}]
        )
        raw_text = response.candidates[0].content.parts[0].text.strip()

        title_text = ""
        category_text = "غير معروف"

        try:
            raw_text_clean = raw_text.strip()

            # 🛠️ لو الاستجابة فيها ```json أو ```
            if raw_text_clean.startswith("```"):
                raw_text_clean = raw_text_clean.strip("`")
                # ممكن يكون فيها json: في البداية
                if raw_text_clean.lower().startswith("json"):
                    raw_text_clean = raw_text_clean[4:].strip()

            parsed = json.loads(raw_text_clean)

            title_text = parsed.get("book_name", "").strip()
            category_text = parsed.get("category", "")

        except json.JSONDecodeError as e:
            # Gemini رجع نص مش JSON
            title_text = raw_text or "UnKnown Title"
            category_text = "غير معروف"

        filename = f"{uuid.uuid4()}.jpg"
        out_path = UPLOAD_DIR / filename
        with open(out_path, "wb") as f:
            f.write(processed_bytes)
        image_return = f"{request.base_url}uploads/{filename}"

        # 8) الاستعلام من Google Books
        cursor.execute("select book_name from books where user_id = %s", (user_id,))
        books = cursor.fetchall()
        for book_name in books:
            if title_text == book_name[0]:
                return {"error": "Book name is already exists"}

        all_books = get_data("all_books", title_text, image_return, user_id)
        if all_books == False:
            query = requests.utils.requote_uri(title_text or "")
            url = f"https://www.googleapis.com/books/v1/volumes?q={query}&key={api_key}"
            gres = requests.get(url, timeout=10)
            gdata = gres.json()

            if gdata.get("totalItems", 0) != 0:

                # 10) تجهيز بيانات الكتاب
                id = str(uuid.uuid4())

                authors = (
                    gdata.get("items", [{}])[0].get("volumeInfo", {}).get("authors")
                ) or ["غير معروف"]
                writer = authors[0] if authors else "غير معروف"

                publisher = (
                    gdata.get("items", [{}])[0].get("volumeInfo", {}).get("publisher")
                ) or "غير معروف"
                total_pages = (
                    gdata.get("items", [{}])[0].get("volumeInfo", {}).get("pageCount")
                ) or 0

                # 11) إدخال البيانات في MySQL (لاحظ إضافة category)

                cursor.execute(
                    """
                    INSERT INTO books (
                        id, book_name, writer,
                        book_type, publisher, total_pages,
                        image_url, user_id, category
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

                # 12) الرد للعميل
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
        else:
            return all_books

    except Exception as e:

        return {"error": f"Can not add the book: "}


@router.post("/add-book")
async def add_book(
    request: Request,
    book_name: str = Form(...),
    writer: str = Form(...),
    publisher: str = Form(...),
    category: str = Form(...),
    total_pages: int = Form(...),
    file: UploadFile = File(...),
):
    try:
        # print(book_name,writer,publisher,category,total_pages)
        user_id = request.cookies.get("id")  # get the user id
        conn = create_connection("library")
        cursor = conn.cursor()
        id = str(uuid.uuid4())
        raw_bytes = await file.read()

        # 2) افتح الصورة وحوّلها RGB
        image = Image.open(BytesIO(raw_bytes)).convert("RGB")

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

        filename = f"{uuid.uuid4()}.jpg"
        out_path = UPLOAD_DIR / filename
        with open(out_path, "wb") as f:
            f.write(processed_bytes)
        image_return = f"{request.base_url}uploads/{filename}"

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

        conn = create_connection("library")
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT id, book_name, image_url,is_in_daily,is_favourite,is_read,category FROM books WHERE user_id = %s",
            (user_id,),
        )
        books = cursor.fetchall()

        cursor.close()
        conn.close()

        if not books:
            return {"error": "No books found "}

        return {"books": books}

    except Exception as e:
        return {"error": "Can not get Books"}


@router.get("/get-book")
async def get_book(book_id: str):
    try:

        conn = create_connection("library")
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM books WHERE id = %s", (book_id,))
        book = cursor.fetchone()

        cursor.close()
        conn.close()

        if not book:
            return {"error": "No books found "}

        return {"book": book}

    except Exception as e:
        return {"error": "Can not get Book"}


@router.delete("/delete-book")
async def delete_book(user_id: str, id: str):
    try:

        conn = create_connection("library")
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

        conn = create_connection("library")
        cursor = conn.cursor()

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


@router.patch("/set-book-read")
async def setInRead(user_id: str, id: str):
    try:

        conn = create_connection("library")
        cursor = conn.cursor()

        cursor.execute(
            "update books set is_read = True WHERE user_id = %s and id = %s",
            (user_id, id),
        )
        conn.commit()
        cursor.close()
        conn.close()
        return {"done": "Book read "}

    except Exception as e:
        return {"error": "Can not set book from reading books"}
