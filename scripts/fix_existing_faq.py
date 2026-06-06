#!/usr/bin/env python3
"""
Fix existing articles: move FAQ JSON-LD from body <script> tag to front matter faqJson field.
"""
import os
import re

posts_dir = "content/posts"
target_files = [
    "2026-06-06-curved-comfort-fit-catholic-cross-band-rings-bulk-wholesale.md",
    "2026-06-06-gold-plated-small-miraculous-medal-baby-baptism-pendant-bulk.md",
    "2026-06-06-sacred-heart-of-jesus-double-sided-brass-pendant-a-timeless.md",
    "2026-06-06-the-sacred-symbol-a-guide-to-meaningful-catholic-rings.md",
    "2026-06-06-wholesale-catholic-gift-basket-fillers-mini-rosary-cross-com.md",
]

for fname in target_files:
    filepath = os.path.join(posts_dir, fname)
    if not os.path.exists(filepath):
        print(f"Not found: {fname}")
        continue

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Extract FAQ JSON from <script type="application/ld+json">...</script>
    match = re.search(
        r'<script type="application/ld\+json">\n(.*?)\n</script>\n',
        content,
        flags=re.DOTALL
    )
    if not match:
        print(f"No FAQ block found in {fname}, skipping")
        continue

    faq_json = match.group(1).strip()

    # Remove FAQ block from body
    content = re.sub(
        r'<script type="application/ld\+json">\n.*?</script>\n*',
        '',
        content,
        flags=re.DOTALL
    )

    # Insert faqJson into front matter (before the closing ---)
    # Find the closing --- of front matter
    parts = content.split('---', 2)
    if len(parts) < 3:
        print(f"Could not parse front matter in {fname}")
        continue

    # Build faqJson as YAML multiline string
    faq_yaml = '\nfaqJson: |\n'
    for line in faq_json.split('\n'):
        faq_yaml += '  ' + line + '\n'

    # Insert before closing ---
    new_content = parts[0] + '---' + parts[1] + faq_yaml + '---' + parts[2]

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"Fixed: {fname}")

print("Done!")
