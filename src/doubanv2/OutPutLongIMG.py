#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
from PIL import Image

MAX_DIM = 65000  # Pillow 的大致安全限制

def concat_images_vertically(image_paths, output_path="long_image.png"):
    image_paths = [p for p in image_paths if os.path.exists(p)]

    if len(image_paths) == 0:
        print("没有收到任何图片。")
        return

    image_paths.sort()
    print("接收到图片：")
    for p in image_paths:
        print(" -", p)

    images = [Image.open(path) for path in image_paths]

    base_width = images[0].width
    resized = []

    for img in images:
        if img.width != base_width:
            ratio = base_width / img.width
            img = img.resize((base_width, int(img.height * ratio)), Image.LANCZOS)
        resized.append(img)

    total_height = sum(img.height for img in resized)

    if total_height > MAX_DIM:
        print(f"⚠️ 拼接后高度 {total_height}px，超过 65000 限制，自动使用 PNG 保存格式。")

    long_image = Image.new("RGB", (base_width, total_height), color=(255,255,255))

    y = 0
    for img in resized:
        long_image.paste(img, (0, y))
        y += img.height

    # 强制使用 PNG，避免 JPEG 限制
    output_path = os.path.splitext(output_path)[0] + ".png"
    long_image.save(output_path, format="PNG")

    print(f"\n拼接完成：{os.path.abspath(output_path)}")


if __name__ == "__main__":
    args = sys.argv[1:]

    if not args:
        print("请把图片拖到命令行中，例如：")
        print("python concat.py pic1.png pic2.png pic3.png")
    else:
        concat_images_vertically(args, "long_image.png")
