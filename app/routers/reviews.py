from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.database import reviews_col, users_col, to_oid, serialize_doc, serialize_list
from app.middlewares.auth import get_current_user

router = APIRouter(prefix="/api/reviews", tags=["Reviews"])

class ReviewRequest(BaseModel):
    clinic_id: Optional[str] = None
    veterinarian_id: Optional[str] = None
    rating: int
    comment: Optional[str] = ""

async def populate_review(r):
    if not r:
        return r
    r_ser = serialize_doc(r)
    if r.get("user_id"):
        u = await users_col.find_one({"_id": to_oid(r["user_id"])}, {"password_hash": 0})
        if u:
            r_ser["user_id"] = serialize_doc(u)
    return r_ser

@router.get("/clinic/{clinic_id}")
async def get_clinic_reviews(clinic_id: str):
    cursor = reviews_col.find({"clinic_id": to_oid(clinic_id)}).sort("created_at", -1)
    reviews = await cursor.to_list(length=100)
    pop = [await populate_review(r) for r in reviews]
    return {"success": True, "count": len(pop), "data": pop}

@router.get("/veterinarian/{vet_id}")
async def get_vet_reviews(vet_id: str):
    cursor = reviews_col.find({"veterinarian_id": to_oid(vet_id)}).sort("created_at", -1)
    reviews = await cursor.to_list(length=100)
    pop = [await populate_review(r) for r in reviews]
    return {"success": True, "count": len(pop), "data": pop}

@router.post("")
async def create_review(req: ReviewRequest, current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("_id")
    data = req.dict()
    data["user_id"] = to_oid(user_id)
    if data.get("clinic_id"):
        data["clinic_id"] = to_oid(data["clinic_id"])
    if data.get("veterinarian_id"):
        data["veterinarian_id"] = to_oid(data["veterinarian_id"])
    data["created_at"] = datetime.utcnow()
    data["updated_at"] = datetime.utcnow()

    res = await reviews_col.insert_one(data)
    data["_id"] = res.inserted_id
    return {"success": True, "message": "Gửi đánh giá thành công!", "data": await populate_review(data)}
