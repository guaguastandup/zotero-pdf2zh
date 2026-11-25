"""Run BabelDOC's real PDF pipeline with local marker translations, no LLM API.

Requires the validated engine and already-downloaded BabelDOC assets. All cache
writes use a temporary profile. Supply your own PDF; generated text is NOT a
real translation. The resulting report records translation and glossary inputs.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


# BabelDOC starts font-subsetting workers with spawn. They must use the same
# isolated cache before importing the writer/translator modules.
if __name__ == '__mp_main__' and os.environ.get('PDF2ZH_REFERENCE_AUDIT_PROFILE'):
    child_profile = Path(os.environ['PDF2ZH_REFERENCE_AUDIT_PROFILE'])
    child_expand = Path.expanduser
    patch.object(Path, 'home', return_value=child_profile).start()
    patch.object(Path, 'expanduser', lambda p: child_profile / str(p)[2:]
                 if str(p).startswith('~/') else child_expand(p)).start()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pdf', type=Path)
    parser.add_argument('--assets-cache', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--native', action='store_true', help='Control run without reference skipping')
    parser.add_argument('--no-terms', action='store_true')
    args = parser.parse_args()
    source = args.pdf.resolve()
    output = args.output.resolve()
    if output == source.parent:
        parser.error('Choose a separate output directory')
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='reference-audit-') as tmp:
        profile = Path(tmp)
        cache = profile / '.cache/babeldoc'
        cache.mkdir(parents=True)
        for name in ('fonts', 'cmap', 'models', 'tiktoken'):
            shutil.copytree(args.assets_cache / name, cache / name)
        expand = Path.expanduser
        with patch.dict(os.environ, {'PDF2ZH_REFERENCE_AUDIT_PROFILE': str(profile)}), \
                patch.object(Path, 'home', return_value=profile), patch.object(
            Path, 'expanduser', lambda p: profile / str(p)[2:]
            if str(p).startswith('~/') else expand(p)
        ):
            from babeldoc.docvision.doclayout import OnnxModel
            from babeldoc.translator.translator import BaseTranslator, set_translate_rate_limiter
            from babeldoc.format.pdf.translation_config import TranslationConfig
            from babeldoc.format.pdf.high_level import translate
            from utils.reference_layout import ReferenceLayoutModel
            from utils.reference_skip import policy_supported
            from importlib.metadata import version
            if not policy_supported() or version("BabelDOC") != "0.7.1":
                parser.error('This audit requires pdf2zh-next 2.10.2 / BabelDOC 0.7.1')

            class MarkerTranslator(BaseTranslator):
                name = 'reference-audit'

                def __init__(self):
                    super().__init__('en', 'zh', True)
                    self.inputs, self.terms = [], []

                def do_translate(self, text, rate_limit_params=None):
                    self.inputs.append(text)
                    return '译文 ' + text

                def do_llm_translate(self, text, rate_limit_params=None):
                    if text is None:
                        return None
                    if '## Here is the input:' in text:
                        items = json.loads(text.split('## Here is the input:')[-1])
                        return json.dumps([{'id': item['id'], 'output': self.do_translate(item['input'])}
                                           for item in items], ensure_ascii=False)
                    if 'Now translate the following text:' in text:
                        return self.do_translate(text.split('Now translate the following text:')[-1].strip())
                    if 'expert multilingual terminologist' not in text:
                        raise ValueError('Unrecognized audit prompt; update the audit translator')
                    self.terms.append(text)
                    return '[]'

            # CPU avoids platform-specific CoreML compilation in this audit.
            with patch('babeldoc.docvision.doclayout.onnxruntime.get_available_providers',
                       return_value=['CPUExecutionProvider']):
                model = OnnxModel.from_pretrained()
            if not args.native:
                model = ReferenceLayoutModel(model)
            translator = MarkerTranslator()
            set_translate_rate_limiter(10000)
            config = TranslationConfig(
                translator, source, 'en', 'zh', model, output_dir=output,
                working_dir=profile / 'work', qps=10000, pool_max_workers=4,
                term_pool_max_workers=4, use_rich_pbar=False, skip_scanned_detection=True,
                auto_extract_glossary=not args.no_terms, disable_same_text_fallback=True,
            )
            result = translate(config)
            report = {'source': str(source), 'marker_translation_only': True,
                      'pdf2zh_next': version('pdf2zh-next'), 'BabelDOC': version('BabelDOC'),
                      'reference_skip': not args.native, 'auto_extract_glossary': not args.no_terms,
                      'preserved_records': getattr(model, 'preserved_records', 0),
                      'translation_inputs': translator.inputs, 'term_inputs': translator.terms}
            (output / 'audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            print(result)
            print(f'Audit report: {output / "audit.json"}')


if __name__ == '__main__':
    main()
