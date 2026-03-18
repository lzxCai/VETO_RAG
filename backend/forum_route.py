from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from auth import get_user
from supabase_client import get_supabase


router = APIRouter(prefix="/api/forum", tags=["forum"])


class ForumCommentResponse(BaseModel):
    id: str
    post_id: str
    user_id: str
    author_name: str
    content: str
    created_at: str


class ForumPostResponse(BaseModel):
    id: str
    user_id: str
    author_name: str
    title: str
    content: str
    likes: int | None = 0
    created_at: str
    forum_comments: List[ForumCommentResponse] = Field(default_factory=list)


class CreatePostRequest(BaseModel):
    user_id: str
    title: str
    content: str


class CreateCommentRequest(BaseModel):
    user_id: str
    content: str


@router.get("/posts", response_model=List[ForumPostResponse])
async def get_forum_posts():
    """获取所有帖子及其评论，按创建时间倒序排列。"""
    try:
        supabase = get_supabase()
        result = (
            supabase.table("forum_posts")
            .select("*, forum_comments(*)")
            .order("created_at", desc=True)
            .execute()
        )
        return result.data or []
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取论坛帖子失败: {str(e)}")


@router.post("/posts", response_model=ForumPostResponse)
async def create_forum_post(request: CreatePostRequest):
    """创建帖子。"""
    try:
        user = await get_user(request.user_id)
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")

        supabase = get_supabase()
        insert_payload = {
            "user_id": request.user_id,
            "author_name": user["username"],
            "title": request.title,
            "content": request.content,
        }

        result = supabase.table("forum_posts").insert(insert_payload).execute()
        if not result.data:
            raise HTTPException(status_code=500, detail="创建帖子失败")

        created_post = result.data[0]
        created_post["forum_comments"] = []
        return created_post
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建帖子失败: {str(e)}")


@router.post("/posts/{post_id}/comments", response_model=ForumCommentResponse)
async def create_forum_comment(post_id: str, request: CreateCommentRequest):
    """为指定帖子创建评论。"""
    try:
        user = await get_user(request.user_id)
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")

        supabase = get_supabase()
        insert_payload = {
            "post_id": post_id,
            "user_id": request.user_id,
            "author_name": user["username"],
            "content": request.content,
        }

        result = supabase.table("forum_comments").insert(insert_payload).execute()
        if not result.data:
            raise HTTPException(status_code=500, detail="创建评论失败")

        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建评论失败: {str(e)}")
