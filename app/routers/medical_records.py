from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime
from app.database import (
    medical_records_col, pets_col, vets_col, clinics_col,
    to_oid, serialize_doc, serialize_list
)
from app.middlewares.auth import get_current_user

router = APIRouter(prefix="/api/medical-records", tags=["Medical Records"])

class MedicalRecordRequest(BaseModel):
    pet_id: str
    veterinarian_id: Optional[str] = None
    clinic_id: Optional[str] = None
    diagnosis: str
    symptoms: Optional[str] = ""
    treatment: Optional[str] = ""
    prescription: Optional[Any] = None
    notes: Optional[str] = ""
    follow_up_date: Optional[str] = None

async def populate_record(rec_doc):
    if not rec_doc:
        return rec_doc
    r_ser = serialize_doc(rec_doc)
    if rec_doc.get("pet_id"):
        pet = await pets_col.find_one({"_id": to_oid(rec_doc["pet_id"])})
        if pet:
            r_ser["pet_id"] = serialize_doc(pet)
    if rec_doc.get("veterinarian_id"):
        vet = await vets_col.find_one({"_id": to_oid(rec_doc["veterinarian_id"])})
        if vet:
            r_ser["veterinarian_id"] = serialize_doc(vet)
    if rec_doc.get("clinic_id"):
        clinic = await clinics_col.find_one({"_id": to_oid(rec_doc["clinic_id"])})
        if clinic:
            r_ser["clinic_id"] = serialize_doc(clinic)
    return r_ser

@router.get("")
async def get_medical_records(
    pet_id: Optional[str] = Query(None),
    veterinarian_id: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user)
):
    query = {}
    if pet_id:
        query["pet_id"] = to_oid(pet_id)
    if veterinarian_id:
        query["veterinarian_id"] = to_oid(veterinarian_id)

    cursor = medical_records_col.find(query).sort("created_at", -1)
    records = await cursor.to_list(length=1000)

    populated = []
    for r in records:
        populated.append(await populate_record(r))

    return {
        "success": True,
        "count": len(populated),
        "data": populated
    }

@router.post("")
async def create_medical_record(req: MedicalRecordRequest, current_user: dict = Depends(get_current_user)):
    data = req.dict()
    data["pet_id"] = to_oid(data["pet_id"])
    if data.get("veterinarian_id"):
        data["veterinarian_id"] = to_oid(data["veterinarian_id"])
    if data.get("clinic_id"):
        data["clinic_id"] = to_oid(data["clinic_id"])
    data["created_at"] = datetime.utcnow()
    data["updated_at"] = datetime.utcnow()

    res = await medical_records_col.insert_one(data)
    data["_id"] = res.inserted_id

    return {
        "success": True,
        "message": "Tạo hồ sơ bệnh án thành công!",
        "data": await populate_record(data)
    }

@router.get("/pet/{pet_id}")
async def get_pet_medical_records(pet_id: str, current_user: dict = Depends(get_current_user)):
    cursor = medical_records_col.find({"pet_id": to_oid(pet_id)}).sort("created_at", -1)
    records = await cursor.to_list(length=1000)
    populated = []
    for r in records:
        populated.append(await populate_record(r))

    return {
        "success": True,
        "count": len(populated),
        "data": populated
    }

@router.get("/{record_id}")
async def get_medical_record(record_id: str):
    rec = await medical_records_col.find_one({"_id": to_oid(record_id)})
    if not rec:
        raise HTTPException(status_code=404, detail="Không tìm thấy hồ sơ bệnh án")
    return {
        "success": True,
        "data": await populate_record(rec)
    }

@router.put("/{record_id}")
async def update_medical_record(record_id: str, req: MedicalRecordRequest, current_user: dict = Depends(get_current_user)):
    data = {k: v for k, v in req.dict().items() if v is not None}
    if data.get("pet_id"):
        data["pet_id"] = to_oid(data["pet_id"])
    if data.get("veterinarian_id"):
        data["veterinarian_id"] = to_oid(data["veterinarian_id"])
    if data.get("clinic_id"):
        data["clinic_id"] = to_oid(data["clinic_id"])
    data["updated_at"] = datetime.utcnow()

    await medical_records_col.update_one({"_id": to_oid(record_id)}, {"$set": data})
    updated = await medical_records_col.find_one({"_id": to_oid(record_id)})
    return {
        "success": True,
        "message": "Cập nhật hồ sơ bệnh án thành công!",
        "data": await populate_record(updated)
    }

@router.delete("/{record_id}")
async def delete_medical_record(record_id: str, current_user: dict = Depends(get_current_user)):
    await medical_records_col.delete_one({"_id": to_oid(record_id)})
    return {
        "success": True,
        "message": "Xóa hồ sơ bệnh án thành công"
    }
