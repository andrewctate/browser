import socket
import ssl


def parse_url(url: str):
    scheme, url = url.split("://", 1)

    assert scheme in ["http", "https"], \
        "Unknown scheme {}".format(scheme)

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


def request(url: str):
    scheme, host, port, path = parse_url(url)

    # TODO - does this check belong in the parse_url func?
    assert host

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

    request = f"GET {path} HTTP/1.0\r\n" \
        + f"Host: {host}\r\n\r\n"

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


def show(body: str):
    in_tag = False

    for char in body:
        if char == '<':
            in_tag = True
        elif char == '>':
            in_tag = False
        elif not in_tag:
            print(char, end='')


def load(url: str):
    headers, body = request(url)
    show(body)


if __name__ == '__main__':
    import sys
    load(sys.argv[1])
