from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime
from app.database import (
    appointments_col, users_col, pets_col, clinics_col, vets_col, services_col,
    to_oid, serialize_doc, serialize_list
)
from app.middlewares.auth import get_current_user
from app.services.notification_service import create_notification

router = APIRouter(prefix="/api/appointments", tags=["Appointments"])

class AppointmentCreateRequest(BaseModel):
    clinic_id: str
    pet_id: str
    veterinarian_id: Optional[str] = None
    service_id: Optional[str] = None
    appointment_date: str
    start_time: str
    reason: Optional[str] = ""
    symptoms: Optional[str] = ""
    notes: Optional[str] = ""

class AppointmentUpdateRequest(BaseModel):
    veterinarian_id: Optional[str] = None
    service_id: Optional[str] = None
    appointment_date: Optional[str] = None
    start_time: Optional[str] = None
    reason: Optional[str] = None
    symptoms: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None

class StatusUpdateRequest(BaseModel):
    status: str
    notes: Optional[str] = None

async def populate_appointment(appt_doc):
    if not appt_doc:
        return appt_doc
    a_ser = serialize_doc(appt_doc)

    if appt_doc.get("owner_id"):
        owner = await users_col.find_one({"_id": to_oid(appt_doc["owner_id"])}, {"password_hash": 0})
        if owner:
            a_ser["owner_id"] = serialize_doc(owner)

    if appt_doc.get("pet_id"):
        pet = await pets_col.find_one({"_id": to_oid(appt_doc["pet_id"])})
        if pet:
            a_ser["pet_id"] = serialize_doc(pet)

    if appt_doc.get("clinic_id"):
        clinic = await clinics_col.find_one({"_id": to_oid(appt_doc["clinic_id"])})
        if clinic:
            a_ser["clinic_id"] = serialize_doc(clinic)

    if appt_doc.get("veterinarian_id"):
        vet = await vets_col.find_one({"_id": to_oid(appt_doc["veterinarian_id"])})
        if vet:
            a_ser["veterinarian_id"] = serialize_doc(vet)

    if appt_doc.get("service_id"):
        svc = await services_col.find_one({"_id": to_oid(appt_doc["service_id"])})
        if svc:
            a_ser["service_id"] = serialize_doc(svc)

    return a_ser

@router.get("")
async def get_appointments(
    status: Optional[str] = Query(None),
    date: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user)
):
    user_role = current_user.get("role")
    user_id = current_user.get("_id")
    query = {}

    if status:
        query["status"] = status
    if date:
        query["appointment_date"] = date

    if user_role == "PET_OWNER":
        query["owner_id"] = to_oid(user_id)
    elif user_role == "CLINIC":
        clinic = await clinics_col.find_one({"owner_id": to_oid(user_id)})
        if clinic:
            query["clinic_id"] = clinic["_id"]
        else:
            return {"success": True, "count": 0, "data": []}
    elif user_role == "VETERINARIAN":
        vet = await vets_col.find_one({"user_id": to_oid(user_id)})
        if vet:
            query["veterinarian_id"] = vet["_id"]
        else:
            return {"success": True, "count": 0, "data": []}

    cursor = appointments_col.find(query).sort([("appointment_date", -1), ("start_time", -1)])
    appts = await cursor.to_list(length=1000)

    populated = []
    for a in appts:
        populated.append(await populate_appointment(a))

    return {
        "success": True,
        "count": len(populated),
        "data": populated
    }

@router.post("")
async def create_appointment(req: AppointmentCreateRequest, current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("_id")
    appt_doc = {
        "owner_id": to_oid(user_id),
        "clinic_id": to_oid(req.clinic_id),
        "pet_id": to_oid(req.pet_id),
        "veterinarian_id": to_oid(req.veterinarian_id) if req.veterinarian_id else None,
        "service_id": to_oid(req.service_id) if req.service_id else None,
        "appointment_date": req.appointment_date,
        "start_time": req.start_time,
        "reason": req.reason or "",
        "symptoms": req.symptoms or "",
        "notes": req.notes or "",
        "status": "PENDING",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }

    res = await appointments_col.insert_one(appt_doc)
    appt_doc["_id"] = res.inserted_id

    populated = await populate_appointment(appt_doc)

    # Gửi thông báo realtime cho chủ phòng khám
    clinic = await clinics_col.find_one({"_id": to_oid(req.clinic_id)})
    if clinic and clinic.get("owner_id"):
        pet_name = populated.get("pet_id", {}).get("name", "thú cưng") if isinstance(populated.get("pet_id"), dict) else "thú cưng"
        await create_notification(
            user_id=str(clinic["owner_id"]),
            notif_type="APPOINTMENT_CREATED",
            title="Lịch hẹn khám mới!",
            content=f"Khách hàng {current_user.get('full_name')} vừa đặt lịch khám cho {pet_name} vào lúc {req.start_time} ngày {req.appointment_date}.",
            reference_id=str(res.inserted_id),
            reference_type="APPOINTMENT"
        )

    return {
        "success": True,
        "message": "Đặt lịch hẹn thành công!",
        "data": populated
    }

@router.get("/{appt_id}")
async def get_appointment(appt_id: str):
    appt = await appointments_col.find_one({"_id": to_oid(appt_id)})
    if not appt:
        raise HTTPException(status_code=404, detail="Không tìm thấy lịch hẹn")
    return {
        "success": True,
        "data": await populate_appointment(appt)
    }

@router.patch("/{appt_id}/status")
async def update_appointment_status(appt_id: str, req: StatusUpdateRequest, current_user: dict = Depends(get_current_user)):
    appt = await appointments_col.find_one({"_id": to_oid(appt_id)})
    if not appt:
        raise HTTPException(status_code=404, detail="Không tìm thấy lịch hẹn")

    old_status = appt.get("status")
    new_status = req.status
    update_data = {"status": new_status, "updated_at": datetime.utcnow()}
    if req.notes is not None:
        update_data["notes"] = req.notes

    await appointments_col.update_one({"_id": to_oid(appt_id)}, {"$set": update_data})
    updated = await appointments_col.find_one({"_id": to_oid(appt_id)})
    populated = await populate_appointment(updated)

    # Bắn thông báo theo trạng thái
    owner_id = appt.get("owner_id")
    clinic_name = populated.get("clinic_id", {}).get("name", "Phòng khám") if isinstance(populated.get("clinic_id"), dict) else "Phòng khám"

    if new_status == "CONFIRMED":
        if owner_id:
            await create_notification(
                user_id=str(owner_id),
                notif_type="APPOINTMENT_CONFIRMED",
                title="Lịch hẹn đã được xác nhận!",
                content=f"Phòng khám {clinic_name} đã xác nhận lịch hẹn của bạn vào {appt.get('start_time')} ngày {appt.get('appointment_date')}.",
                reference_id=appt_id,
                reference_type="APPOINTMENT"
            )
        # Thông báo cho bác sĩ nếu có
        vet_id = appt.get("veterinarian_id")
        if vet_id:
            vet = await vets_col.find_one({"_id": to_oid(vet_id)})
            if vet and vet.get("user_id"):
                await create_notification(
                    user_id=str(vet["user_id"]),
                    notif_type="APPOINTMENT_ASSIGNED",
                    title="Bạn có ca khám mới!",
                    content=f"Bạn đã được phân công ca khám vào {appt.get('start_time')} ngày {appt.get('appointment_date')}.",
                    reference_id=appt_id,
                    reference_type="APPOINTMENT"
                )

    elif new_status == "COMPLETED":
        if owner_id:
            await create_notification(
                user_id=str(owner_id),
                notif_type="APPOINTMENT_COMPLETED",
                title="Khám bệnh hoàn thành!",
                content=f"Ca khám tại {clinic_name} đã hoàn tất. Bạn có thể kiểm tra sổ bệnh án của bé ngay.",
                reference_id=appt_id,
                reference_type="APPOINTMENT"
            )

    elif new_status == "CANCELLED":
        if owner_id:
            await create_notification(
                user_id=str(owner_id),
                notif_type="APPOINTMENT_CANCELLED",
                title="Lịch hẹn đã bị hủy",
                content=f"Lịch hẹn khám tại {clinic_name} vào {appt.get('start_time')} ngày {appt.get('appointment_date')} đã bị hủy.",
                reference_id=appt_id,
                reference_type="APPOINTMENT"
            )

    return {
        "success": True,
        "message": f"Cập nhật trạng thái thành {new_status} thành công!",
        "data": populated
    }

@router.delete("/{appt_id}")
async def delete_appointment(appt_id: str, current_user: dict = Depends(get_current_user)):
    await appointments_col.delete_one({"_id": to_oid(appt_id)})
    return {
        "success": True,
        "message": "Xóa lịch hẹn thành công"
    }
