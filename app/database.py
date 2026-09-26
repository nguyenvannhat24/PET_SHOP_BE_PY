from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from datetime import datetime
from app.config import settings

# Khởi tạo Motor Client
client = AsyncIOMotorClient(settings.MONGO_URI)

# Trích xuất database name từ URI hoặc mặc định 'PetShop'
db = client.get_default_database()
if db.name == "admin" or db.name is None:
    db = client["PetShop"]

# Các Collection chính của hệ thống
users_col = db["users"]
pets_col = db["pets"]
clinics_col = db["clinics"]
vets_col = db["veterinarians"]
services_col = db["services"]
service_categories_col = db["servicecategories"]
appointments_col = db["appointments"]
medical_records_col = db["medicalrecords"]
vaccinations_col = db["vaccinations"]
conversations_col = db["conversations"]
conversation_members_col = db["conversationmembers"]
messages_col = db["messages"]
notifications_col = db["notifications"]
reviews_col = db["reviews"]
products_col = db["products"]
categories_col = db["productcategories"]
carts_col = db["carts"]
orders_col = db["orders"]

def to_oid(val):
    """Chuyển đổi string thành ObjectId nếu hợp lệ"""
    if not val:
        return None
    if isinstance(val, ObjectId):
        return val
    try:
        return ObjectId(str(val))
    except Exception:
        return None

def serialize_doc(doc):
    """Chuyển đổi BSON document MongoDB sang dictionary JSON-friendly (hỗ trợ cả _id và id)"""
    if not doc:
        return None
    res = {}
    for k, v in doc.items():
        if k == "_id":
            str_id = str(v)
            res["_id"] = str_id
            res["id"] = str_id
        elif isinstance(v, ObjectId):
            res[k] = str(v)
        elif isinstance(v, datetime):
            res[k] = v.isoformat()
        elif isinstance(v, dict):
            res[k] = serialize_doc(v)
        elif isinstance(v, list):
            res[k] = [
                serialize_doc(item) if isinstance(item, dict)
                else str(item) if isinstance(item, ObjectId)
                else item.isoformat() if isinstance(item, datetime)
                else item
                for item in v
            ]
        else:
            res[k] = v
    return res

def serialize_list(docs):
    return [serialize_doc(d) for d in docs if d is not None]
