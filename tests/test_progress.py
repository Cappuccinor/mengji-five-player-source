import json
from pathlib import Path
import unittest
from tests.progress_harness import progress_environment

ROOT=Path(__file__).resolve().parents[1]

class ProgressTests(unittest.TestCase):
    def environment(self):
        core=ROOT/'src/progress.j';schema=ROOT/'src/progress_schema.j'
        self.assertTrue(core.exists(),'independent progress core missing')
        self.assertTrue(schema.exists(),'audited progress schema missing')
        # schema functions/globals precede the core so the actual native-free module executes.
        env=progress_environment(schema.read_text(encoding='utf8')+'\n'+core.read_text(encoding='utf8'))
        env['MJ_InitProgress']()
        return env

    def test_defaults_and_player_isolation(self):
        e=self.environment()
        for p in [0,1,2,3,5]:
            self.assertEqual(e['MJ_GetInt'](p,'GG'),0);self.assertFalse(e['MJ_GetBool'](p,'LWJT'))
            self.assertEqual(e['MJ_GetString'](p,'SLD[0]'),'')
        e['MJ_SetInt'](5,'SCORE',123);e['MJ_SetBool'](5,'SWITCH',True)
        self.assertEqual(e['MJ_GetInt'](5,'SCORE'),123);self.assertEqual(e['MJ_GetInt'](1,'SCORE'),0)
        self.assertFalse(e['MJ_GetBool'](1,'SWITCH'))
        e['MJ_SetInt'](4,'SCORE',999);self.assertEqual(e['MJ_GetInt'](4,'SCORE'),0)

    def test_live_setters_enforce_known_types_and_ranges_without_ban_state(self):
        e=self.environment();e['MJ_SetInt'](0,'GG',-5);self.assertEqual(e['MJ_GetInt'](0,'GG'),0)
        e['MJ_SetInt'](0,'GG',999);self.assertEqual(e['MJ_GetInt'](0,'GG'),12)
        e['MJ_SetInt'](0,'TGDS',9999);self.assertEqual(e['MJ_GetInt'](0,'TGDS'),1200)
        e['MJ_SetInt'](0,'MIN',200);self.assertEqual(e['MJ_GetInt'](0,'MIN'),200)
        e['MJ_SetBool'](0,'BAN',True);self.assertFalse(e['MJ_GetBool'](0,'BAN'))
        e['MJ_SetString'](0,'SLD[0]','x'*64);self.assertEqual(e['MJ_GetString'](0,'SLD[0]'),'')

    def test_export_import_roundtrip_uses_own_schema_and_excludes_original_account(self):
        e=self.environment();e['MJ_SetInt'](5,'SCORE',321);e['MJ_SetInt'](5,'GG',3)
        e['MJ_SetBool'](5,'LWJT',True);e['MJ_SetString'](5,'SLD[0]','0'*63)
        code=e['MJ_ExportProgress'](5);self.assertTrue(code.startswith('MJ5_LOCAL_V1:'))
        e2=self.environment();self.assertTrue(e2['MJ_ImportProgress'](1,code))
        self.assertEqual(e2['MJ_GetInt'](1,'SCORE'),321);self.assertEqual(e2['MJ_GetInt'](1,'GG'),3)
        self.assertTrue(e2['MJ_GetBool'](1,'LWJT'));self.assertEqual(e2['MJ_GetString'](1,'SLD[0]'),'0'*63)
        self.assertEqual(e2['MJ_GetInt'](5,'SCORE'),0)
        self.assertEqual(e2['MJ_ExportProgress'](1),code)

    def test_invalid_version_checksum_and_partial_records_leave_existing_progress_unchanged(self):
        e=self.environment();e['MJ_SetInt'](0,'SCORE',77);before=e['MJ_ExportProgress'](0)
        for code in ['',before.replace('V1:','V2:',1),before[:-1],before+'0',before.replace(';',';',1)+';', 'A'*9000]:
            self.assertFalse(e['MJ_ImportProgress'](0,code),code[:30]);self.assertEqual(e['MJ_ExportProgress'](0),before)

    def test_snapshot_validation_rejects_out_of_range_values_even_with_valid_checksum(self):
        e=self.environment();good=e['MJ_ExportProgress'](0);start=good.index(':',len('MJ5_LOCAL_V1:'))+1
        # The schema is explicit; replace GG's token rather than rely on its ordinal.
        keys=json.loads((ROOT/'data/progress-keys.json').read_text(encoding='utf8'))['keys']
        fields=good[start:good.rindex('#')].split(';')[:-1]
        index=next(i for i,item in enumerate(keys) if item['key']=='IGG')
        for value in ['13','-1','2147483648','01','x']:
            altered=list(fields);altered[index]=value
            body=good[:start]+';'.join(altered)+';';code=body+'#'+str(e['MJ_ProgressChecksum'](body))
            self.assertFalse(e['MJ_ImportProgress'](0,code),value)
            self.assertEqual(e['MJ_ExportProgress'](0),good)

    def test_import_lock_does_not_block_ordinary_gameplay_growth_or_export(self):
        e=self.environment();code=e['MJ_ExportProgress'](0);e['MJ_LockProgress']()
        self.assertFalse(e['MJ_ImportProgress'](0,code));e['MJ_SetInt'](0,'SCORE',10)
        self.assertEqual(e['MJ_GetInt'](0,'SCORE'),10);self.assertNotEqual(e['MJ_ExportProgress'](0),code)

    def test_mastery_maximum_and_records_crossing_segments_are_validated(self):
        e=self.environment()
        piece='00'+'05u'+'0'*58
        e['MJ_SetString'](0,'SLD[0]',piece)
        self.assertTrue(e['MJ_ImportProgress'](1,e['MJ_ExportProgress'](0)))
        self.assertEqual(e['MJ_GetString'](1,'SLD[0]'),piece)
        # Hero21 spans zero-based offsets62..64 across two packed strings.
        e['MJ_SetString'](0,'SLD[0]','0'*63);e['MJ_SetString'](0,'SLD[1]','5u'+'0'*61)
        self.assertTrue(e['MJ_ImportProgress'](1,e['MJ_ExportProgress'](0)))
        e['MJ_SetString'](0,'SLD[1]','5v'+'0'*61)
        before=e['MJ_ExportProgress'](1)
        # Build a correctly checksummed record from the otherwise valid export.
        code=e['MJ_ExportProgress'](0)
        self.assertFalse(e['MJ_ImportProgress'](1,code));self.assertEqual(e['MJ_ExportProgress'](1),before)

    def test_actual_roster_schema_and_core_compile(self):
        import tempfile
        from tools.check_jass import check_jass
        self.environment()
        from tools.progress_schema import progress_module
        module=progress_module();boundary=module.index('endglobals\n')+len('endglobals\n')
        source=module[:boundary]+(ROOT/'src/roster.j').read_text(encoding='utf8')+module[boundary:]
        with tempfile.TemporaryDirectory(dir=ROOT/'scratch') as tmp:
            script=Path(tmp)/'progress.j';script.write_text(source,encoding='utf8')
            result=check_jass(script,ROOT/'vendor/jass-1.27.1')
            self.assertTrue(result['passed'],result['output'])

    def test_case_insensitive_slash_normalizing_engine_hash_does_not_corrupt_progress_codes(self):
        source=(ROOT/'src/progress_schema.j').read_text(encoding='utf8')+(ROOT/'src/progress.j').read_text(encoding='utf8')
        e=progress_environment(source);e['StringHash']=lambda text:text.upper().replace('/','\\');e['MJ_InitProgress']()
        e['MJ_SetString'](0,'HGG',('aA/\\'*16)[:63])
        self.assertEqual(e['MJ_GetString'](0,'HGG'),('aA/\\'*16)[:63])
        code=e['MJ_ExportProgress'](0);self.assertNotEqual(code[-3:],'#-1')
        self.assertTrue(e['MJ_ImportProgress'](5,code));self.assertEqual(e['MJ_ExportProgress'](5),code)
