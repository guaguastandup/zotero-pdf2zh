## server.py v4.0.0
# guaguastandup
# zotero-pdf2zh
import platform
import json
import subprocess
import os
import shutil
import sys
import traceback
import importlib.metadata
from collections import defaultdict
# e.g. "pdf2zh": { "conda": { "packages": [...], "python_version": "3.12" } }

# TODO: 如果用户的conda/uv环境路径是自定义的, 需要支持自定义路径
# 目前默认为当用户在命令行中执行uv / conda时, 是可以正常使用的, 而不是执行/usr/local/bin/uv等等才可以使用

def normalize_pkg_name(name: str) -> str:
    return name.lower().replace('_', '-').replace('.', '-').split("=")[0] # .split("=")[0] 去掉==分隔的版本号等

def check_packages_python_snippet(requirements_list):
    from packaging import requirements
    result = {'satisfied': [], 'missing': []}
    for package_requirement in requirements_list:
        try:
            req_obj = requirements.Requirement(package_requirement)
            package_name = req_obj.name
            installed_version = importlib.metadata.version(package_name)
            if req_obj.specifier.contains(installed_version):
                result['satisfied'].append(package_requirement)
            else:
                sys.stderr.write(f"[X] Package version mismatch. Required: '{package_requirement}', installed: '{installed_version}'\n")
                result['missing'].append(package_requirement)
        except importlib.metadata.PackageNotFoundError:
            sys.stderr.write(f"[X] Package not found: '{package_name}'\n")
            result['missing'].append(package_requirement)
        except requirements.InvalidRequirement as e:
            sys.stderr.write(f"[X] Invalid requirement format: '{package_requirement}'\n")
            result['missing'].append(package_requirement)
        except Exception as e:
            sys.stderr.write(f"[X] Other Error while checking '{package_requirement}': {e}\n")
            result['missing'].append(package_requirement)
    print(json.dumps(result))

class VirtualEnvManager:
    def __init__(self, config_path, env_name, default_env_tool, enable_mirror=True, skip_install=False, mirror_source=None):
        self.is_windows = platform.system() == "Windows"
        self.config_path = config_path
        self.skip_install = skip_install
        self.mirror_source = mirror_source

        with open(config_path, 'r', encoding='utf-8') as f:
            self.env_configs = json.load(f)

        self.env_name = env_name
        self.curr_envtool = None
        self.curr_envname = None
        self.conda_env_path = defaultdict(lambda: None)
        self.ensured_env = defaultdict(lambda: None)
        self.default_env_tool = default_env_tool
        self.enable_mirror = enable_mirror
    
    """检查虚拟环境中是否安装了指定包"""
    def check_packages(self, engine, envtool, envname):
        cfg = self.env_configs[engine][envtool]
        required_packages = cfg.get('packages', [])
        if not required_packages:
            print(f"⚠️ 无需检查 packages for {engine} in {envtool}")
            return True
        print(f"🔍 检查 {envtool} 环境 {envname} 中的 packages: {required_packages}")
        try:
            python_executable = 'python.exe' if self.is_windows else 'python'
            if envtool == 'uv':
                python_path = os.path.join(envname, 'Scripts' if self.is_windows else 'bin', python_executable)
                # uv 创建的 venv 可能没有 pip，优先用 uv pip 安装 packaging
                try:
                    subprocess.run(
                        ['uv', 'pip', 'install', 'packaging', '--python', python_path],
                        capture_output=True, timeout=60
                    )
                except Exception:
                    # uv pip 也失败，尝试原来的方式
                    subprocess.run(
                        [python_path, '-m', 'pip', 'install', 'packaging'],
                        capture_output=True, timeout=60
                    )
            elif envtool == 'conda':
                python_path = os.path.join(self.conda_env_path[self.curr_envname], '' if self.is_windows else 'bin', python_executable)
                subprocess.run(
                    [python_path, '-m', 'pip', 'install', 'packaging'],
                    capture_output=True, timeout=60
                )
            command_run = [python_path, "-c",
                "from utils.venv import check_packages_python_snippet; "
                "import json; "
                f"check_packages_python_snippet({json.dumps(required_packages)})" ]
            result = subprocess.run( # 检查 packages 是否都已安装对应版本
                command_run, capture_output=True, text=True, timeout=100
            )
            if result.returncode != 0:
                print(f"❌ 检查 packages 失败: pip list 返回非零退出码")
                return False
            result_out, result_err = result.stdout.strip(), result.stderr.strip()
            result_json = json.loads(result_out)
            installed_packages, missing_packages = result_json["satisfied"], result_json["missing"]
            # installed_packages = {normalize_pkg_name(pkg['name']) for pkg in json.loads(result.stdout)}
            # missing_packages = [pkg for pkg in required_packages if normalize_pkg_name(pkg) not in installed_packages]
            if missing_packages:
                print(f"❌ 缺少 packages: {missing_packages}")
                return False
            print(f"✅ 所有 packages 已安装: {required_packages}")
            return True
        
        except subprocess.TimeoutExpired:
            print(f"⏰ 检查 packages 超时 in {envname}")
        except subprocess.CalledProcessError as e:
            print(f"❌ 检查 packages 失败 in {envname}: {e}")
        except Exception as e:
            print(f"❌ 检查 packages 出错 in {envname}: {e}")
        return False
    
    def install_packages(self, engine, envtool, envname):
        if self.skip_install:
            print(f"⚠️ 跳过在 {envtool} 环境 {envname} 中安装 packages")
            return True
        cfg = self.env_configs[engine][envtool]
        packages = cfg.get('packages', [])
        if not packages:
            print(f"⚠️ 无需安装 packages for {engine} in {envtool}")
            return True
        print(f"🔧 开始(重新)安装 packages: {packages} in {envtool} 环境 {envname}")

        try:
            env = os.environ.copy()
            env['UV_HTTP_TIMEOUT'] = '1200' if envtool == 'uv' else None
            if envtool == 'uv':
                python_executable = 'python.exe' if self.is_windows else 'python'
                python_path = os.path.join(envname, 'Scripts' if self.is_windows else 'bin', python_executable)
                if self.enable_mirror:
                    print("🌍 使用中科大镜像源安装 packages, 如果失败请在命令行参数中添加--enable_mirror=False")
                    subprocess.run(
                    ['uv', 'pip', 'install', '--index-url', self.mirror_source, *packages, '--python', python_path],
                    check=True, timeout=1200, env=env
                )
                else:
                    print("🌍 使用默认 PyPI 源安装 packages, 如果失败请在命令行参数中添加--enable_mirror=True")
                    subprocess.run(
                        ['uv', 'pip', 'install', *packages, '--python', python_path],
                        check=True, timeout=1200, env=env
                    )
            elif envtool == 'conda':
                python_executable = 'python.exe' if self.is_windows else 'python'
                python_path = os.path.join(self.conda_env_path[self.curr_envname], '' if self.is_windows else 'bin', python_executable)
                if self.enable_mirror:
                    print("🌍 使用中科大镜像源安装 packages, 如果失败请在命令行参数中添加--enable_mirror=False")
                    subprocess.run(
                        # ['conda', 'run', '-n', envname, 'pip', 'install', '--index-url', 'https://pypi.tuna.tsinghua.edu.cn/simple', *packages],
                        [python_path, '-m', 'pip', 'install', '--index-url', self.mirror_source, *packages],
                        check=True, timeout=1200
                    )
                else:
                    print("🌍 使用默认 PyPI 源安装 packages, 如果失败请在命令行参数中添加--enable_mirror=True")
                    subprocess.run(
                        # ['conda', 'run', '-n', envname, 'pip', 'install', *packages],
                        [python_path, '-m', 'pip', 'install', *packages],
                        check=True, timeout=1200
                    )
            print(f"✅ packages 安装成功: {packages}")
            return True
        except subprocess.TimeoutExpired:
            print(f"⏰ 安装 packages 超时 in {envname}")
        except subprocess.CalledProcessError as e:
            print(f"❌ 安装 packages 失败 in {envname}: {e}")
        except Exception as e:
            print(f"❌ 安装 packages 出错 in {envname}: {e}")
        return False
    
    """环境初始化（仅创建环境，不安装包）"""
    def create_env(self, engine, envtool):
        envname = self.env_name[engine]
        cfg = self.env_configs[engine][envtool]
        python_version = cfg.get('python_version', '3.12')
        print(f"🔧 开始创建 {envtool} 虚拟环境: {envname} (Python {python_version}) ...")
        try:
            if envtool == 'uv':
                env = os.environ.copy()
                env['UV_HTTP_TIMEOUT'] = '1200' 
                subprocess.run(
                    ['uv', 'venv', envname, '--python', python_version],
                    check=True, timeout=1200 # 1200秒，20分钟超时
                )
            elif envtool == 'conda':
                subprocess.run(['conda', 'create', '-n', envname, f'python={python_version}', '-y'], check=True, timeout=1200)
            return True
        except subprocess.TimeoutExpired:
            print(f"⏰ 创建 {envname} 环境超时")
        except subprocess.CalledProcessError as e:
            print(f"❌ 创建 {envname} 环境失败: {e}")
        except Exception as e:
            print(f"❌ 创建 {envname} 环境出错: {e}")
        return False
    
    def check_envtool(self, envtool): # 检查 uv / conda 是否存在
        try:
            result = subprocess.run([envtool, '--version'], capture_output=True, text=True, timeout=1200)
            return result.returncode == 0
        except Exception as e:
            print(f"❌ 检查 {envtool} 失败: {e}")
            return False
        
    def check_env(self, engine, envtool): # 检查 env 环境是否在uv / conda中存在
        envname = self.env_name.get(engine)

        if envtool == 'uv':
            try:
                uv_env_path = os.path.join('.', envname)
                pyvenv_path = os.path.join(uv_env_path, 'pyvenv.cfg')

                print("🔍 检查 uv 环境: ", uv_env_path)
                # TOCHECK: 对于windows, macOS, linux, 检查路径的区别
                return (os.path.exists(uv_env_path) and os.path.exists(pyvenv_path))
            except Exception as e:
                traceback.print_exc()
                print(f"❌ 检查 {envtool} 虚拟环境 {envname} 失败: {e}")
                return False
        elif envtool == 'conda':
            try:
                result = subprocess.run(['conda', 'env', 'list'], capture_output=True, text=True, timeout=1200)
                if result.returncode == 0:
                    envs = [line.split()[0] for line in result.stdout.splitlines() if line and not line.startswith("#")]
                    print("🔍 检查 conda 环境列表: ", envs)
                    return envname in envs
            except Exception as e:
                print(f"❌ 检查 {envtool} 虚拟环境 {envname} 失败: {e}")
                return False
        return False
        
    def ensure_env(self, engine):
        if self.ensured_env[engine]: # 非None，已获取过，直接返回
            self.curr_envtool, self.curr_envname = self.ensured_env[engine]
            print(f"✅ 使用 {self.curr_envtool} 环境: {self.curr_envname}")
            return True
        # 否则为 None, 需要检查工具和虚拟环境
        envtools = ['conda', 'uv'] if self.default_env_tool == 'conda' else ['uv', 'conda']

        for envtool in envtools:
            if self.check_envtool(envtool):
                envname = self.env_name[engine]
                env_exists = self.check_env(engine, envtool)
                self.curr_envtool = envtool
                self.curr_envname = envname
                if envtool == 'conda':
                    self._get_conda_env_path(envname) # 获取和存储envname对应的路径
                if not env_exists:
                    # 环境不存在：创建环境，然后安装包
                    if not self.create_env(engine, envtool):
                        print(f"❌ 创建 {envtool} 环境 {envname} 失败，继续下一个工具")
                        continue
                    if not self.install_packages(engine, envtool, envname):
                        print(f"⚠️ packages 安装失败，但将继续使用 {envtool} 环境 {envname}")
                else:
                    # 环境存在：检查包是否完整，缺失则安装
                    if not self.check_packages(engine, envtool, envname):
                        print(f"⚠️ 检测到缺少 packages，尝试重新安装")
                        if not self.install_packages(engine, envtool, envname):
                            print(f"⚠️ packages 安装失败，但将继续使用 {envtool} 环境 {envname}")

                self.ensured_env[engine] = (self.curr_envtool, self.curr_envname) # 已检查过环境，缓存，避免反复检查耗时
                print(f"✅ 使用 {envtool} 环境: {self.curr_envname}")
                return True
            else:
                print(f"❌ {envtool} 工具不可用")
        print(f"❌ 无法找到可用的虚拟环境")
        if self.is_windows:
            print("💡 [Windows 提示] uv 和 conda 都不可用或创建失败。建议使用 win.exe 模式：python server.py --enable_winexe=True --winexe_path='xxxxxxx' ")
        return False

    # Add this method inside the VirtualEnvManager class
    def _get_conda_env_path(self, env_name):
        if self.conda_env_path[env_name]: # 非None，已获取过，直接返回
            return self.conda_env_path[env_name]
        # 否则为 None, 需要获取
        try:
            result = subprocess.run(
                ['conda', 'info', '--json'],
                capture_output=True, text=True, check=True, timeout=1200, encoding='utf-8'
            )
            conda_info = json.loads(result.stdout)
            # Conda lists full paths to all environments in 'envs'
            for env_path in conda_info.get('envs', []):
                if os.path.basename(env_path) == env_name:
                    print(f"✅ Found conda env path: {env_path}")
                    self.conda_env_path[env_name] = env_path
                    return env_path
            # As a fallback, check all known environment directories
            for envs_dir in conda_info.get('envs_dirs', []):
                potential_path = os.path.join(envs_dir, env_name)
                if os.path.isdir(potential_path):
                    print(f"✅ Found conda env path in envs_dirs: {potential_path}")
                    self.conda_env_path[env_name] = env_path
                    return potential_path
            print(f"⚠️无法在 'conda info' 的输出中找到环境 '{env_name}' 的路径。")
            return None
        except (subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError) as e:
            print(f"❌ 获取 conda 环境路径时出错: {e}")
            return None

    def get_conda_bin_dir(self):
        try:
            try: # 优先通过 conda info 获取根目录
                conda_info = subprocess.check_output(['conda', 'info', '--json'], shell=True).decode()
                conda_info = json.loads(conda_info)
                conda_base = conda_info.get('conda_prefix', '')
                print(f"Conda base from conda info: {conda_base}")
            except Exception as e:
                print(f"Failed to get conda info: {e}")
                conda_base_path = shutil.which('conda') # 回退到使用 shutil.which
                if not conda_base_path:
                    raise FileNotFoundError("Conda executable not found in PATH.")
                print(f"Conda executable found at: {conda_base_path}")
                conda_base = os.path.dirname(os.path.dirname(conda_base_path))
                if os.path.basename(os.path.dirname(conda_base_path)).lower() not in ['scripts', 'condabin']:
                    print(f"Warning: Unexpected conda executable location: {conda_base_path}")
            bin_dir = os.path.join(conda_base, 'envs', self.curr_envname, 'Scripts' if self.is_windows else 'bin')
            if not os.path.exists(bin_dir):
                print(f"❌ 虚拟环境目录不存在: {bin_dir}")
                envs_dir = os.path.join(conda_base, 'envs')
                if os.path.exists(envs_dir):
                    print(f"可用虚拟环境: {os.listdir(envs_dir)}")
                return False
            print(f"Virtual environment bin directory: {bin_dir}")
            return bin_dir
        except Exception as e:
            print(f"Error locating Conda environment: {e}")
            return False

    # [新增方法] 仅获取处理后的命令和环境变量，不执行命令
    # 专门给 utils/execute.py 的 execute_with_progress() 使用
    # 将"准备虚拟环境命令"与"执行命令"分离，使 execute_with_progress 能捕获输出并解析进度
    def get_command_and_env(self, command):
        engine = 'pdf2zh_next' if 'pdf2zh_next' in ' '.join(command).lower() else 'pdf2zh'

        # 1. 确保虚拟环境存在
        env_result = self.ensure_env(engine)

        if not env_result:
            return command, os.environ.copy()

        # 2. 计算路径（逻辑与 execute_in_env 保持一致）
        try:
            if self.curr_envtool == 'uv':
                bin_dir = os.path.join(self.curr_envname, 'Scripts' if self.is_windows else 'bin')
                python_path = os.path.join(bin_dir, 'python.exe' if self.is_windows else 'python')
            elif self.curr_envtool == 'conda':
                env_full_path = self._get_conda_env_path(self.curr_envname)
                if not env_full_path:
                    # 找不到 conda 路径，回退到原始命令
                    return command, os.environ.copy()
                bin_dir = os.path.join(env_full_path, 'Scripts' if self.is_windows else 'bin')
                python_executable = 'python.exe' if self.is_windows else os.path.join('bin', 'python')
                python_path = os.path.join(env_full_path, python_executable)
            else:
                return command, os.environ.copy()

            # 3. 构造命令（与 execute_in_env 中的逻辑一致）
            cmd = []
            if command[0].lower() in ['pdf2zh', 'pdf2zh_next']:
                executable_name = command[0] + ('.exe' if self.is_windows else '')
                executable_path = os.path.join(bin_dir, executable_name)

                if os.path.exists(executable_path):
                    cmd = [executable_path] + command[1:]
                else:
                    cmd = [python_path, '-u', '-m', command[0]] + command[1:]
            else:
                cmd = [python_path, '-u'] + command

            # 4. 构造环境变量
            env = os.environ.copy()
            env['PYTHONUNBUFFERED'] = '1'
            env['PATH'] = bin_dir + os.pathsep + env.get('PATH', '')

            return cmd, env

        except Exception as e:
            print(f"⚠️ 获取虚拟环境命令失败: {e}")
            traceback.print_exc()
            return command, os.environ.copy()

    # 在虚拟环境中执行
    def execute_in_env(self, command):
        engine = 'pdf2zh_next' if 'pdf2zh_next' in ' '.join(command).lower() else 'pdf2zh'

        def _run(cmd, **popen_kwargs):
            popen_kwargs.setdefault('stdout', None)
            process = subprocess.Popen(
                cmd,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                **popen_kwargs,
            )
            stderr_lines = []
            if process.stderr:
                for line in process.stderr:
                    stderr_lines.append(line)
                    sys.stderr.write(line)
                    sys.stderr.flush()
                process.stderr.close()
            return_code = process.wait()
            aggregated = ''.join(stderr_lines)
            if return_code != 0:
                raise subprocess.CalledProcessError(
                    returncode=return_code,
                    cmd=cmd,
                    output=None,
                    stderr=aggregated,
                )
            return aggregated

        if not self.ensure_env(engine):
            print(f"❌ 无法找到或创建 {engine} 的虚拟环境，尝试直接执行命令...")
            try:
                aggregated = _run(command)
                print(f"✅ 命令执行成功: {' '.join(command)}")
                return aggregated
            except subprocess.CalledProcessError:
                raise
            except Exception as e:
                print(f"\n❌ 执行命令出错: {e}")
                traceback.print_exc()
                raise

        try:
            if self.curr_envtool == 'uv':
                bin_dir = os.path.join(self.curr_envname, 'Scripts' if self.is_windows else 'bin')
                python_path = os.path.join(bin_dir, 'python.exe' if self.is_windows else 'python')
            elif self.curr_envtool == 'conda':
                env_full_path = self._get_conda_env_path(self.curr_envname)
                if not env_full_path:
                    raise FileNotFoundError(f"无法自动定位 Conda 环境 '{self.curr_envname}' 的路径。")
                bin_dir = os.path.join(env_full_path, 'Scripts' if self.is_windows else 'bin')
                python_executable = 'python.exe' if self.is_windows else os.path.join('bin', 'python')
                python_path = os.path.join(env_full_path, python_executable)
                if not os.path.exists(bin_dir):
                    print(f"❌ 虚拟环境目录不存在: {bin_dir}")
                    raise FileNotFoundError(f"虚拟环境目录不存在: {bin_dir}")
            else:
                raise ValueError(f"⚠️ 未知的环境工具: {self.curr_envtool}")

            # --- 命令组装 (保留优点：优先可执行文件，并用-u强制无缓冲) ---

            # 直接执行
            if command[0].lower() in ['pdf2zh', 'pdf2zh_next']:
                # 2. 检查可执行文件时，也考虑 .exe 后缀
                executable_name = command[0] + ('.exe' if self.is_windows else '')
                executable_path = os.path.join(bin_dir, executable_name)
                
                if os.path.exists(executable_path):
                    cmd = [executable_path] + command[1:]
                    print(f"🔍 已找到可执行文件: {executable_path}")
                else:
                    # 使用预先构建好的、路径正确的 python_path
                    cmd = [python_path, '-u', '-m', command[0]] + command[1:]
                    print(f"⚠️ 可执行文件不存在，使用 python -m -u 方式: {' '.join(cmd)}")
            else:
                # 运行其他python命令时，同样使用正确的 python_path
                cmd = [python_path, '-u'] + command

            # 虚拟环境执行
            print(f"🚀 在虚拟环境中执行命令: {' '.join(cmd)}\n")
            # --- 环境变量设置 (保留优点) ---
            env = os.environ.copy()
            env['PYTHONUNBUFFERED'] = '1'  # 再次确保无缓冲
            env['PATH'] = bin_dir + os.pathsep + env.get('PATH', '')

            aggregated = _run(cmd, env=env)
            print()
            print(f"✅ 命令执行成功: {' '.join(cmd)}")
            return aggregated

        except subprocess.CalledProcessError:
            raise
        except FileNotFoundError as e:
            print(f"❌ 环境的可执行文件未找到: {e}")
            print(f"请检查虚拟环境是否正确安装: {self.curr_envname}")
            raise
        except Exception as e:
            print(f"❌ 执行命令出错: {e}")
            traceback.print_exc()
            raise