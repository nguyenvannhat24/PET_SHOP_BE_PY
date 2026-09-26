from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime
from app.database import (
    vets_col, users_col, clinics_col, appointments_col, pets_col,
    to_oid, serialize_doc, serialize_list
)
from app.middlewares.auth import get_current_user

router = APIRouter(prefix="/api/veterinarians", tags=["Veterinarians"])

class VetProfileRequest(BaseModel):
    name: Optional[str] = None
    specialty: Optional[str] = None
    license_number: Optional[str] = None
    years_of_experience: Optional[int] = None
    bio: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    avatar_url: Optional[str] = None
    clinic_id: Optional[str] = None
    working_hours: Optional[Any] = None
    status: Optional[str] = None

async def populate_vet(vet_doc):
    if not vet_doc:
        return vet_doc
    vet_ser = serialize_doc(vet_doc)
    if vet_doc.get("user_id"):
        user = await users_col.find_one({"_id": to_oid(vet_doc["user_id"])}, {"password_hash": 0})
        if user:
            vet_ser["user_id"] = serialize_doc(user)
    if vet_doc.get("clinic_id"):
        clinic = await clinics_col.find_one({"_id": to_oid(vet_doc["clinic_id"])})
        if clinic:
            vet_ser["clinic_id"] = serialize_doc(clinic)
    return vet_ser

@router.get("")
async def get_veterinarians(clinic_id: Optional[str] = Query(None)):
    query = {}
    if clinic_id:
        query["clinic_id"] = to_oid(clinic_id)

    cursor = vets_col.find(query).sort("created_at", -1)
    vets = await cursor.to_list(length=1000)

    populated = []
    for v in vets:
        p_vet = await populate_vet(v)
        populated.append(p_vet)

    return {
        "success": True,
        "count": len(populated),
        "data": populated
    }

@router.get("/my-profile")
async def get_my_vet_profile(current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("_id")
    vet = await vets_col.find_one({"user_id": to_oid(user_id)})
    if not vet:
        # Tự động tạo hồ sơ mặc định nếu chưa có
        default_vet = {
            "user_id": to_oid(user_id),
            "name": current_user.get("full_name", "Bác sĩ"),
            "specialty": "Đa khoa",
            "phone": current_user.get("phone", ""),
            "email": current_user.get("email", ""),
            "avatar_url": current_user.get("avatar_url", ""),
            "status": "ACTIVE",
            "working_hours": {
                "start": "08:00",
                "end": "17:30",
                "days": ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7"]
            },
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        res = await vets_col.insert_one(default_vet)
        vet = await vets_col.find_one({"_id": res.inserted_id})

    return {
        "success": True,
        "data": await populate_vet(vet)
    }

@router.put("/my-profile")
async def update_my_vet_profile(req: VetProfileRequest, current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("_id")
    update_data = {k: v for k, v in req.dict().items() if v is not None}
    if "clinic_id" in update_data and update_data["clinic_id"]:
        update_data["clinic_id"] = to_oid(update_data["clinic_id"])
    update_data["updated_at"] = datetime.utcnow()

    await vets_col.update_one({"user_id": to_oid(user_id)}, {"$set": update_data})
    saved = await vets_col.find_one({"user_id": to_oid(user_id)})
    return {
        "success": True,
        "message": "Cập nhật hồ sơ bác sĩ thành công!",
        "data": await populate_vet(saved)
    }

@router.get("/my-patients")
async def get_my_patients(current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("_id")
    vet = await vets_col.find_one({"user_id": to_oid(user_id)})
    if not vet:
        return {"success": True, "count": 0, "data": []}

    cursor = appointments_col.find({"veterinarian_id": vet["_id"]}).sort("appointment_date", -1)
    appts = await cursor.to_list(length=1000)

    patient_map = {}
    for a in appts:
        pet_id = a.get("pet_id")
        if not pet_id:
            continue
        p_key = str(pet_id)
        if p_key not in patient_map:
            pet_doc = await pets_col.find_one({"_id": to_oid(pet_id)})
            if pet_doc:
                p_ser = serialize_doc(pet_doc)
                owner = await users_col.find_one({"_id": to_oid(pet_doc.get("owner_id"))}, {"password_hash": 0})
                if owner:
                    p_ser["owner"] = serialize_doc(owner)
                p_ser["last_visit"] = a.get("appointment_date")
                p_ser["total_visits"] = 0
                patient_map[p_key] = p_ser

        if p_key in patient_map:
            patient_map[p_key]["total_visits"] += 1

    patients_list = list(patient_map.values())
    return {
        "success": True,
        "count": len(patients_list),
        "data": patients_list
    }

@router.get("/{vet_id}")
async def get_veterinarian(vet_id: str):
    vet = await vets_col.find_one({"_id": to_oid(vet_id)})
    if not vet:
        raise HTTPException(status_code=404, detail="Không tìm thấy bác sĩ")
    return {
        "success": True,
        "data": await populate_vet(vet)
    }

@router.post("")
async def create_veterinarian(req: VetProfileRequest, current_user: dict = Depends(get_current_user)):
    data = req.dict()
    if data.get("clinic_id"):
        data["clinic_id"] = to_oid(data["clinic_id"])
    data["created_at"] = datetime.utcnow()
    data["updated_at"] = datetime.utcnow()

    res = await vets_col.insert_one(data)
    data["_id"] = res.inserted_id
    return {
        "success": True,
        "data": await populate_vet(data)
    }

@router.put("/{vet_id}")
async def update_veterinarian(vet_id: str, req: VetProfileRequest, current_user: dict = Depends(get_current_user)):
    data = {k: v for k, v in req.dict().items() if v is not None}
    if data.get("clinic_id"):
        data["clinic_id"] = to_oid(data["clinic_id"])
    data["updated_at"] = datetime.utcnow()

    await vets_col.update_one({"_id": to_oid(vet_id)}, {"$set": data})
    saved = await vets_col.find_one({"_id": to_oid(vet_id)})
    return {
        "success": True,
        "data": await populate_vet(saved)
    }

@router.delete("/{vet_id}")
async def delete_veterinarian(vet_id: str, current_user: dict = Depends(get_current_user)):
    await vets_col.delete_one({"_id": to_oid(vet_id)})
    return {
        "success": True,
        "message": "Xóa bác sĩ thành công"
    }
