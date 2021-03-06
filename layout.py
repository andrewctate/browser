from dom import Text, Element
import tkinter

HSTEP, VSTEP = 13, 18
PSTEP = VSTEP * .5

# Draws borders around indicated layout types.
# Use this to visually understand how things are being positioned and composed.
SHOW_LAYOUTS = {
    'text': False,
    'line': False,
    'inline': False,
    'block': False,
    'document': False
}

FONTS = {}


def draw_bounding_rect(layout, fill=None, border_color=None):
    return DrawRect(layout.x, layout.y, layout.x + layout.width, layout.y + layout.height, fill=fill, border_color=border_color)


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
    def __init__(self, x1: int, y1: int, text: str, font: tkinter.font.Font, color: str):
        self.top = y1
        self.left = x1
        self.bottom = y1 + font.metrics("linespace")
        self.text = text
        self.font = font
        self.color = color

    def execute(self, scroll: int, canvas: tkinter.Canvas):
        canvas.create_text(self.left, self.top - scroll,
                           text=self.text, font=self.font, fill=self.color, anchor="nw")


class DrawRect:
    def __init__(self, x1, y1, x2, y2, fill=None, border_color=None):
        self.top = y1
        self.left = x1
        self.bottom = y2
        self.right = x2
        self.fill = fill
        self.border_color = border_color

    def execute(self, scroll: int, canvas: tkinter.Canvas):
        border_width = 2 if self.border_color else 0

        canvas.create_rectangle(
            self.left, self.top - scroll,
            self.right, self.bottom - scroll,
            width=border_width,
            outline=self.border_color,
            fill=self.fill
        )


class TextLayout:
    def __init__(self, node, word, parent, previous):
        self.node = node
        self.word = word
        self.children = []
        self.parent = parent
        self.previous = previous

    def __repr__(self):
        return f'TextLayout({self.word})'

    def layout(self):
        weight = self.node.style["font-weight"]
        style = self.node.style["font-style"]
        if style == "normal":
            style = "roman"
        size = int(float(self.node.style["font-size"][:-2]) * .75)
        self.font = get_font(size, weight, style)

        self.width = self.font.measure(self.word)

        if self.previous:
            space = self.previous.font.measure(" ")
            self.x = self.previous.x + space + self.previous.width
        else:
            self.x = self.parent.x

        self.height = self.font.metrics("linespace")

    def paint(self, display_list):
        color = self.node.style["color"]
        display_list.append(
            DrawText(self.x, self.y, self.word, self.font, color))

        if SHOW_LAYOUTS['text']:
            display_list.append(draw_bounding_rect(self, border_color='red'))


class LineLayout:
    def __init__(self, node, parent, previous):
        self.node = node
        self.parent = parent
        self.previous = previous
        self.children = []

    def __repr__(self):
        repr = ''
        for word in self.children:
            repr += str(word) + ' '
        return f'LineLayout({repr})'

    def layout(self):
        self.width = self.parent.width
        self.x = self.parent.x

        if self.previous:
            self.y = self.previous.y + self.previous.height
        else:
            self.y = self.parent.y

        if len(self.children) == 0:
            self.height = 0
            return

        for word in self.children:
            word.layout()

        max_ascent = max([word.font.metrics("ascent")
                          for word in self.children])
        baseline = self.y + 1.25 * max_ascent
        for word in self.children:
            word.y = baseline - word.font.metrics("ascent")

        max_descent = max([word.font.metrics("descent")
                           for word in self.children])

        self.height = 1.25 * (max_ascent + max_descent)

    def paint(self, display_list):
        for child in self.children:
            child.paint(display_list)

        if SHOW_LAYOUTS['line']:
            display_list.append(draw_bounding_rect(self, border_color='green'))


class InlineLayout:
    def __init__(self, node, parent, previous) -> None:
        self.node = node
        self.parent = parent
        self.previous = previous
        self.children = []

    def layout(self) -> None:
        # setup defaults
        self.weight = "normal"
        self.style = "roman"
        self.size = 16

        # position according to family
        self.width = self.parent.width
        self.x = self.parent.x
        if self.previous:
            self.y = self.previous.y + self.previous.height
        else:
            self.y = self.parent.y
        self.cursor_x = self.x

        self.new_line()
        self.recurse(self.node)

        for line in self.children:
            line.layout()

        self.height = sum([line.height for line in self.children])

    def paint(self, display_list):
        bgcolor = self.node.style.get("background-color",
                                      "transparent")
        if bgcolor != "transparent":
            display_list.append(draw_bounding_rect(self, fill=bgcolor))

        for child in self.children:
            child.paint(display_list)

        if SHOW_LAYOUTS['inline']:
            display_list.append(draw_bounding_rect(self, border_color='blue'))

    def recurse(self, tree: Text | Element):
        if isinstance(tree, Text):
            self.text(tree)
        else:
            if tree.tag == "br":
                self.new_line()

            for child in tree.children:
                self.recurse(child)

            # if tree.tag == 'p':
            #     self.new_line()

    def text(self, node):
        weight = node.style["font-weight"]
        style = node.style["font-style"]

        # translate CSS "normal" to TK "roman"
        if style == "normal":
            style = "roman"

        # convert CSS pixels to TK points
        size = int(float(node.style["font-size"][:-2]) * .75)
        font = get_font(size, weight, style)

        # TODO - figure out why this is funky
        right_margin = self.width

        for word in node.text.split():
            word_width = font.measure(word)
            if self.cursor_x + word_width > right_margin:
                before_hyphen, after_hyphen = maybe_hyphenate(
                    word, lambda text: self.cursor_x + font.measure(text) > right_margin)

                if before_hyphen != '':
                    # we had room to put some of the word on this line
                    self.add_text_to_current_line(before_hyphen + '-', node)
                    word = after_hyphen

                self.new_line()

            self.add_text_to_current_line(word, node)
            self.cursor_x += word_width + font.measure(" ")

    def add_text_to_current_line(self, text, node):
        line = self.children[-1]
        text = TextLayout(node, text, line, self.previous_word)
        line.children.append(text)
        self.previous_word = text

    def new_line(self):
        self.previous_word = None
        self.cursor_x = self.x
        last_line = self.children[-1] if self.children else None
        new_line = LineLayout(self.node, self, last_line)
        self.children.append(new_line)


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

        if SHOW_LAYOUTS['block']:
            display_list.append(draw_bounding_rect(
                self, border_color='orange'))


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

        if SHOW_LAYOUTS['document']:
            display_list.append(draw_bounding_rect(
                self, border_color='purple'))
