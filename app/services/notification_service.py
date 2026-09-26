from datetime import datetime
from app.database import notifications_col, to_oid, serialize_doc
from app.socket_server import send_notification_to_user

async def create_notification(user_id, notif_type, title, content, reference_id=None, reference_type=None):
    """Lưu thông báo vào DB và phát socket realtime tới user"""
    if not user_id:
        return None

    doc = {
        "user_id": to_oid(user_id),
        "type": notif_type,
        "title": title,
        "content": content,
        "reference_id": to_oid(reference_id) if reference_id else None,
        "reference_type": reference_type,
        "is_read": False,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }

    res = await notifications_col.insert_one(doc)
    doc["_id"] = res.inserted_id
    serialized = serialize_doc(doc)

    # Phát socket tới room cá nhân của user
    await send_notification_to_user(str(user_id), serialized)
    return serialized
