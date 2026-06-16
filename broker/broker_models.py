from pydantic import BaseModel
from typing import Optional

class Order(BaseModel):
    ticker: str
    action: str
    quantity: float
    price: Optional[float] = None
    type: str = "MARKET"
    status: str = "PENDING"
