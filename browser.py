from entities import entities
import tkinter
import tkinter.font
from request import request_url


FONTS = {}


def get_font(size, weight, slant):
    key = (size, weight, slant)
    if key not in FONTS:
        font = tkinter.font.Font(size=size, weight=weight, slant=slant)
        FONTS[key] = font
    return FONTS[key]


class Text:
    def __init__(self, text: str):
        for entity in entities:
            text = text.replace(entity, entities[entity])
        self.text = text


class Tag:
    def __init__(self, tag):
        self.tag = tag


def get_entity_chars(entity: str):
    if entity in entities:
        return entities[entity]
    return entity


def lex(html: str):
    out = []
    text = ""
    in_tag = False
    for c in html:
        if c == "<":
            in_tag = True
            if text:
                out.append(Text(text))
            text = ""
        elif c == ">":
            in_tag = False
            out.append(Tag(text))
            text = ""
        else:
            text += c
    if not in_tag and text:
        out.append(Text(text))
    return out


def only_body(tokens):
    out = []
    in_body = False
    for tok in tokens:
        if isinstance(tok, Tag):
            if tok.tag.startswith("body"):
                in_body = True
            elif tok.tag.startswith("/body"):
                in_body = False

        if in_body:
            out.append(tok)

    return out


def escape_html(html: str):
    char_to_entity = {}
    for key, val in entities.items():
        char_to_entity[val] = key

    escaped = ''
    for char in html:
        escaped += char_to_entity[char] if char in char_to_entity else char

    return escaped


def build_view_source_html(source: str):
    return f"<body>{escape_html(source)}</body>"


HSTEP, VSTEP = 13, 18
PSTEP = VSTEP * .5


class Layout:
    def __init__(self, tokens: list[Text | Tag], width: int) -> None:
        self.line = []
        self.display_list = []
        self.cursor_x = HSTEP
        self.cursor_y = VSTEP
        self.width = width
        self.weight = "normal"
        self.style = "roman"
        self.size = 16

        for tok in only_body(tokens):
            self.token(tok)

        self.flush()

    def token(self, tok):
        if isinstance(tok, Text):
            self.text(tok)
        elif tok.tag == "i":
            self.style = "italic"
        elif tok.tag == "/i":
            self.style = "roman"
        elif tok.tag == "b":
            self.weight = "bold"
        elif tok.tag == "/b":
            self.weight = "normal"
        elif tok.tag == "small":
            self.size -= 2
        elif tok.tag == "/small":
            self.size += 2
        elif tok.tag == "big":
            self.size += 4
        elif tok.tag == "/big":
            self.size -= 4
        elif tok.tag == "br" or tok.tag == "br /":
            self.flush()
        elif tok.tag == "/p":
            self.flush()
            self.cursor_y += PSTEP

    def text(self, tok):
        font = get_font(
            self.size,
            self.weight,
            self.style,
        )
        for word in tok.text.split():
            w = font.measure(word)
            if self.cursor_x + w > self.width - HSTEP:
                self.flush()
            self.line.append(
                (self.cursor_x, word, font))
            self.cursor_x += w + font.measure(" ")

    def flush(self):
        if not self.line:
            return
        metrics = [font.metrics() for x, word, font in self.line]
        max_ascent = max([metric["ascent"] for metric in metrics])
        baseline = self.cursor_y + 1.25 * max_ascent

        for x, word, font in self.line:
            y = baseline - font.metrics("ascent")
            self.display_list.append((x, y, word, font))

        self.cursor_x = HSTEP
        self.line = []
        max_descent = max([metric["descent"] for metric in metrics])
        self.cursor_y = baseline + 1.25 * max_descent


SCROLL_STEP = 100


class Browser:
    def __init__(self, initial_width: int, initial_height: int):
        self.width, self.height = initial_width, initial_height
        self.window = tkinter.Tk()
        self.canvas = tkinter.Canvas(
            self.window, width=self.width, height=self.height)
        self.canvas.pack()
        self.scroll = 0
        self.tokens = []

        self.window.bind("<Down>", self.scrolldown)
        self.window.bind("<Up>", self.scrollup)
        self.window.bind("<MouseWheel>", self.mousewheel)
        self.window.bind("<Configure>", self.resize)

    def resize(self, e):
        self.canvas.pack(fill='both', expand=1)
        self.width, self.height = e.width, e.height
        self.display_list = Layout(
            self.tokens, e.width).display_list
        self.draw()

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
        self.tokens = lex(build_view_source_html(body)
                          if view_source else body)
        self.display_list = Layout(
            self.tokens, self.width).display_list
        self.draw()


if __name__ == '__main__':
    import sys
    Browser(800, 600).load(sys.argv[1])
    tkinter.mainloop()
