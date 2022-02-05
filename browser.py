import socket
import ssl


def parse_url(url: str):
    scheme, url = url.split("://", 1)

    path = ''
    if '/' in url:
        host, path = url.split('/', 1)
        path = '/' + path
    else:
        host = url

    port = ''
    if ":" in host:
        host, port = host.split(':', 1)

    return scheme, host, port, path


def request_remote(scheme: str, host: str, port: str, path: str):
    assert host, "You must provide a host to connect to!"
    assert path, "You must provide a path to request!"

    s = socket.socket(
        family=socket.AF_INET,
        type=socket.SOCK_STREAM,
        proto=socket.IPPROTO_TCP,
    )

    if not port:
        port = 80 if scheme == "http" else 443

    s.connect((host, port))

    if scheme == "https":
        ctx = ssl.create_default_context()
        s = ctx.wrap_socket(s, server_hostname=host)

    default_headers = {
        "Host": host,
        # see https://datatracker.ietf.org/doc/html/rfc2068#section-8.1.2.1 for more details
        "Connection": "close"
    }

    request = f"GET {path} HTTP/1.1\r\n"

    for header in default_headers.items():
        request += f"{header[0]}: {header[1]}\r\n"

    request += "\r\n"

    s.send(request.encode('utf8'))

    response = s.makefile('r', encoding="utf8", newline="\r\n")

    statusline = response.readline()
    version, status, explanation = statusline.split(' ', 2)
    assert status == "200", "{}: {}\nRequest:\n{}".format(
        status, explanation, request)

    headers = {}
    while True:
        line = response.readline()
        if line == "\r\n":
            break
        header, value = line.split(':', 1)
        headers[header.lower()] = value.strip()

    body = response.read()

    s.close()

    return headers, body


def request_local(path: str):
    with open(path) as file:
        return file.read()


def parse_data_url(url: str):
    _, url = url.split(':', 1)  # discard "data:"
    return url.split(',', 1)


def request(url: str):
    response_body = None
    headers = {}

    if url.startswith("data:"):
        content_type, response_body = parse_data_url(url)
        return headers, response_body

    scheme, host, port, path = parse_url(url)

    if scheme in ["http", "https"]:
        headers, response_body = request_remote(scheme, host, port, path)
    elif scheme == "file":
        response_body = request_local(path)
    else:
        raise RuntimeError(f"Unknown scheme {scheme}")

    return headers, response_body


entity_to_chars = {
    "&lt;": '<',
    "&gt;": '>',
}


def get_entity_chars(entity: str):
    if entity in entity_to_chars:
        return entity_to_chars[entity]
    return entity


def show(body: str):
    in_body = False
    tag_name = ''
    in_tag = False
    entity = ''
    in_entity = False

    for char in body:
        if char == '<':
            in_tag = True
        elif char == '>':
            in_tag = False
            if tag_name == "body":
                in_body = not in_body
            tag_name = ''
        elif in_tag:
            tag_name += char
        elif char == '&':
            entity = char
            in_entity = True
        elif in_entity and char == ';':
            entity += char
            print(get_entity_chars(entity), end='')
            entity = ''
            in_entity = False
        elif in_entity:
            entity += char
        elif in_body and not in_tag:
            print(char, end='')


def load(url: str):
    view_source = url.startswith("view-source:")
    if view_source:
        _, url = url.split(':', 1)

    headers, body = request(url)
    show(body)


if __name__ == '__main__':
    import sys
    load(sys.argv[1])
