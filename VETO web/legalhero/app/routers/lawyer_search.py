from fastapi import APIRouter, HTTPException, Response

from app.schemas.lawyer_search import AddressQuery, LawyerSearchResponse, LocationQuery
from app.services.amap_client import AMapError
from app.services.lawyer_search_service import (
    search_lawyers_by_address,
    search_lawyers_by_location,
)

router = APIRouter(prefix="/api/lawyer", tags=["lawyer-search"])


@router.post(
    "/search-by-location",
    response_model=LawyerSearchResponse,
    summary="按经纬度检索附近律师事务所",
)
async def search_by_location_endpoint(payload: LocationQuery) -> LawyerSearchResponse:
    try:
        return await search_lawyers_by_location(payload)
    except AMapError as e:
        # 高德相关错误，返回 502 以区分参数错误
        raise HTTPException(status_code=502, detail=e.message)


@router.options("/search-by-location", include_in_schema=False)
async def options_search_by_location() -> Response:
    # 让浏览器的 CORS 预检请求返回 200
    return Response(status_code=200)


@router.post(
    "/search-by-address",
    response_model=LawyerSearchResponse,
    summary="按地址文本检索附近律师事务所",
)
async def search_by_address_endpoint(payload: AddressQuery) -> LawyerSearchResponse:
    try:
        return await search_lawyers_by_address(payload)
    except AMapError as e:
        raise HTTPException(status_code=502, detail=e.message)


@router.options("/search-by-address", include_in_schema=False)
async def options_search_by_address() -> Response:
    return Response(status_code=200)

