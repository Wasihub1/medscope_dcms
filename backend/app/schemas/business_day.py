from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, model_validator
from backend.app.schemas.common import BaseSchema


class ChannelBalanceItem(BaseModel):
    channel: str  # CASH, BKASH, NAGAD, BANK_TRANSFER, POS_CARD
    opening_balance: int = Field(default=0, ge=0)
    received_amount: int = Field(default=0, ge=0)


class BusinessDayOpenRequest(BaseModel):
    opening_float: int = Field(default=0, ge=0, description="Physical cash float in drawer")
    opening_balance: Optional[int] = None
    channel_balances: Optional[List[ChannelBalanceItem]] = None
    notes: Optional[str] = Field(default=None, max_length=500)

    @model_validator(mode="before")
    @classmethod
    def normalize_open_req(cls, data):
        if isinstance(data, dict):
            if "opening_balance" in data and "opening_float" not in data:
                data["opening_float"] = int(data["opening_balance"] or 0)
        return data


class BusinessDayChannelBalanceResponse(BaseSchema):
    channel: str
    opening_balance: int
    received_amount: int
    current_balance: Optional[int] = None
    collections_count: Optional[int] = 0

    @model_validator(mode="after")
    def populate_channel_balance(self):
        if self.current_balance is None:
            self.current_balance = self.opening_balance + self.received_amount
        return self


class BusinessDayStatusResponse(BaseSchema):
    is_open: bool
    current_business_day_id: Optional[int] = None
    id: Optional[str] = None
    day_number: Optional[int] = None
    opened_at: Optional[datetime] = None
    opened_by_name: Optional[str] = None
    opening_float: int = 0
    opening_balance: Optional[int] = None
    total_received_today: int = 0
    total_collections: Optional[int] = None
    total_refunds: Optional[int] = 0
    current_balance: Optional[int] = None
    status: Optional[str] = None
    business_date: Optional[str] = None
    channels: List[BusinessDayChannelBalanceResponse] = []
    channel_balances: Optional[List[BusinessDayChannelBalanceResponse]] = None
    can_receptionist_open: bool = True
    can_receptionist_close: bool = False  # Strictly False for Receptionist

    @model_validator(mode="after")
    def populate_aliases(self):
        if self.id is None and self.current_business_day_id:
            self.id = str(self.current_business_day_id)
        if self.opening_balance is None:
            self.opening_balance = self.opening_float
        if self.total_collections is None:
            self.total_collections = self.total_received_today
        if self.current_balance is None:
            self.current_balance = self.opening_float + self.total_received_today
        if self.status is None:
            self.status = "OPEN" if self.is_open else "CLOSED"
        if not self.business_date and self.opened_at:
            self.business_date = self.opened_at.strftime("%Y-%m-%d")
        if self.channel_balances is None:
            self.channel_balances = self.channels
        return self

