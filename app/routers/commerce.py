from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime
from app.database import products_col, categories_col, carts_col, orders_col, to_oid, serialize_doc, serialize_list
from app.middlewares.auth import get_current_user

# 1. Products Router
products_router = APIRouter(prefix="/api/products", tags=["Products"])

@products_router.get("")
async def get_products(category: Optional[str] = Query(None)):
    query = {"status": "ACTIVE"}
    if category:
        query["category_id"] = to_oid(category)
    prods = await products_col.find(query).to_list(length=100)
    return {"success": True, "count": len(prods), "data": serialize_list(prods)}

@products_router.get("/{id}")
async def get_product(id: str):
    prod = await products_col.find_one({"_id": to_oid(id)})
    if not prod:
        raise HTTPException(status_code=404, detail="Sản phẩm không tồn tại")
    return {"success": True, "data": serialize_doc(prod)}

# 2. Cart Router
cart_router = APIRouter(prefix="/api/cart", tags=["Cart"])

class CartItemRequest(BaseModel):
    product_id: str
    quantity: int

@cart_router.get("")
async def get_cart(current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("_id")
    cart = await carts_col.find_one({"user_id": to_oid(user_id)})
    if not cart:
        cart = {"user_id": to_oid(user_id), "items": [], "created_at": datetime.utcnow()}
        res = await carts_col.insert_one(cart)
        cart["_id"] = res.inserted_id
    return {"success": True, "data": serialize_doc(cart)}

@cart_router.post("/items")
async def add_to_cart(req: CartItemRequest, current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("_id")
    cart = await carts_col.find_one({"user_id": to_oid(user_id)})
    if not cart:
        cart = {"user_id": to_oid(user_id), "items": [], "created_at": datetime.utcnow()}
        res = await carts_col.insert_one(cart)
        cart["_id"] = res.inserted_id

    items = cart.get("items", [])
    found = False
    for it in items:
        if str(it.get("product_id")) == req.product_id:
            it["quantity"] += req.quantity
            found = True
            break
    if not found:
        items.append({"product_id": to_oid(req.product_id), "quantity": req.quantity})

    await carts_col.update_one({"_id": cart["_id"]}, {"$set": {"items": items, "updated_at": datetime.utcnow()}})
    updated = await carts_col.find_one({"_id": cart["_id"]})
    return {"success": True, "data": serialize_doc(updated)}

# 3. Orders Router
orders_router = APIRouter(prefix="/api/orders", tags=["Orders"])

class OrderRequest(BaseModel):
    items: List[Any]
    total_amount: float
    shipping_address: str
    phone: str
    payment_method: Optional[str] = "COD"

@orders_router.get("")
async def get_my_orders(current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("_id")
    orders = await orders_col.find({"user_id": to_oid(user_id)}).sort("created_at", -1).to_list(length=100)
    return {"success": True, "count": len(orders), "data": serialize_list(orders)}

@orders_router.post("")
async def create_order(req: OrderRequest, current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("_id")
    data = req.dict()
    data["user_id"] = to_oid(user_id)
    data["status"] = "PENDING"
    data["created_at"] = datetime.utcnow()
    data["updated_at"] = datetime.utcnow()

    res = await orders_col.insert_one(data)
    data["_id"] = res.inserted_id

    # Reset cart
    await carts_col.update_one({"user_id": to_oid(user_id)}, {"$set": {"items": []}})
    return {"success": True, "message": "Đặt hàng thành công!", "data": serialize_doc(data)}
