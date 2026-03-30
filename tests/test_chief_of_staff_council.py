"""Regression coverage for scripts/chief_of_staff_council.py."""

from __future__ import annotations

import pathlib
import sys
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import chief_of_staff_council as council  # type: ignore


class ChiefOfStaffCouncilTests(unittest.TestCase):
    def test_simple_ack_stays_direct_reply(self) -> None:
        result = council.analyze_with_council("收到")
        self.assertEqual(result["classification"], "direct_reply")
        self.assertEqual(result["council"]["chief"]["decision"], "direct_reply")

    def test_general_question_stays_direct_reply(self) -> None:
        result = council.analyze_with_council("1+1什么时候等于3")
        self.assertEqual(result["classification"], "direct_reply")
        self.assertFalse(result["shouldCreateTask"])
        self.assertEqual(result["council"]["chief"]["decision"], "direct_reply")

    def test_vague_small_change_stays_direct_reply(self) -> None:
        result = council.analyze_with_council("帮我把这个按钮颜色改一下")
        self.assertEqual(result["classification"], "direct_reply")
        self.assertFalse(result["shouldCreateTask"])

    def test_setup_request_stays_direct_handle(self) -> None:
        result = council.analyze_with_council("安装keyoku-ai项目")
        self.assertEqual(result["classification"], "direct_handle")
        self.assertFalse(result["shouldCreateTask"])
        self.assertEqual(result["directAgentHint"], "chief_of_staff")

    def test_setup_request_reuses_completed_install(self) -> None:
        def fake_read_preferred_json(name, default):
            if name == "tasks_source.json":
                return [
                    {
                        "id": "JJC-20260321-003",
                        "state": "Done",
                        "title": "安装 keyoku-ai/keyoku 项目",
                        "output": "/tmp/keyoku",
                        "detail": "https://github.com/keyoku-ai/keyoku",
                    }
                ]
            return default

        with mock.patch.object(council, "read_preferred_json", side_effect=fake_read_preferred_json):
            result = council.analyze_with_council("安装下这个https://github.com/keyoku-ai/keyoku")

        self.assertEqual(result["classification"], "direct_handle")
        self.assertEqual(result["historicalMatch"]["taskId"], "JJC-20260321-003")
        self.assertIn("禁止创建 JJC", result["guardrail"])

    def test_simple_weather_lookup_stays_direct_handle(self) -> None:
        result = council.analyze_with_council("查询明天的宁波天气")
        self.assertEqual(result["classification"], "direct_handle")
        self.assertFalse(result["shouldCreateTask"])
        self.assertEqual(result["flowMode"], "direct")
        self.assertEqual(result["dispatchAgent"], "chief_of_staff")
        self.assertEqual(result["council"]["router"]["semanticIntent"], "simple_lookup")
        self.assertTrue(result["council"]["router"]["semanticProfile"]["canChiefHandle"])
        self.assertEqual(result["council"]["router"]["semanticProfile"]["coordinationNeed"], "none")

    def test_complex_research_escalates_to_full_flow(self) -> None:
        result = council.analyze_with_council(
            "帮我调研多Agent协同框架，分析CrewAI、AutoGen、LangGraph的优缺点，并给出对比报告和落地建议"
        )
        self.assertEqual(result["classification"], "create_task")
        self.assertTrue(result["shouldCreateTask"])
        self.assertEqual(result["council"]["chief"]["decision"], "create_task")
        self.assertEqual(result["flowMode"], "full")
        self.assertEqual(result["dispatchAgent"], "planning")

    def test_engineering_fix_uses_light_flow(self) -> None:
        result = council.analyze_with_council("修复 dashboard 首页按钮点击无效的问题，直接改代码并验证结果")
        self.assertEqual(result["classification"], "direct_execute")
        self.assertFalse(result["shouldCreateTask"])
        self.assertEqual(result["flowMode"], "light")
        self.assertEqual(result["dispatchAgent"], "engineering")
        self.assertEqual(result["dispatchOrg"], "工程研发部")
        self.assertFalse(result["council"]["router"]["semanticProfile"]["canChiefHandle"])
        self.assertEqual(result["council"]["router"]["semanticProfile"]["coordinationNeed"], "single_department")

    def test_simple_content_title_task_uses_light_flow(self) -> None:
        result = council.analyze_with_council("把这篇公众号文章标题改得更像行业观察，但不要标题党")
        self.assertEqual(result["classification"], "direct_execute")
        self.assertFalse(result["shouldCreateTask"])
        self.assertEqual(result["flowMode"], "light")
        self.assertEqual(result["dispatchAgent"], "brand_content")
        self.assertEqual(result["dispatchOrg"], "品牌内容部")
        self.assertEqual(result["council"]["router"]["semanticIntent"], "simple_task")

    def test_simple_content_draft_task_uses_light_flow(self) -> None:
        result = council.analyze_with_council("帮我整理一版产品发布朋友圈文案，语气专业一点，直接给可发版本")
        self.assertEqual(result["classification"], "direct_execute")
        self.assertFalse(result["shouldCreateTask"])
        self.assertEqual(result["flowMode"], "light")
        self.assertEqual(result["dispatchAgent"], "brand_content")
        self.assertEqual(result["dispatchOrg"], "品牌内容部")
        self.assertEqual(result["council"]["router"]["semanticIntent"], "simple_task")

    def test_artifact_based_content_generation_uses_light_flow(self) -> None:
        result = council.analyze_with_council("基于这份活动方案，直接输出一版招商海报文案和报名引导语")
        self.assertEqual(result["classification"], "direct_execute")
        self.assertFalse(result["shouldCreateTask"])
        self.assertEqual(result["flowMode"], "light")
        self.assertEqual(result["dispatchAgent"], "brand_content")
        self.assertEqual(result["dispatchOrg"], "品牌内容部")

    def test_contract_risk_review_uses_light_flow(self) -> None:
        result = council.analyze_with_council("帮我看一下这个合作方案有没有明显风险")
        self.assertEqual(result["classification"], "direct_execute")
        self.assertFalse(result["shouldCreateTask"])
        self.assertEqual(result["flowMode"], "light")
        self.assertEqual(result["dispatchAgent"], "compliance_test")
        self.assertEqual(result["dispatchOrg"], "合规测试部")

    def test_org_memory_sync_uses_semantic_direct_execute(self) -> None:
        result = council.analyze_with_council(
            "联网工具受限的问题，所有Agent都可以使用Cli浏览器，写进每个Agent的记忆里"
        )
        self.assertEqual(result["classification"], "direct_execute")
        self.assertFalse(result["shouldCreateTask"])
        self.assertEqual(result["flowMode"], "light")
        self.assertEqual(result["dispatchAgent"], "engineering")
        self.assertEqual(result["dispatchOrg"], "工程研发部")
        self.assertEqual(result["council"]["router"]["semanticIntent"], "org_memory_sync")

    def test_bulk_soul_update_stays_direct_execute(self) -> None:
        result = council.analyze_with_council(
            "给所有 Agent 的 SOUL.md 统一补一条浏览器 CLI 回退规则，并同步到每个工作区"
        )
        self.assertEqual(result["classification"], "direct_execute")
        self.assertFalse(result["shouldCreateTask"])
        self.assertEqual(result["dispatchAgent"], "engineering")
        self.assertEqual(result["dispatchOrg"], "工程研发部")

    def test_global_execution_policy_update_stays_direct_execute(self) -> None:
        result = council.analyze_with_council(
            "统一更新所有智能体提示词，新增交付前必须自检这条执行规范"
        )
        self.assertEqual(result["classification"], "direct_execute")
        self.assertEqual(result["flowMode"], "light")
        self.assertEqual(result["dispatchAgent"], "engineering")
        self.assertEqual(result["dispatchOrg"], "工程研发部")

    def test_bulk_department_boundary_update_stays_direct_execute(self) -> None:
        result = council.analyze_with_council(
            "批量更新部门职责说明，统一补充总裁办与产品规划部的角色边界"
        )
        self.assertEqual(result["classification"], "direct_execute")
        self.assertFalse(result["shouldCreateTask"])
        self.assertEqual(result["flowMode"], "light")
        self.assertEqual(result["dispatchAgent"], "engineering")
        self.assertEqual(result["dispatchOrg"], "工程研发部")

    def test_global_tool_ban_stays_direct_execute(self) -> None:
        result = council.analyze_with_council(
            "所有 Agent 禁用 zhipu-web-search，统一改成浏览器 CLI 回退"
        )
        self.assertEqual(result["classification"], "direct_execute")
        self.assertFalse(result["shouldCreateTask"])
        self.assertEqual(result["dispatchAgent"], "engineering")
        self.assertEqual(result["dispatchOrg"], "工程研发部")

    def test_public_content_uses_light_flow_with_review_gate(self) -> None:
        result = council.analyze_with_council("写一条面向外部公开发布的评论，结合今天的新闻整理成可直接发布的内容")
        self.assertEqual(result["classification"], "direct_execute")
        self.assertEqual(result["flowMode"], "light")
        self.assertEqual(result["dispatchAgent"], "brand_content")
        self.assertTrue(result["finalReviewRequired"])
        self.assertTrue(result["council"]["router"]["semanticProfile"]["finalReviewRequired"])
        self.assertEqual(result["council"]["router"]["semanticProfile"]["coordinationNeed"], "single_department")

    def test_cross_department_industry_research_uses_full_flow(self) -> None:
        result = council.analyze_with_council("调研一个产业，可能涉及技术、市场、安全等多个部门，就让每个部门做自己擅长的事")
        self.assertEqual(result["classification"], "create_task")
        self.assertEqual(result["flowMode"], "full")
        self.assertEqual(result["dispatchAgent"], "planning")
        self.assertEqual(result["council"]["router"]["semanticProfile"]["coordinationNeed"], "cross_department")
        self.assertFalse(result["council"]["router"]["semanticProfile"]["canChiefHandle"])


if __name__ == "__main__":
    unittest.main()
