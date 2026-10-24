"""Plain text from the HTML that sources put in job descriptions: paragraphs and line breaks become
lines, list items become dashes, and scripts and styles are dropped."""

import html
import re
from html.parser import HTMLParser

BLOCKS = frozenset({"p", "div", "section", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "tr"})
SKIPPED = frozenset({"script", "style"})
SPACES = re.compile(r"[ \t\r\f\v]+")
SPACE_AROUND_LINE_BREAKS = re.compile(r" *\n *")
EMPTY_LINES = re.compile(r"\n{3,}")


class TextCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skipping = 0

    def handle_starttag(self, tag: str, _attrs: list[tuple[str, str | None]]) -> None:
        if tag in SKIPPED:
            self.skipping += 1
        elif tag == "br":
            self.parts.append("\n")
        elif tag == "li":
            self.parts.append("\n- ")
        elif tag in BLOCKS:
            self.parts.append("\n\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in SKIPPED:
            self.skipping -= 1
        elif tag in BLOCKS:
            self.parts.append("\n\n")

    def handle_data(self, data: str) -> None:
        if not self.skipping:
            self.parts.append(data)


def plain_text(markup: str | None) -> str:
    if not markup:
        return ""
    collector = TextCollector()
    collector.feed(html.unescape(markup))  # descriptions often arrive escaped once more
    collector.close()
    text = SPACES.sub(" ", "".join(collector.parts))
    text = SPACE_AROUND_LINE_BREAKS.sub("\n", text)
    return EMPTY_LINES.sub("\n\n", text).strip()
