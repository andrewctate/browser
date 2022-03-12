from dom import Text, Element
import tkinter

HSTEP, VSTEP = 13, 18
PSTEP = VSTEP * .5

FONTS = {}


def get_font(size, weight, slant):
    key = (size, weight, slant)
    if key not in FONTS:
        font = tkinter.font.Font(size=size, weight=weight, slant=slant)
        FONTS[key] = font
    return FONTS[key]


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


class DrawText:
    def __init__(self, x1: int, y1: int, text: str, font: tkinter.font.Font):
        self.top = y1
        self.left = x1
        self.bottom = y1 + font.metrics("linespace")
        self.text = text
        self.font = font

    def execute(self, scroll: int, canvas: tkinter.Canvas):
        canvas.create_text(self.left, self.top - scroll,
                           text=self.text, font=self.font, anchor="nw")


class DrawRect:
    def __init__(self, x1, y1, x2, y2, color):
        self.top = y1
        self.left = x1
        self.bottom = y2
        self.right = x2
        self.color = color

    def execute(self, scroll: int, canvas: tkinter.Canvas):
        canvas.create_rectangle(
            self.left, self.top - scroll,
            self.right, self.bottom - scroll,
            width=0,
            fill=self.color,
        )


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
        bgcolor = self.node.style.get("background-color",
                                      "transparent")
        if bgcolor != "transparent":
            x2, y2 = self.x + self.width, self.y + self.height
            rect = DrawRect(self.x, self.y, x2, y2, bgcolor)
            display_list.append(rect)

        for x, y, word, font in self.display_list:
            display_list.append(DrawText(x, y, word, font))

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