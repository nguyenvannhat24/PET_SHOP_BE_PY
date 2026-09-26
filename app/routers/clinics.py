import re
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from app.database import (
    clinics_col, users_col, appointments_col, pets_col, vets_col, services_col,
    to_oid, serialize_doc, serialize_list
)
from app.middlewares.auth import get_current_user, require_roles

router = APIRouter(prefix="/api/clinics", tags=["Clinics"])

class ClinicDataRequest(BaseModel):
    name: str
    type: Optional[str] = "VETERINARY_CLINIC"
    description: Optional[str] = ""
    phone: str
    email: Optional[str] = ""
    address: str
    logo_url: Optional[str] = ""
    cover_url: Optional[str] = ""
    opening_time: Optional[str] = "08:00"
    closing_time: Optional[str] = "20:00"
    working_days: Optional[List[str]] = ['Thứ 2', 'Thứ 3', 'Thứ 4', 'Thứ 5', 'Thứ 6', 'Thứ 7', 'Chủ nhật']

@router.get("")
async def get_clinics(
    search: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    status: Optional[str] = Query(None)
):
    query = {}
    if status:
        query["status"] = status
    if type:
        query["type"] = type
    if search and search.strip():
        rgx = re.compile(search.strip(), re.IGNORECASE)
        query["$or"] = [{"name": rgx}, {"address": rgx}]

    cursor = clinics_col.find(query).sort("created_at", -1)
    clinics = await cursor.to_list(length=1000)
    return {
        "success": True,
        "count": len(clinics),
        "data": serialize_list(clinics)
    }

@router.get("/my-clinic")
async def get_my_clinic(current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("_id")
    clinic = await clinics_col.find_one({"owner_id": to_oid(user_id)})
    return {
        "success": True,
        "data": serialize_doc(clinic)
    }

@router.put("/my-clinic")
async def update_my_clinic(req: ClinicDataRequest, current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("_id")
    data = req.dict()
    data["updated_at"] = datetime.utcnow()

    existing = await clinics_col.find_one({"owner_id": to_oid(user_id)})
    if existing:
        await clinics_col.update_one({"_id": existing["_id"]}, {"$set": data})
        saved = await clinics_col.find_one({"_id": existing["_id"]})
    else:
        data["owner_id"] = to_oid(user_id)
        data["created_at"] = datetime.utcnow()
        res = await clinics_col.insert_one(data)
        saved = await clinics_col.find_one({"_id": res.inserted_id})

    return {
        "success": True,
        "message": "Lưu thông tin phòng khám thành công!",
        "data": serialize_doc(saved)
    }

@router.get("/my-customers")
async def get_my_customers(current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("_id")
    clinic = await clinics_col.find_one({"owner_id": to_oid(user_id)})
    if not clinic:
        return {"success": True, "count": 0, "data": []}

    cursor = appointments_col.find({"clinic_id": clinic["_id"]}).sort("appointment_date", -1)
    appointments = await cursor.to_list(length=1000)

    customer_map = {}
    for appt in appointments:
        owner_id = appt.get("owner_id")
        if not owner_id:
            continue
        cust_key = str(owner_id)

        if cust_key not in customer_map:
            owner_doc = await users_col.find_one({"_id": to_oid(owner_id)}, {"password_hash": 0})
            owner_ser = serialize_doc(owner_doc) if owner_doc else {}
            customer_map[cust_key] = {
                "_id": cust_key,
                "id": cust_key,
                "full_name": owner_ser.get("full_name", "Khách hàng"),
                "email": owner_ser.get("email", ""),
                "phone": owner_ser.get("phone", ""),
                "address": owner_ser.get("address", ""),
                "avatar_url": owner_ser.get("avatar_url", ""),
                "total_visits": 0,
                "completed_visits": 0,
                "last_visit": appt.get("appointment_date"),
                "pets": [],
                "appointments": []
            }

        c_entry = customer_map[cust_key]
        c_entry["total_visits"] += 1
        if appt.get("status") == "COMPLETED":
            c_entry["completed_visits"] += 1

        # Gắn pet nếu có
        pet_id = appt.get("pet_id")
        if pet_id:
            p_key = str(pet_id)
            if not any(str(p.get("_id")) == p_key for p in c_entry["pets"]):
                pet_doc = await pets_col.find_one({"_id": to_oid(pet_id)})
                if pet_doc:
                    c_entry["pets"].append(serialize_doc(pet_doc))

        # Gắn appointment tóm tắt
        c_entry["appointments"].append(serialize_doc(appt))

    customers_list = list(customer_map.values())
    return {
        "success": True,
        "count": len(customers_list),
        "data": customers_list
    }

@router.get("/{clinic_id}")
async def get_clinic_by_id(clinic_id: str):
    clinic = await clinics_col.find_one({"_id": to_oid(clinic_id)})
    if not clinic:
        raise HTTPException(status_code=404, detail="Không tìm thấy phòng khám")

    c_ser = serialize_doc(clinic)
    owner = await users_col.find_one({"_id": to_oid(clinic.get("owner_id"))}, {"password_hash": 0})
    if owner:
        c_ser["owner_id"] = serialize_doc(owner)

    return {
        "success": True,
        "data": c_ser
    }

@router.post("")
async def create_clinic(req: ClinicDataRequest, current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("_id")
    data = req.dict()
    data["owner_id"] = to_oid(user_id)
    data["created_at"] = datetime.utcnow()
    data["updated_at"] = datetime.utcnow()

    res = await clinics_col.insert_one(data)
    data["_id"] = res.inserted_id
    return {
        "success": True,
        "data": serialize_doc(data)
    }

@router.put("/{clinic_id}")
async def update_clinic(clinic_id: str, req: ClinicDataRequest, current_user: dict = Depends(get_current_user)):
    user_id = str(current_user.get("_id"))
    user_role = current_user.get("role")

    clinic = await clinics_col.find_one({"_id": to_oid(clinic_id)})
    if not clinic:
        raise HTTPException(status_code=404, detail="Không tìm thấy phòng khám")

    if user_role != "ADMIN" and str(clinic.get("owner_id")) != user_id:
        raise HTTPException(status_code=403, detail="Bạn không có quyền chỉnh sửa phòng khám này")

    data = {k: v for k, v in req.dict().items() if v is not None}
    data["updated_at"] = datetime.utcnow()

    await clinics_col.update_one({"_id": to_oid(clinic_id)}, {"$set": data})
    updated = await clinics_col.find_one({"_id": to_oid(clinic_id)})
    return {
        "success": True,
        "data": serialize_doc(updated)
    }

@router.delete("/{clinic_id}")
async def delete_clinic(clinic_id: str, current_user: dict = Depends(get_current_user)):
    user_id = str(current_user.get("_id"))
    user_role = current_user.get("role")

    clinic = await clinics_col.find_one({"_id": to_oid(clinic_id)})
    if not clinic:
        raise HTTPException(status_code=404, detail="Không tìm thấy phòng khám")

    if user_role != "ADMIN" and str(clinic.get("owner_id")) != user_id:
        raise HTTPException(status_code=403, detail="Bạn không có quyền xóa phòng khám này")

    await clinics_col.delete_one({"_id": to_oid(clinic_id)})
    return {
        "success": True,
        "message": "Xóa thành công"
    }
