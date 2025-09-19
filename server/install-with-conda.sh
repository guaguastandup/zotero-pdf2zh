#!/bin/bash

# 设置错误处理：脚本在任何命令失败时退出
set -e

# 日志函数
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# 检查Conda是否安装
check_conda() {
    if ! command -v conda &> /dev/null; then
        log "❌ Conda未安装。请先安装Conda（如Miniconda或Anaconda），然后重试。"
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
        if conda run -n "${env_name}" pip install "${packages[@]}"; then
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
    if conda run -n "${env_name}" babeldoc --warmup; then
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
    local pip_cmd=(conda run -n "${env_name}" pip install --upgrade pdf2zh_next)
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

# 创建并激活Conda环境
create_conda_env() {
    local env_name=$1
    local python_version=$2
    local use_mirror=$3
    local run_warmup=$4
    local upgrade=$5
    shift 5
    local packages=("$@")

    log "为 ${env_name} 创建Conda环境..."
    conda create -n "${env_name}" python="${python_version}" -y

    # 配置镜像（如果启用）
    if [ "$use_mirror" = true ]; then
        log "配置清华镜像源..."
        conda run -n "${env_name}" pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
    fi

    log "为 ${env_name} 安装依赖项..."
    install_with_retry "${env_name}" "${packages[@]}"

    # 运行babeldoc --warmup（如果启用）
    if [ "$run_warmup" = true ]; then
        log "检查是否需要运行 babeldoc --warmup（run_warmup=$run_warmup, babeldoc in packages=${packages[*]})"
        if [[ "${packages[*]}" =~ "babeldoc" ]]; then
            run_babeldoc_warmup "${env_name}"
        else
            log "跳过 babeldoc --warmup，因为包列表中不包含 babeldoc"
        fi
    fi

    # 升级pdf2zh_next（如果启用且包列表包含pdf2zh_next）
    if [ "$upgrade" = true ]; then
        log "检查是否需要升级 pdf2zh_next（upgrade=$upgrade, pdf2zh_next in packages=${packages[*]})"
        if [[ "${packages[*]}" =~ "pdf2zh_next" ]]; then
            upgrade_pdf2zh_next "${env_name}" "$use_mirror"
        else
            log "跳过 pdf2zh_next 升级，因为包列表中不包含 pdf2zh_next"
        fi
    fi

    # 清理镜像配置（避免影响其他环境）
    if [ "$use_mirror" = true ]; then
        conda run -n "${env_name}" pip config unset global.index-url
    fi
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

    log "检查Conda是否已安装..."
    check_conda
    log "Conda已安装。"

    # 创建Conda环境
    create_conda_env "zotero-pdf2zh-venv" "3.12" "$use_mirror" "$run_warmup" "$upgrade" "pdf2zh==1.9.11" "pypdf" "PyMuPDF" "flask" "numpy==2.2.0" "toml" "pdfminer.six==20250416" "babeldoc"
    create_conda_env "zotero-pdf2zh-next-venv" "3.12" "$use_mirror" "$run_warmup" "$upgrade" "pdf2zh_next" "pypdf" "PyMuPDF" "flask" "toml" "babeldoc"
}

# 执行主逻辑
main "$@"

log "Conda环境创建并安装完成！"