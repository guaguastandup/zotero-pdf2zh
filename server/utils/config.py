## server.py v4.0.0
# guaguastandup
# zotero-pdf2zh
import json, toml
import os
import re
import subprocess
from pathlib import Path
from utils.config_map import pdf2zh_config_map, pdf2zh_next_config_map

pdf2zh = 'pdf2zh'
pdf2zh_next = 'pdf2zh_next'

def stringToBoolean(value):
    if value == 'true' or value == 'True' or value == True or value == 1:
        return True
    return False


def _version_tuple(value):
    if not value:
        return ()
    return tuple(int(x) for x in re.findall(r'\d+', str(value))[:4])


def _detect_pdf2zh_next_version(config_file):
    """Best-effort lookup of pdf2zh_next in the environment used by this Server.

    This intentionally does not install or update anything. It checks the local
    uv environment first, then a conda environment with the standard project
    name. If no existing environment can be found, return None and allow the
    normal environment bootstrap path to run later.
    """
    server_root = Path(config_file).resolve().parent.parent
    env_name = 'zotero-pdf2zh-next-venv'
    python_candidates = [
        server_root / env_name / 'bin' / 'python',
        server_root / env_name / 'Scripts' / 'python.exe',
    ]

    for python_path in python_candidates:
        if python_path.exists():
            try:
                result = subprocess.run(
                    [
                        str(python_path),
                        '-c',
                        "from importlib.metadata import version; print(version('pdf2zh-next'))",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout.strip()
            except Exception:
                pass

    try:
        result = subprocess.run(
            ['conda', 'info', '--json'],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0:
            conda_info = json.loads(result.stdout)
            for raw_env_path in conda_info.get('envs', []):
                env_path = Path(raw_env_path)
                if env_path.name != env_name:
                    continue
                python_path = (
                    env_path / 'python.exe'
                    if os.name == 'nt'
                    else env_path / 'bin' / 'python'
                )
                if not python_path.exists():
                    continue
                version_result = subprocess.run(
                    [
                        str(python_path),
                        '-c',
                        "from importlib.metadata import version; print(version('pdf2zh-next'))",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                if version_result.returncode == 0 and version_result.stdout.strip():
                    return version_result.stdout.strip()
    except Exception:
        pass

    return None


class Config:
    def __init__(self, request_data):
        self.engine = request_data.get('engine', 'pdf2zh')
        if self.engine not in [pdf2zh, pdf2zh_next]:
            self.engine = pdf2zh

        if self.engine == pdf2zh:
            self.service = request_data.get('service', 'bing')
            if self.service in [None, ''] or len(self.service) < 3:
                self.service = 'bing'
        else:
            if not request_data.get('next_service') or request_data.get('next_service') in [None, '']:
                self.service = request_data.get('service', 'siliconflowfree')
            else:
                self.service = request_data.get('next_service', 'siliconflowfree')
            if self.service in [None, ''] or len(self.service) < 3:
                self.service = 'siliconflowfree'

        self.sourceLang = request_data.get('sourceLang', 'en')
        if self.sourceLang in [None, ''] or len(self.sourceLang) < 2:
            self.sourceLang = 'en'
        self.targetLang = request_data.get('targetLang', 'zh-CN')
        if self.targetLang in [None, ''] or len(self.targetLang) < 2:
            self.targetLang = 'zh-CN'

        self.skip_last_pages = request_data.get('skipLastPages', 0)
        try:
            self.skip_last_pages = int(self.skip_last_pages)
        except (ValueError, TypeError):
            self.skip_last_pages = 0
        if self.skip_last_pages < 0:
            self.skip_last_pages = 0

        self.thread_num = request_data.get('threadNum', 8)
        try: 
            self.thread_num = int(self.thread_num)
            if self.thread_num < 1:
                self.thread_num = 8
        except (ValueError, TypeError):
            self.thread_num = 8
        
        self.qps = request_data.get('qps', 4)
        try:
            self.qps = int(self.qps)
        except (ValueError, TypeError):
            self.qps = 4
        if self.qps < 1:
            self.qps = 4
        
        self.pool_size = request_data.get('poolSize', 0)
        try:
            self.pool_size = int(self.pool_size)
        except (ValueError, TypeError):
            self.pool_size = 0

        # pdf2zh_next uses qps as the worker count when pool_max_workers is unset.
        # Keep 0 as "unset/follow qps" instead of the legacy qps * 10 expansion.
        if self.pool_size < 0:
            self.pool_size = 0
        if self.pool_size > 1000:
            self.pool_size = 1000

        # 如果左右留白部分裁剪太多了, 可以调整pdf_w_offset和pdf_offset_ratio, 宽边裁剪值pdf_w_offset, 窄边裁剪值pdf_w_offset/pdf_offset_ratio
        # TODO: 将裁剪的逻辑添加到zotero配置页面
        self.pdf_w_offset = int(request_data.get('pdf_w_offset', 40))
        self.pdf_h_offset = int(request_data.get('pdf_h_offset', 20))
        self.pdf_offset_ratio = float(request_data.get('pdf_offset_ratio', 5))
        self.pdf_white_margin = int(request_data.get('pdf_white_margin', 0))

        self.mono = stringToBoolean(request_data.get('mono', True))
        self.dual = stringToBoolean(request_data.get('dual', True))
        self.mono_cut = stringToBoolean(request_data.get('mono_cut', False))
        self.dual_cut = stringToBoolean(request_data.get('dual_cut', False))
        self.crop_compare = stringToBoolean(request_data.get('crop_compare', False))
        self.compare = stringToBoolean(request_data.get('compare', False))
        # pdf2zh 1.x
        self.babeldoc = stringToBoolean(request_data.get('babeldoc', False))
        self.skip_font_subsets = stringToBoolean(request_data.get('skipSubsetFonts', False))
        self.font_file = request_data.get('fontFile', '') # pdf2zh 对应的字体路径
        # pdf2zh 2.x
        self.font_family = request_data.get('fontFamily', 'auto') # pdf2zh_next对应的字体选择
        self.dual_mode = request_data.get('dualMode', 'LR')
        self.trans_first = stringToBoolean(request_data.get('transFirst', False))
        self.ocr = stringToBoolean(request_data.get('ocr', False))
        self.auto_ocr = stringToBoolean(request_data.get('autoOcr', False))
        self.no_watermark = stringToBoolean(request_data.get('noWatermark', True))
        self.save_auto_extracted_glossary = stringToBoolean(request_data.get('saveGlossary', False))
        self.disable_glossary = stringToBoolean(request_data.get('disableGlossary', False))
        self.no_dual = stringToBoolean(request_data.get('noDual', False))
        self.no_mono = stringToBoolean(request_data.get('noMono', False))
        self.skip_clean = stringToBoolean(request_data.get('skipClean', False))
        self.enhance_compatibility = stringToBoolean(request_data.get('enhanceCompatibility', False))
        self.disable_rich_text_translate = stringToBoolean(request_data.get('disableRichTextTranslate', False))
        self.translate_table_text = stringToBoolean(request_data.get('translateTableText', False))
        self.only_include_translated_page = stringToBoolean(request_data.get('onlyIncludeTranslatedPage', False))

        print("\n🔍 Config without llm_api: ", self.__dict__)

        self.llm_api = {
            'apiKey': request_data.get('llm_api', {}).get('apiKey', ''),
            'apiUrl': request_data.get('llm_api', {}).get('apiUrl', ''),
            'model': request_data.get('llm_api', {}).get('model', ''),
            'threadnum': request_data.get('llm_api', {}).get('threadNum', self.thread_num), # TODO, 为每个服务单独配置线程数, 暂时不实现
            'extraData': request_data.get('llm_api', {}).get('extraData', {})
        }

    def update_config_file(self, config_file):
        service = self.service
        engine = self.engine
        if engine == pdf2zh:
            # 更新llm api config
            config_map = pdf2zh_config_map.get(service, {})
            if not config_map: # 无需映射, 直接跳过
                print(f"🔍 No config_map found for service: {service}, 如果是新的服务, 请联系开发者更新config_map, 如果不是请忽略")
                return

            with open(config_file, 'r', encoding='utf-8') as f:
                old_config = json.load(f)

            new_config = old_config.copy()

            # 更新字体
            if os.path.exists(self.font_file):
                new_config['NOTO_FONT_PATH'] = self.font_file
                print(f"✏️ 更新字体路径: {self.font_file}")

            # 我们假设config.json文件的格式没有问题
            translator = None
            for t in new_config['translators']:
                if t.get('name') == service:
                    translator = t
                    break
            
            if translator is None:
                print(f"✏️ 服务 '{service}' 在先前配置中不存在, 创建新配置")
                translator = {'name': service, 'envs': {}}
                new_config['translators'].append(translator)
            else:
                if not isinstance(translator.get('envs'), dict): 
                    translator['envs'] = {}

            translator_keys = []
            if 'extraData' in config_map:
                for key in config_map['extraData']:
                    translator_keys.append(key)

            # 先对三个基本的参数进行映射, 如果存在映射关系, 则更新
            keys = ['apiKey', 'apiUrl', 'model'] 
            for key in keys:
                if key in self.llm_api and key in config_map:
                    value = self.llm_api[key]
                    mapped_key = config_map[key]
                    if value not in (None, "", [], {}):  # 跳过空值
                        translator['envs'][mapped_key] = value
                        translator_keys.append(mapped_key)
                        if key == "apiKey":
                            print(f"✏️ 更新 {key}: {mapped_key} = {'*' * 8 + value[-4:] if len(value) > 4 else '*' * len(value)}")
                        else:
                            print(f"✏️ 更新 {key}: {mapped_key} = {value}") 
                    else:
                        print(f"✏️ 跳过 {key}: {mapped_key} = {value} (empty or null)")

            # 将用户设置的extraData也进行映射, 如果存在映射关系, 则更新
            # 一般来说 extraData 包括 siliconFlow, volcanoEngine的EnableThinking, openai的temperature, qwen-mt的ali domains等等, 这个之后更新
            if 'extraData' in self.llm_api and isinstance(self.llm_api['extraData'], dict):
                for key, value in self.llm_api['extraData'].items():
                    if value not in (None, "", [], {}):
                        translator['envs'][key] = value
                        translator_keys.append(key)
                        print(f"✏️ 更新 extraData: {key} = {value}")
                    else:
                        print(f"✏️ 跳过 extraData: {key} = {value} (empty or null)")

            # 将所有不在translator_keys中的key删除
            # 报错: RuntimeError: dictionary changed size during iteration
            for key in list(translator['envs']):
                if key not in translator_keys:
                    del translator['envs'][key]
                    print(f"✏️ 删除旧 {key}")

            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(new_config, f, indent=4, ensure_ascii=False)
                print(f"✏️ 更新 config file: {config_file}")
            
        elif engine == pdf2zh_next: # toml文件, 格式参考server/config/config.toml.example
            config_map = pdf2zh_next_config_map.get(service, {})
            if not config_map:
                print(f"✏️ No config_map found for service: {service}, 如果是新的服务, 请联系开发者更新config_map")
                return

            # DeepSeek V4 thinking controls were added in pdf2zh_next 2.9.0.
            # Do not silently let an older runtime ignore the user's explicit
            # disabled/enabled choice because DeepSeek V4 defaults to thinking.
            if service == 'deepseek':
                model_name = str(self.llm_api.get('model') or '')
                extra_data = self.llm_api.get('extraData') or {}
                if (
                    model_name.startswith('deepseek-v4-')
                    and isinstance(extra_data, dict)
                    and 'deepseek_thinking_mode' in extra_data
                ):
                    installed_version = _detect_pdf2zh_next_version(config_file)
                    if installed_version and _version_tuple(installed_version) < (2, 9, 0):
                        raise ValueError(
                            "当前 pdf2zh_next 版本为 "
                            f"{installed_version}，不支持 DeepSeek V4 的显式思考模式控制。"
                            "请先在 server 目录执行 `python manage_packages.py status` 查看环境，"
                            "并由您主动决定是否执行 `python manage_packages.py update`。"
                            "Server 不会静默升级，也不会忽略该设置后继续请求。"
                        )
            
            with open(config_file, 'r', encoding='utf-8') as f:
                old_config = toml.load(f)

            new_config = old_config.copy() # 我们假设config.toml文件的格式没有问题

            # Keep request-scoped pdf2zh_next options in config.toml so they work
            # even when there is no dedicated CLI wiring in server.py.
            translation_config = new_config.setdefault('translation', {})
            translation_config['pool_max_workers'] = self.pool_size if self.pool_size > 0 else 'null'
            pdf_config = new_config.setdefault('pdf', {})
            pdf_config['only_include_translated_page'] = self.only_include_translated_page

            translator = None 
            if f'{service}_detail' in new_config:
                translator = new_config[f'{service}_detail']
            else:
                print(f"✏️ 服务 '{service}' 在先前配置中不存在, 创建新配置")
                translator = {}
                new_config[f'{service}_detail'] = translator
            
            translator_keys = ['translate_engine_type', 'support_llm']
            if 'extraData' in config_map:
                for key in config_map['extraData']:
                    translator_keys.append(key)

            keys = ['apiKey', 'apiUrl', 'model']
            for key in keys:
                if key in self.llm_api and key in config_map:
                    value = self.llm_api[key]
                    mapped_key = config_map[key]
                    if value not in (None, "", [], {}):
                        translator[mapped_key] = value
                        translator_keys.append(mapped_key)
                        if key == "apiKey":
                            print(f"✏️ 更新 {key}: {mapped_key} = {'*' * 8 + value[-4:] if len(value) > 4 else '*' * len(value)}")
                        else:
                            print(f"✏️ 更新 {key}: {mapped_key} = {value}") 
                    else:
                        translator_keys.append(mapped_key)
                        print(f"✏️ 跳过 {key}: {mapped_key} = {value} (empty or null)")
            
            # 将用户设置的extraData也进行映射, 如果存在映射关系, 则更新
            # 一般来说 extraData 包括 siliconFlow, volcanoEngine的EnableThinking, openai的temperature, qwen-mt的ali domains等等, 这个之后更新
            if 'extraData' in self.llm_api and isinstance(self.llm_api['extraData'], dict):
                for key, value in self.llm_api['extraData'].items():
                    if value not in (None, "", [], {}):
                        translator[key] = value
                        translator_keys.append(key)
                        print(f"✏️ 更新 extraData: {key} = {value}")
                    else:
                        print(f"✏️ 跳过 extraData: {key} = {value} (empty or null)")

            # 将translator中, 所有不在translator_keys中的key删除
            print(translator.keys())
            for key in list(translator.keys()):
                if key not in translator_keys: 
                    del translator[key]
                    print(f"✏️ 删除旧 {key}")

            with open(config_file, 'w', encoding='utf-8') as f:
                toml.dump(new_config, f)
                print(f"✏️ 更新 config file: {config_file}")

            # server.py in older releases uses a legacy singular pool flag.
            # The worker count is already persisted above, so suppress that CLI path.
            self.pool_size = 0
        else:
            print(f"✏️ 不支持的引擎类型: {engine}")
