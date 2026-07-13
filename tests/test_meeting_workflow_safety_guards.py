#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import ast
import json
from pathlib import Path

from src.modules.database import database_api
from src.modules.database.database_manager import DatabaseManager


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_API = PROJECT_ROOT / "src/modules/database/database_api.py"
ASR_PANEL = PROJECT_ROOT / "ui/src/components/AsrPanel.vue"
RECORD_PAGE = PROJECT_ROOT / "ui/src/components/RecordPage.vue"
MEETING_DETAIL = PROJECT_ROOT / "ui/src/components/MeetingDetail.vue"
RICH_TEXT_EDITOR = PROJECT_ROOT / "ui/src/components/RichTextEditor.vue"


def _python_function_source(path: Path, function_name: str) -> str:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            return ast.get_source_segment(source, node).replace("\r\n", "\n").strip()
    raise AssertionError(f"Function {function_name} not found in {path}")


def _const_arrow_block(source: str, const_name: str) -> str:
    marker = f"const {const_name} ="
    start = source.find(marker)
    assert start >= 0, f"{const_name} not found"

    brace_start = source.find("{", start)
    assert brace_start >= 0, f"{const_name} has no function body"

    depth = 0
    for index in range(brace_start, len(source)):
        char = source[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start:index + 1]

    raise AssertionError(f"{const_name} function body is not closed")


def test_summary_prompts_keep_fact_and_no_reasoning_guards():
    prompt_functions = {
        "summary": database_api._create_summary_system_prompt,
        "segment": lambda: database_api._create_segment_system_prompt(1, 2),
        "merge": database_api._create_merge_system_prompt,
        "single_segment_final": database_api._create_single_segment_final_system_prompt,
    }

    for name, build_prompt in prompt_functions.items():
        prompt = build_prompt()
        assert "不得虚构" in prompt or "绝对不添加、推测或虚构" in prompt
        assert "<think>" in prompt or "思考标签" in prompt
        assert "推理过程" in prompt
        assert "/no_think" in prompt

        if name == "summary":
            assert "会议摘要用300-450字" in prompt
            assert "最少20条" in prompt
            assert "YYYY/MM/DD" in prompt
        elif name == "segment":
            assert "请为这部分内容生成结构化的纪要片段，重点关注" in prompt
        elif name == "merge":
            assert "标准输出格式" in prompt
        elif name == "single_segment_final":
            assert "会议摘要用300-450字" in prompt
            assert "最少20条" in prompt
            assert "YYYY/MM/DD" in prompt


def test_project_review_summary_template_changes_final_and_merge_prompts_only():
    final_prompt = database_api._create_summary_system_prompt(template_id="project_review")
    merge_prompt = database_api._create_merge_system_prompt(template_id="project_review")
    segment_prompt = database_api._create_segment_system_prompt(1, 2)

    for prompt in (final_prompt, merge_prompt):
        assert "方案评审型会议纪要" in prompt
        assert "会议主题：" in prompt
        assert "发言人：" in prompt
        assert "四、待办事项" in prompt
        assert "不要输出“会议基本信息”“主要议题讨论”等标准模板标题" in prompt
        assert "/no_think" in prompt

    assert "方案评审型会议纪要" not in segment_prompt
    assert "本段落主要议题" in segment_prompt


def test_qwen3_no_think_marker_is_model_scoped(monkeypatch):
    captured_payloads = []

    def fake_call_llm_gateway(payload):
        captured_payloads.append(payload)
        return {"content": "改写后的纪要"}

    monkeypatch.setattr(database_api, "_call_llm_gateway", fake_call_llm_gateway)

    database_api._revise_minutes_summary(
        "原纪要",
        "压缩一点",
        {"llm": {"serviceType": "vllm", "config": {"model": "gpt-4o"}}}
    )
    assert "/no_think" not in captured_payloads[-1]["messages"][0]["content"]
    assert "/no_think" not in captured_payloads[-1]["messages"][1]["content"]

    database_api._revise_minutes_summary(
        "原纪要",
        "压缩一点",
        {"llm": {"serviceType": "ollama", "config": {"model": "qwen3:30b-a3b-q4_K_M"}}}
    )
    assert captured_payloads[-1]["messages"][0]["content"].endswith("/no_think")
    assert captured_payloads[-1]["messages"][1]["content"].endswith("/no_think")


def test_summary_defaults_use_deepseek_xinference_backend(tmp_path, monkeypatch):
    test_db = DatabaseManager(str(tmp_path / "wyl_asr.db"))
    monkeypatch.setattr(database_api, "db", test_db)

    config = database_api._get_stored_llm_config(include_secrets=False)

    assert config["activeServiceType"] == "xinference"
    assert config["services"]["xinference"]["endpoint"] == "http://10.1.0.26:9997/v1/chat/completions"
    assert config["services"]["xinference"]["model"] == "DeepSeek-R1-671B-1"
    assert database_api.SUMMARY_MODEL_CONFIG["max_context_tokens"] == 128000
    assert database_api.SUMMARY_MODEL_CONFIG["max_output_tokens"] == 64000

    payload = database_api._build_summary_llm_payload(
        [{"role": "user", "content": "测试"}],
        {},
        {}
    )
    normalized = database_api._extract_llm_request(payload)
    request_body, _ = database_api._build_llm_request_body(normalized)

    assert normalized["service_type"] == "xinference"
    assert normalized["endpoint"] == "http://10.1.0.26:9997/v1/chat/completions"
    assert normalized["model"] == "DeepSeek-R1-671B-1"
    assert request_body["max_tokens"] == 64000
    assert request_body["stream"] is False


def test_legacy_default_llm_config_migrates_to_deepseek(tmp_path, monkeypatch):
    test_db = DatabaseManager(str(tmp_path / "wyl_asr.db"))
    monkeypatch.setattr(database_api, "db", test_db)
    test_db.set_config(
        key="llm_config",
        value=json.dumps(database_api.LEGACY_DEFAULT_LLM_CONFIG, ensure_ascii=False),
        description="旧默认配置"
    )

    config = database_api._get_stored_llm_config(include_secrets=False)

    assert config["activeServiceType"] == "xinference"
    assert config["services"]["xinference"]["endpoint"] == "http://10.1.0.26:9997/v1/chat/completions"
    assert config["services"]["xinference"]["model"] == "DeepSeek-R1-671B-1"


def test_summary_segmentation_uses_fixed_character_budget():
    system_tokens = database_api._estimate_summary_tokens(database_api._create_summary_system_prompt())
    text = "\n\n".join(["这是一个会议段落。" * 1000 for _ in range(8)])

    segments = database_api._segment_summary_text(text, system_tokens)

    assert len(segments) == 3
    assert all(
        database_api._summary_text_char_count(segment) <= database_api.SUMMARY_MODEL_CONFIG["segment_max_chars"]
        for segment in segments
    )


def test_summary_backend_single_segment_fallback_generates_final_minutes(monkeypatch):
    task_id = "single-segment-task"
    with database_api.summary_tasks_lock:
        database_api.summary_tasks[task_id] = {
            "task_id": task_id,
            "status": "queued",
            "updated_at_ts": 0
        }

    direct_calls = []
    single_final_calls = []

    def fake_direct_summary(transcript, llm_config, generation_options, custom_requirements=None, template_id=None):
        direct_calls.append(transcript)
        raise database_api.APIError("CONTENT_TOO_LONG", 413)

    def fake_single_segment_final(transcript, llm_config, generation_options, custom_requirements=None, template_id=None):
        single_final_calls.append(transcript)
        return "最终正式会议纪要"

    monkeypatch.setattr(database_api, "_generate_direct_summary_backend", fake_direct_summary)
    monkeypatch.setattr(database_api, "_generate_single_segment_final_summary_backend", fake_single_segment_final)
    monkeypatch.setattr(database_api, "_segment_summary_text", lambda transcript, system_tokens: ["单段转录文本"])
    monkeypatch.setattr(
        database_api,
        "_generate_segment_summary_backend",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("不应调用分段片段生成"))
    )
    monkeypatch.setattr(
        database_api,
        "_merge_summary_segments_backend",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("单段不应调用合并"))
    )

    database_api._generate_summary_backend(task_id, {"transcript": "超长转录文本"})

    with database_api.summary_tasks_lock:
        task = database_api.summary_tasks.pop(task_id)

    assert task["status"] == "succeeded"
    assert task["result"]["summary"] == "最终正式会议纪要"
    assert task["result"]["mode"] == "direct_after_segmentation"
    assert direct_calls == ["超长转录文本"]
    assert single_final_calls == ["单段转录文本"]


def test_summary_backend_direct_generation_uses_regular_final_prompt(monkeypatch):
    task_id = "direct-task"
    with database_api.summary_tasks_lock:
        database_api.summary_tasks[task_id] = {
            "task_id": task_id,
            "status": "queued",
            "updated_at_ts": 0
        }

    direct_calls = []

    def fake_direct_summary(transcript, llm_config, generation_options, custom_requirements=None, template_id=None):
        direct_calls.append(transcript)
        return "普通最终会议纪要"

    monkeypatch.setattr(database_api, "_generate_direct_summary_backend", fake_direct_summary)
    monkeypatch.setattr(
        database_api,
        "_generate_single_segment_final_summary_backend",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("直接生成不应调用单段最终提示词"))
    )

    database_api._generate_summary_backend(task_id, {"transcript": "短转录文本"})

    with database_api.summary_tasks_lock:
        task = database_api.summary_tasks.pop(task_id)

    assert task["status"] == "succeeded"
    assert task["result"]["summary"] == "普通最终会议纪要"
    assert task["result"]["mode"] == "direct"
    assert direct_calls == ["短转录文本"]


def test_summary_backend_long_transcript_uses_character_segmentation(monkeypatch):
    task_id = "long-character-task"
    with database_api.summary_tasks_lock:
        database_api.summary_tasks[task_id] = {
            "task_id": task_id,
            "status": "queued",
            "updated_at_ts": 0
        }

    segmented_calls = []

    monkeypatch.setattr(
        database_api,
        "_generate_direct_summary_backend",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("长文本不应先直传"))
    )

    def fake_segmented_summary(task_id_arg, transcript, llm_config, generation_options, custom_requirements=None, template_id=None, stage_prefix=None):
        segmented_calls.append((task_id_arg, transcript, template_id, stage_prefix))
        return "分段会议纪要", "segmented", 4

    monkeypatch.setattr(database_api, "_generate_segmented_summary_backend", fake_segmented_summary)

    transcript = "这是会议内容。" * 9000
    database_api._generate_summary_backend(task_id, {"transcript": transcript})

    with database_api.summary_tasks_lock:
        task = database_api.summary_tasks.pop(task_id)

    assert task["status"] == "succeeded"
    assert task["result"]["summary"] == "分段会议纪要"
    assert task["result"]["mode"] == "segmented"
    assert task["result"]["segments_count"] == 4
    assert segmented_calls == [(task_id, transcript, "standard", segmented_calls[0][3])]
    assert "超过" in segmented_calls[0][3]


def test_summary_single_segment_final_generation_adapts_output_budget(monkeypatch):
    captured = {}

    def fake_call_summary_llm(messages, llm_config, generation_options, temperature=None, top_p=None):
        captured["max_tokens"] = generation_options["max_tokens"]
        captured["messages"] = messages
        return "会议纪要"

    monkeypatch.setattr(database_api, "_call_summary_llm", fake_call_summary_llm)

    transcript = "这是会议内容。" * 12000
    summary = database_api._generate_single_segment_final_summary_backend(transcript, {}, {})

    assert summary == "会议纪要"
    assert database_api.SUMMARY_MODEL_CONFIG["min_output_tokens"] <= captured["max_tokens"] < 64000
    assert "会议摘要用300-450字" in captured["messages"][0]["content"]
    assert "最少20条" in captured["messages"][0]["content"]
    assert captured["messages"][0]["content"].endswith("/no_think")
    assert captured["messages"][1]["content"].endswith("/no_think")


def test_llm_response_strips_thinking_content():
    content = "<think>这里是推理过程</think>\n\n## 会议摘要\n只保留正文"

    assert database_api._strip_llm_thinking_content(content) == "## 会议摘要\n只保留正文"


def test_llm_response_strips_unlabeled_reasoning_preface():
    content = (
        "好的，我现在需要根据用户提供的会议转录内容生成会议纪要。首先要逐项分析。\n\n"
        "会议基本信息：检查转录中是否有明确提到的时间、地点和参与者。\n\n"
        "## 会议摘要（300字）\n只保留正式纪要"
    )

    assert database_api._strip_llm_thinking_content(content) == "## 会议摘要（300字）\n只保留正式纪要"


def test_llm_response_skips_reasoning_section_sentences_before_plain_heading():
    content = (
        "好的，我现在需要根据用户提供的会议转录内容生成会议纪要。\n\n"
        "会议基本信息：检查转录中是否有明确提到的时间、地点和参与者。\n\n"
        "会议基本信息：\n正式纪要正文"
    )

    assert database_api._strip_llm_thinking_content(content) == "会议基本信息：\n正式纪要正文"


def test_summary_input_strips_translation_lines_without_removing_short_terms():
    transcript = (
        "说话人1\n"
        "这里讨论督办系统界面调整。\n"
        "This part discusses the interface adjustment of the supervision system and repeats the Chinese transcript as an English translation.\n\n"
        "说话人2\n"
        "这里提到 DeepSeek-R1-671B-1 模型。\n"
        "vLLM API\n"
        "继续讨论用章流程。"
    )

    cleaned = database_api._strip_translations_for_summary_text(transcript)

    assert "repeats the Chinese transcript as an English translation" not in cleaned
    assert "DeepSeek-R1-671B-1" in cleaned
    assert "vLLM API" in cleaned
    assert "继续讨论用章流程" in cleaned


def test_upload_workflow_stays_isolated_from_realtime_recording():
    source = ASR_PANEL.read_text(encoding="utf-8")
    toggle_recording = _const_arrow_block(source, "toggleRecording")
    upload_change = _const_arrow_block(source, "handleAudioUploadChange")

    assert "store.startRecording()" in toggle_recording
    assert "store.stopRecording()" in toggle_recording
    assert "uploadApi.recognizeAudio" not in toggle_recording

    assert "uploadApi.recognizeAudio" in upload_change
    assert source.count("uploadApi.recognizeAudio") == 1
    assert "recognitionMode: 'realtime'" in source
    assert 'v-if="!isUploadMode"' in source


def test_meeting_save_persists_generated_minutes_without_generating_detail_artifacts():
    source = RECORD_PAGE.read_text(encoding="utf-8")
    save_meeting = _const_arrow_block(source, "saveMeeting")
    build_transcription = _const_arrow_block(source, "buildTranscriptionContent")

    assert "transcriptionContent: fullTranscriptionContent" in save_meeting
    assert "const generatedMeetingMinutes = editorContent.value.trim()" in save_meeting
    assert "if (generatedMeetingMinutes)" in save_meeting
    assert "meetingData.meetingMinutes = generatedMeetingMinutes" in save_meeting
    assert "meetingData.summary = generatedMeetingMinutes" in save_meeting
    assert "generateSummary" not in save_meeting
    assert "generateEmotionAnalysis" not in save_meeting
    assert "recognitionMode: recognitionMode.value" in save_meeting
    assert "transcriptionSource: isUploadMode.value ? 'upload' : 'realtime'" in save_meeting
    assert "router.push" in save_meeting
    assert "segment.translation" in build_transcription
    assert "翻译：" in build_transcription


def test_save_documents_persists_minutes_when_payload_has_generated_summary(tmp_path, monkeypatch):
    test_db = DatabaseManager(str(tmp_path / "wyl_asr.db"))
    monkeypatch.setattr(database_api, "db", test_db)
    monkeypatch.chdir(tmp_path)
    client = database_api.app.test_client()

    response = client.post(
        "/api/meetings/save-documents",
        json={
            "title": "已生成纪要会议",
            "transcriptionContent": "实时转写文本",
            "meetingMinutes": "已生成会议纪要",
            "summary": "已生成会议纪要",
            "recognitionMode": "realtime",
        }
    )
    assert response.status_code == 201
    payload = response.get_json()["data"]

    assert any(item["type"] == "minutes" for item in payload["saved_files"])
    minutes = test_db.get_meeting_minutes(payload["meeting_id"])
    assert minutes is not None
    assert minutes["summary"] == "已生成会议纪要"


def test_meeting_detail_pending_minutes_can_be_generated():
    source = MEETING_DETAIL.read_text(encoding="utf-8")
    generate_minutes = _const_arrow_block(source, "handleGenerateMinutes")

    assert "generateSummary" in generate_minutes
    assert "options.meetingId = meeting.id" in generate_minutes
    assert "fetchMinutesVersions(meeting.id)" in generate_minutes
    assert "selectedArtifactId.value = 'minutes'" in generate_minutes
    assert "canGenerateMinutes" in source
    assert "生成纪要" in source
    assert "可生成" in source


def test_record_page_right_editor_generates_restored_minutes_with_meeting_context():
    record_source = RECORD_PAGE.read_text(encoding="utf-8")
    editor_source = RICH_TEXT_EDITOR.read_text(encoding="utf-8")
    generate_summary = _const_arrow_block(editor_source, "handleGenerateSummary")

    assert ':meeting-id="restoredMeetingId"' in record_source
    assert ':summary-transcript="summaryTranscriptForEditor"' in record_source
    assert '@summary-generated="handleSummaryGenerated"' in record_source
    assert "restoredTranscriptionText.value.trim() || buildTranscriptionContent()" in record_source

    assert "props.summaryTranscript" in editor_source
    assert "options.meetingId = props.meetingId" in generate_summary
    assert "selectedSummaryTemplate.value" in generate_summary
    assert "emit('summary-generated', summary)" in generate_summary


def test_realtime_save_detail_reports_realtime_transcription_source(tmp_path, monkeypatch):
    test_db = DatabaseManager(str(tmp_path / "wyl_asr.db"))
    monkeypatch.setattr(database_api, "db", test_db)
    monkeypatch.chdir(tmp_path)
    client = database_api.app.test_client()

    response = client.post(
        "/api/meetings/save-documents",
        json={
            "title": "实时转写会议",
            "transcriptionContent": "实时转写文本",
            "recognitionMode": "realtime",
        }
    )
    assert response.status_code == 201
    payload = response.get_json()["data"]
    assert payload["transcription_source"] == "realtime"

    detail_response = client.get(f"/api/meetings/{payload['meeting_id']}")
    assert detail_response.status_code == 200
    detail = detail_response.get_json()["data"]
    assert detail["transcription_source"] == "realtime"
    assert detail["recognitionMode"] == "realtime"

    upload_response = client.get(f"/api/meetings/{payload['meeting_id']}/uploaded-transcription")
    assert upload_response.status_code == 200
    upload_payload = upload_response.get_json()["data"]
    assert upload_payload["source"] == "realtime"
    assert upload_payload["segments"] == []


def test_uploaded_result_persistence_does_not_write_realtime_transcripts(tmp_path, monkeypatch):
    test_db = DatabaseManager(str(tmp_path / "wyl_asr.db"))
    monkeypatch.setattr(database_api, "db", test_db)
    monkeypatch.chdir(tmp_path)

    task_id = database_api._create_upload_task(
        file_name="sample.wav",
        saved_file_name="sample.wav",
        saved_path=str(tmp_path / "sample.wav"),
        language="zh",
        enable_speaker_diarization=True,
        enable_voiceprint_matching=False,
        enable_translation=False,
        speaker_top_k=3,
        expected_speakers=None,
        min_speakers=None,
        max_speakers=None,
        hotword_text="",
        media_info={}
    )

    database_api._save_upload_result_for_task(task_id, {
        "segments": [
            {
                "speaker": "说话人1",
                "text": "上传识别文本",
                "startMs": 0,
                "endMs": 1000,
                "mode": "uploaded-audio"
            }
        ],
        "plain_text": "上传识别文本"
    })

    realtime_rows = test_db.execute_query("SELECT * FROM speech_recognition_results")
    upload_rows = test_db.execute_query("SELECT * FROM uploaded_audio_segments WHERE task_id = ?", (task_id,))

    assert realtime_rows == []
    assert len(upload_rows) == 1
    assert upload_rows[0]["text"] == "上传识别文本"

    client = database_api.app.test_client()
    response = client.post(
        "/api/meetings/save-documents",
        json={
            "title": "上传转写会议",
            "transcriptionContent": "说话人1: 上传识别文本",
            "recognitionMode": "upload",
            "uploadTaskId": task_id,
        }
    )
    assert response.status_code == 201
    payload = response.get_json()["data"]
    assert payload["transcription_source"] == "upload"

    detail_response = client.get(f"/api/meetings/{payload['meeting_id']}")
    assert detail_response.status_code == 200
    detail = detail_response.get_json()["data"]
    assert detail["transcription_source"] == "upload"
    assert detail["recognitionMode"] == "upload"
    assert detail["uploadTaskId"] == task_id

    upload_response = client.get(f"/api/meetings/{payload['meeting_id']}/uploaded-transcription")
    assert upload_response.status_code == 200
    upload_payload = upload_response.get_json()["data"]
    assert upload_payload["source"] == "upload"
    assert upload_payload["task_id"] == task_id
    assert upload_payload["segments"][0]["mode"] == "uploaded-audio"
    assert upload_payload["segments"][0]["text"] == "上传识别文本"
    assert "上传识别文本" in upload_payload["text"]
