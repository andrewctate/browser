from typing import List
import tkinter
import tkinter.font

from request import request_url
from entities import chars_to_entity
from layout import VSTEP, DocumentLayout, DrawRect, DrawText
from css import DescendantSelector, TagSelector, CSSParser
from dom import Text, Element, HTMLParser, only_body


def escape_html(html: str):
    escaped = ''
    for char in html:
        escaped += chars_to_entity(char)

    return escaped


def build_view_source_html(source: str):
    return f"<html><head></head><body>{escape_html(source)}</body></html>"


def style(node: Text | Element, rules: List[tuple[TagSelector | DescendantSelector, dict]]):
    node.style = {}

    # apply global CSS rules
    for selector, body in rules:
        if not selector.matches(node):
            continue
        for property, value in body.items():
            node.style[property] = value

    # apply inline styles
    if isinstance(node, Element) and "style" in node.attributes:
        pairs = CSSParser(node.attributes["style"]).body()
        for property, value in pairs.items():
            node.style[property] = value

    for child in node.children:
        style(child, rules)


SCROLL_STEP = 100


class Browser:
    def __init__(self, initial_width: int, initial_height: int):
        self.width, self.height = initial_width, initial_height
        self.window = tkinter.Tk()
        self.canvas = tkinter.Canvas(
            self.window, width=self.width, height=self.height)
        self.canvas.pack()
        self.scroll = 0

        with open("browser.css") as f:
            self.default_style_sheet = CSSParser(f.read()).parse()

        self.window.bind("<Down>", self.scrolldown)
        self.window.bind("<Up>", self.scrollup)
        self.window.bind("<MouseWheel>", self.mousewheel)
        self.window.bind("<Configure>", self.resize)

    def resize(self, e):
        self.canvas.pack(fill='both', expand=1)
        self.width, self.height = e.width, e.height

        self.build_and_draw_document()

    def mousewheel(self, e):
        scroll_delta = SCROLL_STEP * -e.delta
        if scroll_delta > 0:
            self.scrolldown(e)
        elif scroll_delta < 0:
            self.scrollup(e)

    def scrolldown(self, e):
        max_y = self.document.height - self.height
        self.scroll = min(self.scroll + SCROLL_STEP, max_y)
        self.draw()

    def scrollup(self, e):
        self.scroll = max(self.scroll - SCROLL_STEP, 0)
        self.draw()

    def draw(self):
        self.canvas.delete("all")
        for command in self.display_list:
            if command.top > self.scroll + self.height:
                # falls below the viewport
                continue
            if command.bottom + VSTEP < self.scroll:
                # falls above the viewport
                continue

            command.execute(self.scroll, self.canvas)

    def load(self, url: str):
        view_source = url.startswith("view-source:")
        if view_source:
            _, url = url.split(':', 1)

        headers, body = request_url(url)

        if view_source:
            body = build_view_source_html(body)

        self.nodes = HTMLParser(body).parse()
        rules = self.default_style_sheet.copy()
        style(self.nodes, rules)
        self.build_and_draw_document()

    def build_and_draw_document(self):
        self.document = DocumentLayout(only_body(self.nodes))
        self.document.layout(self.width)
        self.display_list: List[DrawRect | DrawText] = []
        self.document.paint(self.display_list)
        self.draw()


if __name__ == '__main__':
    import sys
    Browser(800, 600).load(sys.argv[1])
    tkinter.mainloop()
