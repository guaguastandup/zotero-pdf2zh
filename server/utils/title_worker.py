"""Translate one title in an isolated pdf2zh_next subprocess."""

import contextlib
import importlib
import importlib.metadata
import io
import json
import logging
import sys


def translate(request):
    # This adapter is verified against the 2.9 settings and translator API.
    version = importlib.metadata.version('pdf2zh-next')
    if version.split('.')[:2] != ['2', '9']:
        return {'status': 'error', 'code': 'unsupported_version'}
    from pdf2zh_next.config.model import SettingsModel
    from pdf2zh_next.config.translate_engine_model import TRANSLATION_ENGINE_METADATA
    from pdf2zh_next.translator.rate_limiter.qps_rate_limiter import QPSRateLimiter

    metadata = next(m for m in TRANSLATION_ENGINE_METADATA
                    if m.cli_flag_name == request['service'])
    engine = metadata.setting_model_type(**request['detail'])
    engine.validate_settings()
    if hasattr(engine, 'transform'):
        engine = engine.transform()
        engine.validate_settings()
    settings = SettingsModel(
        translate_engine_settings=engine,
        translation=dict(lang_in=request['sourceLang'], lang_out=request['targetLang'],
                         qps=1, ignore_cache=True),
    )
    name = engine.translate_engine_type
    module = importlib.import_module(f'pdf2zh_next.translator.translator_impl.{name.lower()}')
    # Instantiate the same engine adapter without the factory's extra Hello request.
    translator = getattr(module, f'{name}Translator')(settings, QPSRateLimiter(1))
    try:
        title = translator.translate(request['title'], ignore_cache=True)
        return {'status': 'success', 'title': title}
    finally:
        client = getattr(translator, 'client', None)
        if client and hasattr(client, 'close'):
            client.close()


def main():
    logging.disable(logging.CRITICAL)
    try:
        request = json.load(sys.stdin)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            result = translate(request)
    except Exception:
        result = {'status': 'error', 'code': 'translation_failed'}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
