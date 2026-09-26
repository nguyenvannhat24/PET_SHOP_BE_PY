import re
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.database import (
    users_col, clinics_col, appointments_col, pets_col,
    to_oid, serialize_doc, serialize_list
)
from app.middlewares.auth import get_current_user, require_roles

router = APIRouter(prefix="/api/admin", tags=["Admin"], dependencies=[Depends(require_roles("ADMIN"))])

class UserStatusRequest(BaseModel):
    status: str

class VerifyClinicRequest(BaseModel):
    is_verified: bool

class AdminAppointmentStatusRequest(BaseModel):
    status: str

@router.get("/dashboard")
async def get_admin_dashboard():
    total_users = await users_col.count_documents({})
    total_owners = await users_col.count_documents({"role": "PET_OWNER"})
    total_vets = await users_col.count_documents({"role": "VETERINARIAN"})
    total_clinics = await clinics_col.count_documents({})
    total_appointments = await appointments_col.count_documents({})
    completed_appointments = await appointments_col.count_documents({"status": "COMPLETED"})
    pending_appointments = await appointments_col.count_documents({"status": "PENDING"})

    # Lấy 5 lịch hẹn gần nhất
    recent_appts = await appointments_col.find({}).sort("created_at", -1).limit(5).to_list(length=5)
    populated_appts = []
    for a in recent_appts:
        a_ser = serialize_doc(a)
        if a.get("owner_id"):
            u = await users_col.find_one({"_id": to_oid(a["owner_id"])}, {"password_hash": 0})
            if u:
                a_ser["owner_id"] = serialize_doc(u)
        if a.get("pet_id"):
            p = await pets_col.find_one({"_id": to_oid(a["pet_id"])})
            if p:
                a_ser["pet_id"] = serialize_doc(p)
        if a.get("clinic_id"):
            c = await clinics_col.find_one({"_id": to_oid(a["clinic_id"])})
            if c:
                a_ser["clinic_id"] = serialize_doc(c)
        populated_appts.append(a_ser)

    return {
        "success": True,
        "data": {
            "stats": {
                "total_users": total_users,
                "total_owners": total_owners,
                "total_vets": total_vets,
                "total_clinics": total_clinics,
                "total_appointments": total_appointments,
                "completed_appointments": completed_appointments,
                "pending_appointments": pending_appointments
            },
            "recent_appointments": populated_appts
        }
    }

@router.get("/users")
async def get_admin_users(
    search: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    status: Optional[str] = Query(None)
):
    query = {}
    if role and role != "ALL":
        query["role"] = role
    if status and status != "ALL":
        query["status"] = status
    if search and search.strip():
        rgx = re.compile(search.strip(), re.IGNORECASE)
        query["$or"] = [{"full_name": rgx}, {"email": rgx}, {"phone": rgx}]

    users = await users_col.find(query, {"password_hash": 0}).sort("created_at", -1).to_list(length=1000)
    return {
        "success": True,
        "count": len(users),
        "data": serialize_list(users)
    }

@router.patch("/users/{user_id}/status")
async def update_user_status(user_id: str, req: UserStatusRequest):
    await users_col.update_one(
        {"_id": to_oid(user_id)},
        {"$set": {"status": req.status, "updated_at": datetime.utcnow()}}
    )
    return {
        "success": True,
        "message": f"Cập nhật trạng thái người dùng thành {req.status} thành công!"
    }

@router.delete("/users/{user_id}")
async def delete_user(user_id: str):
    await users_col.delete_one({"_id": to_oid(user_id)})
    return {
        "success": True,
        "message": "Xóa người dùng thành công!"
    }

@router.get("/clinics")
async def get_admin_clinics():
    clinics = await clinics_col.find({}).sort("created_at", -1).to_list(length=1000)
    populated = []
    for c in clinics:
        c_ser = serialize_doc(c)
        if c.get("owner_id"):
            u = await users_col.find_one({"_id": to_oid(c["owner_id"])}, {"password_hash": 0})
            if u:
                c_ser["owner"] = serialize_doc(u)
        populated.append(c_ser)

    return {
        "success": True,
        "count": len(populated),
        "data": populated
    }

@router.patch("/clinics/{clinic_id}/verify")
async def verify_clinic(clinic_id: str, req: VerifyClinicRequest):
    await clinics_col.update_one(
        {"_id": to_oid(clinic_id)},
        {"$set": {"is_verified": req.is_verified, "updated_at": datetime.utcnow()}}
    )
    return {
        "success": True,
        "message": "Cập nhật trạng thái xác thực phòng khám thành công!"
    }

@router.get("/appointments")
async def get_admin_appointments(
    status: Optional[str] = Query(None)
):
    query = {}
    if status and status != "ALL":
        query["status"] = status

    appts = await appointments_col.find(query).sort("created_at", -1).to_list(length=1000)
    populated = []
    for a in appts:
        a_ser = serialize_doc(a)
        if a.get("owner_id"):
            u = await users_col.find_one({"_id": to_oid(a["owner_id"])}, {"password_hash": 0})
            if u:
                a_ser["owner_id"] = serialize_doc(u)
        if a.get("pet_id"):
            p = await pets_col.find_one({"_id": to_oid(a["pet_id"])})
            if p:
                a_ser["pet_id"] = serialize_doc(p)
        if a.get("clinic_id"):
            c = await clinics_col.find_one({"_id": to_oid(a["clinic_id"])})
            if c:
                a_ser["clinic_id"] = serialize_doc(c)
        populated.append(a_ser)

    return {
        "success": True,
        "count": len(populated),
        "data": populated
    }

@router.patch("/appointments/{appt_id}/status")
async def update_admin_appointment_status(appt_id: str, req: AdminAppointmentStatusRequest):
    await appointments_col.update_one(
        {"_id": to_oid(appt_id)},
        {"$set": {"status": req.status, "updated_at": datetime.utcnow()}}
    )
    return {
        "success": True,
        "message": f"Cập nhật trạng thái lịch hẹn thành {req.status} thành công!"
    }
