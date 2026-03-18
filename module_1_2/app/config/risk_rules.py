"""
第二模块（核心风险条款识别与初步分级）规则配置

说明：
1. 规则优先，不依赖模型。
2. 该文件仅放“可配置规则”，业务逻辑放在 risk_identifier.py。
3. preliminary_level_strategy 采用简化策略，便于后续替换。
"""

from typing import Dict, List


RISK_RULES: List[Dict] = [
    {
        "risk_type": "试用期风险",
        "description": "试用期约定可能缺失、过长或表述不清，导致合规风险。",
        "keywords": [
            "试用期",
            "试用",
            "转正",
            "录用条件",
            "不符合录用条件",
            "延长试用",
        ],
        "strong_keywords": [
            "无试用期",
            "试用期六个月以上",
            "试用期超过六个月",
            "可延长试用期",
            "单方延长试用期",
        ],
        "related_clause_types": [
            "合同期限",
            "其他约定",
        ],
        "preliminary_level_strategy": {
            "high_if_strong_keyword_hit": True,
            "medium_if_keyword_hits_ge": 2,
            "low_if_keyword_hits_ge": 1,
        },
        # 示例触发场景：
        # - “试用期可根据公司安排延长”
        # - “试用期为 8 个月”
        "example_scenarios": [
            "试用期可根据公司安排延长",
            "试用期超过法定合理范围",
        ],
    },
    {
        "risk_type": "试用期工资风险",
        "description": "试用期工资约定过低或缺少明确支付标准，可能存在违法风险。",
        "keywords": [
            "试用期工资",
            "试用期薪资",
            "试用期期间的工资",
            "工资标准",
            "薪酬标准",
            "转正工资",
        ],
        "strong_keywords": [
            "低于最低工资",
            "按最低标准发放",
            "不低于本岗位最低档",
            "试用期不发工资",
            "试用期工资按正式工资",
            "试用期工资为正式工资的",
        ],
        "related_clause_types": [
            "劳动报酬",
            "合同期限",
        ],
        "preliminary_level_strategy": {
            "high_if_strong_keyword_hit": True,
            "medium_if_keyword_hits_ge": 2,
            "low_if_keyword_hits_ge": 1,
        },
        "example_scenarios": [
            "试用期工资不发或明显不合理",
            "只写试用期工资，未写明确计算标准",
        ],
    },
    {
        "risk_type": "薪酬支付风险",
        "description": "工资支付时间、方式、构成不清或存在不当扣减条款。",
        "keywords": [
            "工资",
            "薪酬",
            "劳动报酬",
            "发薪日",
            "支付",
            "发放",
            "发薪方式",
            "发放标准",
            "工资构成",
            "工资标准",
            "工资待遇",
            "薪酬结构",
            "扣发",
            "代扣",
            "绩效工资",
            "计件工资",
            "试用期工资",
            "奖金",
        ],
        "strong_keywords": [
            "公司有权延期支付",
            "拖欠工资",
            "不按月支付",
            "工资由公司酌情发放",
            "可无条件扣减工资",
            "未完成业绩不发工资",
        ],
        "related_clause_types": [
            "劳动报酬",
            "其他约定",
        ],
        # 收紧策略：
        # 1) “支付/工资”不可单独触发，至少要命中更核心薪酬机制词
        # 2) 命中排除语境时（如支付加班工资、经济补偿支付）默认过滤
        "required_any_keywords": [
            "工资构成",
            "薪酬结构",
            "发薪方式",
            "发放标准",
            "工资标准",
            "绩效工资",
            "计件工资",
            "试用期工资",
            "奖金",
            "代扣",
            "扣发",
            "工资待遇",
        ],
        "required_combinations_any": [
            ["工资", "标准"],
            ["工资", "构成"],
            ["工资", "代扣"],
            ["工资", "扣发"],
            ["发薪", "方式"],
            ["试用期", "工资"],
            ["绩效", "工资"],
            ["计件", "工资"],
        ],
        "blocked_phrases": [
            "支付加班工资",
            "加班工资支付",
            "支付经济补偿",
            "经济补偿支付",
            "加班费支付",
        ],
        "blocked_context_max_keyword_hits_to_filter": 3,
        "preliminary_level_strategy": {
            "high_if_strong_keyword_hit": True,
            "medium_if_keyword_hits_ge": 3,
            "low_if_keyword_hits_ge": 2,
        },
        "example_scenarios": [
            "工资发放时间完全由公司决定",
            "约定公司可单方扣减工资",
        ],
    },
    {
        "risk_type": "社保公积金风险",
        "description": "社保公积金缴纳主体、时点或责任约定不明或不合规。",
        "keywords": [
            "社会保险",
            "社保",
            "五险",
            "公积金",
            "住房公积金",
            "缴纳",
            "代缴",
            "社保基数",
            "社保手续",
            "转正后缴纳",
            "试用期后缴纳",
        ],
        "strong_keywords": [
            "不缴纳社保",
            "自愿放弃社保",
            "社保由员工自行承担",
            "不缴纳住房公积金",
            "不为乙方办理社保",
        ],
        "related_clause_types": [
            "社会保险和福利待遇",
            "其他约定",
        ],
        # 收紧策略：
        # 1) 单独“社会保险/社保”不触发风险
        # 2) 需命中核心办理/缴纳词
        # 3) 对工伤/职业病/患病待遇、关系转移手续等场景降噪
        "required_any_keywords": [
            "缴纳",
            "代缴",
            "公积金",
            "住房公积金",
            "手续",
            "转正后缴纳",
            "试用期后缴纳",
            "社保手续",
        ],
        "required_combinations_any": [
            ["社会保险", "缴纳"],
            ["社保", "缴纳"],
            ["社保", "代缴"],
            ["社会保险", "手续"],
            ["社保", "手续"],
            ["住房", "公积金"],
            ["公积金", "缴纳"],
            ["转正后", "缴纳"],
            ["试用期后", "缴纳"],
        ],
        "blocked_phrases": [
            "工伤",
            "职业病",
            "患病",
            "非因工负伤",
            "医疗期",
            "社会保险关系转移手续",
            "档案和社会保险关系转移手续",
            "关系转移手续",
        ],
        "blocked_context_max_keyword_hits_to_filter": 3,
        "preliminary_level_strategy": {
            "high_if_strong_keyword_hit": True,
            "medium_if_keyword_hits_ge": 2,
            "low_if_keyword_hits_ge": 2,
        },
        "example_scenarios": [
            "员工签字放弃社保",
            "社保全部由员工个人承担",
        ],
    },
    {
        "risk_type": "竞业限制风险",
        "description": "竞业限制范围、期限、补偿、违约责任约定不当。",
        "keywords": [
            "竞业限制",
            "竞业",
            "离职后不得从事竞争业务",
            "同类企业",
            "限制从业",
            "限制就业",
            "竞业补偿",
            "补偿金",
            "竞业违约金",
        ],
        "strong_keywords": [
            "竞业限制",
            "竞业",
            "离职后不得从事竞争业务",
            "同类企业",
            "限制从业",
            "限制就业",
            "无需支付竞业补偿",
            "终身竞业限制",
            "离职后永久不得",
            "竞业限制不限地域",
            "违约金由公司单方决定",
        ],
        # 只有强表达命中才触发，避免“保密/商业秘密”误报为竞业限制。
        "require_strong_keyword": True,
        "related_clause_types": [
            "保密义务/竞业限制",
            "其他约定",
        ],
        "preliminary_level_strategy": {
            "high_if_strong_keyword_hit": True,
            "medium_if_keyword_hits_ge": 2,
            "low_if_keyword_hits_ge": 1,
        },
        "example_scenarios": [
            "竞业限制无补偿条款",
            "竞业限制范围和期限明显过宽",
        ],
    },
    {
        "risk_type": "培训服务期风险",
        "description": "培训服务期约定与违约责任可能不对等或过重。",
        "keywords": [
            "培训",
            "服务期",
            "专项培训",
            "培训费用",
            "培训协议",
            "违约金",
            "赔偿",
        ],
        "strong_keywords": [
            "服务期无限延长",
            "违约金按培训费数倍",
            "任何离职均需全额赔偿",
            "培训费由员工全部承担",
        ],
        # 培训服务期风险需要“培训词 + 约束性词”同时命中。
        "keyword_groups": {
            "training_terms": [
                "培训",
                "专项培训",
                "培训费用",
                "培训协议",
            ],
            "constraint_terms": [
                "服务期",
                "约定服务期",
                "服务期限",
                "协议",
                "违约责任",
                "违约金",
                "赔偿",
            ],
        },
        "require_keyword_groups_all": ["training_terms", "constraint_terms"],
        "related_clause_types": [
            "培训服务期",
            "职业培训和劳动保护",
            "其他约定",
        ],
        "preliminary_level_strategy": {
            "high_if_strong_keyword_hit": True,
            "medium_if_keyword_hits_ge": 2,
            "low_if_keyword_hits_ge": 1,
        },
        "example_scenarios": [
            "培训后离职需支付明显过高违约金",
            "服务期条款未约定计算和扣减规则",
        ],
    },
    {
        "risk_type": "单方调岗调薪风险",
        "description": "公司单方调整岗位、地点、薪酬或考核结果影响工资的权限过宽。",
        "keywords": [
            "调岗",
            "调薪",
            "岗位调整",
            "薪酬调整",
            "工作地点调整",
            "服从公司安排",
            "绩效考核",
        ],
        "strong_keywords": [
            "公司可单方调岗",
            "公司可单方调薪",
            "无条件服从调岗",
            "不同意调岗视为自动离职",
            "公司有权随时调整岗位和薪酬",
        ],
        "related_clause_types": [
            "工作内容和工作地点",
            "劳动报酬",
            "其他约定",
        ],
        "preliminary_level_strategy": {
            "high_if_strong_keyword_hit": True,
            "medium_if_keyword_hits_ge": 2,
            "low_if_keyword_hits_ge": 1,
        },
        "example_scenarios": [
            "约定公司可随时单方调整岗位与工资",
            "不同意调岗即视为员工违约或离职",
        ],
    },
]


RISK_TYPES = [rule["risk_type"] for rule in RISK_RULES]
