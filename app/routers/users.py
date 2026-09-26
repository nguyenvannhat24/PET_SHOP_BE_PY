from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.database import users_col, to_oid, serialize_doc
from app.middlewares.auth import get_current_user

router = APIRouter(prefix="/api/users", tags=["Users"])

class UpdateProfileRequest(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    avatar_url: Optional[str] = None

@router.get("/profile")
async def get_profile(current_user: dict = Depends(get_current_user)):
    return {
        "success": True,
        "data": current_user
    }

@router.put("/profile")
async def update_profile(req: UpdateProfileRequest, current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("_id")
    update_data = {k: v for k, v in req.dict().items() if v is not None}
    update_data["updated_at"] = datetime.utcnow()

    await users_col.update_one({"_id": to_oid(user_id)}, {"$set": update_data})
    updated = await users_col.find_one({"_id": to_oid(user_id)})

    return {
        "success": True,
        "message": "Cập nhật thông tin thành công!",
        "data": serialize_doc(updated)
    }

@router.get("/{user_id}")
async def get_user_by_id(user_id: str):
    user = await users_col.find_one({"_id": to_oid(user_id)}, {"password_hash": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")
    return {
        "success": True,
        "data": serialize_doc(user)
    }
