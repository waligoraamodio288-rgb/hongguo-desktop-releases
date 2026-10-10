"""Read-only desktop social API; upstream signing belongs to hongguo.api."""
import threading
import time
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query


def _number(value):
    try:
        return max(0, int(value))
    except (ValueError, TypeError):
        return 0


def _item(value, reply=False):
    common = value.get("Common" if reply else "common") or {}
    content = common.get("content") or {}
    user = (common.get("user_info") or {}).get("base_info") or {}
    stat = value.get("stat") or {}
    images = content.get("image_data_list") or {}
    if isinstance(images, dict):
        images = images.get("image_data") or []
    return {"id": str(value.get("reply_id" if reply else "comment_id") or ""),
            "parent_id": str(value.get("reply_to_comment_id") or ""),
            "text": str(content.get("text") or ""),
            "author": str(user.get("user_name") or "红果用户"),
            "created_at": _number(common.get("create_timestamp")),
            "likes": _number(stat.get("digg_count")),
            "replies": _number(stat.get("reply_count")),
            "image_count": len(images) if isinstance(images, list) else 0,
            "offset_ms": _number((value.get("expand") or {}).get("offset_time"))}


def _page(data, reply=False):
    info = data.get("comment_list_info" if reply else "common_list_info") or {}
    rows = data.get("reply_list" if reply else "data_list") or []
    items = [_item(row if reply else row.get("comment") or {}, reply) for row in rows]
    cursor = str(info.get("cursor") or "")
    return {"items": [item for item in items if item["id"]],
            "cursor": cursor, "has_more": bool(info.get("has_more")) and bool(cursor),
            "total": _number(info.get("total")),
            "next_offset_ms": _number((data.get("extra") or {}).get("next_query_danmaku_list_time"))}


class SocialService:
    def __init__(self, provider):
        self.provider = provider
        self.stats_cache = {}
        self.lock = threading.Lock()

    def context(self, sid, ep):
        _, episodes = self.provider.get_episodes(sid)
        episode = next((row for row in episodes if row.get("index") == ep), None)
        if not episode or not episode.get("vid"):
            raise HTTPException(404, "未找到当前集")
        return episode

    def request(self, path, body):
        result = self.provider.api("POST", path, body=body, max_retries=1)
        if result.get("code") != 0 or not isinstance(result.get("data"), dict):
            raise HTTPException(502, "红果暂未返回社交数据，请稍后重试")
        return result["data"]

    def body(self, sid, group, kind, cursor):
        return {"group_id": group, "group_type": 1 if kind == "series" else 30,
                "comment_type": {"episode": 4, "series": 2, "danmaku": 20}[kind],
                "comment_source": {"episode": 4, "series": 1, "danmaku": 601}[kind],
                "server_channel": {"episode": 18, "series": 46, "danmaku": 1000}[kind],
                "sort": 1, "count": 90 if kind == "danmaku" else 20, "cursor": cursor,
                "aid": int(self.provider.CFG["base_query"]["aid"]), "compliance_status": 0,
                "business_param": {"book_id": sid, "need_count": not bool(cursor)}}

    def comments(self, sid, ep, kind, cursor="", offset_ms=0):
        episode = self.context(sid, ep)
        group = sid if kind == "series" else str(episode["vid"])
        body = self.body(sid, group, kind, cursor)
        if kind == "episode":
            body["business_param"]["sort"] = "video_innerflow"
        if kind == "danmaku":
            body["business_param"] = {"book_id": sid, "start_offset_time": offset_ms,
                                      "playlet_item_duration": int(float(episode.get("duration") or 0) * 1000),
                                      "need_danmaku_guide_type": []}
        return _page(self.request(f"/novel/commentapi/comment/list/{group}/v1/", body))

    def replies(self, sid, ep, comment_id, cursor=""):
        episode = self.context(sid, ep)
        body = self.body(sid, str(episode["vid"]), "episode", cursor)
        body.update(comment_id=comment_id, comment_source=504)
        body["business_param"]["need_count"] = False
        return _page(self.request(f"/novel/commentapi/reply/list/{comment_id}/v1/", body), True)

    def metrics(self, sid, ep, refresh=False):
        with self.lock:
            cached = self.stats_cache.get(sid)
            if cached and not refresh and time.monotonic() - cached[0] < 30:
                meta, episodes = cached[1:]
            else:
                data = self.request("/novel/player/multi_video_detail/v1/", self.provider._episodes_body(sid))
                video = (data.get(sid) or {}).get("video_data")
                if not video:
                    raise HTTPException(502, "当前剧集统计暂不可用")
                meta, episodes = self.provider._parse_episode_detail(sid, video)
                # This small TTL is separate from the six-hour episode metadata cache.
                if len(self.stats_cache) >= 64:
                    self.stats_cache.pop(next(iter(self.stats_cache)))
                self.stats_cache[sid] = (time.monotonic(), meta, episodes)
        episode = next((row for row in episodes if row.get("index") == ep), None)
        if not episode:
            raise HTTPException(404, "未找到当前集")
        return {"series_id": sid, "episode": ep, "vid": str(episode["vid"]),
                "likes": _number(episode.get("digged_count")),
                "comments": _number(episode.get("comment_count")),
                "favorites": _number(meta.get("followed_cnt")), "updated_at": int(time.time())}


def make_router(provider, *, authorize, emoji_catalog=lambda: {}):
    service = SocialService(provider)
    router = APIRouter(prefix="/desktop/social", dependencies=[Depends(authorize)])
    sid_arg = Query(..., pattern=r"^\d{8,24}$")
    ep_arg = Query(..., ge=1, le=100000)
    cursor_arg = Query("", max_length=8192)

    def guarded(fn, *args):
        try:
            return fn(*args)
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(502, "社交数据加载失败，请稍后重试") from None

    @router.get('/emojis')
    def emojis():
        return {'items':guarded(emoji_catalog)}

    @router.get("/metrics")
    def metrics(series_id: str = sid_arg, ep: int = ep_arg, refresh: bool = False):
        return guarded(service.metrics, series_id, ep, refresh)

    @router.get("/comments")
    def comments(series_id: str = sid_arg, ep: int = ep_arg,
                 kind: Literal["episode", "series"] = "episode", cursor: str = cursor_arg):
        return guarded(service.comments, series_id, ep, kind, cursor)

    @router.get("/danmaku")
    def danmaku(series_id: str = sid_arg, ep: int = ep_arg, cursor: str = cursor_arg,
                offset_ms: int = Query(0, ge=0, le=86400000)):
        return guarded(service.comments, series_id, ep, "danmaku", cursor, offset_ms)

    @router.get("/replies")
    def replies(series_id: str = sid_arg, ep: int = ep_arg,
                comment_id: str = Query(..., pattern=r"^\d{8,24}$"), cursor: str = cursor_arg):
        return guarded(service.replies, series_id, ep, comment_id, cursor)

    return router
