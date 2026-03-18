import os
from functools import lru_cache


class Settings:
    """
    简单配置对象，目前只负责管理高德 Key。
    后续如果有更多配置，可以继续往这里加。
    """

    def __init__(self) -> None:
        self.amap_api_key: str | None = os.getenv("AMAP_API_KEY")


@lru_cache
def get_settings() -> Settings:
    return Settings()

