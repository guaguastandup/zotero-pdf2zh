#!/bin/bash

# 设置错误处理：脚本在任何命令失败时退出
set -e

# 日志函数
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# 检查uv是否安装
check_uv() {
    if ! command -v uv &> /dev/null; then
        log "❌ uv未安装。请先安装uv或检查是否已加入全局路径，然后重试。"
        exit 1
    fi
}

# 安装依赖并支持重试机制
install_with_retry() {
    local env_name=$1
    local max_attempts=3
    local attempt=1
    shift 1
    local packages=("$@")

    while [ $attempt -le $max_attempts ]; do
        log "尝试安装依赖项（第${attempt}次）..."
        if uv pip install "${packages[@]}"; then
            log "依赖项安装成功！"
            return 0
        else
            log "安装失败，将在3秒后重试..."
            sleep 3
            ((attempt++))
        fi
    done
    log "❌ 安装失败，已达到最大重试次数 (${max_attempts})。"
    exit 1
}

# 运行babeldoc --warmup
run_babeldoc_warmup() {
    local env_name=$1
    log "运行 babeldoc --warmup..."
    if "${env_name}/bin/babeldoc" --warmup; then
        log "babeldoc --warmup 执行成功！"
    else
        log "❌ babeldoc --warmup 执行失败。"
        exit 1
    fi
}

# 升级pdf2zh_next包
upgrade_pdf2zh_next() {
    local env_name=$1
    local use_mirror=$2
    log "升级 pdf2zh_next 包..."
    local pip_cmd=(uv pip install --upgrade pdf2zh_next)
    if [ "$use_mirror" = true ]; then
        pip_cmd+=(--index-url https://pypi.tuna.tsinghua.edu.cn/simple)
    fi
    if "${pip_cmd[@]}"; then
        log "pdf2zh_next 升级成功！"
    else
        log "❌ pdf2zh_next 升级失败。"
        exit 1
    fi
}

# 创建并激活uv环境
create_uv_env() {
    local env_name=$1
    local python_version=$2
    local use_mirror=$3
    local run_warmup=$4
    local upgrade=$5
    shift 5
    local packages=("$@")

    log "为 ${env_name} 创建uv环境..."
    uv venv "${env_name}" --python="${python_version}"
    log "为 ${env_name} 安装依赖项..."
    source "${env_name}/bin/activate"

    if [ "$use_mirror" = true ]; then
        install_with_retry "${env_name}" "${packages[@]}" --index-url https://pypi.tuna.tsinghua.edu.cn/simple
    else
        install_with_retry "${env_name}" "${packages[@]}"
    fi

    # 运行babeldoc --warmup（如果启用）
    if [ "$run_warmup" = true ] && [[ "${packages[*]}" =~ "babeldoc" ]]; then
        run_babeldoc_warmup "${env_name}"
    fi

    # 升级pdf2zh_next（如果启用且包列表包含pdf2zh_next）
    if [ "$upgrade" = true ] && [[ "${packages[*]}" =~ "pdf2zh_next" ]]; then
        upgrade_pdf2zh_next "${env_name}" "$use_mirror"
    fi

    deactivate
}

# 主逻辑
main() {
    # 默认值
    use_mirror=true
    run_warmup=false
    upgrade=false

    # 调试：打印传入的参数
    log "接收到的命令行参数: $@"

    # 检查命令行参数
    while [ $# -gt 0 ]; do
        case "$1" in
            --no-mirror)
                use_mirror=false
                log "禁用镜像"
                shift
                ;;
            --warmup)
                run_warmup=true
                log "启用 babeldoc --warmup"
                shift
                ;;
            --upgrade)
                upgrade=true
                log "启用 pdf2zh_next 升级"
                shift
                ;;
            *)
                log "❌ 未知参数: $1"
                exit 1
                ;;
        esac
    done

    log "检查uv是否已安装..."
    check_uv
    log "uv已安装。"

    # 创建uv环境
    create_uv_env "zotero-pdf2zh-venv" "3.12" "$use_mirror" "$run_warmup" "$upgrade" "pdf2zh==1.9.11" "pypdf" "PyMuPDF" "flask" "numpy==2.2.0" "toml" "pdfminer.six==20250416" "babeldoc"
    create_uv_env "zotero-pdf2zh-next-venv" "3.12" "$use_mirror" "$run_warmup" "$upgrade" "pdf2zh_next" "pypdf" "PyMuPDF" "flask" "toml" "babeldoc"
}

# 执行主逻辑
main "$@"

log "uv环境创建并安装完成！"