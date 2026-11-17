"""Truthful labels for audited local free benefits; retain all gameplay requirements."""

def free_ability_text(raw):
    # Input member is hash-pinned by prepare_free_objects, including AMJ5 clone.
    text=raw.decode('utf8')
    replacements={
        '点击打开|Cffffff00称号面板|r，查看所有称号与相关属性':'点击打开|Cffffff00称号面板|r，查看所有称号与相关属性|n本版原付费内容免费；通关、毕业、积分等成长要求保留',
        '点击打开|Cffffff00坐骑面板|r，查看所有坐骑与相关属性':'点击打开|Cffffff00坐骑面板|r，查看所有坐骑与相关属性|n本版原付费内容免费；通关、毕业、积分等成长要求保留',
        '点击打开|Cffffff00翅膀面板|r，查看所有翅膀与相关属性':'点击打开|Cffffff00翅膀面板|r，查看所有翅膀与相关属性|n本版原付费内容免费；通关、毕业、积分等成长要求保留',

        '在平台商城购买永久解锁':'本版免费解锁',
        '打赏活动专属翅膀，活动结束后绝版':'本版免费外观，可在面板切换',
        '打赏活动专属称号，活动结束后绝版':'本版免费称号，可在面板切换',
        '购买商城内所有道具后自动激活':'本版免费全套预设自动激活',
        '需要在平台商城购买：烂铁祝福、黄金祝福、白金祝福、钻石祝福、泰瑞尔皮肤、九尾狐宠物、沙河通行证、无尽黄金魔袋，集齐自动激活生效':'本版免费全套内容自动生效，无需平台购买',
        '（购买|r沙河通行证|cffff0000后才可以获得通关点数）':'（本版通行证免费，点数通过实际通关获得）',
        ' - 购买|r金币礼包|Cff00ffff后可以领取|n - 在平台商城用金币购买':' - 本版金币礼包免费领取',
        ' - 购买|r木材礼包|Cff00ffff后可以领取|n - 在平台商城用木材购买':' - 本版木材礼包免费领取',
        ' - 购买|r《魔兽争霸3：重制版》|Cff00ffff后可以领取':' - 本版药水礼包免费领取',
    }
    for old,new in replacements.items():
        if old not in text:raise ValueError('paid ability label drift: '+old)
        text=text.replace(old,new)
    return text.encode('utf8')
