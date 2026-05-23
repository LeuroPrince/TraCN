from html.parser import HTMLParser

import httpx


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self._in_title = False
        self._skip = False
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip = True
        if tag == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip = False
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if not text or self._skip:
            return
        if self._in_title:
            self.title = f"{self.title} {text}".strip()
        elif len(text) > 1:
            self.parts.append(text)


async def fetch_page_preview(url: str) -> dict[str, str]:
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        response = await client.get(url, headers={"User-Agent": "TraCN local research tracker/0.1"})
        response.raise_for_status()
    parser = TextExtractor()
    parser.feed(response.text)
    body = " ".join(parser.parts)
    return {
        "url": str(response.url),
        "title": parser.title,
        "text_preview": body[:4000],
    }
