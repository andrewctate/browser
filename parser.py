
from typing import List
from entities import entity_to_chars_dict
from request import request_url


def only_body(root):
    return root.children[1]


class Element:
    def __init__(self, tag: str, attributes: dict, parent):
        self.tag = tag
        self.attributes = attributes
        self.children = []
        self.parent = parent

    def __repr__(self):
        return "<" + self.tag + ">"


class Text:
    def __init__(self, text: str, parent: Element):
        for entity in entity_to_chars_dict:
            text = text.replace(entity, entity_to_chars_dict[entity])
        self.text = text
        self.children = []
        self.parent = parent

    def __repr__(self):
        return "Text(" + repr(self.text) + ")"


class HTMLParser:
    HEAD_TAGS = [
        "base", "basefont", "bgsound", "noscript",
        "link", "meta", "title", "style", "script",
    ]
    SELF_CLOSING_TAGS = [
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr",
    ]

    def __init__(self, html):
        self.html = html
        self.unfinished = []

    def implicit_tags(self, tag: str):
        while True:
            open_tags = [node.tag for node in self.unfinished]
            if open_tags == [] and tag != "html":
                self.add_tag("html")
            elif open_tags == ["html"] \
                    and tag not in ["head", "body", "/html"]:
                if tag in self.HEAD_TAGS:
                    self.add_tag("head")
                else:
                    self.add_tag("body")
            elif open_tags == ["html", "head"] and \
                    tag not in ["/head"] + self.HEAD_TAGS:
                self.add_tag("/head")
            else:
                break

    def get_attributes(self, text):
        parts = text.split()
        tag = parts[0].lower()
        attributes = {}
        for attrpair in parts[1:]:
            if "=" in attrpair:
                key, value = attrpair.split("=", 1)
                if len(value) > 2 and value[0] in ["'", "\""]:
                    value = value[1:-1]
                attributes[key.lower()] = value
            else:
                attributes[attrpair.lower()] = ""
        return tag, attributes

    def parse(self):
        text = ""
        in_tag = False
        for c in self.html:
            if c == "<":
                in_tag = True
                if text:
                    self.add_text(text)
                text = ""
            elif c == ">":
                in_tag = False
                self.add_tag(text)
                text = ""
            else:
                text += c
        if not in_tag and text:
            self.add_text(text)
        return self.finish()

    def add_text(self, text):
        if text.isspace():
            return
        self.implicit_tags(None)
        parent = self.unfinished[-1]
        node = Text(text, parent)
        parent.children.append(node)

    def add_tag(self, tag):
        tag, attributes = self.get_attributes(tag)
        # throw away doctype and comments
        if tag.startswith("!"):
            return
        self.implicit_tags(tag)
        if tag.startswith("/"):
            if len(self.unfinished) == 1:
                return
            node = self.unfinished.pop()
            parent = self.unfinished[-1]
            parent.children.append(node)
        elif tag in self.SELF_CLOSING_TAGS:
            parent = self.unfinished[-1]
            node = Element(tag, attributes, parent)
            parent.children.append(node)
        else:
            parent = self.unfinished[-1] if self.unfinished else None
            self.unfinished.append(Element(tag, attributes, parent))

    def finish(self) -> List[Text | Element]:
        if len(self.unfinished) == 0:
            self.add_tag("html")
        while len(self.unfinished) > 1:
            node = self.unfinished.pop()
            parent = self.unfinished[-1]
            parent.children.append(node)
        return self.unfinished.pop()


def print_tree(node, indent=0):
    print(" " * indent, node)
    for child in node.children:
        print_tree(child, indent + 2)


class CSSParser:
    def __init__(self, s: str):
        self.s = s
        self.i = 0

    def white_space(self):
        while self.i < len(self.s) and self.s[self.i].isspace():
            self.i += 1

    def word(self):
        beginning = self.i
        while self.i < len(self.s):
            if self.s[self.i].isalnum() or self.s[self.i] in "#-.%":
                self.i += 1
            else:
                break

        assert self.i > beginning
        return self.s[beginning:self.i]

    def literal(self, literal: str):
        assert self.i < len(
            self.s) and self.s[self.i] == literal, f'literal didn\'t match: {literal}'
        self.i += 1

    def pair(self):
        prop = self.word()
        self.white_space()
        self.literal(':')
        self.white_space()
        value = self.word()

        return prop.lower(), value

    def body(self):
        pairs = {}
        while self.i < len(self.s):
            try:
                prop, value = self.pair()
                pairs[prop] = value
                self.white_space()
                self.literal(';')
                self.white_space()
            except AssertionError:
                why = self.ignore_until([";"])
                if why == ";":
                    self.literal(";")
                    self.whitespace()
                else:
                    break

        return pairs

    def ignore_until(self, chars: List[str]):
        while self.i < len(self.s):
            if self.s[self.i] not in chars:
                self.i += 1
            else:
                return self.s[self.i]


if __name__ == '__main__':
    import sys
    headers, body = request_url(sys.argv[1])
    nodes = HTMLParser(body).parse()
    print_tree(nodes)
