"""
自动化评测脚本 eval_runner.py (基于 Step 4 验收要求)
加载 tests/agent_cases.json 评测集，量化意图识别准确率、动作分类率与槽位提取准确率。
"""
import sys
import os
import json
import asyncio

# 添加搜索路径
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
AGENT_SERVICE_DIR = os.path.join(PROJECT_ROOT, "agent_service")

if AGENT_SERVICE_DIR not in sys.path:
    sys.path.insert(0, AGENT_SERVICE_DIR)

from runtime.intent_router import IntentRouter
from runtime.context_manager import SessionContext


async def run_evaluation():
    cases_path = os.path.join(CURRENT_DIR, "agent_cases.json")
    if not os.path.exists(cases_path):
        print(f"[ERROR] 找不到用例文件: {cases_path}")
        return False

    with open(cases_path, "r", encoding="utf-8") as f:
        cases = json.load(f)

    total = len(cases)
    intent_correct = 0
    action_correct = 0
    params_correct = 0
    params_checked = 0

    print("=" * 70)
    print(f"🚀 开始执行 Fluent Music Agent Step 4 自动化基准评测 (共 {total} 个用例)")
    print("=" * 70)

    # 预设上下文（模拟上一轮推荐了《稻香》）
    mock_session = SessionContext(session_id="eval_mock")
    mock_session.add_assistant_message(
        "为你推荐了周杰伦的《稻香》和林俊杰的《豆浆油条》，希望你心情好起来！",
        recommended_tracks=[
            {"title": "稻香", "artist": "周杰伦", "index": 4},
            {"title": "豆浆油条", "artist": "林俊杰", "index": 40}
        ]
    )

    for case in cases:
        cid = case["id"]
        query = case["query"]
        exp_intent = case["expected_intent"]
        exp_action = case.get("expected_action", "")
        exp_params = case.get("expected_params", {})
        is_context_ref = case.get("is_context_referential", False)

        # 路由评测
        ctx = mock_session if is_context_ref else None
        res = await IntentRouter.route_intent(query, llm_provider=None, context_session=ctx)

        # 意图检验
        intent_match = (res.intent_type == exp_intent)
        if intent_match:
            intent_correct += 1

        # Action 检验
        action_match = (res.action == exp_action) or (not exp_action and not res.action)
        if action_match:
            action_correct += 1

        # 槽位检验
        param_match = True
        if exp_params:
            params_checked += 1
            for k, v in exp_params.items():
                if res.params.get(k) != v:
                    param_match = False
                    break
            if param_match:
                params_correct += 1
        elif is_context_ref:
            params_checked += 1
            # 上下文指代期望能解析出推荐的第一首或者标记为上下文指代
            if res.params.get("query") == "稻香" or res.params.get("is_context_referential"):
                params_correct += 1
            else:
                param_match = False

        status = "✅ PASS" if (intent_match and action_match and param_match) else "❌ FAIL"
        print(f"[{status}] {cid:22} | 输入: \"{query}\"")
        if status == "❌ FAIL":
            print(f"       期望: intent={exp_intent}, action={exp_action}, params={exp_params}")
            print(f"       实际: intent={res.intent_type}, action={res.action}, params={res.params}")

    intent_acc = (intent_correct / total) * 100
    action_acc = (action_correct / total) * 100
    param_acc = (params_correct / params_checked) * 100 if params_checked > 0 else 100.0

    print("=" * 70)
    print("📊 评测基准总结报告：")
    print(f"  - 总测试用例数: {total}")
    print(f"  - 意图分类准确率 (Intent Accuracy): {intent_acc:.1f}% ({intent_correct}/{total})")
    print(f"  - 动作分类准确率 (Action Accuracy): {action_acc:.1f}% ({action_correct}/{total})")
    print(f"  - 参数槽位准确率 (Params Accuracy): {param_acc:.1f}% ({params_correct}/{params_checked})")
    print("=" * 70)

    passed = (intent_acc >= 90.0 and action_acc >= 90.0)
    if passed:
        print("🎉 恭喜！Step 4 基准评测全部达到验收标准 (>= 90%)！")
    else:
        print("⚠️ 评测未达到 90% 基准线，请检查规则或提取算法。")

    return passed


if __name__ == "__main__":
    success = asyncio.run(run_evaluation())
    sys.exit(0 if success else 1)
