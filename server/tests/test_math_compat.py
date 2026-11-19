"""No-API checks for request routing, opt-in scope and native composition."""
import base64
import tempfile
import unittest
import multiprocessing
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pymupdf
from utils import math_compat, math_fonts, math_variables, table_runtime
from utils.config import Config


class MathCompatibilityTests(unittest.TestCase):
    def test_math_policy_survives_spawn_and_restores_parent(self):
        if not math_compat.policy_supported():
            self.skipTest("needs a validated engine pair")
        for method in multiprocessing.get_all_start_methods():
            probe = Path(__file__).parent / "fixtures/math_process_probe.py"
            result = subprocess.run([sys.executable, str(probe), method],
                                    capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_explicit_opt_in_and_legacy_engine_unchanged(self):
        self.assertFalse(Config({"engine":"pdf2zh_next"}).math_compatibility)
        self.assertTrue(Config({"engine":"pdf2zh_next", "mathCompatibility":True}).math_compatibility)
        self.assertTrue(Config({"engine":"pdf2zh_next", "llm_api":{
            "extraData":{"mathCompatibility":"true"}}}).math_compatibility)
        self.assertFalse(Config({"engine":"pdf2zh", "mathCompatibility":True}).math_compatibility)
        self.assertFalse(Config({"engine":"pdf2zh_next", "mathCompatibility":False,
            "llm_api":{"extraData":{"mathCompatibility":"true"}}}).math_compatibility)

    def test_cli_flag_is_consumed_and_combines_with_existing_policies(self):
        base=["python", "-m", "pdf2zh_next", "paper.pdf"]
        self.assertEqual(table_runtime.prepare_table_runtime_command(base),base)
        result=table_runtime.prepare_table_runtime_command(base+[math_compat.FLAG])
        self.assertEqual(result[3:],["none",math_compat.FLAG,"paper.pdf"])
        combined=table_runtime.prepare_table_runtime_command(base+[
            "--zotero-reference-skip","--zotero-table-mode","fixed",math_compat.FLAG])
        self.assertEqual(combined[3:],["fixed","--zotero-reference-skip",math_compat.FLAG,"paper.pdf"])
        with self.assertRaises(ValueError):
            table_runtime.prepare_table_runtime_command(["pdf2zh",math_compat.FLAG])

    def test_unverified_pair_never_installs_private_api_hooks(self):
        with patch.object(math_compat,"version",side_effect=lambda p:"99.0.0"):
            self.assertFalse(math_compat.policy_supported())
            with patch.dict("sys.modules",{"pdf2zh_next":None}):
                math_compat.install_math_policy()()

    def test_math_fonts_do_not_include_body_italic_fonts(self):
        names=["ABCDEF+AdvMacMthSyN","ABCDEF+AdvOT123.I","ABCDEF+AdvOT123.I+20",
               "TimesNewRomanPS-ItalicMT","CMTI10","Arial"]
        self.assertEqual(math_fonts.detect(names),["AdvMacMthSyN"])
        for name in ["AdvP4C4E01", "AdvEls-m", "AdvPi1", "AdvPSSym", "MathType", "MTExtra"]:
            self.assertEqual(math_fonts.detect(["ABCDEF+"+name]), [name])
        self.assertEqual(math_fonts.base_name("BASE64:"+base64.b64encode(b"ABCDEF+AdvPi1").decode()),"AdvPi1")

    def test_prose_cmr_is_excluded_across_all_selected_pages(self):
        def page(text):
            return SimpleNamespace(get_text=lambda _: {"blocks":[{"lines":[{"spans":[
                {"font":"CMR10","text":text}]}]}]})
        self.assertEqual(math_fonts.tex_roman_math_fonts([page("1+exp(x)")],[0]),["CMR10"])
        self.assertEqual(math_fonts.tex_roman_math_fonts([page("1+exp(x)"),page("ordinary prose")],[0,1]),[])
        self.assertEqual(math_fonts.tex_roman_math_fonts([page("if")],[0]),[])

    def test_noop_and_explicit_user_font_override_never_copy_source(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/"control.pdf"
            with pymupdf.open() as doc:
                doc.new_page().insert_text((30,40),"Ordinary italic prose remains text.",fontname="heit")
                doc.save(source)
            config=SimpleNamespace(input_file=source,formular_font_pattern=None,
                ocr_workaround=False,auto_enable_ocr_workaround=True,should_translate_page=lambda _:True)
            before=source.read_bytes()
            with patch.object(math_compat.shutil,"copyfile",side_effect=AssertionError("must not copy")):
                self.assertEqual(math_compat.prepare_input(config),(None,set(),{}))
                with patch.object(math_fonts,"detect",return_value=["AdvMacMthSyN"]), \
                        patch.object(math_compat,"version",return_value="0.6.4"):
                    self.assertEqual(math_compat.prepare_input(config),(None,set(),{}))
                config.formular_font_pattern="user-choice"
                self.assertEqual(math_compat.prepare_input(config),(None,set(),{}))
            self.assertEqual(source.read_bytes(),before)
            self.assertEqual(config.input_file,source)
            config.formular_font_pattern = None
            config.doc_layout_model = sentinel = object()
            with patch.object(math_fonts,"detect",return_value=["AdvMacMthSyN"]), \
                    patch.object(math_compat,"version",return_value="0.7.1"), \
                    patch.object(math_variables,"protect_variables",return_value=0):
                temporary, additions, _info = math_compat.prepare_input(config)
            self.assertIsNotNone(temporary)
            temporary.cleanup()
            self.assertIn("AdvMacMthSyN", additions)
            self.assertIs(config.doc_layout_model.model, sentinel)
            self.assertNotEqual(config.input_file, source)

    def test_runtime_hooks_compose_with_native_fonts_and_restore(self):
        # Real engine imports, but no translators, model weights or APIs.
        if not math_compat.policy_supported():
            self.skipTest("needs a validated engine pair")
        from pdf2zh_next import high_level
        from babeldoc.format.pdf.document_il.utils import formular_helper
        native_config=high_level.create_babeldoc_config
        native_font=formular_helper.is_formulas_font
        config=SimpleNamespace()
        def prepare(value):
            value.formular_font_pattern=math_fonts.extend_native_pattern({"ZoteroMathItalic","AdvMacMthSyN"})
            return None,set(),{}
        with patch.object(high_level,"create_babeldoc_config",return_value=config), \
                patch.object(math_compat,"prepare_input",side_effect=prepare):
            factory=high_level.create_babeldoc_config
            restore=math_compat.install_math_policy()
            try:
                high_level.create_babeldoc_config(None,None)
                pattern=config.formular_font_pattern
                self.assertTrue(formular_helper.is_formulas_font("ZoteroMathItalic-0-0",pattern))
                self.assertTrue(formular_helper.is_formulas_font("AdvMacMthSyN",pattern))
                for name in ["CMR10","Arial","CMMI10","Symbol","AdvOT123.I"]:
                    self.assertEqual(formular_helper.is_formulas_font(name,pattern),native_font(name,None))
                self.assertEqual(formular_helper.is_formulas_font("ZoteroMathItalic-0-0","^Other$"),
                                 native_font("ZoteroMathItalic-0-0","^Other$"))
            finally:restore()
            self.assertIs(high_level.create_babeldoc_config,factory)
        self.assertIs(high_level.create_babeldoc_config,native_config)
        self.assertIs(formular_helper.is_formulas_font,native_font)

    def test_rust_bridge_receives_the_extended_pattern(self):
        from importlib.metadata import version
        if not math_compat.policy_supported() or version("BabelDOC") != "0.7.1":
            self.skipTest("Rust bridge belongs to BabelDOC 0.7.1")
        from babeldoc.format.pdf.high_level import _rust_stage_configs
        config=SimpleNamespace(**{key:False for key in (
            "skip_formula_offset_calculation", "ocr_workaround", "remove_non_formula_lines",
            "figure_table_protection_threshold", "non_formula_line_iou_threshold",
            "formular_char_pattern", "debug", "merge_alternating_line_numbers",
            "split_short_lines", "short_line_split_factor", "lang_out")})
        config.formular_font_pattern=math_fonts.extend_native_pattern({"AdvMacMthSyN"})
        result=_rust_stage_configs(config,SimpleNamespace(font_source_styles={}))
        self.assertEqual(result['styles']['config_fields']['formular_font_pattern'],config.formular_font_pattern)
        self.assertEqual(result['paragraph']['formular_font_pattern'],config.formular_font_pattern)
