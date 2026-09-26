from fastapi import APIRouter, HTTPException, Depends, Query
from datetime import datetime
from app.database import notifications_col, to_oid, serialize_doc, serialize_list
from app.middlewares.auth import get_current_user

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])

@router.get("")
async def get_notifications(
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user.get("_id")
    cursor = notifications_col.find({"user_id": to_oid(user_id)}).sort("created_at", -1).limit(limit)
    notifs = await cursor.to_list(length=limit)
    return {
        "success": True,
        "count": len(notifs),
        "data": serialize_list(notifs)
    }

@router.get("/unread-count")
async def get_unread_count(current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("_id")
    count = await notifications_col.count_documents({
        "user_id": to_oid(user_id),
        "is_read": False
    })
    return {
        "success": True,
        "count": count
    }

@router.patch("/{notif_id}/read")
async def mark_as_read(notif_id: str, current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("_id")
    await notifications_col.update_one(
        {"_id": to_oid(notif_id), "user_id": to_oid(user_id)},
        {"$set": {"is_read": True, "updated_at": datetime.utcnow()}}
    )
    return {
        "success": True,
        "message": "Đã đánh dấu thông báo là đã đọc"
    }

@router.patch("/read-all")
async def mark_all_as_read(current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("_id")
    await notifications_col.update_many(
        {"user_id": to_oid(user_id), "is_read": False},
        {"$set": {"is_read": True, "updated_at": datetime.utcnow()}}
    )
    return {
        "success": True,
        "message": "Đã đánh dấu tất cả thông báo là đã đọc"
    }
