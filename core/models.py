from dataclasses import dataclass
from typing import List

@dataclass
class SalesItem:
    product_name: str
    quantity: float  # destek: adet ve kg (ondalık miktar)
    unit_net: float
    line_gross: float

@dataclass
class Receipt:
    fis_id: str
    customer_name: str
    kdv_rate: float
    discount_rate: float
    vat_included: bool
    items: List[SalesItem]
