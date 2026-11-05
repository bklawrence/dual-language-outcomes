"""Read published HTML fragments from JSON page payloads without running code.

Some district sites send programme text in a Nuxt hydration payload rather than
in the initial visible DOM. The returned text may also contain banners or
templates: researchers must still review the passage and its programme scope.
"""
from html.parser import HTMLParser
import json
import re


class _PayloadReader(HTMLParser):
    def __init__(self):
        super().__init__()
        self.inside = False
        self.parts = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == 'script':
            self.inside = values.get('type') == 'application/json'

    def handle_endtag(self, tag):
        if tag == 'script':
            self.inside = False

    def handle_data(self, data):
        if self.inside:
            self.parts.append(data)


class _TextReader(HTMLParser):
    def __init__(self):
        super().__init__()
        self.skip = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style', 'noscript'}:
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in {'script', 'style', 'noscript'}:
            self.skip = max(0, self.skip - 1)
        if tag in {'p', 'div', 'li', 'h1', 'h2', 'h3', 'tr', 'br'}:
            self.parts.append('\n')

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def embedded_page_text(raw):
    """Extract HTML-valued JSON strings, including nested serialized JSON."""
    reader = _PayloadReader()
    reader.feed(raw.decode('utf-8', errors='replace') if isinstance(raw, bytes) else raw)
    fragments = []
    seen = set()

    def visit(value, depth=0):
        if depth > 40:
            raise ValueError('Page payload exceeds extraction nesting limit')
        if isinstance(value, dict):
            for child in value.values():
                visit(child, depth + 1)
        elif isinstance(value, list):
            for child in value:
                visit(child, depth + 1)
        elif isinstance(value, str):
            text = value.strip()
            if text.startswith(('{', '[')):
                try:
                    nested = json.loads(text)
                except ValueError:
                    pass
                else:
                    visit(nested, depth + 1)
                    return
            if re.match(r'<(?:p|h[1-6]|table|ul|ol|div|img|a|span)\b', text, re.I) and text not in seen:
                fragments.append(text)
                seen.add(text)

    for part in reader.parts:
        try:
            payload = json.loads(part)
        except ValueError:
            continue
        visit(payload)
    text = _TextReader()
    text.feed('\n'.join(fragments))
    return ' '.join(''.join(text.parts).split())
