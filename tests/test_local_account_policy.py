import importlib.util
import json
from pathlib import Path
import unittest

from tests.progress_harness import progress_environment
from tools.patching import functions
from tools.player_stage import calls

ROOT = Path(__file__).resolve().parents[1]


class LocalAccountPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_no_cloud_writes import PlatformStageTests
        PlatformStageTests.setUpClass()
        from tools.platform_stage import prepare_platform
        script, _ = prepare_platform(PlatformStageTests.before)
        cls.before = {name: match[0].replace('DzAPI_Map_HasMallItem(', 'MJ_ContentAvailable(')
                      for name, match in functions(script.decode()).items()}

    def adapt(self):
        self.assertIsNotNone(importlib.util.find_spec('tools.local_account_policy'),
                             'local account policy adapter missing')
        from tools.local_account_policy import apply_account_policy
        return apply_account_policy(self.before)

    def environment(self, extra=''):
        self.adapt()
        source = '\n'.join((ROOT / p).read_text(encoding='utf8') for p in
                           ['src/progress_schema.j', 'src/progress.j', 'src/local_account_rules.j'])
        env = progress_environment(source + '\n' + extra)
        env.update(Fa=1, MJ_FreePhase=1, IsPlayerInForce=lambda p, force: p in [0, 1, 2, 3, 5])
        return env

    def test_all_account_calls_leave_but_real_room_context_survives(self):
        after, report = self.adapt()
        source = ''.join(after.values())
        for native in ['DzAPI_Map_GetMapLevel', 'DzAPI_Map_GetLadderLevel', 'DzAPI_Map_GetGuildName',
                       'DzAPI_Map_GetGuildRole', 'DzAPI_Map_GetMapLevelRank', 'DzAPI_Map_IsBlueVIP',
                       'DzAPI_Map_GetMapConfig', 'RequestExtraBooleanData', 'RequestExtraIntegerData']:
            self.assertEqual(list(calls(source, native)), [], native)
        self.assertEqual(len(list(calls(source, 'DzAPI_Map_GetMatchType'))), 10)
        self.assertEqual(len(list(calls(source, 'DzAPI_Map_IsRPGLadder'))), 1)
        self.assertEqual(self.before['s2'], after['s2'])
        self.assertEqual(set(report['changed_functions']),
                         {name for name in self.before if self.before[name] != after[name]})
        self.assertIn('本版通关', after['BRf'])
        self.assertNotIn('局数：', after['BRf'])

    def test_old_identity_announcements_are_removed_without_losing_mastery_display(self):
        after, _ = self.adapt()
        for identity in ['【蓝V】', '【鉴赏家】', '【名人堂】', '排行榜', '检测到你曾经是']:
            self.assertNotIn(identity, after['uu'])
        self.assertIn('最熟练英雄', after['uu'])
        self.assertIn('本版免费', after['uu'])

    def test_clear_scale_is_bounded_without_changing_real_progress(self):
        e = self.environment()
        for value, expected in [(0, 0), (3, 3), (80, 80), (999, 100)]:
            e['MJ_SetInt'](5, 'GGC', value)
            self.assertEqual(e['MJ_LocalBenefitClears'](5), expected)
            self.assertEqual(e['MJ_GetInt'](5, 'GGC'), value)
        self.assertEqual(e['MJ_LocalBenefitClears'](4), 0)

    def test_local_presets_are_exclusive_and_unknown_requests_fail_closed(self):
        e = self.environment()
        self.assertTrue(e['MJ_LocalAccountBenefit'](5, 'COOPERATIVE'))
        self.assertFalse(e['MJ_LocalAccountBenefit'](5, 'STAR_GUILD'))
        self.assertTrue(e['MJ_LocalAccountBenefit'](5, 'RETURN_RECENT'))
        self.assertFalse(e['MJ_LocalAccountBenefit'](5, 'RETURN_OLD'))
        self.assertFalse(e['MJ_LocalAccountBenefit'](5, 'unknown'))
        self.assertFalse(e['MJ_LocalAccountBenefit'](4, 'RATING_GIFT'))
        e['MJ_FreePhase'] = 0
        self.assertFalse(e['MJ_LocalAccountBenefit'](5, 'RATING_GIFT'))

    def test_configuration_documents_actual_defaults_and_unknown_native_requests_fail_closed(self):
        e = self.environment()
        data = json.loads((ROOT / 'data/local-account-policy.json').read_text(encoding='utf8'))
        self.assertEqual(e['MJ_LocalGuildPreset'], data['presets']['guild']['default'])
        self.assertEqual(e['MJ_LocalReturnPreset'], data['presets']['return']['default'])
        self.assertFalse(data['clear_scale']['changes_saved_GGC'])
        self.assertEqual(data['clear_scale']['benefit_cap'], 100)
        from tools.local_account_policy import apply_account_policy
        unknown = dict(self.before)
        unknown['uu'] = unknown['uu'].replace('RequestExtraBooleanData(48,', 'RequestExtraBooleanData(99,')
        with self.assertRaises(ValueError):
            apply_account_policy(unknown)

    def test_actual_gift_body_filters_unrelated_ability_even_for_star_preset(self):
        after, _ = self.adapt()
        e = self.environment(after['BQp'])
        e.update(MJ_LocalGuildPreset=2, EK={}, DI={}, GetTriggeringTrigger=lambda: 9,
                 GetHandleId=lambda x: x, GetSpellAbilityId=lambda: 12345,
                 GetTriggerUnit=lambda: 99, GetOwningPlayer=lambda u: 5,
                 GetManipulatedItem=lambda: None, RemoveItem=lambda i: None)
        e['BQp']()
        self.assertEqual(e['DI'], {})

    def test_actual_rating_gift_keeps_per_player_once_flag(self):
        after, _ = self.adapt()
        e = self.environment(after['BQp'])
        gold = []
        stats = []
        e.update(EK={}, DI={}, HQ={5: 99}, GetTriggeringTrigger=lambda: 9,
                 GetHandleId=lambda x: x, GetSpellAbilityId=lambda: 0x41304548,
                 GetTriggerUnit=lambda: 99, GetOwningPlayer=lambda u: 5,
                 GetPlayerId=lambda p: p, GetManipulatedItem=lambda: None,
                 RemoveItem=lambda i: None, PLAYER_STATE_RESOURCE_GOLD=0,
                 AdjustPlayerStateBJ=lambda value, p, state: gold.append((value, p)),
                 bj_HEROSTAT_INT=0, bj_HEROSTAT_AGI=1, bj_HEROSTAT_STR=2, bj_MODIFYMETHOD_ADD=0,
                 ModifyHeroStat=lambda stat, unit, method, value: stats.append((stat, value)),
                 DestroyEffect=lambda effect: None, sM=lambda *args: None,
                 DisplayTimedTextToPlayer=lambda *args: None, DisplayTextToPlayer=lambda *args: None,
                 SetPlayerAbilityAvailable=lambda *args: None)
        e['BQp']()
        e['BQp']()
        self.assertEqual(gold, [(1666, 5)])
        self.assertEqual(stats, [(0, 1), (1, 1), (2, 1)])

    def test_actual_cosmetic_body_requires_exact_command_and_replaces_one_effect(self):
        after, _ = self.adapt()
        e = self.environment(after['BSS'])
        effects = []
        e.update(DI={}, HQ={5: 99}, GetTriggerPlayer=lambda: 5, GetHandleId=lambda h: h,
                 GetPlayerId=lambda p: p, GetEventPlayerChatString=lambda: '-other',
                 MJ_ContentAvailable=lambda p, key: True, DestroyEffect=lambda fx: effects.append(('remove', fx)),
                 LoadEffectHandle=lambda *args: 88, AddSpecialEffectTargetUnitBJ=lambda *args: effects.append(('add', args)),
                 SaveEffectHandle=lambda *args: None, bj_lastCreatedEffect=77,
                 DisplayTextToPlayer=lambda *args: None)
        e['BSS']()
        self.assertEqual(effects, [])
        e['GetEventPlayerChatString'] = lambda: '-txch3'
        e['BSS']()
        self.assertEqual([action for action, _ in effects], ['remove', 'add'])

    def test_actual_best_stage_copy_preserves_real_score_without_account_threshold(self):
        after, _ = self.adapt()
        e = self.environment(after['BR5'])
        e.update(DI={}, EK={}, HQ={5: 99}, GetEnumPlayer=lambda: 5, GetPlayerId=lambda p: p,
                 GetHandleId=lambda h: h, KillUnit=lambda u: None,
                 TU=e['MJ_GetInt'], TT=e['MJ_SetInt'])
        # First OR branch is true, and the recorded stage really exceeds the old DCG.
        e['SaveBoolean'](e['DI'], '全局', 0x9D29CC1F, True)
        e['SaveInteger'](e['DI'], '全局', 0x8B909B14, 17)
        e['BR5']()
        self.assertEqual(e['MJ_GetInt'](5, 'DCG'), 17)
        self.assertEqual(e['MJ_GetInt'](5, 'DCGR'), 17)


if __name__ == '__main__':
    unittest.main()
