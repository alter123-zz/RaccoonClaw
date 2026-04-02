import pathlib
import sys

SCRIPTS = pathlib.Path(__file__).resolve().parent.parent / 'scripts'
sys.path.insert(0, str(SCRIPTS))

import review_rubric as rubric


def test_resolve_app_dev_profile_adds_security_for_plugin_requirement():
    payload = rubric.build_brief('app_dev', '改造知乎助手插件，补上登录鉴权和外部接口回调')
    keys = [item['key'] for item in payload['requiredChecks']]
    assert 'security' in keys
    assert 'testing' in keys


def test_evaluate_plan_flags_missing_readiness_checks():
    payload = rubric.evaluate_plan(
        '1. 拆解需求\n2. 分配工程研发部\n3. 输出开发排期',
        mode_id='tech_service',
        requirement='为客户交付一套网站改造与上线方案',
    )
    assert payload['ok'] is False
    assert any(item['key'] == 'testing' for item in payload['missingFindings'])
