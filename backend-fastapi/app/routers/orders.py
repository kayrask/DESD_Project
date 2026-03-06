from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr

from app.supabase_client import get_supabase

router = APIRouter(prefix="/orders", tags=["orders"])


class OrderCreate(BaseModel):
    fullName: str
    email: EmailStr
    address: str
    city: str
    postalCode: str
    paymentMethod: str


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_order(order: OrderCreate):
    """
    Create a new checkout order in Supabase.
    """
    try:
        supabase = get_supabase()
        
        # Insert order into checkout_orders table
        response = supabase.table("checkout_orders").insert({
            "full_name": order.fullName,
            "email": order.email,
            "address": order.address,
            "city": order.city,
            "postal_code": order.postalCode,
            "payment_method": order.paymentMethod,
            "status": "pending"
        }).execute()
        
        if response.data:
            return {
                "id": response.data[0].get("id"),
                "message": "Order created successfully",
                "data": response.data[0]
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create order"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/{order_id}")
async def get_order(order_id: int):
    """
    Get a checkout order by ID from Supabase.
    """
    try:
        supabase = get_supabase()
        response = supabase.table("checkout_orders").select("*").eq("id", order_id).execute()
        
        if response.data:
            return response.data[0]
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
