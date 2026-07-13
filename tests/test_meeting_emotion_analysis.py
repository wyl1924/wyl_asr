#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from src.modules.database import database_api


def test_build_emotion_analysis_scores_transcript_signals():
    transcript = """
张三: 我对这个结果很满意，也感谢大家支持。
李四: 我担心上线风险比较高，可能会有延迟，需要再确认。
张三: 这次进展很顺利，我有信心继续推进。
"""

    analysis = database_api._build_emotion_analysis(transcript)

    assert analysis["segment_count"] == 3
    assert analysis["speaker_count"] == 2
    assert len(analysis["speaker_analyses"]) == 2
    assert analysis["speaker_analyses"][0]["main_signal_label"]
    assert analysis["scores"]["positive"] >= 2
    assert analysis["scores"]["negative"] >= 1
    assert analysis["scores"]["risk"] >= 1
    assert analysis["scores"]["uncertain"] >= 2
    assert analysis["highlights"]


def test_build_emotion_markdown_contains_product_sections():
    markdown = database_api._build_emotion_markdown(
        "项目例会",
        "张三: 我担心上线风险，需要确认。"
    )

    assert "# 项目例会 - 情绪分析" in markdown
    assert "## 总体判断" in markdown
    assert "## 指标概览" in markdown
    assert "## 说话人分布" in markdown
    assert "## 逐人分析" in markdown
    assert "### 张三" in markdown
    assert "## 重点片段" in markdown
    assert "没有明确证据时不做情绪推断" in markdown


def test_build_emotion_analysis_handles_empty_transcript():
    analysis = database_api._build_emotion_analysis("")

    assert analysis["segment_count"] == 0
    assert analysis["speaker_count"] == 0
    assert analysis["tone"] == "证据不足"
    assert analysis["highlights"] == []


def test_build_emotion_analysis_handles_single_speaker():
    analysis = database_api._build_emotion_analysis(
        "张三: 我对结果很满意，也感谢大家支持。"
    )

    assert analysis["segment_count"] == 1
    assert analysis["speaker_count"] == 1
    assert analysis["speaker_stats"][0]["speaker"] == "张三"
    assert analysis["speaker_stats"][0]["tone"]
    assert analysis["scores"]["positive"] >= 1


def test_build_emotion_analysis_handles_english_transcript():
    analysis = database_api._build_emotion_analysis(
        "Alice: The rollout is smooth and the team will follow up.\n"
        "Bob: There is a risk of delay and pressure this week."
    )

    assert analysis["speaker_count"] == 2
    assert analysis["scores"]["positive"] >= 1
    assert analysis["scores"]["risk"] >= 2
    assert analysis["scores"]["negative"] >= 1


def test_build_emotion_analysis_keeps_neutral_text_neutral():
    analysis = database_api._build_emotion_analysis(
        "张三: 今天介绍系统菜单。\n李四: 下一页展示字段定义。"
    )

    assert analysis["scores"] == {
        "positive": 0,
        "negative": 0,
        "risk": 0,
        "uncertain": 0,
    }
    assert analysis["tone"] == "证据不足"
    assert analysis["highlights"] == []


def test_build_emotion_analysis_handles_long_transcript():
    transcript = "\n".join(
        f"说话人{i % 3}: 我担心第{i}项有风险，可能会延迟，需要确认。"
        for i in range(120)
    )

    analysis = database_api._build_emotion_analysis(transcript)

    assert analysis["segment_count"] == 120
    assert analysis["speaker_count"] == 3
    assert len(analysis["highlights"]) <= 6
    assert analysis["scores"]["risk"] >= 120
    assert analysis["scores"]["negative"] >= 120
    assert analysis["scores"]["uncertain"] >= 120


def test_build_emotion_analysis_handles_uploaded_speaker_blocks():
    transcript = """
**张三** [00:00 - 00:03]
这个方案很顺利，我比较满意。

翻译：The plan is smooth.

**李四** [00:04 - 00:08]
但是我担心上线风险比较高，可能会有延迟，需要再确认。
"""

    analysis = database_api._build_emotion_analysis(transcript)
    speakers = {item["speaker"]: item for item in analysis["speaker_analyses"]}

    assert analysis["segment_count"] == 2
    assert analysis["speaker_count"] == 2
    assert "张三" in speakers
    assert "李四" in speakers
    assert speakers["张三"]["scores"]["positive"] >= 1
    assert speakers["李四"]["scores"]["negative"] >= 1
    assert speakers["李四"]["scores"]["risk"] >= 2
    assert all(item["speaker"] != "翻译" for item in analysis["speaker_analyses"])
