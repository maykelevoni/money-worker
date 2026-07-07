"""Google Trends enrichment via pytrends (unofficial, free, no API key).

Fetched on-demand on the topic detail page for a SINGLE term — never for a whole
list — so we don't hammer Google Trends and trip its rate limit. Every call is
best-effort: any failure (network, 429, library missing) returns None and the UI
falls back to the AI-estimated data.
"""

_BLOCKS = "▁▂▃▄▅▆▇█"


def _sparkline(values: list[float]) -> str:
    """Render a numeric series as unicode block sparkline."""
    nums = [v for v in values if v is not None]
    if not nums:
        return ""
    lo, hi = min(nums), max(nums)
    span = (hi - lo) or 1
    return "".join(_BLOCKS[min(len(_BLOCKS) - 1, int((v - lo) / span * (len(_BLOCKS) - 1)))]
                    for v in nums)


def _change_pct(values: list[float]) -> int | None:
    """Percent change from the first quarter's average to the last quarter's."""
    nums = [v for v in values if v is not None]
    if len(nums) < 4:
        return None
    q = max(1, len(nums) // 4)
    start = sum(nums[:q]) / q
    end = sum(nums[-q:]) / q
    if start == 0:
        return None
    return int(round((end - start) / start * 100))


def interest(term: str, timeframe: str = "today 12-m") -> dict | None:
    """Real Google Trends read for one term.

    Returns {sparkline, change_pct, rising:[{query, note}], related:[...]} or None
    if Trends is unavailable for any reason.
    """
    term = (term or "").strip()
    if not term:
        return None
    try:
        from pytrends.request import TrendReq

        pytrends = TrendReq(hl="en-US", tz=0)
        pytrends.build_payload([term], timeframe=timeframe)

        iot = pytrends.interest_over_time()
        series = []
        if iot is not None and not iot.empty and term in iot:
            series = [float(x) for x in iot[term].tolist()]

        rising = []
        try:
            rq = pytrends.related_queries().get(term) or {}
            rdf = rq.get("rising")
            if rdf is not None and not rdf.empty:
                for _, row in rdf.head(5).iterrows():
                    val = int(row["value"])
                    note = "Breakout" if val >= 5000 else f"+{val}%"
                    rising.append({"query": str(row["query"]), "note": note})
        except Exception:
            pass

        if not series and not rising:
            return None
        return {
            "sparkline": _sparkline(series),
            "change_pct": _change_pct(series),
            "rising": rising,
        }
    except Exception:
        return None
