from os.path import join
from os import stat
from time import time

CACHE_DIR = './cache'


class Cache():
    @staticmethod
    def cache(url: str, response: bytes, max_age: int = "none"):
        with open(join("cache", url.replace('/', '_')), 'wb') as file:
            file.write(bytes(f"max_age={max_age}\n",
                       encoding="UTF-8") + response)

    @staticmethod
    def retrieve(url: str) -> bytes:
        try:
            with open(join("cache", url.replace('/', '_')), 'rb') as file:
                contents = file.read()
                max_age_directive, cached_response = contents.split(b'\n', 1)
                _, max_age = max_age_directive.decode('UTF-8').split('=')
                cache_fresh = True
                if max_age != "none":
                    # if a user manually edits the metadata for a file in the cache on unix systems, st_ctime won't be accurate
                    # see https://docs.python.org/3/library/stat.html#stat.ST_CTIME for more info
                    modified_time = stat(file.fileno()).st_ctime
                    current_time = int(time())
                    cache_fresh = (current_time - modified_time) < int(max_age)

                return cached_response if cache_fresh else None
        except FileNotFoundError:
            return None
