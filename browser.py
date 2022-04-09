from typing import List
import tkinter
import tkinter.font

from request import request_url, resolve_url
from entities import chars_to_entity
from layout import VSTEP, DocumentLayout, DrawRect, DrawText, get_font
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
CHROME_HEIGHT = 100


class Tab:
    def __init__(self, width: int, height: int):
        self.set_dimensions(width, height)

        self.history = []

        with open("browser.css") as f:
            self.default_style_sheet = CSSParser(f.read()).parse()

    def mousewheel(self, delta: int):
        scroll_delta = SCROLL_STEP * -delta
        if scroll_delta > 0:
            self.scrolldown()
        elif scroll_delta < 0:
            self.scrollup()

    def scrolldown(self):
        max_y = self.document.height - self.height
        self.scroll = min(self.scroll + SCROLL_STEP, max_y)

    def scrollup(self):
        self.scroll = max(self.scroll - SCROLL_STEP, 0)

    def set_dimensions(self, width: int, height: int):
        self.width, self.height = width, height

    def click(self, x: int, y: int):
        y += self.scroll

        layouts_under_click = [layout for layout in tree_to_list(self.document, [])
                               if layout.x <= x < layout.x + layout.width
                               and layout.y <= y < layout.y + layout.height]

        element = layouts_under_click[-1].node

        if not element:
            return

        while element:
            if isinstance(element, Text):
                pass
            elif element.tag == 'a':
                href_url = resolve_url(element.attributes['href'], self.url)
                self.load(href_url)

            element = element.parent

    def go_back(self):
        if len(self.history) > 1:
            self.history.pop()
            back = self.history.pop()
            self.load(back)

    def draw(self, canvas: tkinter.Canvas):
        for command in self.display_list:
            if command.top > self.scroll + self.height - CHROME_HEIGHT:
                # falls below the viewport
                continue
            if command.bottom + VSTEP < self.scroll:
                # falls above the viewport
                continue

            command.execute(self.scroll - CHROME_HEIGHT, canvas)

    def load(self, url: str):
        self.history.append(url)
        view_source = url.startswith("view-source:")
        if view_source:
            _, url = url.split(':', 1)

        self.url = url

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

        self.scroll = 0

        self.build_and_paint_document()

    def build_and_paint_document(self):
        self.document = DocumentLayout(only_body(self.nodes))
        self.document.layout(self.width)
        self.display_list: List[DrawRect | DrawText] = []
        self.document.paint(self.display_list)


HOME_PAGE = "https://browser.engineering/"


class Browser:
    def __init__(self, initial_width: int, initial_height: int):
        self.width, self.height = initial_width, initial_height
        self.window = tkinter.Tk()
        self.canvas = tkinter.Canvas(
            self.window, width=self.width, height=self.height, bg="white")
        self.canvas.pack()
        self.scroll = 0

        self.tabs = []
        self.active_tab = None

        self.focus = None
        self.address_bar = ""

        # wait for TK paint, then bind the event listeners
        self.window.wait_visibility(self.canvas)
        self.window.bind("<Down>", self.handle_down)
        self.window.bind("<Up>", self.handle_up)
        self.window.bind("<MouseWheel>", self.handle_mousewheel)
        self.window.bind("<Configure>", self.resize)

        self.window.bind("<Button-1>", self.handle_click)
        self.window.bind("<Key>", self.handle_key)
        self.window.bind("<Return>", self.handle_enter)

    def handle_down(self, e):
        self.tabs[self.active_tab].scrolldown()
        self.draw()

    def handle_up(self, e):
        self.tabs[self.active_tab].scrollup()
        self.draw()

    def handle_mousewheel(self, e):
        self.tabs[self.active_tab].mousewheel(e.delta)
        self.draw()

    def handle_click(self, e):
        self.focus = None

        if e.y < CHROME_HEIGHT:
            if 40 <= e.x < 40 + 80 * len(self.tabs) and 0 <= e.y < 40:
                self.active_tab = int((e.x - 40) / 80)
            elif 10 <= e.x < 30 and 10 <= e.y < 30:
                self.load(HOME_PAGE)
            elif 10 <= e.x < 35 and 40 <= e.y < 90:
                self.tabs[self.active_tab].go_back()
            elif 50 <= e.x < self.width - 10 and 40 <= e.y < 90:
                self.focus = "address bar"
                self.address_bar = ""
        else:
            self.tabs[self.active_tab].click(e.x, e.y - CHROME_HEIGHT)

        self.draw()

    def handle_key(self, e):
        is_backspace = e.keysym == 'BackSpace'

        if not is_backspace:
            if len(e.char) == 0:
                return

            if not (0x20 <= ord(e.char) < 0x7f):
                # outside ascii character range and not backspace
                return

        if self.focus == "address bar":
            if is_backspace:
                self.address_bar = self.address_bar[0:-1]
            else:
                self.address_bar += e.char
            self.draw()

    def handle_enter(self, e):
        if self.focus == "address bar":
            self.tabs[self.active_tab].load(self.address_bar)
            self.focus = None
            self.draw()

    def resize(self, e):
        self.canvas.pack(fill='both', expand=1)
        self.width, self.height = e.width, e.height
        self.tabs[self.active_tab].set_dimensions(self.width, self.height)
        self.tabs[self.active_tab].build_and_paint_document()
        self.draw()

    def draw(self):
        self.canvas.delete('all')
        self.tabs[self.active_tab].draw(self.canvas)

        # fill in browser chrome
        tab_width, tab_height = 80, 40
        tabfont = get_font(20, "normal", "roman")
        for i, tab in enumerate(self.tabs):
            name = "Tab {}".format(i)
            x1, x2 = tab_height + tab_width * i, 120 + tab_width * i
            self.canvas.create_line(x1, 0, x1, 40, fill="black")
            self.canvas.create_line(x2, 0, x2, 40, fill="black")
            self.canvas.create_text(x1 + 10, 10, anchor="nw", text=name,
                                    font=tabfont, fill="black")
            if i == self.active_tab:
                self.canvas.create_line(0, 40, x1, 40, fill="black")
                self.canvas.create_line(x2, 40, self.width, 40, fill="black")

        # draw the new-tab button
        buttonfont = get_font(30, "normal", "roman")
        self.canvas.create_rectangle(10, 10, 30, 30,
                                     outline="black", width=1)
        self.canvas.create_text(11, 0, anchor="nw", text="+",
                                font=buttonfont, fill="black")

        # draw the address bar
        self.canvas.create_rectangle(40, 50, self.width - 10, 90,
                                     outline="black", width=1)

        if self.focus == "address bar":
            self.canvas.create_text(
                55, 55, anchor='nw', text=self.address_bar,
                font=buttonfont, fill="black")
            w = buttonfont.measure(self.address_bar)
            self.canvas.create_line(55 + w, 55, 55 + w, 85, fill="black")
        else:
            url = self.tabs[self.active_tab].url
            self.canvas.create_text(55, 55, anchor='nw', text=url,
                                    font=buttonfont, fill="black")

        # draw back button
        self.canvas.create_rectangle(10, 50, 35, 90,
                                     outline="black", width=1)
        self.canvas.create_polygon(
            15, 70, 30, 55, 30, 85, fill='black')

        self.canvas.create_line(
            0, CHROME_HEIGHT, self.width, CHROME_HEIGHT, fill="black")

    def load(self, url):
        new_tab = Tab(self.width, self.height)
        new_tab.load(url)
        self.active_tab = len(self.tabs)
        self.tabs.append(new_tab)
        self.draw()


if __name__ == '__main__':
    import sys
    initial_url = sys.argv[1] if len(sys.argv) < 1 else HOME_PAGE
    Browser(800, 600).load(initial_url)
    tkinter.mainloop()
