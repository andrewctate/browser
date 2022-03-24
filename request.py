from email.policy import default
from gzip import decompress
import socket
import ssl

from cache import Cache

MAX_REDIRECT_COUNT = 5


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


def fetch_response(scheme: str, host: str, port: str, path: str, accept_compressed=True):
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
        "User-Agent": "Andrew's Toy Browser",
        # see https://datatracker.ietf.org/doc/html/rfc2068#section-8.1.2.1 for more details
        "Connection": "close"
    }

    if accept_compressed:
        default_headers["Accept-Encoding"] = "gzip"

    request = f"GET {path} HTTP/1.1\r\n"

    for key, val in default_headers.items():
        request += f"{key}: {val}\r\n"

    request += "\r\n"

    s.send(request.encode('utf8'))

    response = s.makefile('rb', buffering=0).read()

    s.close()

    return response


def extract_response_info(response: bytes):
    lines = response.split(b"\r\n")

    statusline = lines[0].decode("utf-8", "ignore")

    version, status, explanation = statusline.split(' ', 2)

    headers = {}
    for i, line in enumerate(lines[1:]):
        if line == b'':
            # (b'' was b"\r\n")
            break
        header, value = line.decode("utf-8", "ignore").split(':', 1)
        headers[header.lower()] = value.strip()

    body = b''
    if "transfer-encoding" in headers and headers["transfer-encoding"] == "chunked":
        # see https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Transfer-Encoding#chunked_encoding for more detail
        chunks = lines[i+3::2]
        for chunk in chunks:
            if chunk == b'':
                # Reached terminating chunk
                break
            body += chunk
    else:
        body = lines[-1]

    if "content-encoding" in headers:
        if headers["content-encoding"] == "gzip":
            body = decompress(body)
        else:
            raise TypeError('This browser only accepts gzip encoding')

    body = body.decode('utf-8', "ignore")

    return status, explanation, headers, body


def request_remote(url: str):
    redirect_count = 0
    cache_hit = False

    while redirect_count < MAX_REDIRECT_COUNT:
        response = Cache.retrieve(url)

        if response:
            cache_hit = True
        else:
            scheme, host, port, path = parse_url(url)

            assert host, "You must provide a host to connect to!"
            assert path, "You must provide a path to request!"

            response = fetch_response(
                scheme, host, port, path, accept_compressed=False)

        status, explanation, headers, body = extract_response_info(
            response)

        if status.startswith("3"):
            assert "location" in headers, "Redirect response must contain a location header!"
            url = headers["location"]
        else:
            break

        redirect_count += 1

    assert redirect_count < MAX_REDIRECT_COUNT, "Reached max redirects"

    assert status == "200", "{}: {}\n".format(
        status, explanation)

    if not cache_hit:
        # could cache redirects and 404s as well
        if "cache-control" in headers:
            cache_control = headers["cache-control"]
            if cache_control.startswith("max-age"):
                _, max_age = cache_control.split('=')
                Cache.cache(url, response, int(max_age))

    return headers, body


def request_local(path: str) -> str:
    with open(path) as file:
        return file.read()


def parse_data_url(url: str) -> list:
    _, url = url.split(':', 1)  # discard "data:"
    return url.split(',', 1)


def request_url(url: str):
    response_body = None
    headers = {}

    if url.startswith("data:"):
        content_type, response_body = parse_data_url(url)
        return headers, response_body

    scheme, host, port, path = parse_url(url)

    if scheme in ["http", "https"]:
        headers, response_body = request_remote(url)
    elif scheme == "file":
        response_body = request_local(path)
    else:
        raise RuntimeError(f"Unknown scheme {scheme}")

    return headers, response_body


# converts normal, host-relative, and path-relative URLs to normal URLs
def resolve_url(url: str, current: str):
    if "://" in url:
        return url
    elif url.startswith("/"):
        scheme, hostpath = current.split("://", 1)
        host, oldpath = hostpath.split("/", 1)
        return scheme + "://" + host + url
    else:
        dir, _ = current.rsplit("/", 1)
        while url.startswith("../"):
            url = url[3:]
            if dir.count("/") == 2:
                continue
            dir, _ = dir.rsplit("/", 1)
        return dir + "/" + url
