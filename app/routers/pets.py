from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from app.database import pets_col, users_col, to_oid, serialize_doc, serialize_list
from app.middlewares.auth import get_current_user

router = APIRouter(prefix="/api/pets", tags=["Pets"])

class PetCreateRequest(BaseModel):
    name: str
    species: str
    breed: Optional[str] = ""
    age: Optional[int] = 0
    gender: Optional[str] = "UNKNOWN"
    date_of_birth: Optional[str] = None
    weight: Optional[float] = None
    color: Optional[str] = ""
    avatar_url: Optional[str] = None
    image_url: Optional[str] = None
    is_neutered: Optional[bool] = False
    allergies: Optional[str] = ""
    chronic_conditions: Optional[str] = ""
    health_status: Optional[str] = ""
    notes: Optional[str] = ""

class PetUpdateRequest(BaseModel):
    name: Optional[str] = None
    species: Optional[str] = None
    breed: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    date_of_birth: Optional[str] = None
    weight: Optional[float] = None
    color: Optional[str] = None
    avatar_url: Optional[str] = None
    image_url: Optional[str] = None
    is_neutered: Optional[bool] = None
    allergies: Optional[str] = None
    chronic_conditions: Optional[str] = None
    health_status: Optional[str] = None
    notes: Optional[str] = None

def normalize_pet_avatar(pet_dict):
    if not pet_dict:
        return pet_dict
    av = pet_dict.get("avatar_url") or pet_dict.get("image_url") or ""
    pet_dict["avatar_url"] = av
    pet_dict["image_url"] = av
    return pet_dict

async def populate_pet_owner(pet_dict):
    if not pet_dict:
        return pet_dict
    normalize_pet_avatar(pet_dict)
    owner_id = pet_dict.get("owner_id")
    if owner_id:
        owner = await users_col.find_one({"_id": to_oid(owner_id)}, {"password_hash": 0})
        pet_dict["owner_id"] = serialize_doc(owner) if owner else owner_id
    return pet_dict

@router.get("")
async def get_pets(
    owner_id: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user)
):
    query = {}
    user_role = current_user.get("role")
    current_id = current_user.get("_id")

    if user_role == "PET_OWNER":
        query["owner_id"] = to_oid(current_id)
    elif owner_id:
        query["owner_id"] = to_oid(owner_id)

    cursor = pets_col.find(query).sort("created_at", -1)
    pets = await cursor.to_list(length=1000)

    # Populate owner
    populated_pets = []
    for p in pets:
        p_ser = serialize_doc(p)
        await populate_pet_owner(p_ser)
        populated_pets.append(p_ser)

    return {
        "success": True,
        "count": len(populated_pets),
        "data": populated_pets
    }

@router.post("")
async def create_pet(req: PetCreateRequest, current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("_id")
    avatar = req.avatar_url or req.image_url or ""
    pet_doc = {
        "owner_id": to_oid(user_id),
        "name": req.name,
        "species": req.species,
        "breed": req.breed or "",
        "age": req.age or 0,
        "gender": req.gender or "UNKNOWN",
        "date_of_birth": req.date_of_birth,
        "weight": req.weight,
        "color": req.color or "",
        "avatar_url": avatar,
        "image_url": avatar,
        "is_neutered": bool(req.is_neutered),
        "allergies": req.allergies or "",
        "chronic_conditions": req.chronic_conditions or "",
        "health_status": req.health_status or "Khỏe mạnh",
        "notes": req.notes or "",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }

    res = await pets_col.insert_one(pet_doc)
    pet_doc["_id"] = res.inserted_id

    p_ser = serialize_doc(pet_doc)
    await populate_pet_owner(p_ser)

    return {
        "success": True,
        "message": "Thêm thú cưng thành công!",
        "data": p_ser
    }

@router.get("/{pet_id}")
async def get_pet(pet_id: str, current_user: dict = Depends(get_current_user)):
    pet = await pets_col.find_one({"_id": to_oid(pet_id)})
    if not pet:
        raise HTTPException(status_code=404, detail="Không tìm thấy thú cưng")

    p_ser = serialize_doc(pet)
    await populate_pet_owner(p_ser)
    return {
        "success": True,
        "data": p_ser
    }

@router.put("/{pet_id}")
async def update_pet(pet_id: str, req: PetUpdateRequest, current_user: dict = Depends(get_current_user)):
    pet = await pets_col.find_one({"_id": to_oid(pet_id)})
    if not pet:
        raise HTTPException(status_code=404, detail="Không tìm thấy thú cưng")

    user_role = current_user.get("role")
    current_id = str(current_user.get("_id"))
    if user_role != "ADMIN" and str(pet.get("owner_id")) != current_id:
        raise HTTPException(status_code=403, detail="Bạn không có quyền chỉnh sửa thú cưng này")

    update_data = {k: v for k, v in req.dict().items() if v is not None}
    
    # Đồng bộ avatar_url và image_url
    if "avatar_url" in update_data and not update_data.get("image_url"):
        update_data["image_url"] = update_data["avatar_url"]
    elif "image_url" in update_data and not update_data.get("avatar_url"):
        update_data["avatar_url"] = update_data["image_url"]

    update_data["updated_at"] = datetime.utcnow()

    await pets_col.update_one({"_id": to_oid(pet_id)}, {"$set": update_data})
    updated = await pets_col.find_one({"_id": to_oid(pet_id)})

    p_ser = serialize_doc(updated)
    await populate_pet_owner(p_ser)
    return {
        "success": True,
        "message": "Cập nhật thông tin thú cưng thành công!",
        "data": p_ser
    }

@router.delete("/{pet_id}")
async def delete_pet(pet_id: str, current_user: dict = Depends(get_current_user)):
    pet = await pets_col.find_one({"_id": to_oid(pet_id)})
    if not pet:
        raise HTTPException(status_code=404, detail="Không tìm thấy thú cưng")

    user_role = current_user.get("role")
    current_id = str(current_user.get("_id"))
    if user_role != "ADMIN" and str(pet.get("owner_id")) != current_id:
        raise HTTPException(status_code=403, detail="Bạn không có quyền xóa thú cưng này")

    await pets_col.delete_one({"_id": to_oid(pet_id)})
    return {
        "success": True,
        "message": "Xóa thú cưng thành công!"
    }
