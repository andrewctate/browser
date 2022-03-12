from typing import List
from dom import Element


class TagSelector:
    def __init__(self, tag: str):
        self.tag = tag
        self.priority = 1

    def __repr__(self):
        return self.tag

    def matches(self, node):
        return isinstance(node, Element) and self.tag == node.tag


class DescendantSelector:
    def __init__(self, ancestor, descendant: TagSelector):
        self.ancestor = ancestor
        self.descendant = descendant
        self.priority = ancestor.priority + descendant.priority

    def __repr__(self):
        repr = self.descendant.tag
        cursor = self.ancestor
        while isinstance(cursor, DescendantSelector):
            repr = cursor.descendant.tag + ' ' + repr
            cursor = cursor.ancestor

        return cursor.tag + ' ' + repr

    def matches(self, node):
        if not self.descendant.matches(node):
            return False
        while node.parent:
            if self.ancestor.matches(node.parent):
                return True
            node = node.parent

        return False


class CSSParser:
    def __init__(self, s: str):
        self.s = s
        self.i = 0

    def whitespace(self):
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
        self.whitespace()
        self.literal(':')
        self.whitespace()
        value = self.word()

        return prop.lower(), value

    def body(self):
        pairs = {}
        while self.i < len(self.s) and self.s[self.i] != "}":
            try:
                prop, value = self.pair()
                pairs[prop] = value
                self.whitespace()
                self.literal(';')
                self.whitespace()
            except AssertionError:
                why = self.ignore_until([";", "}"])
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

    def selector(self):
        out = TagSelector(self.word().lower())
        self.whitespace()
        while self.i < len(self.s) and self.s[self.i] != '{':
            tag = self.word()
            descendant = TagSelector(tag.lower())
            out = DescendantSelector(out, descendant)
            self.whitespace()

        return out

    def parse(self) -> List[tuple[TagSelector | DescendantSelector, dict]]:
        rules = []
        while self.i < len(self.s):
            try:
                self.whitespace()
                selector = self.selector()
                self.literal("{")
                self.whitespace()
                body = self.body()
                self.literal("}")
                rules.append((selector, body))
            except AssertionError:
                why = self.ignore_until(["}"])
                if why == '}':
                    self.literal('}')
                    self.whitespace()
                else:
                    break

        return rules


def print_rules(rules: List[tuple[TagSelector | DescendantSelector, dict]]):
    for selector, rule in rules:
        print(selector)
        for prop, val in rule.items():
            print(f'\t{prop}: {val}')


if __name__ == '__main__':
    css = '''
    a {
        background-color: blue;
        font-size: 20px;
    }

    h1 a {
        background-color: red;
    }
    '''
    rules = CSSParser(css).parse()
    print_rules(rules)
