from entities import chars_to_entity
import tkinter
import tkinter.font
from parser import Element, HTMLParser, Text, only_body
from request import request_url


FONTS = {}


def get_font(size, weight, slant):
    key = (size, weight, slant)
    if key not in FONTS:
        font = tkinter.font.Font(size=size, weight=weight, slant=slant)
        FONTS[key] = font
    return FONTS[key]


def escape_html(html: str):
    escaped = ''
    for char in html:
        escaped += chars_to_entity(char)

    return escaped


def build_view_source_html(source: str):
    return f"<html><head></head><body>{escape_html(source)}</body></html>"


HSTEP, VSTEP = 13, 18
PSTEP = VSTEP * .5


def maybe_hyphenate(word: str, too_long):
    before_hyphen = ''
    after_hyphen = ''
    if '\N{soft hyphen}' in word:
        past_hyphen = False
        for piece in word.split('\N{soft hyphen}'):
            if not past_hyphen and not too_long(before_hyphen + piece + '-'):
                before_hyphen += piece
            else:
                past_hyphen = True
                after_hyphen += piece

    return before_hyphen, after_hyphen


# source: https://html.spec.whatwg.org/multipage/#toc-semantics
BLOCK_ELEMENTS = [
    "html", "body", "article", "section", "nav", "aside",
    "h1", "h2", "h3", "h4", "h5", "h6", "hgroup", "header",
    "footer", "address", "p", "hr", "pre", "blockquote",
    "ol", "ul", "menu", "li", "dl", "dt", "dd", "figure",
    "figcaption", "main", "div", "table", "form", "fieldset",
    "legend", "details", "summary"
]


def get_layout_mode(node: Text | Element) -> str:
    if isinstance(node, Text):
        return "inline"
    elif node.children:
        for child in node.children:
            if isinstance(child, Text):
                continue
            if child.tag in BLOCK_ELEMENTS:
                return "block"
        return "inline"
    else:
        return "block"


class BlockLayout:
    def __init__(self, node, parent, previous) -> None:
        self.node = node
        self.parent = parent
        self.previous = previous
        self.children = []

    def layout(self):
        self.width = self.parent.width
        self.x = self.parent.x
        if self.previous:
            self.y = self.previous.y + self.previous.height
        else:
            self.y = self.parent.y

        previous = None
        for child in self.node.children:
            if get_layout_mode(child) == "inline":
                next = InlineLayout(child, self, previous)
            else:
                next = BlockLayout(child, self, previous)

            self.children.append(next)
            previous = next

        for child in self.children:
            child.layout()

        # height computation must happen after the children are laid out
        # since the parent should be tall enough to fit them all
        self.height = sum([child.height for child in self.children])

    def paint(self, display_list):
        for child in self.children:
            child.paint(display_list)


class InlineLayout:
    def __init__(self, node, parent, previous) -> None:
        self.node = node
        self.parent = parent
        self.previous = previous
        self.children = []

    def layout(self) -> None:
        # setup defaults
        self.line = []
        self.display_list = []
        self.weight = "normal"
        self.style = "roman"
        self.size = 16
        self.is_super = False

        # position according to family
        self.width = self.parent.width
        self.x = self.parent.x
        if self.previous:
            self.y = self.previous.y + self.previous.height
        else:
            self.y = self.parent.y
        self.cursor_x = self.x
        self.cursor_y = self.y

        self.recurse(self.node)
        self.flush()

        self.height = self.cursor_y - self.y

    def paint(self, display_list):
        display_list.extend(self.display_list)

    def recurse(self, tree: Text | Element):
        if isinstance(tree, Text):
            self.text(tree)
        else:
            self.open_tag(tree.tag)
            for child in tree.children:
                self.recurse(child)
            self.close_tag(tree.tag)

    def open_tag(self, tag):
        if tag == "i":
            self.style = "italic"
        elif tag == "b":
            self.weight = "bold"
        elif tag == "small":
            self.size -= 2
        elif tag == "big":
            self.size += 4
        elif tag == "sup":
            self.is_super = True
            self.size //= 2
        elif tag == "br":
            self.flush()

    def close_tag(self, tag):
        if tag == "i":
            self.style = "roman"
        elif tag == "b":
            self.weight = "normal"
        elif tag == "small":
            self.size += 2
        elif tag == "big":
            self.size -= 4
        elif tag == "sup":
            self.is_super = False
            self.size *= 2
        elif tag == "p":
            self.flush()
            self.cursor_y += PSTEP

    def text(self, tok):
        font = get_font(
            self.size,
            self.weight,
            self.style,
        )

        right_margin = self.width - HSTEP

        for word in tok.text.split():
            w = font.measure(word)
            if self.cursor_x + w > right_margin:
                before_hyphen, after_hyphen = maybe_hyphenate(
                    word, lambda text: self.cursor_x + font.measure(text) > right_margin)

                if before_hyphen != '':
                    # we had room to put some of the word on this line
                    self.line.append(
                        (self.cursor_x, before_hyphen + '-', font, self.is_super))
                    word = after_hyphen

                self.flush()

            self.line.append(
                (self.cursor_x, word, font, self.is_super))
            self.cursor_x += w + font.measure(" ")

    def flush(self):
        if not self.line:
            return
        metrics = [font.metrics() for x, word, font, is_super in self.line]
        max_ascent = max([metric["ascent"] for metric in metrics])
        baseline = self.cursor_y + 1.25 * max_ascent
        super_ascent_adjustment = None

        for i, (x, word, font, is_super) in enumerate(self.line):
            ascent_adjustment = font.metrics("ascent")
            if is_super and i > 0:
                if not self.line[i-1][3]:
                    # record for following super words
                    super_ascent_adjustment = self.line[i -
                                                        1][2].metrics("ascent")
                ascent_adjustment = super_ascent_adjustment

            y = baseline - ascent_adjustment
            self.display_list.append((x, y, word, font))

        self.cursor_x = self.x
        self.line = []
        max_descent = max([metric["descent"] for metric in metrics])
        self.cursor_y = baseline + 1.25 * max_descent


class DocumentLayout:
    def __init__(self, node) -> None:
        self.node = node
        self.parent = None
        self.children = []

    def layout(self, width):
        child = BlockLayout(self.node, self, None)
        self.children.append(child)

        self.width = width - 2 * HSTEP
        self.x = HSTEP
        self.y = VSTEP
        child.layout()
        self.height = child.height + 2 * VSTEP

    def paint(self, display_list):
        self.children[0].paint(display_list)


SCROLL_STEP = 100


class Browser:
    def __init__(self, initial_width: int, initial_height: int):
        self.width, self.height = initial_width, initial_height
        self.window = tkinter.Tk()
        self.canvas = tkinter.Canvas(
            self.window, width=self.width, height=self.height)
        self.canvas.pack()
        self.scroll = 0

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

        # don't let the user scroll beyond the top
        if self.scroll + scroll_delta < 0:
            scroll_delta = 0

        self.scroll += scroll_delta
        self.draw()

    def scrolldown(self, e):
        self.scroll += SCROLL_STEP
        self.draw()

    def scrollup(self, e):
        if self.scroll > 0:
            self.scroll -= SCROLL_STEP
            self.draw()

    def draw(self):
        self.canvas.delete("all")
        for x, y, c, font in self.display_list:
            if y > self.scroll + self.height:
                continue
            if y + VSTEP < self.scroll:
                continue
            self.canvas.create_text(
                x, y - self.scroll, text=c, font=font, anchor="nw")

    def load(self, url: str):
        view_source = url.startswith("view-source:")
        if view_source:
            _, url = url.split(':', 1)

        headers, body = request_url(url)

        if view_source:
            body = build_view_source_html(body)

        self.nodes = HTMLParser(body).parse()
        self.build_and_draw_document()

    def build_and_draw_document(self):
        self.document = DocumentLayout(only_body(self.nodes))
        self.document.layout(self.width)
        self.display_list = []
        self.document.paint(self.display_list)
        self.draw()


if __name__ == '__main__':
    import sys
    Browser(800, 600).load(sys.argv[1])
    tkinter.mainloop()
