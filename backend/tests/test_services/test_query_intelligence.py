from app.services.query_intelligence import (
    analyze_query,
    build_response_instructions,
    extract_keywords,
)


def test_analyze_query_detects_comparison_intent():
    profile = analyze_query("请对比 CNN 和 RNN 的区别，并给出依据")

    assert profile.intent == "comparison"
    assert profile.answer_style == "compare"
    assert profile.requires_comparison is True
    assert profile.requires_evidence is True
    assert "cnn" in profile.keywords
    assert "rnn" in profile.keywords


def test_analyze_query_detects_process_intent():
    profile = analyze_query("RAG 的检索生成流程有哪些步骤？")

    assert profile.intent == "process"
    assert profile.answer_style == "steps"
    assert profile.requires_steps is True


def test_extract_keywords_filters_question_noise():
    keywords = extract_keywords("请总结这个文档如何降低幻觉风险？")

    assert "文档" not in keywords
    assert all("如何" not in keyword for keyword in keywords)
    assert any("幻觉" in keyword for keyword in keywords)


def test_extract_keywords_returns_clean_comparison_subjects_and_dimensions():
    keywords = extract_keywords(
        "监督学习、无监督学习和强化学习有什么区别？请从训练数据、学习方式和应用场景三个方面比较。"
    )

    assert keywords == [
        "监督学习",
        "无监督学习",
        "强化学习",
        "训练数据",
        "学习方式",
        "应用场景",
    ]


def test_build_response_instructions_matches_answer_style():
    profile = analyze_query("比较混合检索和向量检索的差异")
    instructions = build_response_instructions(profile)

    assert "对比表" in instructions
    assert "[编号]" in instructions
