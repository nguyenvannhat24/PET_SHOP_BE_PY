import re
from fastapi import APIRouter, Query
from typing import Optional
from app.database import clinics_col, vets_col, services_col, users_col, to_oid, serialize_doc, serialize_list

router = APIRouter(prefix="/api/search", tags=["Search"])

@router.get("")
async def search(
    q: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    species: Optional[str] = Query(None)
):
    results = {}
    text_query = {}
    if q and q.strip():
        rgx = re.compile(q.strip(), re.IGNORECASE)
        text_query["$or"] = [{"name": rgx}, {"description": rgx}]

    if not type or type == "clinic":
        clinics = await clinics_col.find(text_query).limit(10).to_list(length=10)
        results["clinics"] = serialize_list(clinics)

    if not type or type == "veterinarian":
        vet_query = {}
        if q and q.strip():
            rgx_v = re.compile(q.strip(), re.IGNORECASE)
            vet_query["$or"] = [{"specialty": rgx_v}, {"bio": rgx_v}, {"name": rgx_v}]
        vets = await vets_col.find(vet_query).limit(10).to_list(length=10)
        pop_vets = []
        for v in vets:
            v_ser = serialize_doc(v)
            if v.get("user_id"):
                u = await users_col.find_one({"_id": to_oid(v["user_id"])}, {"password_hash": 0})
                if u:
                    v_ser["user_id"] = serialize_doc(u)
            pop_vets.append(v_ser)
        results["veterinarians"] = pop_vets

    if not type or type == "service":
        srv_query = {**text_query}
        if species:
            srv_query["species"] = re.compile(species, re.IGNORECASE)
        services = await services_col.find(srv_query).limit(20).to_list(length=20)
        pop_srvs = []
        for s in services:
            s_ser = serialize_doc(s)
            if s.get("clinic_id"):
                c = await clinics_col.find_one({"_id": to_oid(s["clinic_id"])})
                if c:
                    s_ser["clinic_id"] = serialize_doc(c)
            pop_srvs.append(s_ser)
        results["services"] = pop_srvs

    return {
        "success": True,
        "data": results
    }
