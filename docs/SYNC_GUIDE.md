# 文档同步指南

## 仓库结构

- **源仓库**: `zotero-pdf2zh/docs` - 文档源文件
- **部署仓库**: `zotero-pdf2zh.github.io` - GitHub Pages 托管
  - `source` 分支: 存放源文件
  - `main` 分支: 存放构建后的静态文件

## 同步步骤

### 方法一：手动执行命令

```bash
# 1. 同步源文件到 github.io 仓库
rsync -av --delete \
  --exclude='.git' \
  --exclude='node_modules' \
  --exclude='.vitepress/dist' \
  --exclude='.vitepress/cache' \
  --exclude='.DS_Store' \
  /Users/zhangxinyue/personal/code/-new-code-space-/Zotero/zo-dev/zotero-pdf2zh/docs/ \
  /Users/zhangxinyue/personal/code/-new-code-space-/Zotero/zo-dev/zotero-pdf2zh.github.io/

# 2. 恢复 GitHub Actions 配置（rsync 会删除）
mkdir -p /Users/zhangxinyue/personal/code/-new-code-space-/Zotero/zo-dev/zotero-pdf2zh.github.io/.github/workflows

# 3. 提交并推送
cd /Users/zhangxinyue/personal/code/-new-code-space-/Zotero/zo-dev/zotero-pdf2zh.github.io
git add .
git commit -m "Update docs"
git push origin source
```

### 方法二：创建同步脚本

在 `zotero-pdf2zh` 根目录创建 `sync-docs.sh`：

```bash
#!/bin/bash
set -e

DOCS_SRC="/Users/zhangxinyue/personal/code/-new-code-space-/Zotero/zo-dev/zotero-pdf2zh/docs"
DOCS_DEST="/Users/zhangxinyue/personal/code/-new-code-space-/Zotero/zo-dev/zotero-pdf2zh.github.io"
WORKFLOW_FILE=".github/workflows/deploy.yml"

echo "Syncing docs..."
rsync -av --delete \
  --exclude='.git' \
  --exclude='node_modules' \
  --exclude='.vitepress/dist' \
  --exclude='.vitepress/cache' \
  --exclude='.DS_Store' \
  "$DOCS_SRC/" "$DOCS_DEST/"

echo "Restoring workflow file..."
mkdir -p "$DOCS_DEST/.github/workflows"
cat > "$DOCS_DEST/$WORKFLOW_FILE" << 'EOF'
name: Build and Deploy Docs

on:
  push:
    branches:
      - source
  workflow_dispatch:

permissions:
  contents: write

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout source branch
        uses: actions/checkout@v4
        with:
          ref: source

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Install pnpm
        run: npm install -g pnpm

      - name: Build docs
        run: |
          pnpm install
          pnpm docs:build

      - name: Deploy to main branch
        uses: actions/checkout@v4
        with:
          ref: main
          path: main-branch

      - name: Copy built files to main branch
        run: |
          cd main-branch
          find . -maxdepth 1 ! -name '.git' ! -name '.nojekyll' ! -name '.' -exec rm -rf {} +
          cp -r ${{ github.workspace }}/.vitepress/dist/* .
          touch .nojekyll

      - name: Commit and push to main
        run: |
          cd main-branch
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git config user.name "github-actions[bot]"
          git add .
          git diff --staged --quiet || git commit -m "Deploy from source @ ${{ github.sha }}"
          git push origin main
EOF

echo "Committing and pushing..."
cd "$DOCS_DEST"
git add .
git commit -m "Update docs" || echo "No changes to commit"
git push origin source

echo "Done! Check https://github.com/zotero-pdf2zh/zotero-pdf2zh.github.io/actions for build status."
```

然后执行：
```bash
chmod +x sync-docs.sh
./sync-docs.sh
```

## 查看部署状态

- Actions: https://github.com/zotero-pdf2zh/zotero-pdf2zh.github.io/actions
- 网站: https://zotero-pdf2zh.github.io/

## 本地预览

```bash
cd /Users/zhangxinyue/personal/code/-new-code-space-/Zotero/zo-dev/zotero-pdf2zh/docs
pnpm install
pnpm docs:dev
```
