# Public Assets Directory

Static assets served by Vite. Files in this directory are copied to the build output at `/`.

## Directory Structure

```
public/
├── images/
│   └── screenshots/        # Product screenshots for landing page
│       ├── msfEditor.png
│       ├── job_details.png
│       └── jobs_queue.png
├── favicons/              # Site icons and favicons
│   └── (add favicon files here)
└── README.md             # This file
```

## Usage

### Images

Reference images from components using absolute paths:

```jsx
<img src="/images/screenshots/example.png" alt="Description" />
```

### Favicons

Add favicon files to `/favicons/` and reference in `index.html`:

```html
<link rel="icon" type="image/svg+xml" href="/favicons/favicon.svg" />
<link rel="icon" type="image/png" href="/favicons/favicon.png" />
```

## Guidelines

1. **Optimize images before adding:**
   - Use WebP for photos (better compression)
   - Use PNG for screenshots with text
   - Use SVG for icons and logos

2. **Naming conventions:**
   - Use lowercase with underscores: `job_details.png`
   - Be descriptive: `msf_editor_screenshot.png` not `img1.png`

3. **Size recommendations:**
   - Screenshots: 1920x1080 @ 2x resolution
   - Icons: SVG preferred, or PNG at multiple sizes
   - Compress images using tools like ImageOptim or TinyPNG

## Vite Static Asset Handling

Files in `public/` are:
- Served at root path `/`
- NOT processed by Vite build pipeline
- Copied as-is to build output
- Suitable for assets that never change or need exact filenames
