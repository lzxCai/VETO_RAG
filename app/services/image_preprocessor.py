"""
图像预处理入口（手机拍照场景预留）。

当前实现默认透传，后续可扩展：
- 倾斜校正
- 透视变换
- 阴影/反光抑制
- 清晰度增强
"""

from __future__ import annotations

from typing import Dict, List


def preprocess_page_images(
    page_images: List[Dict],
    enable_preprocess: bool = False,
) -> List[Dict]:
    """
    对页面图像进行预处理。
    当前版本不改变图像，仅透传。
    """
    if not enable_preprocess:
        return page_images

    # V1 先留入口，不做重处理，避免引入新依赖与不稳定因素。
    return page_images
