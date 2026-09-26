from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime
from app.database import (
    vaccinations_col, pets_col, vets_col, clinics_col,
    to_oid, serialize_doc, serialize_list
)
from app.middlewares.auth import get_current_user

router = APIRouter(prefix="/api/vaccinations", tags=["Vaccinations"])

class VaccinationRequest(BaseModel):
    pet_id: str
    vaccine_name: str
    administered_date: str
    next_due_date: Optional[str] = None
    veterinarian_id: Optional[str] = None
    clinic_id: Optional[str] = None
    batch_number: Optional[str] = ""
    notes: Optional[str] = ""

async def populate_vaccination(vac_doc):
    if not vac_doc:
        return vac_doc
    v_ser = serialize_doc(vac_doc)
    if vac_doc.get("pet_id"):
        pet = await pets_col.find_one({"_id": to_oid(vac_doc["pet_id"])})
        if pet:
            v_ser["pet_id"] = serialize_doc(pet)
    if vac_doc.get("veterinarian_id"):
        vet = await vets_col.find_one({"_id": to_oid(vac_doc["veterinarian_id"])})
        if vet:
            v_ser["veterinarian_id"] = serialize_doc(vet)
    if vac_doc.get("clinic_id"):
        clinic = await clinics_col.find_one({"_id": to_oid(vac_doc["clinic_id"])})
        if clinic:
            v_ser["clinic_id"] = serialize_doc(clinic)
    return v_ser

@router.get("")
async def get_vaccinations(
    pet_id: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user)
):
    query = {}
    if pet_id:
        query["pet_id"] = to_oid(pet_id)

    cursor = vaccinations_col.find(query).sort("administered_date", -1)
    vacs = await cursor.to_list(length=1000)

    populated = []
    for v in vacs:
        populated.append(await populate_vaccination(v))

    return {
        "success": True,
        "count": len(populated),
        "data": populated
    }

@router.post("")
async def create_vaccination(req: VaccinationRequest, current_user: dict = Depends(get_current_user)):
    data = req.dict()
    data["pet_id"] = to_oid(data["pet_id"])
    if data.get("veterinarian_id"):
        data["veterinarian_id"] = to_oid(data["veterinarian_id"])
    if data.get("clinic_id"):
        data["clinic_id"] = to_oid(data["clinic_id"])
    data["created_at"] = datetime.utcnow()
    data["updated_at"] = datetime.utcnow()

    res = await vaccinations_col.insert_one(data)
    data["_id"] = res.inserted_id

    return {
        "success": True,
        "message": "Thêm sổ tiêm chủng thành công!",
        "data": await populate_vaccination(data)
    }

@router.get("/{vac_id}")
async def get_vaccination(vac_id: str):
    vac = await vaccinations_col.find_one({"_id": to_oid(vac_id)})
    if not vac:
        raise HTTPException(status_code=404, detail="Không tìm thấy lịch tiêm chủng")
    return {
        "success": True,
        "data": await populate_vaccination(vac)
    }

@router.put("/{vac_id}")
async def update_vaccination(vac_id: str, req: VaccinationRequest, current_user: dict = Depends(get_current_user)):
    data = {k: v for k, v in req.dict().items() if v is not None}
    if data.get("pet_id"):
        data["pet_id"] = to_oid(data["pet_id"])
    if data.get("veterinarian_id"):
        data["veterinarian_id"] = to_oid(data["veterinarian_id"])
    if data.get("clinic_id"):
        data["clinic_id"] = to_oid(data["clinic_id"])
    data["updated_at"] = datetime.utcnow()

    await vaccinations_col.update_one({"_id": to_oid(vac_id)}, {"$set": data})
    updated = await vaccinations_col.find_one({"_id": to_oid(vac_id)})
    return {
        "success": True,
        "message": "Cập nhật tiêm chủng thành công!",
        "data": await populate_vaccination(updated)
    }

@router.delete("/{vac_id}")
async def delete_vaccination(vac_id: str, current_user: dict = Depends(get_current_user)):
    await vaccinations_col.delete_one({"_id": to_oid(vac_id)})
    return {
        "success": True,
        "message": "Xóa tiêm chủng thành công"
    }
