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

# macOS Finder 会在任意目录生成 .DS_Store。旧 source 分支还曾经追踪过
# 根目录 .DS_Store。先恢复所有“已被 Git 跟踪但被 Finder 修改/删除”的
# .DS_Store，避免把脚本自己的清理动作误判成用户工作区修改。
while IFS= read -r -d '' tracked_path; do
  if [ "$(basename "$tracked_path")" = ".DS_Store" ]; then
    if ! git diff --quiet -- "$tracked_path"; then
      echo "🧹 恢复 Git 已跟踪的 Finder 元数据: $tracked_path"
      git restore -- "$tracked_path"
    fi
  fi
done < <(git ls-files -z)

# 再删除未跟踪的 .DS_Store。这里只删除 Finder 元数据，不会自动丢弃
# 任何其他未跟踪文件或用户修改。
UNTRACKED_DS_COUNT=0
while IFS= read -r -d '' untracked_path; do
  if [ "$(basename "$untracked_path")" = ".DS_Store" ]; then
    rm -f -- "$untracked_path"
    UNTRACKED_DS_COUNT=$((UNTRACKED_DS_COUNT + 1))
  fi
done < <(git ls-files --others --exclude-standard -z)
if [ "$UNTRACKED_DS_COUNT" -gt 0 ]; then
  echo "🧹 清理了 $UNTRACKED_DS_COUNT 个未跟踪的 .DS_Store。"
fi

# 除 Finder 元数据外，任何本地修改都必须由用户自己处理。
if [ -n "$(git status --porcelain)" ]; then
  echo "❌ 文档仓库存在未提交的本地修改，已停止同步："
  git status --short
  echo "请先提交、stash 或手工处理这些修改后重试。"
  exit 1
fi

git pull --ff-only origin source

# pull 完成后，正式停止追踪仓库中所有历史 .DS_Store，并写入
# .gitignore。这里的删除会和本次文档同步一起提交，因此下一次运行
# 不会再被 macOS Finder 元数据阻塞。
while IFS= read -r -d '' tracked_path; do
  if [ "$(basename "$tracked_path")" = ".DS_Store" ]; then
    git rm -f -- "$tracked_path" >/dev/null
  fi
done < <(git ls-files -z)

touch .gitignore
if ! grep -qxF '.DS_Store' .gitignore; then
  printf '\n.DS_Store\n' >> .gitignore
fi

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
