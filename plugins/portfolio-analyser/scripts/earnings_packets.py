"""Read only explicitly permitted evidence for the particular phase being researched."""

from html.parser import HTMLParser
import re
from urllib.parse import urlsplit, urljoin
from . import earnings_sources as sources


class Extract(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.links = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("style", "script"):
            self.hidden += 1
        if tag == "a":
            self.links.append(dict(attrs).get("href", ""))

    def handle_endtag(self, tag):
        if tag in ("style", "script") and self.hidden:
            self.hidden -= 1

    def handle_data(self, data):
        if not self.hidden and data.strip():
            self.parts.append(data.strip())


def packet(identity, phase, candidates):
    """Caller supplied URLs never grant network access. Return bounded text, not instructions."""
    import os

    feed = identity.get("feed") or ""
    registry = sources.load_registry().get(feed, {})
    urls = []
    allowed = set()
    agent = None
    if registry.get("rights"):
        urls = registry.get(
            {
                "calendar": "calendar_urls",
                "preview": "expectation_urls",
                "actual": "unused",
            }[phase],
            [],
        )[:4]
        allowed = {urlsplit(url).hostname for url in [registry["url"], *urls]}
        agent = registry["user_agent"]
    if feed.startswith("sec:"):
        agent = os.getenv("SEC_USER_AGENT")
        allowed.add("www.sec.gov")
        if not urls and phase in ("preview", "calendar"):
            return {
                "documents": [],
                "gaps": [
                    "No licensed " + phase + " source supplied for this SEC issuer"
                ],
            }
    if phase == "actual":
        urls = [c["url"] for c in candidates][:4]
    gaps = []
    result = []
    visited = set()
    for url in urls:
        if url in visited or len(visited) >= 6:
            continue
        visited.add(url)
        parsed = urlsplit(url)
        if not agent or not sources.safe_url(url) or parsed.hostname not in allowed:
            gaps.append("No permitted source for " + url)
            continue
        if parsed.hostname == "www.sec.gov" and (
            not feed.startswith("sec:")
            or not parsed.path.startswith(
                "/Archives/edgar/data/" + str(int(feed[4:])) + "/"
            )
        ):
            gaps.append("Outside this issuer's filing archive")
            continue
        try:
            raw = sources.fetch(url, agent)
            if raw.startswith(b"%PDF"):
                gaps.append("PDF extraction unavailable for " + url)
                continue
            if raw.startswith(b"BEGIN:VCALENDAR"):
                unfolded = re.sub(r"\r?\n[ \t]", "", raw.decode("utf-8"))
                entries = [
                    match
                    for match in re.findall(
                        r"BEGIN:VEVENT.*?END:VEVENT", unfolded, re.S
                    )
                    if re.search(registry["earnings_title_pattern"], match, re.I)
                ]
                result.append(
                    {
                        "url": url,
                        "text": "\n".join(entries)[:42000],
                        "attribution": registry["rights"],
                    }
                )
                continue
            html = Extract()
            html.feed(raw.decode("utf-8", errors="replace"))
            if (
                phase == "calendar"
                and registry.get("discover_ical")
                and not url.endswith(".ics")
            ):
                urls.extend(
                    dict.fromkeys(
                        urljoin(url, href)
                        for href in html.links
                        if href.endswith(".ics")
                    )
                )
                continue
            result.append(
                {
                    "url": url,
                    "text": " ".join(html.parts)[:42000],
                    "attribution": registry.get("rights", "SEC EDGAR"),
                }
            )
            if phase == "actual" and parsed.hostname == "www.sec.gov":
                for link in html.links:
                    if re.search(r"(ex.?99|exhibit.?99|earnings|release)", link, re.I):
                        target = urljoin(url, link)
                        if target not in urls:
                            urls.append(target)
        except (ValueError, OSError, UnicodeError) as exc:
            gaps.append(type(exc).__name__ + " at " + url)
        except Exception as exc:
            gaps.append("Source unavailable (" + type(exc).__name__ + ") at " + url)
    return {
        "documents": result,
        "gaps": gaps
        or ([] if result else ["No permitted " + phase + " source configured"]),
    }


def evidence_packet(task):
    # A completed daily dossier may already prove the exact release, its outcome, actuals
    # and guidance. Keep its original sources. Incomplete matches still require the document.
    import json

    if task["phase"] == "actual":
        for candidate in task.get("candidate", []):
            for dossier in task.get("prior_dossier", []):
                source_ids = {
                    s["source_id"]
                    for s in dossier["sources"]
                    if s["url"] == candidate["url"]
                }
                observed = any(
                    event.get("outcome")
                    and source_ids.intersection(event["source_ids"])
                    for event in dossier["events"]
                )
                facts = [
                    f
                    for f in dossier["facts"]
                    if f["period"] == task["schedule"]["period"]
                    and f["value"] is not None
                    and source_ids.intersection(f["source_ids"])
                ]
                if observed and {f["value_kind"] for f in facts} >= {
                    "actual",
                    "guidance",
                }:
                    return {
                        "documents": [
                            {
                                "url": candidate["url"],
                                "text": json.dumps(dossier, ensure_ascii=False),
                                "prior_report_id": dossier["report_id"],
                            }
                        ],
                        "gaps": [],
                    }
    return packet(task["identity"], task["phase"], task.get("candidate") or [])
