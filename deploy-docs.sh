#!/bin/bash
# 将主项目 docs/ 源文件同步到 zotero-pdf2zh.github.io:source。
# github.io 仓库自己的 GitHub Actions 会负责构建并部署到 main。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCS_SRC="$SCRIPT_DIR/docs"
DOCS_REPO="${DOCS_REPO:-$(cd "$SCRIPT_DIR/.." && pwd)/zotero-pdf2zh.github.io}"

if [ ! -d "$DOCS_REPO/.git" ]; then
  echo "❌ 未找到文档仓库: $DOCS_REPO"
  echo "请先 clone https://github.com/zotero-pdf2zh/zotero-pdf2zh.github.io"
  echo "或通过 DOCS_REPO=/path/to/zotero-pdf2zh.github.io ./deploy-docs.sh 指定路径。"
  exit 1
fi

echo "📚 主项目文档源: $DOCS_SRC"
echo "🌐 文档部署仓库: $DOCS_REPO"

cd "$DOCS_REPO"
git fetch origin source
git switch source
git pull --ff-only origin source

echo "🔄 同步 docs/ → github.io:source ..."
rsync -av --delete \
  --exclude='.git/' \
  --exclude='.github/' \
  --exclude='node_modules/' \
  --exclude='.vitepress/dist/' \
  --exclude='.vitepress/cache/' \
  --exclude='.DS_Store' \
  "$DOCS_SRC/" "$DOCS_REPO/"

# source 分支自己的部署 workflow 不属于主项目 docs/，必须保留。
if [ ! -f "$DOCS_REPO/.github/workflows/deploy.yml" ]; then
  echo "❌ .github/workflows/deploy.yml 不存在，停止提交，避免破坏 Pages 部署流程。"
  exit 1
fi

git add -A
if git diff --staged --quiet; then
  echo "✅ 文档已经是最新版本，无需提交。"
  exit 0
fi

git commit -m "docs: sync v4.1.0 documentation"
git push origin source

echo "✅ 已推送 source 分支。"
echo "GitHub Actions 将自动构建并部署到 main。"
echo "网站: https://zotero-pdf2zh.github.io/"
echo "Actions: https://github.com/zotero-pdf2zh/zotero-pdf2zh.github.io/actions"
