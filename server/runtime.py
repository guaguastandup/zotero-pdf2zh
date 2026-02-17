## runtime.py v3.0.36
# guaguastandup
# zotero-pdf2zh
#
# Runtime configuration, path management, and argument normalization.
# Extracted from server.py to reduce single-file complexity.

import os
import sys
import json
import shutil
import traceback
import argparse
import toml

# ---- Version info ----
__version__ = "3.0.36"
update_log = "近期版本新增了自定义镜像源选项, 新增了自定义更新源选项, 您可以通过--update_source参数指定更新源, 目前支持github和gitee. 修复了预热模式脚本. 修复了包检查环节. 开始支持Zotero 8. 修复了gitee源的问题."

# ---- Engine / venv constants ----
pdf2zh = "pdf2zh"
pdf2zh_next = "pdf2zh_next"
venv = "venv"

venv_name = {
    pdf2zh: "zotero-pdf2zh-venv",
    pdf2zh_next: "zotero-pdf2zh-next-venv",
}

default_env_tool = "uv"
enable_venv = True

PORT = 8890
LEGACY_WINEXE_DEFAULT_PATH = "./pdf2zh-v2.6.3-BabelDOC-v0.5.7-win64/pdf2zh/pdf2zh.exe"
PACKAGED_DATA_DIRNAME = "PDF2ZH Server"


def resolve_app_root():
    # PyInstaller/Nuitka 等冻结环境下，优先以可执行文件所在目录作为安装根目录。
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


# 所有系统: 获取当前脚本所在的路径
root_path = resolve_app_root()
runtime_data_root = root_path
config_folder = os.path.join(runtime_data_root, "config")
output_folder = os.path.join(runtime_data_root, "translated")
config_path = {
    pdf2zh: os.path.join(config_folder, "config.json"),
    pdf2zh_next: os.path.join(config_folder, "config.toml"),
    venv: os.path.join(config_folder, "venv.json"),
}


def configure_runtime_paths(data_root=None):
    """根据运行模式设置可写目录和配置文件路径。"""
    global runtime_data_root, config_folder, output_folder, config_path
    runtime_data_root = os.path.abspath(data_root or root_path)
    config_folder = os.path.join(runtime_data_root, "config")
    output_folder = os.path.join(runtime_data_root, "translated")
    config_path = {
        pdf2zh: os.path.join(config_folder, "config.json"),
        pdf2zh_next: os.path.join(config_folder, "config.toml"),
        venv: os.path.join(config_folder, "venv.json"),
    }


def resolve_default_config_folder():
    # 打包后的 onedir 结构中，模板配置通常位于 _internal/config。
    candidates = [
        os.path.join(root_path, "config"),
        os.path.join(root_path, "_internal", "config"),
    ]
    for candidate in candidates:
        if os.path.isdir(candidate):
            return candidate
    return candidates[0]


def normalize_runtime_args(parsed_args):
    """在启动阶段统一参数语义，确保打包模式不会触发环境安装逻辑。"""
    if not parsed_args.packaged_mode:
        if parsed_args.data_root:
            configure_runtime_paths(parsed_args.data_root)
        else:
            configure_runtime_paths(root_path)
        return parsed_args

    if not parsed_args.data_root:
        if os.name == "nt":
            program_data = os.environ.get("PROGRAMDATA", "C:\\ProgramData")
            parsed_args.data_root = os.path.join(program_data, PACKAGED_DATA_DIRNAME)
        else:
            parsed_args.data_root = os.path.join(root_path, PACKAGED_DATA_DIRNAME)

    if not parsed_args.engine_root:
        parsed_args.engine_root = os.path.join(root_path, "engine")
    parsed_args.engine_root = os.path.abspath(parsed_args.engine_root)
    parsed_args.data_root = os.path.abspath(parsed_args.data_root)

    # 打包模式只允许内置可执行文件模式，禁止自动更新与虚拟环境安装。
    parsed_args.enable_venv = False
    parsed_args.check_update = False
    parsed_args.skip_install = True
    parsed_args.enable_winexe = True
    # 打包托盘模式下不附着控制台，避免翻译时弹出黑框窗口。
    parsed_args.winexe_attach_console = False

    if (
        not parsed_args.winexe_path
        or parsed_args.winexe_path == LEGACY_WINEXE_DEFAULT_PATH
    ):
        parsed_args.winexe_path = os.path.join(parsed_args.engine_root, "pdf2zh.exe")
    elif not os.path.isabs(parsed_args.winexe_path):
        parsed_args.winexe_path = os.path.abspath(
            os.path.join(parsed_args.engine_root, parsed_args.winexe_path)
        )

    configure_runtime_paths(parsed_args.data_root)
    return parsed_args


def runtime_mode_label(parsed_args):
    return "packaged_full" if parsed_args.packaged_mode else "standard"


def validate_runtime_args(parsed_args):
    if parsed_args.packaged_mode and not os.path.exists(parsed_args.winexe_path):
        raise FileNotFoundError(
            f"packaged_mode 启动失败: 未找到内置引擎可执行文件: {parsed_args.winexe_path}"
        )


def prepare_path():
    print("🔍 [配置文件] 检查文件路径中...")
    os.makedirs(runtime_data_root, exist_ok=True)
    os.makedirs(config_folder, exist_ok=True)
    os.makedirs(output_folder, exist_ok=True)
    default_config_folder = resolve_default_config_folder()
    for _, path in config_path.items():
        example_file = os.path.join(
            default_config_folder, os.path.basename(path) + ".example"
        )
        if os.path.exists(example_file):
            if os.path.exists(path):
                print(
                    f"⚠️ [配置文件] 发现旧的配置文件 {path}, 为了确保配置文件格式正确, 将使用 {example_file} 覆盖旧的配置文件."
                )
            else:
                print(
                    f"🔍 [配置文件] 发现缺失的配置文件 {path}, 将使用 {example_file} 作为初始配置文件."
                )
            shutil.copyfile(example_file, path)
        try:
            if path.endswith(".json"):
                with open(path, "r", encoding="utf-8") as f:
                    json.load(f)
            elif path.endswith(".toml"):
                with open(path, "r", encoding="utf-8") as f:
                    toml.load(f)
        except Exception as e:
            traceback.print_exc()
            print(
                f"⚠️ [配置文件] {path} 文件格式错误, 请检查文件格式并尝试删除非.example文件后重试! 错误信息: {e}\n"
            )
    print("✅ [配置文件] 文件路径检查完成\n")


def str2bool(v):
    if isinstance(v, bool):
        return v
    if v.lower() in ("yes", "true", "t", "1", "y"):
        return True
    elif v.lower() in ("no", "false", "f", "0", "n"):
        return False
    else:
        raise argparse.ArgumentTypeError("Boolean value expected.")
