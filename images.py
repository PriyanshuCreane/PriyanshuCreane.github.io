import os
import re
import shutil
import urllib.parse
from pathlib import Path


# Paths (using raw strings for Windows paths)
posts_dir = Path(r"C:\Users\priya\Documents\Apple6454\content\posts")
attachments_dir = Path(r"C:\Users\priya\OneDrive\Documents\Obsidian Vault\Posts")
static_images_dir = Path(r"C:\Users\priya\Documents\Apple6454\static\images")

# Make sure source exists
if not posts_dir.exists():
    raise FileNotFoundError(f"Posts directory not found: {posts_dir}")

# Ensure destination directory exists
static_images_dir.mkdir(parents=True, exist_ok=True)

# Config
SUPPORTED_EXT = ('.png', '.jpg', '.jpeg', '.gif', '.svg')
# If True, don't actually copy files; just show what would happen
DRY_RUN = False


def url_for(path: str) -> str:
    """Return a URL-safe path for use in markdown (preserve subfolders).

    Example: 'folder/My Image.png' -> 'folder/My%20Image.png'
    """
    parts = Path(path).parts
    return '/'.join(urllib.parse.quote_plus(p) for p in parts)


image_pattern = re.compile(r"\[\[([^\]]+?(?:\.(?:png|jpg|jpeg|gif|svg)))\]\]", re.IGNORECASE)
# Markdown image pattern: capture the URL/path inside ![alt](path)
md_image_pattern = re.compile(r"!{1,2}\[[^\]]*\]\(([^)]+)\)")


def find_attachment_file(rel_path: str) -> Path | None:
    """Given a relative path or URL-encoded name seen in markdown, try to
    resolve it to a file inside `attachments_dir`.

    Strategy:
    - URL-decode the path
    - If it contains subfolders, respect them when checking
    - Try exact match, then fallback to a simple glob search by stem
    """
    # Decode URL-encoded names like 'Pasted%20image.png'
    decoded = urllib.parse.unquote_plus(rel_path)
    p = Path(decoded)

    # If the path begins with a leading '/images/' (already pointing to static), strip it
    if str(p).startswith('/images/'):
        p = Path(str(p).lstrip('/').split('/', 1)[1])

    candidate = attachments_dir.joinpath(*p.parts)
    if candidate.exists():
        return candidate

    # Try simple fallback: look for files with the same stem and same suffix anywhere inside attachments_dir
    stem = p.stem
    suffix = p.suffix
    if not suffix and '.' in rel_path:
        # last-resort: try to infer suffix from original string
        suffix = Path(rel_path).suffix

    if suffix:
        pattern = f"{stem}*{suffix}"
    else:
        pattern = f"{stem}*"

    for match in attachments_dir.rglob(pattern):
        # Return the first match (can be improved later with better heuristics)
        return match

    # Looser fallback: try prefix matches (useful for pasted images with differing timestamps)
    prefix = stem
    # remove trailing digits from prefix (common in pasted image timestamps)
    prefix = re.sub(r"\d+$", "", prefix)
    if prefix:
        for match in attachments_dir.rglob(f"{prefix}*"):
            return match

    return None


# Step 1: Process each markdown file in posts directory
for md_path in posts_dir.glob('*.md'):
    with md_path.open('r', encoding='utf-8') as f:
        content = f.read()

    # Step 2: Find all image links in Obsidian style [[path/to/image.png]]
    images = image_pattern.findall(content)

    # Also find standard markdown image links like ![alt](/images/foo.png) or ![alt](Pasted image.png)
    md_images = md_image_pattern.findall(content)

    # If there are no Obsidian-style or markdown-style image links, skip this file
    if not images and not md_images:
        continue

    for image in images:
        # Normalize path separators from Obsidian (which can use /)
        image_rel = image.replace('\\', '/').lstrip('/')

        # Only process supported extensions
        if not image_rel.lower().endswith(SUPPORTED_EXT):
            print(f"Skipping unsupported extension: {image_rel}")
            continue

        # Build markdown replacement
        md_url = f"/images/{url_for(image_rel)}"
        markdown_image = f"![{Path(image_rel).stem}]({md_url})"

        content = content.replace(f"[[{image}]]", markdown_image)

        # Copy file from attachments into static images, preserving subfolders
        src = find_attachment_file(image_rel)
        if src is None:
            print(f"File not found in attachments (Obsidian link), skipped: {image_rel}")
            continue
        dest = static_images_dir.joinpath(*Path(image_rel).parts)
        dest.parent.mkdir(parents=True, exist_ok=True)

        if DRY_RUN:
            print(f"DRY RUN: would copy {src} -> {dest}")
        else:
            shutil.copy2(src, dest)
            print(f"Copied: {src} -> {dest}")

    # Write updated content back to the markdown file
    with md_path.open('w', encoding='utf-8') as f:
        f.write(content)

    # Now handle markdown-style images
    if md_images:
        for img_path in md_images:
            # Skip external URLs and data URIs
            if img_path.startswith('http://') or img_path.startswith('https://') or img_path.startswith('data:'):
                continue

            # Normalize and decode path
            decoded = urllib.parse.unquote_plus(img_path)
            # If already points to /images/, strip that for mapping
            if decoded.startswith('/images/'):
                rel = decoded.lstrip('/images/').lstrip('/')
            else:
                rel = decoded.lstrip('/')

            # Only process supported extensions
            if not any(rel.lower().endswith(ext) for ext in SUPPORTED_EXT):
                # not an image we handle
                continue

            src = find_attachment_file(rel)
            if src is None:
                print(f"File not found in attachments (markdown link), skipped: {rel}")
                continue

            dest = static_images_dir.joinpath(*Path(rel).parts)
            dest.parent.mkdir(parents=True, exist_ok=True)
            if DRY_RUN:
                print(f"DRY RUN: would copy (md) {src} -> {dest}")
            else:
                shutil.copy2(src, dest)
                print(f"Copied (md): {src} -> {dest}")

print("Markdown files processed and images copied (where found).")
