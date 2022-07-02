# Browser

This is a toy browser I'm building to learn more about the workings of the web platform. I'm mostly following the excellent curriculum at https://browser.engineering.

![Browser screenshot](/imgs/browser.png "Browser in action")
![Browser screenshot with layout annotations](/imgs/layout_tree.png "With layout annotations")

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

- Supports tag name and descendant selectors (no classes)
- Applies inline CSS and linked stylesheets
- Respects file-order tie-breaker rule
- Robust to malformed/unsupported properties
- Supported properties
  - `background-color`
  - `font-size` (inherited, supports `px` and `%`)
  - `font-style` (inherited)
  - `font-weight` (inherited)
  - `color` (inherited)

### Navigation

- Supports multiple tabs
- Navigation by address bar
- Back button
- Hyperlinks
- URL fragments

### Misc

- Supports implicit `html`, `head`, and `body` tags
