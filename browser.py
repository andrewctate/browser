import tkinter
from request import request_url

entity_to_char = {
    "&lt;": '<',
    "&gt;": '>',
}


def get_entity_chars(entity: str):
    if entity in entity_to_char:
        return entity_to_char[entity]
    return entity


def lex(body: str):
    text = ''

    in_body = False
    tag_contents = ''
    in_tag = False

    for char in body:
        if char == '<':
            in_tag = True
        elif char == '>':
            in_tag = False
            if tag_contents.startswith("body"):
                in_body = not in_body
            tag_contents = ''
        elif in_tag:
            tag_contents += char
        elif in_body and not in_tag:
            text += char

    for entity in entity_to_char:
        text = text.replace(entity, entity_to_char[entity])

    return text


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


def layout(text, width):
    display_list = []
    cursor_x, cursor_y = HSTEP, VSTEP
    for c in text:
        display_list.append((cursor_x, cursor_y, c))
        cursor_x += HSTEP
        if cursor_x >= width - HSTEP:
            cursor_y += VSTEP
            cursor_x = HSTEP
        elif c == '\n':
            cursor_y += PSTEP
            cursor_x = HSTEP

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
        self.text = ''
        self.window.bind("<Down>", self.scrolldown)
        self.window.bind("<Up>", self.scrollup)
        self.window.bind("<MouseWheel>", self.mousewheel)
        self.window.bind("<Configure>", self.resize)

    def resize(self, e):
        self.canvas.pack(fill='both', expand=1)
        self.width, self.height = e.width, e.height
        self.display_list = layout(self.text, e.width)
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
        for x, y, c in self.display_list:
            if y > self.scroll + self.height:
                continue
            if y + VSTEP < self.scroll:
                continue
            self.canvas.create_text(x, y - self.scroll, text=c)

    def load(self, url: str):
        view_source = url.startswith("view-source:")
        if view_source:
            _, url = url.split(':', 1)

        headers, body = request_url(url)
        self.text = lex(build_view_source_html(body) if view_source else body)
        self.display_list = layout(self.text, self.width)
        self.draw()


if __name__ == '__main__':
    import sys
    Browser(800, 600).load(sys.argv[1])
    tkinter.mainloop()
