## server.py v3.0.36
# guaguastandup
# zotero-pdf2zh
import sys
import argparse

import runtime
from runtime import (
    __version__,
    update_log,
    PORT,
    LEGACY_WINEXE_DEFAULT_PATH,
    enable_venv,
    default_env_tool,
    str2bool,
    normalize_runtime_args,
    validate_runtime_args,
    runtime_mode_label,
    prepare_path,
)
from utils.translator import PDFTranslator
from utils.auto_updater import check_for_updates, perform_update_optimized


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--port", type=int, default=PORT, help="Port to run the server on"
    )
    parser.add_argument(
        "--packaged_mode",
        type=str2bool,
        default=False,
        help="打包发布模式（full安装包），禁用venv安装逻辑并强制使用内置引擎。",
    )
    parser.add_argument(
        "--engine_root",
        type=str,
        default="",
        help="打包模式下的引擎目录（默认: <server_root>/engine）",
    )
    parser.add_argument(
        "--data_root",
        type=str,
        default="",
        help="运行时可写目录（配置/输出/日志）。打包模式默认 ProgramData。",
    )

    parser.add_argument(
        "--enable_venv", type=str2bool, default=enable_venv, help="脚本自动开启虚拟环境"
    )
    parser.add_argument(
        "--env_tool",
        type=str,
        default=default_env_tool,
        help="虚拟环境管理工具, 默认使用 uv",
    )
    parser.add_argument(
        "--check_update", type=str2bool, default=True, help="启动时检查更新"
    )
    parser.add_argument(
        "--update_source",
        type=str,
        default="gitee",
        help="更新源设置为gitee或github, 默认为gitee",
    )
    parser.add_argument(
        "--debug", type=str2bool, default=False, help="Enable debug mode"
    )
    parser.add_argument(
        "--enable_winexe",
        type=str2bool,
        default=False,
        help="使用pdf2zh_next Windows可执行文件运行脚本, 仅限Windows系统",
    )
    parser.add_argument(
        "--enable_mirror",
        type=str2bool,
        default=True,
        help="启用下载镜像加速, 仅限中国大陆用户",
    )
    parser.add_argument(
        "--mirror_source",
        type=str,
        default="https://mirrors.ustc.edu.cn/pypi/simple",
        help="自定义您的PyPI镜像源, 仅限中国大陆用户",
    )
    parser.add_argument(
        "--winexe_path",
        type=str,
        default=LEGACY_WINEXE_DEFAULT_PATH,
        help="Windows可执行文件的路径",
    )
    parser.add_argument(
        "--winexe_attach_console",
        type=str2bool,
        default=True,
        help="Winexe模式是否尝试附着父控制台显示实时日志 (默认True)",
    )
    parser.add_argument(
        "--skip_install", type=str2bool, default=False, help="跳过虚拟环境中的安装"
    )
    args = parser.parse_args()
    args = normalize_runtime_args(args)
    try:
        validate_runtime_args(args)
    except Exception as e:
        print(f"❌ 启动参数校验失败: {e}")
        sys.exit(1)

    print(f"🚀 启动参数: {args}\n")
    print(
        "💡 如果您来自网络上的视频教程/文字教程, 并且在执行中遇到问题, 请优先阅读【本项目主页】, 以获得最准确的安装信息: \ngithub: https://github.com/guaguastandup/zotero-pdf2zh\ngitee: https://gitee.com/guaguastandup/zotero-pdf2zh"
    )
    print("💡 另外, 常见问题文档: https://docs.qq.com/markdown/DU0RPQU1vaEV6UXJC")
    print(
        "💡 如遇到无法解决的问题请加入QQ群: 443031486, 口令为: github, 提问前您需要先阅读本项目指南和常见问题文档, 提问时必须将本终端完整的信息复制到txt文件中并截图zotero插件设置, 一并发送到群里, 感谢配合!\n"
    )
    print("==== 🌍翻译期间请勿关闭此窗口🌍 =====\n")

    print("🏠 当前版本: ", __version__, "更新日志: ", update_log)
    if args.check_update:
        update_info = check_for_updates(
            local_version=__version__, update_source=args.update_source
        )
        if update_info:
            local_v, remote_v = update_info
            print(f"🎉 发现新版本！当前版本: {local_v}, 最新版本: {remote_v}")
            try:
                answer = input("是否要立即更新? (y/n): ").lower()
            except (EOFError, KeyboardInterrupt):
                answer = "n"
                print("\n无法获取用户输入，已自动取消更新。")

            if answer in ["y", "yes"]:
                perform_update_optimized(
                    root_path=runtime.root_path,
                    local_version=__version__,
                    expected_version=remote_v,
                    update_source=args.update_source,
                )
            else:
                print("👌 已取消更新。")

    print("🏠 当前路径: ", runtime.root_path)
    print("🏠 运行目录: ", runtime.runtime_data_root)
    print("🏠 运行模式: ", runtime_mode_label(args))
    print("🏠 当前版本: ", __version__)
    prepare_path()
    translator = PDFTranslator(args)
    translator.run(args.port, debug=args.debug)
