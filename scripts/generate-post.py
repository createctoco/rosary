#!/usr/bin/env python3
"""
AI Blog Post Generator for Hugo
Reads config.yaml, picks the next unused keyword, generates an article via DeepSeek/OpenAI API,
saves as Hugo markdown post in content/posts/
"""

import os
import sys
import json
import yaml
import requests
import re
import hashlib
import random
from datetime import datetime, timezone

# ============================================
# Load Configuration
# ============================================
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

keywords = config.get("keywords", [])
alibaba_store_url = config.get("alibaba_store_url", "https://mecrt.en.alibaba.com/")
alibaba_products = config.get("alibaba_product_urls", [])
auto_image = config.get("auto_image", True)
review_mode = config.get("review_mode", False)
image_style = config.get("image_style", "elegant product photography, soft lighting, clean background")

# Pick 2-3 random product links for this article
num_links = min(random.randint(2, 3), len(alibaba_products))
selected_products = random.sample(alibaba_products, num_links) if alibaba_products else []

# AI API Configuration
api_key = os.environ.get("OPENAI_API_KEY", "")
ai_model = os.environ.get("AI_MODEL", "deepseek-chat")
ai_base_url = os.environ.get("AI_BASE_URL", "https://api.deepseek.com/v1").rstrip("/")

if not api_key:
    print("ERROR: OPENAI_API_KEY not set")
    sys.exit(1)

# ============================================
# Find Next Unused Keyword
# ============================================
existing_keywords = set()
posts_dir = "content/posts"
if os.path.isdir(posts_dir):
    for filename in os.listdir(posts_dir):
        if filename.endswith(".md"):
            filepath = os.path.join(posts_dir, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("keyword:"):
                        existing_keywords.add(
                            line.split(":", 1)[1].strip().strip('"').strip("'")
                        )

available = [k for k in keywords if k not in existing_keywords]
if not available:
    # All keywords used, restart from the beginning
    available = keywords
    print("All keywords have been used. Starting over.")

keyword = available[0]
print(f"Selected keyword: {keyword}")

# ============================================
# AI Prompt (B2B Wholesale + Alibaba Traffic)
# ============================================
title_prompt = f"""Suggest 3 SEO-optimized blog post titles for the topic: "{keyword}"
The titles should target wholesale buyers, importers, and church procurement officers.
Return ONLY the titles, one per line, no numbering, no extra comments.
Keep titles under 70 characters for Google SERP."""

content_prompt = f"""Write a 1100-1300 word English B2B SEO article for the catholic religious gifts industry.
Target audience: global wholesale buyers, importers, church procurement officers, and gift shop owners.

Topic: {keyword}

Requirements:
1. Structure: H1 title + multiple H2/H3 subheadings
2. Content must include: product buying guide, wholesale MOQ tips, material introduction, quality inspection advice
3. Write in professional B2B tone, informative and authoritative
4. Include practical tips buyers can act on immediately
5. NO fluff or filler content - every sentence must provide real value

Naturally insert these hyperlinks in the article text (use appropriate anchor text, max 3 links total):
- Link to "{alibaba_store_url}" with anchor text like "Professional Catholic Religious Gifts Wholesale Supplier" or "Verified Religious Gifts Manufacturer"
""" + "\n".join([
    f'- Link to "{p["url"]}" with anchor text: "{p["anchor"]}"'
    for p in selected_products
]) + """

At the end of the article, add a FAQ section with 3-5 common questions and detailed answers about this topic.

Then add this exact HTML block at the very end (before closing):
<div style="margin:30px 0;padding:20px;background:#f5f5f5;border-radius:6px;border-left:4px solid #c81623;">
<p><strong>Looking for bulk catholic religious gifts, rosary, or cross pendants?</strong> We are a verified Alibaba supplier offering custom OEM, factory direct pricing, and worldwide shipping.</p>
<a href="{alibaba_store_url}" target="_blank" rel="noopener" style="display:inline-block;padding:10px 20px;background:#ff4400;color:#fff;border-radius:4px;font-weight:bold;text-decoration:none;margin-top:10px;">Browse All Products on Alibaba.com</a>
</div>

Output in standard Markdown format with proper H2/H3 headers, bullet points where appropriate, and bold text for emphasis.
Do NOT add any preamble or commentary - just output the article directly."""

# ============================================
# Call AI API (OpenAI Compatible)
# ============================================
def call_ai(prompt, max_tokens=4000):
    """Call DeepSeek or OpenAI compatible API"""
    url = f"{ai_base_url}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = {
        "model": ai_model,
        "messages": [
            {"role": "system", "content": "You are a professional B2B content writer specializing in catholic religious gifts, rosary beads, and church supplies. You write SEO-optimized articles for wholesale buyers."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.8,
        "max_tokens": max_tokens,
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=120)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"ERROR calling AI API: {e}")
        sys.exit(1)

print("Generating title...")
title_raw = call_ai(title_prompt, max_tokens=500)
titles = [t.strip().lstrip("0123456789.-) ") for t in title_raw.split("\n") if t.strip()]
title = titles[0] if titles else keyword.replace("-", " ").title()

print(f"Article title: {title}")
print("Generating article content...")
content = call_ai(content_prompt, max_tokens=4000)

# ============================================
# Generate Hugo Front Matter + Save
# ============================================
now = datetime.now(timezone.utc)
date_str = now.strftime("%Y-%m-%d")
datetime_str = now.strftime("%Y-%m-%dT%H:%M:%SZ")

# Clean title for filename
safe_title = re.sub(r"[^a-zA-Z0-9\s-]", "", title.lower())
safe_title = re.sub(r"\s+", "-", safe_title).strip("-")[:80]
filename = f"{date_str}-{safe_title}.md"
filepath = os.path.join(posts_dir, filename)

# Auto-generate tags from keyword
tags = keyword.split()[:5]
if len(tags) < 2:
    tags = [keyword]

# Determine category
if any(w in keyword.lower() for w in ["rosary", "bead", "pray", "tasbih", "misbaha"]):
    category = "Rosary"
elif any(w in keyword.lower() for w in ["cross", "crucifix", "pendant"]):
    category = "Cross"
elif any(w in keyword.lower() for w in ["wholesale", "bulk", "oem", "factory", "import", "sourcing"]):
    category = "Wholesale"
elif any(w in keyword.lower() for w in ["saint", "medal", "guardian", "lady"]):
    category = "Devotional"
else:
    category = "Guide"

# Generate meta description
meta_desc = content[:160].replace("\n", " ").strip()

front_matter = f"""---
title: "{title}"
date: {datetime_str}
draft: false
keyword: "{keyword}"
tags: [{", ".join(tags)}]
categories: [{category}]
description: "{meta_desc}"
author: "CTOCO Religious Gifts"
ShowToc: true
TocOpen: false
---

"""

full_post = front_matter + "\n" + content

with open(filepath, "w", encoding="utf-8") as f:
    f.write(full_post)

print(f"Post saved: {filepath}")
print(f"Keyword: {keyword}")
print(f"Title: {title}")
print(f"Category: {category}")
print(f"Tags: {tags}")
print(f"Word count: ~{len(content.split())}")

# ============================================
# Optional: Generate Featured Image Prompt
# ============================================
if auto_image:
    image_prompt = f"{keyword}, {image_style}"
    image_prompt_hash = hashlib.md5(image_prompt.encode()).hexdigest()[:8]
    print(f"Image prompt (save for manual use or integrate with image API): {image_prompt}")

print("\nDone! Post generated successfully.")
