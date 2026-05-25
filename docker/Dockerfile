# syntax=docker/dockerfile:1

# 先声明一次，后面阶段还能复用，避免 ${PY_BASE} 为空
ARG PY_BASE=python:3.12-slim

# 取官方 docker CLI 二进制（只要客户端，不起守护进程）
FROM docker:27-cli AS dockercli

# 在使用它的阶段前再声明一次（多阶段必须这样）
ARG PY_BASE
FROM ${PY_BASE}

# 基础工具
RUN apt-get update && \
  apt-get install -y --no-install-recommends \
  curl unzip ca-certificates dumb-init fonts-noto-cjk && \
  rm -rf /var/lib/apt/lists/*

# 复制 docker 客户端到最终镜像
COPY --from=dockercli /usr/local/bin/docker /usr/local/bin/docker
RUN docker --version

ENV PYTHONDONTWRITEBYTECODE=1 \
  PYTHONUNBUFFERED=1 \
  PORT=8890 \
  TZ=Asia/Shanghai \
  ZOTERO_PDF2ZH_FROM_IMAGE=awwaawwa/pdfmathtranslate-next:latest

# server.zip 下载地址（默认官方 raw；下面给出镜像“注释示例”，需要时自行改）
ARG SERVER_ZIP_URL="https://raw.githubusercontent.com/guaguastandup/zotero-pdf2zh/main/server.zip"
# 可选：GitHub 代理前缀（默认空，不启用）
# 需要时可在 docker-compose 的 build.args 里传入，例如 https://ghproxy.net/
ARG GITHUB_PROXY_PREFIX=""
# 备选镜像（示例，默认不启用）：
#   jsDelivr（推荐公开文件直链）：
#   ARG SERVER_ZIP_URL="https://cdn.jsdelivr.net/gh/guaguastandup/zotero-pdf2zh@main/server.zip"

WORKDIR /app

# 下载并解压 server.zip（默认用官方 raw；如开启代理前缀，前面加 ${GITHUB_PROXY_PREFIX}）
RUN set -eu; \
  echo "Download server from: ${GITHUB_PROXY_PREFIX}${SERVER_ZIP_URL}"; \
  curl -fL --retry 3 --retry-delay 2 \
  "${GITHUB_PROXY_PREFIX}${SERVER_ZIP_URL}" -o /tmp/server.zip && \
  mkdir -p /app/server && \
  unzip -q /tmp/server.zip -d /app && \
  rm -f /tmp/server.zip && \
  # 备份示例配置到不会被挂载遮住的位置
  mkdir -p /opt/pdf2zh-defaults && \
  for f in config.toml.example config.json.example venv.json.example; do \
  if [ -f "/app/server/config/$f" ]; then \
  cp "/app/server/config/$f" "/opt/pdf2zh-defaults/$f"; \
  fi; \
  done

# 安装 Python 依赖（全部在容器内完成；不用 venv）默认官方 PyPI，失败时回退到 USTC
RUN python -m pip install -U pip && \
  (pip install --no-cache-dir -r /app/server/requirements.txt || \
  (echo "Primary PyPI failed, retrying via USTC mirror..." >&2 && \
  pip install --no-cache-dir -i https://mirrors.ustc.edu.cn/pypi/simple \
  -r /app/server/requirements.txt))

# 放置 pdf2zh_next 壳脚本：把调用转给 next 镜像
# 关键：使用 --volumes-from $HOSTNAME 继承当前容器的挂载，从而在“子容器”里也能访问 /app/server/translated 与 /app/server/config
RUN printf '%s\n' \
  '#!/bin/sh' \
  'set -eu' \
  'img="${ZOTERO_PDF2ZH_FROM_IMAGE:-awwaawwa/pdfmathtranslate-next:latest}"' \
  'cid="$(cat /etc/hostname)"' \
  'exec docker run --rm --volumes-from "${cid}" -e TZ -e http_proxy -e https_proxy -e HF_ENDPOINT "$img" pdf2zh_next "$@"' \
  > /usr/local/bin/pdf2zh_next && chmod +x /usr/local/bin/pdf2zh_next

# 生成启动脚本：若挂载目录里缺失配置，则用备份示例生成；随后启动 server.py
RUN printf '%s\n' \
  '#!/bin/sh' \
  'set -eu' \
  'mkdir -p /app/server/translated /app/server/config' \
  '# 首次启动生成 config.toml/config.json/venv.json（如果缺失）' \
  'if [ ! -f /app/server/config/config.toml ] && [ -f /opt/pdf2zh-defaults/config.toml.example ]; then' \
  '  cp /opt/pdf2zh-defaults/config.toml.example /app/server/config/config.toml' \
  'fi' \
  'if [ ! -f /app/server/config/config.json ] && [ -f /opt/pdf2zh-defaults/config.json.example ]; then' \
  '  cp /opt/pdf2zh-defaults/config.json.example /app/server/config/config.json' \
  'fi' \
  'if [ ! -f /app/server/config/venv.json ] && [ -f /opt/pdf2zh-defaults/venv.json.example ]; then' \
  '  cp /opt/pdf2zh-defaults/venv.json.example /app/server/config/venv.json' \
  'fi' \
  '# 启动 server（固定 8890；禁用 venv、禁用自动更新；env_tool 让 server 走系统环境）' \
  'exec python /app/server/server.py --enable_venv=False --check_update=False --port="${PORT:-8890}" --env_tool=system' \
  > /usr/local/bin/entrypoint.sh && chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 8890
ENTRYPOINT ["/usr/bin/dumb-init", "--"]
CMD ["/usr/local/bin/entrypoint.sh"]
