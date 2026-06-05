#!/usr/bin/env python3
"""为没有 featureimage 的文章随机分配 static/images/ 中的图片。"""
import os
import re
import random
import glob

posts_dir = "content/posts"
images_dir = "static/images"

# 收集 static/images/ 下所有图片
extensions = ('*.jpg', '*.jpeg', '*.png', '*.webp', '*.gif')
image_files = []
for ext in extensions:
    image_files.extend(glob.glob(os.path.join(images_dir, ext)))
    image_files.extend(glob.glob(os.path.join(images_dir, ext.upper())))

if not image_files:
    print("ERROR: No images found in static/images/")
    exit(1)

print(f"Found {len(image_files)} images for fallback.")

count = 0
for fname in os.listdir(posts_dir):
    if not fname.endswith(".md"):
        continue
    fpath = os.path.join(posts_dir, fname)
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()

    # 已有 featureimage 则跳过
    if re.search(r'^\s*featureimage:', content, re.MULTILINE):
        continue

    # 随机选一张图片
    chosen = random.choice(image_files)
    basename = os.path.basename(chosen)
    image_path = f"images/{basename}"  # Hugo 从 static/images/ 提供

    # 在第二个 --- 前插入 featureimage + thumbnail
    lines = content.split('\n')
    insert_idx = None
    dash_count = 0
    for i, line in enumerate(lines):
        if line.strip() == '---':
            dash_count += 1
            if dash_count == 2:
                insert_idx = i
                break

    if insert_idx is None:
        print(f"WARNING: second --- not found in {fname}, skipping")
        continue

    lines.insert(insert_idx, f'featureimage: "{image_path}"')
    lines.insert(insert_idx + 1, f'thumbnail: "{image_path}"')

    with open(fpath, "w", encoding="utf-8") as f:
        f.write('\n'.join(lines))

    count += 1
    print(f"Added featureimage to {fname}: {image_path}")

print(f"\nTotal: {count} posts updated.")
