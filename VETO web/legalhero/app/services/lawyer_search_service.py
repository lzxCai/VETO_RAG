from __future__ import annotations

from typing import List

from app.schemas.lawyer_search import (
    AddressQuery,
    LawyerItem,
    LawyerSearchResponse,
    LocationQuery,
    SearchCenter,
)
from app.services.amap_client import AMapClient, AMapError


class LawyerSearchService:
    """
    律师事务所检索业务封装。
    """

    def __init__(self, amap_client: AMapClient | None = None) -> None:
        self._amap = amap_client or AMapClient()

    async def search_by_location(self, query: LocationQuery) -> LawyerSearchResponse:
        pois = await self._amap.search_around(
            longitude=query.longitude,
            latitude=query.latitude,
            radius=query.radius or 5000,
            keyword=query.keyword or "律师事务所",
        )

        items: List[LawyerItem] = []
        for poi in pois:
            location = poi.get("location") or ""
            if "," not in location:
                continue
            lon_str, lat_str = location.split(",", 1)

            tel = poi.get("tel") or poi.get("telephone") or ""

            # 高德 distance 字段是字符串，单位米
            distance_str = poi.get("distance") or "0"
            try:
                distance = int(float(distance_str))
            except ValueError:
                distance = 0

            items.append(
                LawyerItem(
                    name=poi.get("name", ""),
                    address=poi.get("address", "") or poi.get("adname", ""),
                    longitude=float(lon_str),
                    latitude=float(lat_str),
                    distance=distance,
                    tel=tel or None,
                )
            )

        return LawyerSearchResponse(
            success=True,
            query_mode="location",
            keyword=query.keyword or "律师事务所",
            center=SearchCenter(longitude=query.longitude, latitude=query.latitude),
            count=len(items),
            items=items,
            message=None if items else "在指定范围内未找到律师事务所。",
        )

    async def search_by_address(self, query: AddressQuery) -> LawyerSearchResponse:
        # 1. 先把地址转坐标
        lon, lat = await self._amap.geocode(query.address)

        # 2. 复用按坐标检索逻辑
        location_query = LocationQuery(
            longitude=lon,
            latitude=lat,
            radius=query.radius,
            keyword=query.keyword,
        )
        base_resp = await self.search_by_location(location_query)

        # 覆盖 query_mode，补充一下 message（携带原始地址）
        base_resp.query_mode = "address"
        if base_resp.message:
            base_resp.message = f"{base_resp.message}（地址：{query.address}）"
        return base_resp


async def search_lawyers_by_location(query: LocationQuery) -> LawyerSearchResponse:
    service = LawyerSearchService()
    return await service.search_by_location(query)


async def search_lawyers_by_address(query: AddressQuery) -> LawyerSearchResponse:
    service = LawyerSearchService()
    return await service.search_by_address(query)

