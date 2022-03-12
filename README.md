## Supported Features

### Requests

- URL schemes: `http:`, `https:` (TLS), `data:`, `file:` and `view-source:`
- G-ZIP content encoding
- Chunked transfer encoding
- Response Caching (respects basic `Cache-Control` headers)

### Typesetting

- Supports `i`, `b`, `small`, `big`, `sup`, `br`, `p`
- Supports HTML4 entities (with a few others)
- Respects soft-hyphens (`&shy;`)

### Window interactions

- Scroll, both with mousewheel and arrow keys
  - Prevents scrolling past end of content (harder than you might think)
- Resizing

### Elements

- Parses HTML to construct DOM nodes
- Supports `block` and `inline` elements in the layout tree

### Styling

- Parses basic inline CSS
- Robust to malformed/unsupported properties
- Supported properties
  - `background-color`

### Misc

- Supports implicit `html`, `head`, and `body` tags
