#!/usr/bin/env python3
"""
Auto-generate a B2B SEO blog post using DeepSeek API.
Saves output as content/posts/YYYY-MM-DD-slug.md
Supports multiple posts per day with unique filenames.
Features:
  - Pexels API for featured images (with local images/ fallback)
  - Markdown output for TOC compatibility
  - Hero image support (Blowfish theme)
"""

import os
import sys
import re
import random
import glob
import yaml
import requests
from datetime import datetime, timezone, timedelta

# ============================================
# Load Configuration
# ============================================
def load_config():
    with open("blog-config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def get_alibaba(config):
    return {
        "store": config.get("alibaba_store_url", ""),
        "products": config.get("alibaba_products", [])
    }

# ============================================
# Pick Keyword (avoid duplicates, random selection)
# ============================================
def pick_keyword(config):
    keywords = config.get("keywords", [])
    if not keywords:
        print("ERROR: no keywords found in blog-config.yaml")
        sys.exit(1)

    posts_dir = "content/posts"
    used = set()
    if os.path.exists(posts_dir):
        for fname in os.listdir(posts_dir):
            if not fname.endswith(".md"):
                continue
            filepath = os.path.join(posts_dir, fname)
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("keyword:"):
                        val = line.split(":", 1)[1].strip().strip('"').strip("'")
                        used.add(val)

    available = [k for k in keywords if k not in used]
    if not available:
        print("All keywords used, resetting cycle...")
        available = keywords  # all used, restart cycle

    chosen = random.choice(available)
    print(f"Used keywords: {len(used)}/{len(keywords)}")
    print(f"Selected keyword: {chosen}")
    return chosen

# ============================================
# Fetch Featured Image from Pexels API
# ============================================

def is_japanese_image(photo):
    """
    Check if a Pexels photo is Japanese-themed and should be excluded.
    Returns True if the image should be SKIPPED.
    """
    # Blacklisted Pexels photo IDs (confirmed bad images)
    BLACKLISTED_PHOTO_IDS = {
        "9566267",   # Japanese-themed image, confirmed by user
    }

    photo_id = str(photo.get("id", ""))
    if photo_id in BLACKLISTED_PHOTO_IDS:
        print(f"  Skipping blacklisted photo ID: {photo_id}")
        return True

    # Check alt text for Japanese-related keywords
    alt_text = (photo.get("alt") or "").lower()
    japanese_keywords = [
        "japan", "japanese", "tokyo", "kyoto", "osaka", "hiroshima",
        "shinto", "torii", "geisha", "kimono", "sake", "matcha",
        "zen garden", "bonsai", "origami", "sushi", "ramen",
    ]
    for kw in japanese_keywords:
        if kw in alt_text:
            print(f"  Skipping Japanese-themed photo (alt: ...{alt_text[:60]}...)")
            return True

    # Check photographer name for CJK characters (Japanese/Chinese/Korean)
    photographer = photo.get("photographer", "")
    if __import__('re').search(r'[぀-ゟ゠-ヿ一-鿿]', photographer):
        print(f"  Skipping photo by CJK photographer: {photographer}")
        return True

    return False


def fetch_pexels_image(keyword, api_key):
    """Fetch a Pexels image URL (no local download, avoid repo bloat)"""
    if not api_key:
        print("No Pexels API key provided, skipping Pexels")
        return None

    search_terms = [
        keyword.replace("wholesale", "").replace("bulk", "").replace("OEM", "").replace("guide", "").strip(),
        "catholic rosary beads",
        "rosary",
        "catholic prayer"
    ]

    for search_term in search_terms:
        if not search_term.strip():
            continue
        try:
            print(f"Searching Pexels for: {search_term}")
            response = requests.get(
                "https://api.pexels.com/v1/search",
                params={"query": search_term, "per_page": 15, "size": "large"},
                headers={"Authorization": api_key},
                timeout=15
            )
            response.raise_for_status()
            data = response.json()

            if data.get("photos"):
                # Filter out Japanese-themed images
                filtered_photos = [p for p in data["photos"] if not is_japanese_image(p)]
                if not filtered_photos:
                    print(f"  All {len(data['photos'])} photos filtered out (Japanese-themed), trying next search term...")
                    continue
                photo = random.choice(filtered_photos)
                image_url = photo["src"]["large2x"]
                photographer = photo.get("photographer", "Pexels")
                print(f"Pexels image URL: {image_url} (by {photographer})")
                return image_url  # Return URL directly, no local download

        except Exception as e:
            print(f"Warning: Pexels search failed for '{search_term}': {e}")
            continue

    print("Warning: Could not fetch any image from Pexels")
    return None

# ============================================
# Fallback: Random Image from Local images/ Folder
# ============================================
def fetch_local_fallback_image():
    """Pick a random image from static/images/ (no copy, avoid repo bloat)"""
    images_dir = "static/images"
    if not os.path.exists(images_dir):
        images_dir = "images"
    if not os.path.exists(images_dir):
        print("No local images/ folder found, skipping fallback")
        return None

    extensions = ('*.jpg', '*.jpeg', '*.png', '*.webp', '*.gif')
    image_files = []
    for ext in extensions:
        image_files.extend(glob.glob(os.path.join(images_dir, ext)))
        image_files.extend(glob.glob(os.path.join(images_dir, ext.upper())))

    if not image_files:
        print("No images found in images/ folder, skipping fallback")
        return None

    chosen = random.choice(image_files)
    basename = os.path.basename(chosen)
    print(f"Local fallback image: {basename}")
    return f"https://rosarysupply.com/images/{basename}"  # Absolute URL for Blowfish hotlinkFeatureImage


# ============================================
# Get Featured Image (Pexels first, local fallback)
# ============================================
def get_featured_image(keyword, pexels_api_key):
    """Try Pexels API first; fallback to local random image if fails"""
    image_url = fetch_pexels_image(keyword, pexels_api_key)
    if image_url:
        return image_url

    print("Pexels failed, trying local images/ fallback...")
    local_image = fetch_local_fallback_image()
    if local_image:
        return local_image

    print("Warning: no feature image available for this post")
    return None

# ============================================
# Call DeepSeek API
# ============================================
def call_api(prompt, api_key, model, api_url, temperature=0.85):
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": 2500
    }
    resp = requests.post(
        f"{api_url}/chat/completions",
        headers=headers,
        json=payload,
        timeout=90
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]

# ============================================
# Build Prompts
# ============================================
def build_title_prompt(keyword):
    return f"Generate a short, SEO-friendly blog post title about: {keyword}. Output ONLY the title, nothing else."

def build_faq_prompt(keyword, title):
    return f"""Generate 2-3 FAQ items (JSON-LD format) related to the blog post titled "{title}" with keyword "{keyword}".
The topic is Catholic religious goods wholesale/B2B.

Anti-AI rules for FAQ answers:
- Do NOT start answers with "Yes, " or "Absolutely, " — get straight to the point
- Use plain, conversational English — like a factory sales rep answering a buyer's question
- Keep answers short: 1-3 sentences max
- Include real numbers when relevant (e.g., MOQ, sizes, lead times)

Output ONLY valid JSON-LD for a FAQPage (schema.org format), no markdown, no explanation.
Example format:
{{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {{
      "@type": "Question",
      "name": "Actual buyer question here?",
      "acceptedAnswer": {{
        "@type": "Answer",
        "text": "Natural sounding answer..."
      }}
    }}
  ]
}}
"""

def build_article_prompt(keyword, alibaba):
    products = alibaba["products"]
    store = alibaba["store"]
    product_list = "\n".join([f"  - {p}" for p in products]) if products else ""

    return f"""You are an experienced B2B content writer for a Catholic rosary beads factory.

=== 花撸AI味根除指令（必须严格执行，违反任何一条即为废稿） ===

【禁止的 AI 高频固定句式 — 出现即废稿】
- "in today's market" / "in today's competitive market" / "in the modern market"
- "it's worth mentioning" / "it is worth noting" / "it's important to note"
- "key advantage" / "stands out as" / "game-changer" / "must-have"
- "ideal choice" / "perfect choice" / "excellent choice" / "go-to choice"
- "elevate your" / "elevating your" / "enhance your" / "enhancing your"
- "in the world of" / "in the realm of" / "in the landscape of"
- "comprehensive guide" / "ultimate guide" / "complete guide"
- "transform your" / "make a statement"
- "timeless addition" / "timeless piece"
- "whether you're X or Y" / "whether you are X or Y"
- "not only X but also Y" (not only...but also 整个句式禁用)
- "looking to" + verb (如 "looking to elevate", "looking to enhance")
- "In conclusion" / "To sum up" / "In summary" / "All in all" / "Ultimately"
- "首先/其次/最后" 等模板过渡词

【句式打散规则 — 必须遵守】
- 长短句穿插：有的句子5-8词，有的15-20词，不要每句都12-15词
- 拆分长复合句：一个超过25词的句子，拆成2个短句
- 偶尔用口语化补充，比如：
  "Many catholic believers pick this handmade rosary for baptism gifts."
  "We've been getting a lot of orders from parish gift shops lately."
  "Honestly, the 8mm size outsells everything else by a mile."
- 允许不完整句、反问句、感叹句，打破 AI 文本熵特征
- 段落长度随机：有的2-3句，有的只有1句

【排比句禁令】
- 禁止连续3个以上结构相同的句子
- 禁止每段字数高度一致

【写作人设】
- 用「我们」而不是「该厂」「该工厂」
- 写作风格参考真实工厂老板/销售写的博客：直接、带点个人观点、偶尔跑题
- 可以适度使用反问句、感叹句

=== 独家产品信息（必须自然植入，这是AI编不出来的独家数据，直接拉高E-E-A-T） ===

每篇文案必须包含以下信息（至少提及3项，以自然方式融入上下文，不要硬塞列表）：
1. 实木念珠用料 — 我们的念珠用的是天然实木，不是塑料或者树脂仿木
2. 手工雕刻工艺 — 每颗珠子是手工打磨的，不是机器批量压出来的
3. 念珠尺寸 — 念珠一般是8mm和10mm居多，6mm的也有但偏小，12mm偏大
4. 绳结打法 — 可以打秘鲁结(Peruvian knot)，也可以打平结(flat knot)，看客户需求
5. 定制 LOGO — 可以在吊牌或者包装上定制 LOGO，church name、parish name 都行
6. 天主教使用场景 — 洗礼gift、初圣体、坚振、婚礼、葬礼追思、日常祈祷、玫瑰经团契
7. 起订量 — 小批量 OEM 起订量是1200pcs，现货产品起订量是12pcs，数量越多越便宜

植入示例（仅供参考风格，不要照抄）：
- "Our wooden rosaries use real solid wood — not the plastic imitation stuff you see on cheap imports. Each bead is hand-carved and polished."
- "The 8mm size? That's our best seller. 10mm comes close second. We can do Peruvian knot or flat knot — up to you."
- "MOQ for OEM with your logo is 1200 pieces. For our in-stock items, you can start at just 12 pieces. Buy more, pay less."

=== IMPORTANT CONSTRAINT ===
This is a CATHOLIC/CHRISTIAN religious goods website.
- ONLY write about Catholic and Christian religious items.
- NEVER write about Islamic prayer beads (tasbih, misbaha), Buddhist mala, Hindu jewelry, or any non-Catholic/non-Christian religious topics.

Write a 900-1200 word English blog post targeting: {keyword}

Requirements:
- B2B English, targeting wholesale buyers, importers, church procurement
- Use Markdown: ## for H2, ### for H3
- Do NOT follow a fixed structure — let the content flow naturally
- Vary paragraph length wildly: some 1-sentence paragraphs, some long ones
- Include 3-5 headings total (not always the same number)
- Naturally mention the Alibaba store ({store}) and 2-3 product links in the body:
{product_list}
- End with a conclusion, but keep it natural (no "In conclusion" or similar AI clichés)
- Do NOT include a title (H1) — we add it separately
- Do NOT include meta description or JSON-LD (we add separately)
- Tone: like a real factory owner writing — direct, personal, occasionally imperfect English is OK

Output ONLY the article in Markdown format, no preamble.
"""

# ============================================
# Parse Title
# ============================================
def extract_title(text):
    for line in text.split('\n'):
        line = line.strip()
        if line.startswith('# '):
            title = line.lstrip('# ').strip()
            return title[:80]
        if line and not line.startswith('#') and not line.startswith('---'):
            title = re.sub(r'[*_`#]', '', line)
            return title.strip()[:80]
    return "Untitled"

def slugify(text):
    slug = text.lower()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s-]+', '-', slug)
    return slug[:60].strip('-')

# ============================================
# Build Markdown File Content
# ============================================
def build_markdown(title, keyword, article_md, alibaba, featured_image, faq_json):
    # Use Beijing time (UTC+8) consistently
    tz_bj = timezone(timedelta(hours=8))
    now = datetime.now(tz_bj)
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H%M%S")
    slug = slugify(title)
    filepath = f"content/posts/{date_str}-{slug}.md"

    # If file already exists, append time suffix to avoid collision
    if os.path.exists(filepath):
        filepath = f"content/posts/{date_str}-{time_str}-{slug}.md"

    store = alibaba["store"]
    products = alibaba["products"]
    random_links = random.sample(products, min(2, len(products))) if products else []

    iso_date = now.strftime("%Y-%m-%dT%H:%M:%S+08:00")

    # Escape double quotes in title for safe YAML
    safe_title = title.replace('"', '\\"')
    # Build front matter
    front_matter_lines = [
        '---',
        f'title: "{safe_title}"',
        f'date: {iso_date}',
        'draft: false',
        f'keyword: "{keyword}"',
        'tags: ["wholesale", "catholic", "rosary", "B2B"]',
        'categories: ["Rosary Beads"]',
    ]
    if featured_image:
        front_matter_lines.append(f'featureimage: "{featured_image}"')
        front_matter_lines.append(f'thumbnail: "{featured_image}"')
    # Store FAQ JSON in front matter (YAML multiline string)
    if faq_json and faq_json.strip():
        front_matter_lines.append('faqJson: |')
        for line in faq_json.strip().split('\n'):
            front_matter_lines.append('  ' + line)
    front_matter_lines.append('---')
    front_matter = '\n'.join(front_matter_lines)

    # CTA block in Markdown
    cta = "## Shop Wholesale Rosary Beads\n\n"
    cta += f"Looking for wholesale catholic rosary beads? Visit our **[Alibaba Store]({store})** for factory-direct pricing.\n\n"
    if random_links:
        cta += "### Featured Products\n\n"
        for link in random_links:
            cta += f"- [View Product on Alibaba]({link})\n"

    content = f"""{front_matter}

{article_md}

---

{cta}
"""

    return filepath, content

# ============================================
# Main Flow
# ============================================
def main():
    config = load_config()
    keyword = pick_keyword(config)

    api_key = os.environ.get("OPENAI_API_KEY", "")
    model = os.environ.get("AI_MODEL", "deepseek-chat")
    api_url = os.environ.get("AI_API_URL", "https://api.deepseek.com/v1")
    pexels_api_key = os.environ.get("PEXELS_API_KEY", "")

    if not api_key:
        print("ERROR: OPENAI_API_KEY environment variable not set")
        sys.exit(1)

    # 1. Generate title
    print("Generating title...")
    title_raw = call_api(build_title_prompt(keyword), api_key, model, api_url)
    title = title_raw.strip().strip('"').strip("'")
    print(f"Title: {title}")

    # 2. Fetch featured image (Pexels API → local images/ fallback)
    print("Fetching featured image...")
    featured_image = get_featured_image(keyword, pexels_api_key)
    if featured_image:
        print(f"Featured image: {featured_image}")
    else:
        print("No featured image for this post")

    # 3. Generate article (Markdown format for TOC compatibility)
    print("Generating article...")
    alibaba = get_alibaba(config)
    article_md = call_api(build_article_prompt(keyword, alibaba), api_key, model, api_url, temperature=0.85)

    # 3b. Generate FAQ dynamically
    print("Generating FAQ...")
    try:
        faq_raw = call_api(build_faq_prompt(keyword, title), api_key, model, api_url, temperature=0.9)
        # Extract JSON from possible markdown wrapping
        faq_raw = faq_raw.strip()
        if faq_raw.startswith("```"):
            faq_raw = re.sub(r'^```[a-z]*\n|```$', '', faq_raw, flags=re.MULTILINE)
        faq_json = faq_raw.strip()
        # Validate it looks like JSON-LD
        if not faq_json.startswith('{'):
            faq_json = ""
            print("Warning: FAQ output doesn't look like JSON, skipping")
        else:
            print("FAQ generated successfully")
    except Exception as e:
        print(f"Warning: FAQ generation failed: {e}")
        faq_json = ""

    # 4. Save file
    os.makedirs("content/posts", exist_ok=True)
    filepath, content = build_markdown(title, keyword, article_md, alibaba, featured_image, faq_json)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"Saved: {filepath}")
    print("Done!")

if __name__ == "__main__":
    main()
