from typing import List
import tkinter
import tkinter.font

from request import request_url, resolve_url
from entities import chars_to_entity
from layout import VSTEP, DocumentLayout, DrawRect, DrawText
from css import DescendantSelector, TagSelector, CSSParser, print_rules
from dom import Text, Element, HTMLParser, only_body


def escape_html(html: str):
    escaped = ''
    for char in html:
        escaped += chars_to_entity(char)

    return escaped


def build_view_source_html(source: str):
    return f"<html><head></head><body>{escape_html(source)}</body></html>"


INHERITED_PROPERTIES = {
    "font-size": "16px",
    "font-style": "normal",
    "font-weight": "normal",
    "color": "black",
}


def compute_style(node, property, value):
    if property == "font-size":
        if value.endswith("px"):
            return value
        elif value.endswith("%"):
            if node.parent:
                parent_font_size = node.parent.style["font-size"]
            else:
                parent_font_size = INHERITED_PROPERTIES["font-size"]

            # have to resolve percentage to a pixel value since font-size is a "computed style"
            # see https://www.w3.org/TR/CSS2/cascade.html#computed-value for more info
            node_pct = float(value[:-1]) / 100
            parent_px = float(parent_font_size[:-2])
            return str(node_pct * parent_px) + "px"
        else:
            return None
    else:
        return value


def apply_rule_body(rule_body, node):
    for property, value in rule_body.items():
        computed_value = compute_style(node, property, value)
        if not computed_value:
            continue
        node.style[property] = computed_value


def style(node: Text | Element, rules: List[tuple[TagSelector | DescendantSelector, dict]]):
    # TODO - should this function be invoked from the nodes themselves?
    node.style = {}

    # inherit properties
    for property, default_value in INHERITED_PROPERTIES.items():
        if node.parent:
            node.style[property] = node.parent.style[property]
        else:
            node.style[property] = default_value

    # apply global CSS rules
    for selector, body in rules:
        if selector.matches(node):
            apply_rule_body(body, node)

    # apply inline styles
    if isinstance(node, Element) and "style" in node.attributes:
        body = CSSParser(node.attributes["style"]).body()
        apply_rule_body(body, node)

    for child in node.children:
        style(child, rules)


def cascade_priority(rule):
    selector, body = rule
    return selector.priority


def tree_to_list(tree, list):
    list.append(tree)
    for child in tree.children:
        tree_to_list(child, list)
    return list


SCROLL_STEP = 100


class Browser:
    def __init__(self, initial_width: int, initial_height: int):
        self.width, self.height = initial_width, initial_height
        self.window = tkinter.Tk()
        self.canvas = tkinter.Canvas(
            self.window, width=self.width, height=self.height, bg="white")
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

        stylesheet_links = [node.attributes['href']
                            for node in tree_to_list(self.nodes, [])
                            if isinstance(node, Element)
                            and node.tag == 'link'
                            and 'href' in node.attributes
                            and node.attributes.get("rel") == "stylesheet"]

        rules = self.default_style_sheet.copy()

        for link in stylesheet_links:
            try:
                header, body = request_url(resolve_url(link, url))
            except:
                continue
            rules.extend(CSSParser(body).parse())

        # Note that before sorting rules, it is in file order. Since Python’s sorted function keeps the
        # relative order of things when possible, file order thus acts as a tie breaker, as it should.
        # See https://www.w3.org/TR/2011/REC-CSS2-20110607/cascade.html#cascading-order
        style(self.nodes, sorted(rules, key=cascade_priority))
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
