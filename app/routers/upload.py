import os
import uuid
import aiofiles
from typing import Optional
from fastapi import APIRouter, UploadFile, File, HTTPException
from app.config import settings

router = APIRouter(prefix="/api/upload", tags=["Upload"])

@router.post("")
@router.post("/")
async def upload_file(
    image: Optional[UploadFile] = File(None),
    file: Optional[UploadFile] = File(None)
):
    target = image or file
    if not target or not target.filename:
        raise HTTPException(status_code=400, detail="Vui lòng chọn một file ảnh")

    # Tạo tên file độc nhất tránh trùng lặp
    ext = os.path.splitext(target.filename)[1] or ".jpg"
    filename = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(settings.UPLOAD_DIR, filename)

    try:
        async with aiofiles.open(file_path, 'wb') as out_file:
            content = await target.read()
            await out_file.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi lưu tệp: {str(e)}")

    image_url = f"/uploads/{filename}"

    return {
        "success": True,
        "message": "Upload thành công",
        "url": image_url,
        "imageUrl": image_url,
        "data": {
            "url": image_url,
            "imageUrl": image_url,
            "filename": filename
        }
    }

