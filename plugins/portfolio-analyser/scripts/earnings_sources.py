"""Small, bounded probes. The operator owns the feed allowlist and its usage rights."""

import hashlib
import json
import os
import re
from datetime import datetime
from urllib.parse import urlsplit
from xml.etree import ElementTree

import httpx


def load_registry():
    registry = {}
    if os.getenv("EARNINGS_SNB_NONCOMMERCIAL") == "1":
        registry["snb:adhoc"] = {
            "url": "https://www.snb.ch/public/rss/en/adhoc",
            "calendar_urls": [
                "https://www.snb.ch/en/services-events/digital-services/rss-calendar-feeds"
            ],
            "discover_ical": True,
            "zone": "Europe/Zurich",
            "earnings_title_pattern": r"(interim results of the Swiss National Bank|annual result of the Swiss National Bank)",
            "rights": "SNB own content only, attributed, non-commercial. https://www.snb.ch/en/srv/disclaimer_copyright",
            "user_agent": "Thomas noncommercial earnings reader",
        }
    path = os.getenv("EARNINGS_FEEDS")
    if path:
        with open(path, encoding="utf-8") as source:
            registry.update(json.load(source))
    return registry


def safe_url(url):
    parsed = urlsplit(url)
    return (
        parsed.scheme == "https"
        and parsed.hostname
        and not parsed.username
        and not parsed.password
    )


def fetch(url, agent):
    with httpx.stream(
        "GET", url, headers={"User-Agent": agent}, timeout=25, follow_redirects=False
    ) as response:
        response.raise_for_status()
        data = bytearray()
        for block in response.iter_bytes(65536):
            data.extend(block)
            if len(data) > 5_000_000:
                raise ValueError("Source exceeds the document limit")
        return bytes(data)


def probe(feed, day, *, read=fetch):
    """Return document candidates only. Matching an item is not proof of publication."""
    if not feed:
        return [], "No permitted release feed configured"
    if re.fullmatch(r"sec:[0-9]{1,10}", feed):
        agent = os.getenv("SEC_USER_AGENT")
        if not agent:
            return [], "SEC_USER_AGENT with operator contact is required"
        cik = int(feed[4:])
        rows = json.loads(
            read(f"https://data.sec.gov/submissions/CIK{cik:010d}.json", agent)
        )["filings"]["recent"]
        candidates = []
        for form, items, filed, accession, doc in zip(
            rows["form"],
            rows["items"],
            rows["filingDate"],
            rows["accessionNumber"],
            rows["primaryDocument"],
            strict=True,
        ):
            if filed != day.isoformat() or not (
                form == "8-K" and "2.02" in items or form == "6-K"
            ):
                continue
            if not re.fullmatch(r"[\w.-]+", doc) or not re.fullmatch(
                r"[\d-]+", accession
            ):
                continue
            url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession.replace('-', '')}/{doc}"
            candidates.append(
                {"url": url, "title": form + " " + accession, "revision": accession}
            )
        return candidates, None
    entry = load_registry().get(feed)
    if not entry or not entry.get("rights") or not safe_url(entry.get("url", "")):
        return [], "Missing licensed source in operator registry"
    # A publisher-specific Atom feed; only the explicitly approved HTTPS URL is fetched.
    raw = read(entry["url"], entry["user_agent"])
    if b"<!DOCTYPE" in raw.upper():
        raise ValueError("Feed DTD is not supported")
    candidates = []
    root = ElementTree.fromstring(raw)
    ns = "{http://www.w3.org/2005/Atom}"
    from zoneinfo import ZoneInfo

    for item in [*root.findall(ns + "entry"), *root.findall("./channel/item")]:
        if item.tag == ns + "entry":
            link = item.find(ns + "link")
            url = link.get("href", "") if link is not None else ""
            title = item.findtext(ns + "title", "")
            published = item.findtext(ns + "updated")
        else:
            url = item.findtext("link", "")
            title = item.findtext("title", "")
            published = item.findtext(
                "{http://purl.org/dc/elements/1.1/}date"
            ) or item.findtext("pubDate")
        if (
            not published
            or not safe_url(url)
            or not re.search(entry["earnings_title_pattern"], title, re.I)
        ):
            continue
        try:
            moment = datetime.fromisoformat(published.replace("Z", "+00:00"))
        except ValueError:
            from email.utils import parsedate_to_datetime

            moment = parsedate_to_datetime(published)
        if (
            not moment.tzinfo
            or moment.astimezone(ZoneInfo(entry["zone"])).date() != day
        ):
            continue
        candidates.append(
            {
                "url": url,
                "title": title,
                "published_at": moment.isoformat(),
                "revision": hashlib.sha256(ElementTree.tostring(item)).hexdigest(),
            }
        )
    return candidates, None


def issuers():
    path = os.getenv("EARNINGS_ISSUERS")
    if path:
        with open(path, encoding="utf-8") as file:
            return json.load(file)
    return {
        "snb:issuer": {
            "name": "Swiss National Bank",
            "isin": "CH0001319265",
            "symbol": "SNBN",
            "feed": "snb:adhoc",
        },
        "cik:70858": {
            "name": "Bank of America Corporation",
            "isin": "US0605051046",
            "symbol": "BAC",
            "feed": "sec:70858",
        },
        "cik:320193": {
            "name": "Apple Inc.",
            "isin": "US0378331005",
            "symbol": "AAPL",
            "feed": "sec:320193",
        },
    }


def stock_from_isin(isin):
    """Resolve a single requested ISIN; holdings are never uploaded for lookup."""
    import re
    import httpx

    if not re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}[0-9]", isin):
        raise ValueError("Use an unambiguous stock ISIN")
    matches = [
        (k, v)
        for k, v in issuers().items()
        if isin in [v.get("isin"), *v.get("isin_aliases", [])]
    ]
    if len(matches) == 1:
        return matches[0]
    response = httpx.post(
        "https://api.openfigi.com/v3/mapping",
        json=[{"idType": "ID_ISIN", "idValue": isin, "securityType2": "Common Stock"}],
        timeout=8,
    )
    response.raise_for_status()
    rows = [
        row
        for row in response.json()[0].get("data", [])
        if row.get("marketSector") == "Equity"
        and row.get("securityType2") == "Common Stock"
        and row.get("shareClassFIGI")
    ]
    if not rows or len({r["shareClassFIGI"] for r in rows}) != 1:
        raise ValueError(
            "No unambiguous common-stock mapping; a verified issuer entry is required"
        )
    return "isin:" + isin.lower(), {
        "isin": isin,
        "name": isin,
        "share_class_figi": rows[0]["shareClassFIGI"],
    }
