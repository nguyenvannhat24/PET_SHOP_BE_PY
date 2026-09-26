from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from app.database import (
    conversations_col, conversation_members_col, messages_col,
    users_col, clinics_col, vets_col,
    to_oid, serialize_doc, serialize_list
)
from app.middlewares.auth import get_current_user
from app.socket_server import emit_message_to_conversation
from app.services.notification_service import create_notification

router = APIRouter(prefix="/api/chat", tags=["Chat"])

class OpenConversationRequest(BaseModel):
    targetUserId: str
    appointmentId: Optional[str] = None

class SendMessageRequest(BaseModel):
    content: Optional[str] = ""
    messageType: Optional[str] = "TEXT"
    fileUrl: Optional[str] = None

async def get_partner_details(partner_user_id):
    if not partner_user_id:
        return {"full_name": "Người dùng", "role": "USER"}
    partner_doc = await users_col.find_one({"_id": to_oid(partner_user_id)}, {"password_hash": 0})
    if not partner_doc:
        return {"full_name": "Người dùng", "role": "USER"}

    partner_ser = serialize_doc(partner_doc)
    role = partner_ser.get("role")
    if role == "CLINIC":
        clinic = await clinics_col.find_one({"owner_id": to_oid(partner_user_id)})
        if clinic:
            partner_ser["clinic"] = serialize_doc(clinic)
    elif role == "VETERINARIAN":
        vet = await vets_col.find_one({"user_id": to_oid(partner_user_id)})
        if vet:
            partner_ser["veterinarian"] = serialize_doc(vet)

    return partner_ser

@router.post("/conversations")
async def get_or_create_conversation(req: OpenConversationRequest, current_user: dict = Depends(get_current_user)):
    current_id = current_user.get("_id")
    target_id = req.targetUserId

    if str(current_id) == str(target_id):
        raise HTTPException(status_code=400, detail="Bạn không thể tự tạo cuộc hội thoại với chính mình")

    # Tìm các hội thoại mà current_id đang tham gia
    my_memberships = await conversation_members_col.find({"user_id": to_oid(current_id)}).to_list(length=1000)
    my_conv_ids = [m["conversation_id"] for m in my_memberships]

    # Kiểm tra target_id có chung hội thoại không
    shared = await conversation_members_col.find_one({
        "conversation_id": {"$in": my_conv_ids},
        "user_id": to_oid(target_id)
    })

    if shared:
        conv = await conversations_col.find_one({"_id": shared["conversation_id"]})
    else:
        # Tạo hội thoại mới
        new_conv = {
            "appointment_id": to_oid(req.appointmentId) if req.appointmentId else None,
            "last_message": "Bắt đầu cuộc trò chuyện mới",
            "last_message_at": datetime.utcnow(),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        res = await conversations_col.insert_one(new_conv)
        new_conv["_id"] = res.inserted_id
        conv = new_conv

        # Thêm 2 thành viên
        await conversation_members_col.insert_many([
            {"conversation_id": conv["_id"], "user_id": to_oid(current_id), "created_at": datetime.utcnow()},
            {"conversation_id": conv["_id"], "user_id": to_oid(target_id), "created_at": datetime.utcnow()}
        ])

    partner_details = await get_partner_details(target_id)

    return {
        "success": True,
        "data": {
            "conversation": serialize_doc(conv),
            "partner": partner_details
        }
    }

@router.get("/conversations")
async def get_user_conversations(current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("_id")
    memberships = await conversation_members_col.find({"user_id": to_oid(user_id)}).to_list(length=1000)
    conv_ids = [m["conversation_id"] for m in memberships]

    cursor = conversations_col.find({"_id": {"$in": conv_ids}}).sort("last_message_at", -1)
    conversations = await cursor.to_list(length=1000)

    result = []
    for conv in conversations:
        # Tìm thành viên còn lại
        other_m = await conversation_members_col.find_one({
            "conversation_id": conv["_id"],
            "user_id": {"$ne": to_oid(user_id)}
        })
        partner_id = other_m.get("user_id") if other_m else None
        partner_info = await get_partner_details(partner_id)

        # Đếm tin chưa đọc
        unread_count = await messages_col.count_documents({
            "conversation_id": conv["_id"],
            "sender_id": {"$ne": to_oid(user_id)},
            "is_read": False
        })

        conv_ser = serialize_doc(conv)
        result.append({
            "_id": conv_ser.get("_id"),
            "id": conv_ser.get("id"),
            "last_message": conv_ser.get("last_message"),
            "last_message_at": conv_ser.get("last_message_at"),
            "partner": partner_info,
            "unread_count": unread_count
        })

    return {
        "success": True,
        "count": len(result),
        "data": result
    }

@router.get("/conversations/{conversation_id}/messages")
async def get_messages(
    conversation_id: str,
    limit: int = Query(100, ge=1, le=500),
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user.get("_id")

    # Xác thực thành viên
    is_member = await conversation_members_col.find_one({
        "conversation_id": to_oid(conversation_id),
        "user_id": to_oid(user_id)
    })
    if not is_member:
        raise HTTPException(status_code=403, detail="Bạn không có quyền truy cập cuộc trò chuyện này")

    # Đánh dấu đã đọc
    await messages_col.update_many(
        {"conversation_id": to_oid(conversation_id), "sender_id": {"$ne": to_oid(user_id)}, "is_read": False},
        {"$set": {"is_read": True, "updated_at": datetime.utcnow()}}
    )

    cursor = messages_col.find({"conversation_id": to_oid(conversation_id)}).sort("created_at", 1).limit(limit)
    messages = await cursor.to_list(length=limit)

    populated = []
    for msg in messages:
        m_ser = serialize_doc(msg)
        sender_id = msg.get("sender_id")
        if sender_id:
            sender = await users_col.find_one({"_id": to_oid(sender_id)}, {"password_hash": 0})
            if sender:
                m_ser["sender_id"] = serialize_doc(sender)
        populated.append(m_ser)

    return {
        "success": True,
        "count": len(populated),
        "data": populated
    }

@router.post("/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: str,
    req: SendMessageRequest,
    current_user: dict = Depends(get_current_user)
):
    sender_id = current_user.get("_id")

    is_member = await conversation_members_col.find_one({
        "conversation_id": to_oid(conversation_id),
        "user_id": to_oid(sender_id)
    })
    if not is_member:
        raise HTTPException(status_code=403, detail="Bạn không phải thành viên của cuộc trò chuyện này")

    if not req.content and not req.fileUrl:
        raise HTTPException(status_code=400, detail="Nội dung tin nhắn không được để trống")

    msg_doc = {
        "conversation_id": to_oid(conversation_id),
        "sender_id": to_oid(sender_id),
        "content": req.content or "",
        "message_type": req.messageType or "TEXT",
        "file_url": req.fileUrl or None,
        "is_read": False,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }

    res = await messages_col.insert_one(msg_doc)
    msg_doc["_id"] = res.inserted_id

    # Cập nhật conversation
    preview = "[Hình ảnh]" if req.messageType == "IMAGE" else req.content
    await conversations_col.update_one(
        {"_id": to_oid(conversation_id)},
        {"$set": {"last_message": preview, "last_message_at": datetime.utcnow(), "updated_at": datetime.utcnow()}}
    )

    # Populated message
    m_ser = serialize_doc(msg_doc)
    sender = await users_col.find_one({"_id": to_oid(sender_id)}, {"password_hash": 0})
    if sender:
        m_ser["sender_id"] = serialize_doc(sender)

    # Tìm thành viên còn lại
    other_members = await conversation_members_col.find({
        "conversation_id": to_oid(conversation_id),
        "user_id": {"$ne": to_oid(sender_id)}
    }).to_list(length=100)

    recipient_ids = [str(m["user_id"]) for m in other_members]

    # Phát tin nhắn realtime qua Socket.io vào conv: và user: rooms
    await emit_message_to_conversation(conversation_id, m_ser, recipient_ids)

    # Gửi thông báo đẩy
    for rid in recipient_ids:
        await create_notification(
            user_id=rid,
            notif_type="NEW_MESSAGE",
            title=f"Tin nhắn mới từ {current_user.get('full_name')}",
            content=preview,
            reference_id=conversation_id,
            reference_type="CONVERSATION"
        )

    return {
        "success": True,
        "data": m_ser
    }
