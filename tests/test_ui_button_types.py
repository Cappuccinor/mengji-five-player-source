from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class UIButtonTypesTests(unittest.TestCase):
    def test_script_dialog_buttons_match_client_template_type(self):
        # War3Patch.mpq/UI/FrameDef/UI/ScriptDialog.fdf declares this template
        # GLUETEXTBUTTON with a ButtonText child; plain BUTTON loses the caption.
        source = (ROOT/'src/hero_ui.j').read_text(encoding='utf8')
        buttons = re.findall(r'DzCreateFrameByTagName\("([^"]+)",([^\n]+),"ScriptDialogButton",0\)', source)
        self.assertEqual(len(buttons), 5)
        self.assertTrue(all(kind == 'GLUETEXTBUTTON' for kind, _ in buttons))
        for caption in ['上页', '下页', '确定英雄 / 准备', '取消准备']:
            self.assertIn('call DzFrameSetText(frame,"'+caption+'")', source)
