from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.config import get_settings


class AMapError(Exception):
    """高德服务异常，用于统一封装错误信息。"""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class AMapClient:
    """
    高德 Web 服务 API 简单封装。
    目前只用到：
    - 地理编码：把地址转成经纬度
    - 周边搜索：根据经纬度搜索附近 POI
    """

    GEO_URL = "https://restapi.amap.com/v3/geocode/geo"
    AROUND_URL = "https://restapi.amap.com/v3/place/around"

    def __init__(self, api_key: Optional[str] = None) -> None:
        settings = get_settings()
        self.api_key = api_key or settings.amap_api_key
        if not self.api_key:
            raise AMapError("AMAP_API_KEY 未配置，请在环境变量中设置。")

    async def geocode(self, address: str) -> Tuple[float, float]:
        """
        把地址转换为 (longitude, latitude)。
        """
        params = {"key": self.api_key, "address": address}

        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(self.GEO_URL, params=params)

        if resp.status_code != 200:
            raise AMapError(f"高德地理编码接口请求失败，HTTP {resp.status_code}")

        data: Dict[str, Any] = resp.json()
        if data.get("status") != "1":
            raise AMapError(f"高德地理编码接口返回错误：{data.get('info', '未知错误')}")

        geocodes: List[Dict[str, Any]] = data.get("geocodes", [])
        if not geocodes:
            raise AMapError("未能根据该地址解析到坐标。")

        location = geocodes[0].get("location")
        if not location or "," not in location:
            raise AMapError("高德返回的坐标格式异常。")

        lon_str, lat_str = location.split(",", 1)
        return float(lon_str), float(lat_str)

    async def search_around(
        self,
        longitude: float,
        latitude: float,
        radius: int,
        keyword: str,
        page_size: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        在经纬度附近搜索 POI。
        这里只返回 POI 列表，字段在 service 层做进一步整理。
        """
        params = {
            "key": self.api_key,
            "location": f"{longitude},{latitude}",
            "radius": radius,
            "keywords": keyword,
            "offset": page_size,
            "page": 1,
        }

        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(self.AROUND_URL, params=params)

        if resp.status_code != 200:
            raise AMapError(f"高德周边搜索接口请求失败，HTTP {resp.status_code}")

        data: Dict[str, Any] = resp.json()
        if data.get("status") != "1":
            raise AMapError(f"高德周边搜索接口返回错误：{data.get('info', '未知错误')}")

        pois: List[Dict[str, Any]] = data.get("pois", []) or []
        return pois

