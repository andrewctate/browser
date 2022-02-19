import tkinter
import tkinter.font
from request import request_url


class Text:
    def __init__(self, text: str):
        for entity in entity_to_char:
            text = text.replace(entity, entity_to_char[entity])
        self.text = text


class Tag:
    def __init__(self, tag):
        self.tag = tag


entity_to_char = {
    "&lt;": '<',
    "&gt;": '>',
}


def get_entity_chars(entity: str):
    if entity in entity_to_char:
        return entity_to_char[entity]
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
    for key, val in entity_to_char.items():
        char_to_entity[val] = key

    escaped = ''
    for char in html:
        escaped += char_to_entity[char] if char in char_to_entity else char

    return escaped


def build_view_source_html(source: str):
    return f"<body>{escape_html(source)}</body>"


HSTEP, VSTEP = 13, 18
PSTEP = VSTEP + VSTEP / 2


def layout(tokens, width: int):
    display_list = []
    cursor_x, cursor_y = HSTEP, VSTEP

    weight = "normal"
    style = "roman"

    for tok in only_body(tokens):
        if isinstance(tok, Text):
            font = tkinter.font.Font(
                size=16,
                weight=weight,
                slant=style,
            )
            for word in tok.text.split():
                w = font.measure(word)
                if cursor_x + w > width - HSTEP:
                    cursor_y += font.metrics("linespace") * 1.25
                    cursor_x = HSTEP
                display_list.append((cursor_x, cursor_y, word, font))
                cursor_x += w + font.measure(" ")

        elif tok.tag == "i":
            style = "italic"
        elif tok.tag == "/i":
            style = "roman"
        elif tok.tag == "b":
            weight = "bold"
        elif tok.tag == "/b":
            weight = "normal"

    # for c in text:
    #     display_list.append((cursor_x, cursor_y, c))
    #     cursor_x += HSTEP
    #     if cursor_x >= width - HSTEP:
    #         cursor_y += VSTEP
    #         cursor_x = HSTEP
    #     elif c == '\n':
    #         cursor_y += PSTEP
    #         cursor_x = HSTEP

    return display_list


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
        self.display_list = layout(self.tokens, e.width, self.font)
        self.draw()

    def mousewheel(self, e):
        scroll_delta = SCROLL_STEP * -e.delta
        if self.scroll + scroll_delta > 0:
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
        self.display_list = layout(
            self.tokens, self.width)
        self.draw()


if __name__ == '__main__':
    import sys
    Browser(800, 600).load(sys.argv[1])
    tkinter.mainloop()
