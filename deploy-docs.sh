#!/bin/bash
# 部署文档到 zotero-pdf2zh.github.io

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "📦 构建文档..."
cd "$SCRIPT_DIR/docs"
npm run docs:build

echo "📤 部署到 GitHub Pages..."
cd "../zotero-pdf2zh.github.io"
find . -maxdepth 1 ! -name '.git' ! -name '.nojekyll' ! -name '.' -exec rm -rf {} +
cp -r ../zotero-pdf2zh/docs/.vitepress/dist/* .

git add .
git commit -m "Update docs @ $(date +'%Y-%m-%d %H:%M:%S')" || echo "没有新的更改"
git push origin main

echo "✅ 部署完成！访问 https://zotero-pdf2zh.github.io/"
