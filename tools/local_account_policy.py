"""Replace audited account reads with explicit standalone benefit decisions.

The enclosing free stage owns source hashes, module insertion and claim guards.
This transformer consumes complete function bodies and never changes its input.
"""
from tools.lane_stage import block, once
from tools.player_stage import calls


ACCOUNT_NATIVES = (
    'DzAPI_Map_GetMapLevel', 'DzAPI_Map_GetLadderLevel', 'DzAPI_Map_GetGuildName',
    'DzAPI_Map_GetGuildRole', 'DzAPI_Map_GetMapLevelRank', 'DzAPI_Map_IsBlueVIP',
    'DzAPI_Map_GetMapConfig', 'RequestExtraBooleanData', 'RequestExtraIntegerData',
    'RequestExtraStringData',
)


def _rewrite_calls(body, native, replacement):
    for start, end, args in reversed(list(calls(body, native))):
        body = body[:start] + replacement(args) + body[end:]
    return body


def _condition(body, predicate, replacement):
    matches = [line for line in body.splitlines() if line.startswith('if ') and predicate(line)]
    if len(matches) != 1:
        raise ValueError('account condition anchor drift: ' + str(matches))
    return once(body, matches[0] + '\n', replacement + '\n')


def _drop_branch(body, predicate):
    matches = [line for line in body.splitlines() if line.startswith('if ') and predicate(line)]
    if len(matches) != 1:
        raise ValueError('account branch anchor drift: ' + str(matches))
    return once(body, block(body, matches[0]), '')


def apply_account_policy(bodies: dict[str, str]):
    """Return copied bodies plus changed-function evidence; room context stays real."""
    updated = dict(bodies)
    # Historical ranking announcements have no truthful local equivalent.
    body = updated['uu']
    body = _drop_branch(body, lambda line: 'DzAPI_Map_GetMapLevelRank(' in line and '==1 then' in line)
    body = _drop_branch(body, lambda line: 'RequestExtraIntegerData(52,' in line)
    body = _drop_branch(body, lambda line: '$D3B856BE' in line)
    updated['uu'] = body

    # A selected free appearance confers no historical rank or guild identity.
    for name in ['u7', 'BQp', 'BSS']:
        body = updated[name]
        sender = 'GetTriggerPlayer()' if name == 'BSS' else 'GetOwningPlayer(GetTriggerUnit())'
        prefix = 'GetEventPlayerChatString()=="-txch2" and ' if name == 'BSS' else ''
        body = _condition(body, lambda line: 'RequestExtraIntegerData(52,' in line,
                          'if ' + prefix + 'MJ_LocalAccountBenefit(' + sender + ',"RANK_COSMETIC") then')
        updated[name] = body

    # Best-stage caches derive exclusively from the actual standalone record.
    for name in ['wb', 'BOT', 'BR5']:
        body = updated[name]
        line = next(line for line in body.splitlines() if line.startswith('if DzAPI_Map_GetMapLevel('))
        old = block(body, line)
        content = old.split('\n', 1)[1].split('\nelse\n', 1)[0]
        if name == 'wb':
            content = 'if MJ_GetInt(GetEnumPlayer(),"DCG")>0 then\n' + content + '\nendif'
        updated[name] = once(body, old, content + '\n')

    # Fix original AND/OR leaks while replacing mutually exclusive guild groups.
    for name in ['ux', 'u1', 'u7', 'wW', 'wZ', 'BQp', 'BSS']:
        body = updated[name]
        for line in list(body.splitlines()):
            if not line.startswith('if ') or 'DzAPI_Map_GetGuildName(' not in line:
                continue
            args = next(calls(line, 'DzAPI_Map_GetGuildName'))[2]
            star = '星悦' in line
            key = 'STAR_GUILD' if star else 'COOPERATIVE'
            prefix = ''
            if name == 'BQp':
                prefix = '(GetSpellAbilityId()==$41304442 or GetSpellAbilityId()==$41304F32) and '
            elif name == 'BSS':
                prefix = 'GetEventPlayerChatString()=="-txch3" and '
                key = 'STAR_COSMETIC'
            body = once(body, line + '\n', 'if ' + prefix + 'MJ_LocalAccountBenefit(' + args + ',"' + key + '") then\n')
        if name == 'BSS':
            for command in ['4', '5', '6']:
                body = _condition(body, lambda line, c=command: 'GetEventPlayerChatString()=="-txch' + c + '"' in line,
                                  'if GetEventPlayerChatString()=="-txch' + command + '" and MJ_LocalAccountBenefit(GetTriggerPlayer(),"NAMED_COSMETIC") then')
        updated[name] = body
    updated['ur'] = ('function ur takes nothing returns nothing\n'
                     'if LoadBoolean(DI,StringHash("全局"),$BBE94EFD)==false and LoadBoolean(DI,StringHash("全局"),$88CEC9C2)==false and MJ_LocalAccountBenefit(GetEnumPlayer(),"COOPERATIVE") then\n'
                     'call DisplayTextToForce(GetPlayersAll(),GetPlayerName(GetEnumPlayer())+" - 本版免费合作加成：攻击吸血+1%、免伤+1%。")\n'
                     'endif\nendfunction\n')

    body = updated['BQp']
    body = _condition(body, lambda line: 'RequestExtraIntegerData(46,' in line and '$413045' not in line and '>=3 or ' in line,
                      'if MJ_LocalAccountBenefit(GetOwningPlayer(GetTriggerUnit()),"RATING_GIFT") then')
    body = _condition(body, lambda line: 'RequestExtraIntegerData(46,' in line,
                      'if MJ_LocalAccountBenefit(GetOwningPlayer(GetTriggerUnit()),"VOTE_GIFT") then')
    updated['BQp'] = body

    removed = []
    for name, body in list(updated.items()):
        before = body
        for native in ACCOUNT_NATIVES:
            amount = len(list(calls(body, native)))
            if not amount:
                continue
            if native == 'DzAPI_Map_GetMapLevel':
                replace = lambda args: 'MJ_LocalBenefitClears(' + args + ')'
            elif native == 'DzAPI_Map_GetLadderLevel':
                # This sole condition grants R006, not a displayed platform level.
                body = _condition(body, lambda line: native + '(' in line,
                                  'if MJ_LocalAccountBenefit(GetEnumPlayer(),"LADDER_REWARD") then')
                removed.append(dict(function=name, native=native, count=amount))
                continue
            elif native == 'DzAPI_Map_IsBlueVIP':
                replace = lambda args: 'MJ_LocalAccountBenefit(' + args + ',"BLUE_BONUS")'
            elif native == 'DzAPI_Map_GetMapConfig':
                def replace(args):
                    if args != '"NOTE"':
                        raise ValueError('unknown local notice request: ' + args)
                    return 'MJ_LocalNotice()'
            elif native == 'RequestExtraBooleanData':
                def replace(args):
                    request, player, rest = args.split(',', 2)
                    if request == '44': key = 'REMASTER_GIFT'
                    elif request == '48': key = 'APPRECIATOR'
                    elif request == '53':
                        flags = rest.split(',')[-3]
                        key = {'16': 'COLLECTOR', '8': 'RETURN_RECENT', '4': 'RETURN_OLD'}.get(flags)
                        if key is None: raise ValueError('unknown return/collection request: ' + args)
                    else: raise ValueError('unknown boolean account request: ' + args)
                    return 'MJ_LocalAccountBenefit(' + player + ',"' + key + '")'
            elif native == 'RequestExtraIntegerData':
                def replace(args):
                    request, player, rest = args.split(',', 2)
                    if request != '45': raise ValueError('unresolved integer account request: ' + args)
                    return 'MJ_GetInt(' + player + ',"GGC")'
            else:
                raise ValueError('unresolved account native: ' + name + '/' + native)
            body = _rewrite_calls(body, native, replace)
            removed.append(dict(function=name, native=native, count=amount))
        if body != before:
            updated[name] = body

    # Display the actual local record and local benefits, with no account identity claims.
    for name in ['uY', 'us', 'uu', 'BQp', 'BRf']:
        body = updated[name].replace('地图等级', '本版通关').replace('局数：', '本版通关次数：')
        if name == 'uu':
            replacements = {
                '【蓝V】': '【本版免费】', '主播玩家': '玩家', '【鉴赏家】': '【本版免费】',
                '加入本局游戏，如果本图让您满意请帮忙在评论区写下你的感受！送上福利': '加入本局游戏，获得本版免费福利',
                '已收藏': '获得本版免费收藏福利：', '是最忠实的': '获得本版免费',
                '回流老玩家': '回流福利', '，在|r7|cff00ffff天内获得额外掉落率': '，本局获得额外掉落率',
                '检测到你曾经是': '本版免费福利：',
            }
            for old, new in replacements.items(): body = body.replace(old, new)
        if name == 'BQp':
            replacements = {
                '领取了五星好评礼包': '领取了本版免费礼包',
                '你还没有进行五星好评，不能领取此礼包！': '本版免费礼包当前不可领取。',
                '领取重制版礼包': '领取本版免费药水礼包',
                '你还没有购买《魔兽争霸3：重制版》，不能领取此礼包！': '本版免费药水礼包当前不可领取。',
                '领取了投票礼包': '领取了本版免费成长礼包',
                '先|Cffb399ff投票|r|Cffffffbf「梦迹沙河2」|r就可领取此礼包！非常感谢，祝游戏愉快！（投票越多三围加的越高）': '本版免费成长礼包当前不可领取。',
                '领取了星悦公会专属礼包': '领取了本版免费星悦预设礼包',
                '你的本版通关以大于3级': '你的本版通关已超过3次',
                '你的本版通关还不到4级': '你的本版通关不足4次',
            }
            for old, new in replacements.items(): body = body.replace(old, new)
        updated[name] = body

    # Fail closed for future or missed account native call sites.
    for name, body in updated.items():
        for native in ACCOUNT_NATIVES:
            if list(calls(body, native)):
                raise ValueError('remaining account read: ' + name + '/' + native)
    changed = [name for name in bodies if updated[name] != bodies[name]]
    removed_account_calls = [dict(function=name, native=native, count=len(list(calls(body, native))))
                             for name, body in bodies.items() for native in ACCOUNT_NATIVES
                             if list(calls(body, native))]
    return updated, dict(changed_functions=changed, namespace='MJ5_LOCAL_V1',
                         room_context_retained=['DzAPI_Map_GetMatchType', 'DzAPI_Map_IsRPGLadder'],
                         rewritten_calls=removed, removed_account_calls=removed_account_calls,
                         runtime_verified=False)
