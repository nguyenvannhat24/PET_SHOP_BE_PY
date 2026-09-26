import re
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime
from app.database import (
    services_col, service_categories_col, clinics_col,
    to_oid, serialize_doc, serialize_list
)
from app.middlewares.auth import get_current_user

router = APIRouter(prefix="/api/services", tags=["Services"])

DEFAULT_CATEGORIES = [
    {
        "name": "Tắm & Spa Grooming",
        "icon": "Bath",
        "description": "Tắm sấy khử mùi, vệ sinh tai móng, dưỡng lông mượt mà chuyên sâu",
        "status": "ACTIVE"
    },
    {
        "name": "Cắt tỉa & Nhuộm tạo kiểu",
        "icon": "Scissors",
        "description": "Cắt tỉa lông chuyên nghiệp, cạo bàn, tạo kiểu theo yêu cầu cho thú cưng",
        "status": "ACTIVE"
    },
    {
        "name": "Khám & Điều trị bệnh",
        "icon": "Stethoscope",
        "description": "Khám tổng quát, xét nghiệm máu, siêu âm, điều trị da liễu và bệnh lý",
        "status": "ACTIVE"
    },
    {
        "name": "Tiêm phòng & Tẩy giun",
        "icon": "Syringe",
        "description": "Tiêm phòng dại, vaccine 7 bệnh cho chó, 4 bệnh cho mèo, xổ giun định kỳ",
        "status": "ACTIVE"
    },
    {
        "name": "Khách sạn lưu trú thú cưng",
        "icon": "Hotel",
        "description": "Trông giữ thú cưng phòng máy lạnh, giám sát camera 24/7, dinh dưỡng tiêu chuẩn",
        "status": "ACTIVE"
    },
    {
        "name": "Nha khoa & Phẫu thuật",
        "icon": "Sparkles",
        "description": "Lấy cao răng, triệt sản đực/cái an toàn, phẫu thuật chỉnh hình và tiểu phẫu",
        "status": "ACTIVE"
    }
]

class ServiceCreateRequest(BaseModel):
    name: str
    category_id: Optional[str] = None
    clinic_id: Optional[str] = None
    price: float
    duration_minutes: Optional[int] = 45
    description: Optional[str] = ""
    image_url: Optional[str] = ""
    species: Optional[str] = "ALL"
    status: Optional[str] = "ACTIVE"

class ServiceUpdateRequest(BaseModel):
    name: Optional[str] = None
    category_id: Optional[str] = None
    clinic_id: Optional[str] = None
    price: Optional[float] = None
    duration_minutes: Optional[int] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    species: Optional[str] = None
    status: Optional[str] = None

async def populate_service(svc_doc):
    if not svc_doc:
        return svc_doc
    s_ser = serialize_doc(svc_doc)
    if svc_doc.get("clinic_id"):
        clinic = await clinics_col.find_one({"_id": to_oid(svc_doc["clinic_id"])})
        if clinic:
            s_ser["clinic_id"] = serialize_doc(clinic)
    if svc_doc.get("category_id"):
        cat = await service_categories_col.find_one({"_id": to_oid(svc_doc["category_id"])})
        if cat:
            s_ser["category_id"] = serialize_doc(cat)
    return s_ser

@router.get("/categories")
async def get_categories():
    categories = await service_categories_col.find({"status": "ACTIVE"}).sort("created_at", 1).to_list(length=100)
    if not categories:
        # Tự động seed nếu rỗng
        now = datetime.utcnow()
        for c in DEFAULT_CATEGORIES:
            c_doc = {**c, "created_at": now, "updated_at": now}
            await service_categories_col.insert_one(c_doc)
        categories = await service_categories_col.find({"status": "ACTIVE"}).sort("created_at", 1).to_list(length=100)

    return {
        "success": True,
        "count": len(categories),
        "data": serialize_list(categories)
    }

@router.get("")
async def get_services(
    q: Optional[str] = Query(None),
    category_id: Optional[str] = Query(None),
    clinic_id: Optional[str] = Query(None),
    species: Optional[str] = Query(None),
    min_price: Optional[float] = Query(None),
    max_price: Optional[float] = Query(None),
    sort: Optional[str] = Query("newest")
):
    query = {"status": "ACTIVE"}

    if q and q.strip():
        rgx = re.compile(q.strip(), re.IGNORECASE)
        query["$or"] = [{"name": rgx}, {"description": rgx}]

    if category_id and category_id != "ALL":
        query["category_id"] = to_oid(category_id)

    if clinic_id and clinic_id != "ALL":
        query["clinic_id"] = to_oid(clinic_id)

    if species and species != "ALL":
        rgx_sp = re.compile(species, re.IGNORECASE)
        query["$and"] = query.get("$and", [])
        query["$and"].append({
            "$or": [
                {"species": rgx_sp},
                {"species": "ALL"},
                {"species": {"$exists": False}},
                {"species": ""}
            ]
        })

    if min_price is not None or max_price is not None:
        query["price"] = {}
        if min_price is not None:
            query["price"]["$gte"] = float(min_price)
        if max_price is not None:
            query["price"]["$lte"] = float(max_price)

    sort_field = "created_at"
    sort_dir = -1
    if sort == "price_asc":
        sort_field, sort_dir = "price", 1
    elif sort == "price_desc":
        sort_field, sort_dir = "price", -1
    elif sort == "duration_asc":
        sort_field, sort_dir = "duration_minutes", 1

    cursor = services_col.find(query).sort(sort_field, sort_dir)
    services = await cursor.to_list(length=1000)

    populated = []
    for s in services:
        p_s = await populate_service(s)
        populated.append(p_s)

    return {
        "success": True,
        "count": len(populated),
        "data": populated
    }

@router.get("/my-clinic")
async def get_my_clinic_services(current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("_id")
    clinic = await clinics_col.find_one({"owner_id": to_oid(user_id)})
    if not clinic:
        return {"success": True, "count": 0, "data": []}

    services = await services_col.find({"clinic_id": clinic["_id"]}).sort("created_at", -1).to_list(length=1000)
    populated = []
    for s in services:
        p_s = await populate_service(s)
        populated.append(p_s)

    return {
        "success": True,
        "count": len(populated),
        "data": populated
    }

@router.get("/{service_id}")
async def get_service_by_id(service_id: str):
    svc = await services_col.find_one({"_id": to_oid(service_id)})
    if not svc:
        raise HTTPException(status_code=404, detail="Dịch vụ không tồn tại")
    return {
        "success": True,
        "data": await populate_service(svc)
    }

@router.post("")
async def create_service(req: ServiceCreateRequest, current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("_id")
    clinic_id = req.clinic_id

    if not clinic_id:
        clinic = await clinics_col.find_one({"owner_id": to_oid(user_id)})
        if not clinic:
            raise HTTPException(status_code=400, detail="Không tìm thấy phòng khám của bạn để thêm dịch vụ")
        clinic_id = str(clinic["_id"])

    data = req.dict()
    data["clinic_id"] = to_oid(clinic_id)
    if data.get("category_id"):
        data["category_id"] = to_oid(data["category_id"])
    data["created_at"] = datetime.utcnow()
    data["updated_at"] = datetime.utcnow()

    res = await services_col.insert_one(data)
    data["_id"] = res.inserted_id

    return {
        "success": True,
        "message": "Thêm dịch vụ thành công!",
        "data": await populate_service(data)
    }

@router.put("/{service_id}")
async def update_service(service_id: str, req: ServiceUpdateRequest, current_user: dict = Depends(get_current_user)):
    svc = await services_col.find_one({"_id": to_oid(service_id)})
    if not svc:
        raise HTTPException(status_code=404, detail="Dịch vụ không tồn tại")

    data = {k: v for k, v in req.dict().items() if v is not None}
    if data.get("category_id"):
        data["category_id"] = to_oid(data["category_id"])
    if data.get("clinic_id"):
        data["clinic_id"] = to_oid(data["clinic_id"])
    data["updated_at"] = datetime.utcnow()

    await services_col.update_one({"_id": to_oid(service_id)}, {"$set": data})
    updated = await services_col.find_one({"_id": to_oid(service_id)})
    return {
        "success": True,
        "message": "Cập nhật dịch vụ thành công!",
        "data": await populate_service(updated)
    }

@router.patch("/{service_id}/status")
async def toggle_service_status(service_id: str, current_user: dict = Depends(get_current_user)):
    svc = await services_col.find_one({"_id": to_oid(service_id)})
    if not svc:
        raise HTTPException(status_code=404, detail="Dịch vụ không tồn tại")

    new_status = "INACTIVE" if svc.get("status") == "ACTIVE" else "ACTIVE"
    await services_col.update_one({"_id": to_oid(service_id)}, {"$set": {"status": new_status, "updated_at": datetime.utcnow()}})
    updated = await services_col.find_one({"_id": to_oid(service_id)})
    return {
        "success": True,
        "message": f"Dịch vụ đã chuyển sang trạng thái {new_status}",
        "data": await populate_service(updated)
    }

@router.delete("/{service_id}")
async def delete_service(service_id: str, current_user: dict = Depends(get_current_user)):
    await services_col.delete_one({"_id": to_oid(service_id)})
    return {
        "success": True,
        "message": "Xóa dịch vụ thành công"
    }
