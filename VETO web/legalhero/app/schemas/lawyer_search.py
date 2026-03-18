from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class LocationQuery(BaseModel):
    longitude: float = Field(..., description="经度")
    latitude: float = Field(..., description="纬度")
    radius: Optional[int] = Field(5000, description="搜索半径，单位米")
    keyword: Optional[str] = Field("律师事务所", description="搜索关键词")

    @field_validator("radius")
    @classmethod
    def radius_must_be_positive(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError("radius 必须为正整数")
        return v


class AddressQuery(BaseModel):
    address: str = Field(..., min_length=1, description="地址文本，如学校名称或详细地址")
    radius: Optional[int] = Field(5000, description="搜索半径，单位米")
    keyword: Optional[str] = Field("律师事务所", description="搜索关键词")

    @field_validator("radius")
    @classmethod
    def radius_must_be_positive(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError("radius 必须为正整数")
        return v


class SearchCenter(BaseModel):
    longitude: float
    latitude: float


class LawyerItem(BaseModel):
    name: str
    address: str
    longitude: float
    latitude: float
    distance: int
    tel: Optional[str] = None


class LawyerSearchResponse(BaseModel):
    success: bool
    query_mode: Literal["location", "address"]
    keyword: str
    center: SearchCenter
    count: int
    items: List[LawyerItem]
    message: Optional[str] = None

