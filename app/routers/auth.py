from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
from app.database import users_col, to_oid, serialize_doc
from app.middlewares.auth import hash_password, verify_password, create_access_token, get_current_user

router = APIRouter(prefix="/api/auth", tags=["Auth"])

class RegisterRequest(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    phone: Optional[str] = ""
    role: Optional[str] = "PET_OWNER"

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

@router.post("/register")
async def register(req: RegisterRequest):
    existing = await users_col.find_one({"email": req.email.lower()})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email đã được sử dụng"
        )

    hashed = hash_password(req.password)
    user_doc = {
        "full_name": req.full_name,
        "email": req.email.lower(),
        "password_hash": hashed,
        "phone": req.phone or "",
        "role": req.role or "PET_OWNER",
        "status": "ACTIVE",
        "avatar_url": "",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }

    res = await users_col.insert_one(user_doc)
    user_id = str(res.inserted_id)

    token = create_access_token({"id": user_id, "role": user_doc["role"]})

    user_data = {
        "id": user_id,
        "_id": user_id,
        "full_name": user_doc["full_name"],
        "email": user_doc["email"],
        "role": user_doc["role"],
        "avatar_url": user_doc["avatar_url"]
    }

    return {
        "success": True,
        "message": "Đăng ký tài khoản thành công!",
        "token": token,
        "data": user_data,
        "user": user_data
    }

@router.post("/login")
async def login(req: LoginRequest):
    user = await users_col.find_one({"email": req.email.lower()})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email hoặc mật khẩu không chính xác"
        )

    if user.get("status") != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản của bạn đã bị vô hiệu hóa hoặc bị khóa"
        )

    if not verify_password(req.password, user.get("password_hash", "")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email hoặc mật khẩu không chính xác"
        )

    user_id = str(user["_id"])
    token = create_access_token({"id": user_id, "role": user.get("role", "PET_OWNER")})

    user_data = {
        "id": user_id,
        "_id": user_id,
        "full_name": user.get("full_name"),
        "email": user.get("email"),
        "role": user.get("role"),
        "avatar_url": user.get("avatar_url", "")
    }

    return {
        "success": True,
        "message": "Đăng nhập thành công!",
        "token": token,
        "data": user_data,
        "user": user_data
    }

@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    return {
        "success": True,
        "data": current_user
    }
