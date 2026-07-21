"""Real TikTok video search — the research brain, powered by davidteather/TikTok-Api.

Replaces the old AI keyword explorer: instead of *estimating* topics, we search
TikTok for videos that already went viral, read their real stats (views/likes/
comments/shares), and let the user either steal the idea or clone the movement onto
their avatar (Motion Clip — no face reused).

This drives a headless Chromium under the hood, so every call is slow (~10-30s) and
must run off the request thread. Keyword ("item") search is the flakiest TikTok
endpoint and really wants a valid `ms_token`; a blank query falls back to the
trending feed, which is far more reliable and needs no token.
"""
import asyncio

from django.conf import settings


class NotAvailable(Exception):
    """The TikTokApi package / browser isn't installed."""


class ScrapeError(Exception):
    """TikTok blocked us or returned nothing (often: missing/expired ms_token)."""


def is_available() -> bool:
    try:
        import TikTokApi  # noqa: F401
    except Exception:
        return False
    return True


def _ms_tokens() -> list:
    tok = (settings.TIKTOK_MS_TOKEN or "").strip()
    return [tok] if tok else [None]


def _to_int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _pluck(video_dict: dict) -> dict:
    """Pull the fields we care about out of a video's raw `as_dict`, defensively.

    TikTok changes this structure periodically, so every access is a soft .get().
    """
    stats = video_dict.get("stats") or video_dict.get("statsV2") or {}
    author = video_dict.get("author") or {}
    music = video_dict.get("music") or {}
    vid = video_dict.get("video") or {}

    tiktok_id = str(video_dict.get("id") or "")
    handle = str(author.get("uniqueId") or "")
    url = (
        f"https://www.tiktok.com/@{handle}/video/{tiktok_id}"
        if handle and tiktok_id
        else ""
    )
    return {
        "tiktok_id": tiktok_id,
        "url": url,
        "caption": str(video_dict.get("desc") or "").strip(),
        "author_name": str(author.get("nickname") or "").strip(),
        "author_handle": handle,
        "thumbnail_url": str(vid.get("cover") or vid.get("originCover") or ""),
        "duration": _to_int(vid.get("duration")),
        "music": str(music.get("title") or "").strip(),
        "views": _to_int(stats.get("playCount")),
        "likes": _to_int(stats.get("diggCount")),
        "comments": _to_int(stats.get("commentCount")),
        "shares": _to_int(stats.get("shareCount")),
        "saves": _to_int(stats.get("collectCount")),
    }


async def _search_async(query: str, count: int) -> list[dict]:
    from TikTokApi import TikTokApi

    out: list[dict] = []
    async with TikTokApi() as api:
        await api.create_sessions(
            ms_tokens=_ms_tokens(),
            num_sessions=1,
            sleep_after=3,
            browser=settings.TIKTOK_BROWSER,
            headless=True,
        )
        if query:
            source = api.search.search_type(query, "item", count=count)
        else:
            source = api.trending.videos(count=count)
        async for video in source:
            try:
                data = _pluck(video.as_dict)
            except Exception:
                continue
            if data["tiktok_id"]:
                out.append(data)
    return out


def search(query: str = "", count: int = 20) -> list[dict]:
    """Search TikTok for videos (blank query = trending). Blocking + slow.

    Returns a list of plucked dicts. Raises NotAvailable if the package is missing,
    ScrapeError if TikTok blocked us or handed back nothing.
    """
    if not is_available():
        raise NotAvailable(
            "TikTok search isn't installed on the server (TikTokApi + a browser)."
        )
    try:
        results = asyncio.run(_search_async(query.strip(), count))
    except Exception as e:  # browser crash, block, timeout, structure change…
        raise ScrapeError(str(e)) from e
    if not results:
        raise ScrapeError(
            "TikTok returned no results — it likely blocked the request. "
            "Add a fresh TIKTOK_MS_TOKEN and try again."
        )
    return results


def _run_search_job(search_id: int, query: str, count: int):
    """Background worker: scrape TikTok, save finds onto the search, flip its status.

    Mirrors shorts._run_pipeline — writes progress to the row the page polls.
    """
    from django.db import connections

    from ..models import VideoFind, VideoSearch

    try:
        workspace_id = VideoSearch.objects.values_list("workspace_id", flat=True).get(
            pk=search_id
        )
        results = search(query, count=count)
        VideoFind.objects.bulk_create(
            [
                VideoFind(workspace_id=workspace_id, search_id=search_id, **r)
                for r in results
            ]
        )
        VideoSearch.objects.filter(pk=search_id).update(status="done")
    except Exception as e:
        VideoSearch.objects.filter(pk=search_id).update(status="error", error=str(e)[:500])
    finally:
        connections.close_all()


def start_search(search, count: int = 20):
    """Kick a search off in a background thread; the page polls the row for status."""
    import threading

    threading.Thread(
        target=_run_search_job,
        args=(search.pk, search.query, count),
        daemon=True,
    ).start()


async def _download_async(url: str) -> bytes:
    from TikTokApi import TikTokApi

    async with TikTokApi() as api:
        await api.create_sessions(
            ms_tokens=_ms_tokens(),
            num_sessions=1,
            sleep_after=3,
            browser=settings.TIKTOK_BROWSER,
            headless=True,
        )
        video = api.video(url=url)
        await video.info()  # populate the video so bytes() has a session/context
        return await video.bytes()


def download(url: str) -> bytes:
    """Fetch a TikTok video's MP4 bytes (for seeding a Motion Clip). Blocking + slow."""
    if not is_available():
        raise NotAvailable("TikTok download isn't installed on the server.")
    try:
        data = asyncio.run(_download_async(url))
    except Exception as e:
        raise ScrapeError(str(e)) from e
    if not data:
        raise ScrapeError("Couldn't download that video (TikTok blocked the fetch).")
    return data
