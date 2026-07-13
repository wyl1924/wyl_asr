#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pytest

from src.modules.database import database_api
from src.modules.config.arg_parser import parse_arguments
from src.modules.core.server_state import build_sensevoice_config, build_upload_asr_config, get_local_model_path


def _write_fake_model(root, name):
    model_dir = root / "models" / name
    model_dir.mkdir(parents=True)
    (model_dir / "config.yaml").write_text("model: fake\n", encoding="utf-8")
    (model_dir / "model.onnx").write_bytes(b"onnx")
    return model_dir


def test_upload_defaults_keep_large_limit_and_whole_file_threshold():
    assert database_api.app.config["MAX_CONTENT_LENGTH"] == 2 * 1024 * 1024 * 1024
    assert database_api.UPLOAD_ASR_DEFAULT_MAX_MB == 2048
    max_audio_bytes, asr_unit_bytes = database_api._get_upload_asr_limits()
    assert max_audio_bytes == 2 * 1024 * 1024 * 1024
    assert asr_unit_bytes == max_audio_bytes


def test_upload_asr_config_defaults_to_official_internal_speaker_path(tmp_path):
    vad_dir = _write_fake_model(tmp_path, "speech_fsmn_vad_zh-cn-16k-common-pytorch")
    punc_dir = _write_fake_model(tmp_path, "punc_ct-transformer_zh-cn-common-vocab272727-pytorch")
    spk_dir = _write_fake_model(tmp_path, "speech_campplus_sv_zh-cn_16k-common")
    args = parse_arguments([])

    assert args.upload_asr_enable_internal_speaker is True
    assert args.upload_asr_model == "iic/SenseVoiceSmall"
    config = build_upload_asr_config(args, str(tmp_path))
    assert config["vad_model"] == str(vad_dir)
    assert config["punc_model"] == str(punc_dir)
    assert config["spk_model"] == str(spk_dir)
    assert config["spk_mode"] == "vad_segment"
    assert args.upload_asr_merge_vad is False
    assert config["vad_kwargs"]["max_single_segment_time"] == 15000


def test_upload_asr_config_can_use_explicit_internal_speaker_mode(tmp_path):
    vad_dir = _write_fake_model(tmp_path, "speech_fsmn_vad_zh-cn-16k-common-pytorch")
    punc_dir = _write_fake_model(tmp_path, "punc_ct-transformer_zh-cn-common-vocab272727-pytorch")
    spk_dir = _write_fake_model(tmp_path, "speech_campplus_sv_zh-cn_16k-common")
    args = parse_arguments([
        "--upload_asr_enable_internal_speaker",
        "--upload_asr_punc_model", "ct-punc",
        "--upload_asr_spk_mode", "punc_segment",
    ])

    assert args.upload_asr_enable_internal_speaker is True
    config = build_upload_asr_config(args, str(tmp_path))
    assert config["vad_model"] == str(vad_dir)
    assert config["punc_model"] == str(punc_dir)
    assert config["spk_model"] == str(spk_dir)
    assert config["spk_mode"] == "punc_segment"
    assert config["vad_kwargs"]["max_single_segment_time"] == 15000


def test_upload_vad_short_name_resolves_to_local_model_alias(tmp_path):
    model_dir = tmp_path / "models" / "speech_fsmn_vad_zh-cn-16k-common-pytorch"
    model_dir.mkdir(parents=True)
    (model_dir / "config.yaml").write_text("model: vad\n", encoding="utf-8")
    (model_dir / "model.onnx").write_bytes(b"onnx")

    assert get_local_model_path("fsmn-vad", str(tmp_path)) == str(model_dir)


def test_upload_asr_internal_speaker_can_be_disabled_for_asr_only_mode():
    args = parse_arguments([
        "--no-upload_asr_enable_internal_speaker",
        "--upload_asr_spk_mode", "vad_segment",
        "--upload_asr_punc_model", "upload-punc",
        "--upload_asr_spk_model", "upload-spk",
    ])

    config = build_upload_asr_config(args, "/tmp/nonexistent-project-root")

    assert "spk_model" not in config
    assert "punc_model" not in config
    assert "spk_mode" not in config


def test_upload_asr_settings_do_not_leak_into_2pass_sensevoice_config(tmp_path):
    punc_dir = _write_fake_model(tmp_path, "punc_ct-transformer_zh-cn-common-vocab272727-pytorch")
    spk_dir = _write_fake_model(tmp_path, "speech_campplus_sv_zh-cn_16k-common")
    args = parse_arguments([
        "--upload_asr_enable_internal_speaker",
        "--upload_asr_spk_mode", "vad_segment",
        "--upload_asr_vad_max_single_segment_time", "12000",
        "--upload_asr_punc_model", "ct-punc",
        "--upload_asr_spk_model", "cam++",
    ])

    realtime_config = build_sensevoice_config(args)
    upload_config = build_upload_asr_config(args, str(tmp_path))

    assert realtime_config["vad_model"] is None
    assert "punc_model" not in realtime_config
    assert "spk_model" not in realtime_config
    assert "spk_mode" not in realtime_config
    assert upload_config["punc_model"] == str(punc_dir)
    assert upload_config["spk_model"] == str(spk_dir)
    assert upload_config["spk_mode"] == "vad_segment"
    assert upload_config["vad_kwargs"]["max_single_segment_time"] == 12000


def test_extract_asr_segments_accepts_official_sentence_field():
    segments = database_api._extract_asr_segments({
        "sentence_info": [
            {"sentence": "官网字段文本。", "start": 100, "end": 900, "spk": 0}
        ]
    })

    assert segments == [{
        "text": "官网字段文本。",
        "speaker_key": 0,
        "start_ms": 100,
        "end_ms": 900,
    }]


def test_upload_options_force_diarization_and_parse_voiceprint_flag():
    with database_api.app.test_request_context(
        "/api/upload/audio/recognize",
        method="POST",
        data={
            "enable_speaker_diarization": "false",
            "enable_voiceprint_matching": "true",
            "speaker_top_k": "5",
        },
    ):
        options = database_api._parse_upload_recognition_options()

    assert options["enable_speaker_diarization"] is True
    assert options["enable_voiceprint_matching"] is True
    assert options["speaker_top_k"] == 5


def test_modelscope_diarization_segments_are_normalized_with_speaker_labels():
    result = {
        "text_segments": [
            {"speaker": 0, "text": "第一句。", "start": 0.0, "end": 1.2},
            {"speaker": 1, "text": "第二句。", "start": 1.2, "end": 2.5},
            {"speaker": 0, "text": "第三句。", "start": 2500, "end": 3100},
        ]
    }

    segments = database_api._normalize_modelscope_diarization_segments(result, duration_seconds=10)

    assert [segment["speaker"] for segment in segments] == ["说话人1", "说话人2", "说话人1"]
    assert [segment["text"] for segment in segments] == ["第一句。", "第二句。", "第三句。"]
    assert [segment["startMs"] for segment in segments] == [0, 1200, 2500]
    assert [segment["endMs"] for segment in segments] == [1200, 2500, 3100]


def test_recognize_uploaded_audio_uses_official_funasr_speaker_info_before_voiceprint(tmp_path, monkeypatch):
    audio_path = tmp_path / "uploaded.wav"
    audio_path.write_bytes(b"audio")

    from src.modules.audio import audio_format_handler

    monkeypatch.setattr(audio_format_handler, "probe_media_info", lambda path: {
        "duration": 2.0,
        "sample_rate": 16000,
        "channels": 1,
        "format": "wav",
        "codec": "pcm_s16le",
        "size": 5,
    })
    monkeypatch.setattr(
        audio_format_handler,
        "convert_media_to_wav",
        lambda saved_path, target_sr=16000, target_channels=1: str(audio_path)
    )
    monkeypatch.setattr(audio_format_handler, "cleanup_temp_file", lambda path: None)
    monkeypatch.setattr(database_api, "_persist_uploaded_recognition_audio", lambda saved_path, converted_path: {
        "path": str(audio_path),
        "file_name": "uploaded_recognition.wav",
        "source_file_name": "uploaded.wav",
        "time_base": "recognition_wav_16k_mono",
    })

    asr_calls = []
    voiceprint_calls = []

    def fake_asr(audio_path_arg, server_state, language, **kwargs):
        asr_calls.append((audio_path_arg, language, kwargs))
        return {
            "text": "第一句。",
            "timestamp": [[0, 1000]],
            "sentence_info": [{"text": "第一句。", "start": 0, "end": 1000, "spk": 0}],
            "chunk_count": 1,
            "chunked": False,
            "audio_size": 5,
        }

    monkeypatch.setattr(database_api, "_run_uploaded_audio_asr", fake_asr)
    monkeypatch.setattr(
        database_api,
        "_run_uploaded_modelscope_diarization",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("不应再调用旧ModelScope asr-inference入口"))
    )

    def fake_voiceprint(audio_path_arg, speaker_segments, top_k=3):
        voiceprint_calls.append((audio_path_arg, speaker_segments, top_k))
        return {
            "label_result": {
                "speaker_type": "registered",
                "speaker_label": "张三",
                "confidence": 0.91,
            }
        }

    monkeypatch.setattr(database_api, "_identify_uploaded_speaker_from_segments", fake_voiceprint)
    monkeypatch.setattr(database_api, "_apply_uploaded_result_corrections", lambda result, **kwargs: result)

    class FakeArgs:
        upload_asr_enable_internal_speaker = True

    class FakeServerState:
        args = FakeArgs()

    result = database_api._recognize_uploaded_audio_file(
        saved_path=str(audio_path),
        original_filename="uploaded.wav",
        server_state=FakeServerState(),
        language="zh",
        enable_speaker_diarization=True,
        top_k=4,
        enable_voiceprint_matching=True,
        enable_translation=False,
        expected_speakers=2,
    )

    assert len(asr_calls) == 1
    assert len(voiceprint_calls) == 1
    assert voiceprint_calls[0][2] == 4
    assert result["segments"][0]["speaker"] == "张三"
    assert result["asr_metadata"]["speaker_segment_source"] == "funasr_sentence_info_spk"
    assert result["asr_metadata"]["diarization_model"] is None


def test_run_uploaded_audio_asr_uses_whole_file_once(tmp_path, monkeypatch):
    audio_path = tmp_path / "whole.wav"
    audio_path.write_bytes(b"audio")
    progress = []

    class FakeUploadModel:
        spk_model = object()

        def __init__(self):
            self.inputs = []
            self.kwargs = []

        def generate(self, input, **kwargs):
            self.inputs.append(input)
            self.kwargs.append(kwargs)
            return [{
                "text": "整文件文本",
                "timestamp": [[0, 1000]],
                "sentence_info": [{"text": "整文件文本", "start": 0, "end": 1000, "spk": 0}],
            }]

    class FakeArgs:
        upload_asr_batch_size_s = 60
        upload_asr_merge_vad = False
        upload_asr_merge_length_s = 8
        upload_asr_language = "zh"
        upload_asr_enable_internal_speaker = True

    class FakeState:
        args = FakeArgs()
        model_asr_upload = FakeUploadModel()

    monkeypatch.setattr(database_api, "_clean_asr_text", lambda text, server_state: text)
    monkeypatch.setattr(database_api, "_ensure_cuda_memory_available", lambda size: True)
    monkeypatch.setattr(database_api, "_clear_cuda_memory", lambda: None)

    result = database_api._run_uploaded_audio_asr(
        str(audio_path),
        FakeState(),
        "zh",
        expected_speakers=2,
        progress_callback=lambda done, total: progress.append((done, total)),
    )

    assert FakeState.model_asr_upload.inputs == [str(audio_path)]
    upload_kwargs = FakeState.model_asr_upload.kwargs[0]
    assert upload_kwargs["batch_size_s"] == 60
    assert upload_kwargs["preset_spk_num"] == 2
    assert upload_kwargs["return_spk_res"] is True
    assert upload_kwargs["sentence_timestamp"] is True
    assert upload_kwargs["merge_vad"] is False
    assert "merge_length_s" not in upload_kwargs
    assert upload_kwargs["language"] == "zh"
    assert upload_kwargs["use_itn"] is True
    assert result["text"] == "整文件文本"
    assert result["chunk_count"] == 1
    assert result["chunked"] is False
    assert progress == [(0, 1), (1, 1)]


def test_run_uploaded_audio_asr_keeps_legacy_params_when_internal_speaker_disabled(tmp_path, monkeypatch):
    audio_path = tmp_path / "legacy.wav"
    audio_path.write_bytes(b"audio")

    class FakeUploadModel:
        def __init__(self):
            self.kwargs = []

        def generate(self, input, **kwargs):
            self.kwargs.append(kwargs)
            return [{"text": "旧路径文本"}]

    class FakeArgs:
        upload_asr_batch_size_s = 60
        upload_asr_merge_vad = False
        upload_asr_merge_length_s = 8
        upload_asr_language = "zh"
        upload_asr_enable_internal_speaker = False

    class FakeState:
        args = FakeArgs()
        model_asr_upload = FakeUploadModel()

    monkeypatch.setattr(database_api, "_ensure_cuda_memory_available", lambda size: True)
    monkeypatch.setattr(database_api, "_clear_cuda_memory", lambda: None)

    database_api._run_uploaded_audio_asr(
        str(audio_path),
        FakeState(),
        "zh",
        expected_speakers=2,
    )

    upload_kwargs = FakeState.model_asr_upload.kwargs[0]
    assert upload_kwargs["merge_vad"] is False
    assert "merge_length_s" not in upload_kwargs
    assert upload_kwargs["language"] == "zh"
    assert upload_kwargs["use_itn"] is True
    assert "preset_spk_num" not in upload_kwargs


def test_run_uploaded_audio_asr_can_enable_internal_vad_merge(tmp_path, monkeypatch):
    audio_path = tmp_path / "merge.wav"
    audio_path.write_bytes(b"audio")

    class FakeUploadModel:
        spk_model = object()

        def __init__(self):
            self.kwargs = []

        def generate(self, input, **kwargs):
            self.kwargs.append(kwargs)
            return [{"text": "合并文本"}]

    class FakeArgs:
        upload_asr_batch_size_s = 60
        upload_asr_merge_vad = True
        upload_asr_merge_length_s = 8
        upload_asr_language = "zh"
        upload_asr_enable_internal_speaker = True

    class FakeState:
        args = FakeArgs()
        model_asr_upload = FakeUploadModel()

    monkeypatch.setattr(database_api, "_ensure_cuda_memory_available", lambda size: True)
    monkeypatch.setattr(database_api, "_clear_cuda_memory", lambda: None)

    database_api._run_uploaded_audio_asr(str(audio_path), FakeState(), "zh")

    upload_kwargs = FakeState.model_asr_upload.kwargs[0]
    assert upload_kwargs["merge_vad"] is True
    assert upload_kwargs["merge_length_s"] == 8


def test_run_uploaded_audio_asr_derives_preset_from_speaker_range(tmp_path, monkeypatch):
    audio_path = tmp_path / "range.wav"
    audio_path.write_bytes(b"audio")

    class FakeUploadModel:
        spk_model = object()

        def __init__(self):
            self.kwargs = []

        def generate(self, input, **kwargs):
            self.kwargs.append(kwargs)
            return [{"text": "范围人数文本"}]

    class FakeArgs:
        upload_asr_batch_size_s = 60
        upload_asr_merge_vad = False
        upload_asr_merge_length_s = 8
        upload_asr_language = "zh"
        upload_asr_enable_internal_speaker = True

    class FakeState:
        args = FakeArgs()
        model_asr_upload = FakeUploadModel()

    monkeypatch.setattr(database_api, "_ensure_cuda_memory_available", lambda size: True)
    monkeypatch.setattr(database_api, "_clear_cuda_memory", lambda: None)

    database_api._run_uploaded_audio_asr(
        str(audio_path),
        FakeState(),
        "zh",
        min_speakers=4,
        max_speakers=6,
    )

    upload_kwargs = FakeState.model_asr_upload.kwargs[0]
    assert upload_kwargs["preset_spk_num"] == 5
    assert upload_kwargs["return_spk_res"] is True


def test_run_uploaded_audio_asr_rejects_long_internal_speaker_without_acceleration(tmp_path, monkeypatch):
    audio_path = tmp_path / "long.wav"
    audio_path.write_bytes(b"audio")

    class FakeUploadModel:
        spk_model = object()

        def generate(self, input, **kwargs):
            raise AssertionError("长音频CPU保护应在调用FunASR前生效")

    class FakeArgs:
        upload_asr_batch_size_s = 60
        upload_asr_merge_vad = False
        upload_asr_merge_length_s = 8
        upload_asr_language = "zh"
        upload_asr_enable_internal_speaker = True
        device = "cpu"
        ngpu = 0

    class FakeState:
        args = FakeArgs()
        model_asr_upload = FakeUploadModel()

    monkeypatch.setenv("UPLOAD_INTERNAL_SPEAKER_CPU_MAX_SECONDS", "60")
    monkeypatch.setattr(database_api, "_ensure_cuda_memory_available", lambda size: True)
    monkeypatch.setattr(database_api, "_clear_cuda_memory", lambda: None)
    monkeypatch.setattr(database_api, "_upload_asr_has_accelerated_device", lambda args: False)

    with pytest.raises(database_api.APIError) as exc_info:
        database_api._run_uploaded_audio_asr(
            str(audio_path),
            FakeState(),
            "zh",
            expected_speakers=2,
            media_duration_seconds=120,
        )

    assert exc_info.value.status_code == 422
    assert "长音频" in exc_info.value.message


def test_recognize_uploaded_audio_prefers_asr_sentence_info_spk(tmp_path, monkeypatch):
    audio_path = tmp_path / "uploaded.wav"
    audio_path.write_bytes(b"audio")

    from src.modules.audio import audio_format_handler

    monkeypatch.setattr(audio_format_handler, "probe_media_info", lambda path: {
        "duration": 2.0,
        "sample_rate": 16000,
        "channels": 1,
        "format": "wav",
        "codec": "pcm_s16le",
        "size": 5,
    })
    monkeypatch.setattr(
        audio_format_handler,
        "convert_media_to_wav",
        lambda saved_path, target_sr=16000, target_channels=1: str(audio_path)
    )
    monkeypatch.setattr(audio_format_handler, "cleanup_temp_file", lambda path: None)
    monkeypatch.setattr(database_api, "_persist_uploaded_recognition_audio", lambda saved_path, converted_path: {
        "path": str(audio_path),
        "file_name": "uploaded_recognition.wav",
        "source_file_name": "uploaded.wav",
        "time_base": "recognition_wav_16k_mono",
    })
    monkeypatch.setattr(database_api, "_run_uploaded_audio_asr", lambda *args, **kwargs: {
        "text": "第一句。第二句。",
        "timestamp": [[0, 2000]],
        "sentence_info": [
            {"text": "第一句。", "start": 0, "end": 1000, "spk": 0},
            {"text": "第二句。", "start": 1000, "end": 2000, "spk": 1},
        ],
        "chunk_count": 1,
        "chunked": False,
        "audio_size": 5,
    })

    def fail_if_vad_path_is_used(*args, **kwargs):
        raise AssertionError("有sentence_info.spk时不应再走上传VAD后处理路径")

    monkeypatch.setattr(
        database_api,
        "_build_uploaded_vad_sensevoice_diarization_segments",
        fail_if_vad_path_is_used
    )

    def fail_if_voiceprint_is_used(*args, **kwargs):
        raise AssertionError("声纹匹配未启用时不应调用声纹识别")

    monkeypatch.setattr(
        database_api,
        "_identify_uploaded_speaker_from_segments",
        fail_if_voiceprint_is_used
    )
    monkeypatch.setattr(database_api, "_apply_uploaded_result_corrections", lambda result, **kwargs: result)

    class FakeArgs:
        upload_asr_enable_internal_speaker = True

    class FakeServerState:
        args = FakeArgs()

    result = database_api._recognize_uploaded_audio_file(
        saved_path=str(audio_path),
        original_filename="uploaded.wav",
        server_state=FakeServerState(),
        language="zh",
        enable_speaker_diarization=True,
        top_k=3,
        enable_voiceprint_matching=False,
        enable_translation=False,
        expected_speakers=2,
    )

    assert [segment["speaker"] for segment in result["segments"]] == ["说话人1", "说话人2"]
    assert [segment["text"] for segment in result["segments"]] == ["第一句。", "第二句。"]
    assert result["asr_metadata"]["speaker_segment_source"] == "funasr_sentence_info_spk"
    assert result["asr_metadata"]["speaker_count"] == 2
    assert result["asr_metadata"]["voiceprint_matching_enabled"] is False


def test_recognize_uploaded_audio_keeps_single_asr_spk_without_vad_retry(tmp_path, monkeypatch):
    audio_path = tmp_path / "uploaded.wav"
    audio_path.write_bytes(b"audio")

    from src.modules.audio import audio_format_handler

    monkeypatch.setattr(audio_format_handler, "probe_media_info", lambda path: {
        "duration": 2.0,
        "sample_rate": 16000,
        "channels": 1,
        "format": "wav",
        "codec": "pcm_s16le",
        "size": 5,
    })
    monkeypatch.setattr(
        audio_format_handler,
        "convert_media_to_wav",
        lambda saved_path, target_sr=16000, target_channels=1: str(audio_path)
    )
    monkeypatch.setattr(audio_format_handler, "cleanup_temp_file", lambda path: None)
    monkeypatch.setattr(database_api, "_persist_uploaded_recognition_audio", lambda saved_path, converted_path: {
        "path": str(audio_path),
        "file_name": "uploaded_recognition.wav",
        "source_file_name": "uploaded.wav",
        "time_base": "recognition_wav_16k_mono",
    })
    monkeypatch.setattr(database_api, "_run_uploaded_audio_asr", lambda *args, **kwargs: {
        "text": "第一句。第二句。",
        "timestamp": [[0, 2000]],
        "sentence_info": [
            {"text": "第一句。", "start": 0, "end": 1000, "spk": 0},
            {"text": "第二句。", "start": 1000, "end": 2000, "spk": 0},
        ],
        "chunk_count": 1,
        "chunked": False,
        "audio_size": 5,
    })

    def fail_if_vad_path_is_used(*args, **kwargs):
        raise AssertionError("上传音视频不应再用VAD+embedding重切说话人与文本")

    monkeypatch.setattr(
        database_api,
        "_build_uploaded_vad_sensevoice_diarization_segments",
        fail_if_vad_path_is_used
    )
    monkeypatch.setattr(database_api, "_apply_uploaded_result_corrections", lambda result, **kwargs: result)

    class FakeArgs:
        upload_asr_enable_internal_speaker = False

    class FakeServerState:
        args = FakeArgs()

    result = database_api._recognize_uploaded_audio_file(
        saved_path=str(audio_path),
        original_filename="uploaded.wav",
        server_state=FakeServerState(),
        language="zh",
        enable_speaker_diarization=True,
        top_k=3,
        enable_voiceprint_matching=False,
        enable_translation=False,
        expected_speakers=2,
    )

    assert [segment["speaker"] for segment in result["segments"]] == ["说话人1", "说话人1"]
    assert [segment["text"] for segment in result["segments"]] == ["第一句。", "第二句。"]
    assert result["asr_metadata"]["speaker_segment_source"] == "funasr_sentence_info_spk"
    assert result["asr_metadata"]["speaker_count"] == 1


def test_uploaded_recognition_segments_match_voiceprint_only_when_enabled(monkeypatch):
    calls = []

    def fake_identify(audio_path, segments, top_k=3):
        calls.append((audio_path, segments, top_k))
        return {
            "label_result": {
                "speaker_type": "registered",
                "speaker_label": f"实名说话人{len(calls)}",
                "confidence": 0.91,
            }
        }

    monkeypatch.setattr(database_api, "_identify_uploaded_speaker_from_segments", fake_identify)
    rec_result = {
        "sentence_info": [
            {"text": "第一句。", "start": 0, "end": 1000, "spk": 0},
            {"text": "第二句。", "start": 1000, "end": 2000, "spk": 1},
        ]
    }

    dynamic_segments = database_api._build_uploaded_recognition_segments(
        "audio.wav",
        rec_result,
        enable_speaker_diarization=True,
        top_k=3,
        enable_voiceprint_matching=False,
    )
    assert calls == []
    assert [segment["speaker"] for segment in dynamic_segments] == ["说话人1", "说话人2"]

    registered_segments = database_api._build_uploaded_recognition_segments(
        "audio.wav",
        rec_result,
        enable_speaker_diarization=True,
        top_k=5,
        enable_voiceprint_matching=True,
    )
    assert len(calls) == 2
    assert [call[2] for call in calls] == [5, 5]
    assert [segment["speaker"] for segment in registered_segments] == ["实名说话人1", "实名说话人2"]
    assert {segment["speaker_type"] for segment in registered_segments} == {"registered"}


def test_vad_diarization_splits_plain_asr_text_when_timestamps_missing(monkeypatch):
    import numpy as np
    from src.modules.speaker import speaker_verification

    monkeypatch.setattr(database_api, "_detect_uploaded_speech_ranges", lambda audio_path, server_state: [
        (0, 1000),
        (1000, 2000),
        (2000, 3000),
    ])
    monkeypatch.setattr(database_api, "_write_audio_segment", lambda audio_path, start_ms, end_ms: f"/tmp/{start_ms}_{end_ms}.wav")
    monkeypatch.setattr(speaker_verification, "extract_embedding", lambda audio_path: np.array([1.0, 0.0]))
    monkeypatch.setattr(
        database_api,
        "_cluster_uploaded_speaker_windows",
        lambda embeddings, expected_speakers, min_speakers=None, max_speakers=None: [0, 1, 0]
    )

    class FakeState:
        model_asr_upload = None

    segments = database_api._build_uploaded_vad_sensevoice_diarization_segments(
        "audio.wav",
        FakeState(),
        "zh",
        "",
        expected_speakers=2,
        rec_result={"text": "第一句。第二句。第三句。", "sentence_info": [], "timestamp": None},
    )

    assert [segment["speaker"] for segment in segments] == ["说话人1", "说话人2", "说话人1"]
    assert [segment["startMs"] for segment in segments] == [0, 1000, 2000]
    assert [segment["endMs"] for segment in segments] == [1000, 2000, 3000]
    assert "".join(segment["text"] for segment in segments) == "第一句。第二句。第三句。"


def test_vad_diarization_keeps_time_segments_when_embeddings_fail(monkeypatch):
    from src.modules.speaker import speaker_verification

    monkeypatch.setattr(database_api, "_detect_uploaded_speech_ranges", lambda audio_path, server_state: [
        (0, 1000),
        (1000, 2000),
        (2000, 3000),
    ])
    monkeypatch.setattr(database_api, "_write_audio_segment", lambda audio_path, start_ms, end_ms: f"/tmp/{start_ms}_{end_ms}.wav")
    monkeypatch.setattr(
        speaker_verification,
        "extract_embedding",
        lambda audio_path: (_ for _ in ()).throw(RuntimeError("embedding failed"))
    )

    segments = database_api._build_uploaded_vad_sensevoice_diarization_segments(
        "audio.wav",
        object(),
        "zh",
        "",
        expected_speakers=None,
        rec_result={"text": "第一句。第二句。第三句。", "sentence_info": [], "timestamp": None},
    )

    assert len(segments) == 3
    assert {segment["speaker"] for segment in segments} == {"说话人1"}
    assert [segment["timestamp"] for segment in segments] == [[[0, 1000]], [[1000, 2000]], [[2000, 3000]]]


def test_speaker_range_sampling_preserves_coverage():
    ranges = [(index * 1000, (index + 1) * 1000) for index in range(10)]

    sampled = database_api._sample_uploaded_speech_ranges_for_speaker(ranges, max_segments=4)

    assert len(sampled) == 4
    assert sampled[0] == ranges[0]
    assert sampled[-1] == ranges[-1]
    assert sampled == sorted(sampled)


def test_vad_diarization_samples_embeddings_but_preserves_full_range_output(monkeypatch):
    import numpy as np
    from src.modules.speaker import speaker_verification

    raw_ranges = [(index * 1000, (index + 1) * 1000) for index in range(10)]
    embedding_calls = []
    progress_updates = []

    monkeypatch.setattr(database_api, "_detect_uploaded_speech_ranges", lambda audio_path, server_state: raw_ranges)
    monkeypatch.setenv("UPLOAD_SPEAKER_MAX_VAD_SEGMENTS", "4")
    monkeypatch.setattr(
        database_api,
        "_write_audio_segment",
        lambda audio_path, start_ms, end_ms: f"/tmp/{start_ms}_{end_ms}.wav"
    )

    def fake_extract_embedding(audio_path):
        embedding_calls.append(audio_path)
        return np.array([float(len(embedding_calls)), 0.0])

    monkeypatch.setattr(speaker_verification, "extract_embedding", fake_extract_embedding)
    monkeypatch.setattr(
        database_api,
        "_cluster_uploaded_speaker_windows",
        lambda embeddings, expected_speakers, min_speakers=None, max_speakers=None: [0, 1, 0, 1]
    )

    segments = database_api._build_uploaded_vad_sensevoice_diarization_segments(
        "audio.wav",
        object(),
        "zh",
        "",
        expected_speakers=2,
        rec_result={
            "text": "第一句。第二句。第三句。第四句。",
            "sentence_info": [],
            "timestamp": None
        },
        progress_callback=lambda stage, progress: progress_updates.append((stage, progress))
    )

    assert len(embedding_calls) == 4
    assert len(segments) == 10
    assert [segment["startMs"] for segment in segments] == [start for start, _ in raw_ranges]
    assert [segment["endMs"] for segment in segments] == [end for _, end in raw_ranges]
    assert "".join(segment["text"] for segment in segments) == "第一句。第二句。第三句。第四句。"
    assert {segment["speaker"] for segment in segments} == {"说话人1", "说话人2"}
    assert any(stage == "speaker" and progress > 80 for stage, progress in progress_updates)


def test_vad_diarization_skips_piece_asr_when_merged_ranges_exceed_limit(monkeypatch):
    import numpy as np
    from src.modules.speaker import speaker_verification

    raw_ranges = [(index * 1000, (index + 1) * 1000) for index in range(10)]
    monkeypatch.setattr(database_api, "_detect_uploaded_speech_ranges", lambda audio_path, server_state: raw_ranges)
    monkeypatch.setenv("UPLOAD_SPEAKER_MAX_VAD_SEGMENTS", "4")
    monkeypatch.setenv("UPLOAD_SPEAKER_PIECE_ASR_MAX_SEGMENTS", "3")
    monkeypatch.setattr(
        database_api,
        "_write_audio_segment",
        lambda audio_path, start_ms, end_ms: f"/tmp/{start_ms}_{end_ms}.wav"
    )
    monkeypatch.setattr(speaker_verification, "extract_embedding", lambda audio_path: np.array([1.0, 0.0]))
    monkeypatch.setattr(
        database_api,
        "_cluster_uploaded_speaker_windows",
        lambda embeddings, expected_speakers, min_speakers=None, max_speakers=None: [0, 1, 0, 1]
    )
    monkeypatch.setattr(
        database_api,
        "_recognize_uploaded_audio_piece",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("piece ASR should be skipped"))
    )

    class FakeState:
        model_asr_upload = object()

    segments = database_api._build_uploaded_vad_sensevoice_diarization_segments(
        "audio.wav",
        FakeState(),
        "zh",
        "",
        expected_speakers=2,
        rec_result={"text": "完整文本不能因为抽样丢失。", "sentence_info": [], "timestamp": None},
    )

    assert len(segments) == 4
    assert "".join(segment["text"] for segment in segments) == "完整文本不能因为抽样丢失。"
    assert [segment["startMs"] for segment in segments] == [0, 2000, 5000, 8000]
    assert [segment["endMs"] for segment in segments] == [2000, 5000, 8000, 10000]


def test_vad_diarization_runs_piece_asr_on_merged_speaker_ranges(monkeypatch):
    import numpy as np
    from src.modules.speaker import speaker_verification

    raw_ranges = [(index * 1000, (index + 1) * 1000) for index in range(10)]
    piece_calls = []
    monkeypatch.setattr(database_api, "_detect_uploaded_speech_ranges", lambda audio_path, server_state: raw_ranges)
    monkeypatch.setenv("UPLOAD_SPEAKER_MAX_VAD_SEGMENTS", "4")
    monkeypatch.setenv("UPLOAD_SPEAKER_PIECE_ASR_MAX_SEGMENTS", "4")
    monkeypatch.setattr(
        database_api,
        "_write_audio_segment",
        lambda audio_path, start_ms, end_ms: f"/tmp/{start_ms}_{end_ms}.wav"
    )
    monkeypatch.setattr(speaker_verification, "extract_embedding", lambda audio_path: np.array([1.0, 0.0]))
    monkeypatch.setattr(
        database_api,
        "_cluster_uploaded_speaker_windows",
        lambda embeddings, expected_speakers, min_speakers=None, max_speakers=None: [0, 0, 0, 0]
    )

    def fake_piece_asr(upload_asr_model, audio_path, server_state, language, hotword_text):
        piece_calls.append(audio_path)
        return "合并后的对应音频文本。"

    monkeypatch.setattr(database_api, "_recognize_uploaded_audio_piece", fake_piece_asr)

    class FakeState:
        model_asr_upload = object()

    segments = database_api._build_uploaded_vad_sensevoice_diarization_segments(
        "audio.wav",
        FakeState(),
        "zh",
        "",
        expected_speakers=1,
        rec_result={"text": "这段全文不应该被按比例切。", "sentence_info": [], "timestamp": None},
    )

    assert piece_calls == ["/tmp/0_10000.wav"]
    assert len(segments) == 1
    assert segments[0]["speaker"] == "说话人1"
    assert segments[0]["startMs"] == 0
    assert segments[0]["endMs"] == 10000
    assert segments[0]["text"] == "合并后的对应音频文本。"


def test_validate_uploaded_audio_buffer_rejects_over_limit(tmp_path):
    audio_path = tmp_path / "too_large.wav"
    audio_path.write_bytes(b"1234567890")

    with pytest.raises(database_api.APIError) as exc_info:
        database_api._validate_uploaded_audio_buffer(str(audio_path), max_audio_bytes=5)

    assert exc_info.value.status_code == 413
    assert "上传音频过大" in exc_info.value.message


def test_generate_uploaded_asr_chunk_disables_spk_on_type_error_when_fallback_allowed():
    class FakeUploadModel:
        def __init__(self):
            self.calls = []

        def generate(self, input, **kwargs):
            self.calls.append(kwargs)
            if len(self.calls) == 1:
                raise TypeError("speaker diarization failed")
            return [{"text": "ok"}]

    model = FakeUploadModel()
    result = database_api._generate_uploaded_asr_chunk(
        model,
        "audio.wav",
        {
            "cache": {},
            "merge_vad": True,
            "merge_length_s": 8,
            "hotword": "无纸化",
            "preset_spk_num": 2,
            "language": "zh",
        },
    )

    assert result == [{"text": "ok"}]
    assert model.calls[1]["language"] == "zh"
    assert model.calls[1]["return_spk_res"] is False
    assert "preset_spk_num" not in model.calls[1]
    assert "hotword" not in model.calls[1]


def test_generate_uploaded_asr_chunk_stops_internal_speaker_type_error():
    class FakeUploadModel:
        def __init__(self):
            self.calls = []

        def generate(self, input, **kwargs):
            self.calls.append(kwargs)
            raise TypeError("'>' not supported between instances of 'float' and 'NoneType'")

    model = FakeUploadModel()

    with pytest.raises(database_api.APIError) as exc_info:
        database_api._generate_uploaded_asr_chunk(
            model,
            "long.wav",
            {
                "cache": {},
                "merge_vad": True,
                "preset_spk_num": 5,
                "return_spk_res": True,
                "language": "zh",
            },
            allow_text_fallback=False,
        )

    assert exc_info.value.status_code == 500
    assert len(model.calls) == 1


def test_collect_registration_audio_ranges_uses_segments_and_caps_duration():
    ranges = database_api._collect_registration_audio_ranges({
        "segments": [
            {"start_ms": 5000, "end_ms": 14000},
            {"startMs": 20000, "endMs": 32000},
            {"start_ms": 1000, "end_ms": 2000},
        ],
        "max_duration_ms": 15000
    })

    assert ranges == [
        (1000, 2000),
        (5000, 14000),
        (20000, 25000),
    ]


def test_public_registration_audio_ref_hides_internal_path():
    public_ref = database_api._public_registration_audio_ref({
        "path": "/tmp/internal.wav",
        "file_name": "sample_recognition.wav",
        "source_file_name": "sample.mp4",
        "time_base": "recognition_wav_16k_mono"
    })

    assert public_ref == {
        "file_name": "sample_recognition.wav",
        "source_file_name": "sample.mp4",
        "time_base": "recognition_wav_16k_mono"
    }


def test_register_uploaded_segment_source_fallback_uses_media_converter(monkeypatch):
    calls = {}

    def fake_resolve(base_dir, filename):
        calls["resolved"] = (base_dir, filename)
        return "/tmp/source-video.mp4"

    def fake_convert(source_path, target_sr=16000, target_channels=1):
        calls["convert"] = (source_path, target_sr, target_channels)
        return "/tmp/converted-recognition.wav"

    def fake_write_segments(audio_path, segments):
        calls["write_segments"] = (audio_path, segments)
        return "/tmp/register-segment.wav"

    def fake_cleanup(path):
        calls.setdefault("cleanup", []).append(path)

    monkeypatch.setattr(database_api, "_resolve_uploaded_audio_path", fake_resolve)
    monkeypatch.setattr(database_api, "_write_audio_segments", fake_write_segments)

    from src.modules.audio import audio_format_handler
    from src.modules.speaker import speaker_manager

    monkeypatch.setattr(audio_format_handler, "convert_media_to_wav", fake_convert)
    monkeypatch.setattr(audio_format_handler, "cleanup_temp_file", fake_cleanup)
    monkeypatch.setattr(speaker_manager, "init_speaker_manager", lambda args=None: True)
    monkeypatch.setattr(
        speaker_manager,
        "register_speaker",
        lambda **kwargs: {"success": True, "speaker_name": kwargs["speaker_name"]}
    )

    client = database_api.app.test_client()
    response = client.post(
        "/api/speakers/register-uploaded-segment",
        json={
            "speaker_name": "张三",
            "registration_audio": {"source_file_name": "uploaded-video.mp4"},
            "segments": [{"start_ms": 1000, "end_ms": 8000}],
        },
    )

    assert response.status_code == 201
    assert calls["convert"] == ("/tmp/source-video.mp4", 16000, 1)
    assert calls["write_segments"] == (
        "/tmp/converted-recognition.wav",
        [{"start_ms": 1000, "end_ms": 8000}],
    )
    assert calls["cleanup"] == ["/tmp/register-segment.wav", "/tmp/converted-recognition.wav"]
    payload = response.get_json()["data"]
    assert payload["registration_source"]["time_base"] == "converted_source_wav_16k_mono"


def test_write_audio_segment_prefers_media_extractor(monkeypatch):
    calls = {}

    from src.modules.audio import audio_format_handler

    def fake_extract(audio_path, start_ms, end_ms):
        calls["extract"] = (audio_path, start_ms, end_ms)
        return "/tmp/extracted-segment.wav"

    monkeypatch.setattr(audio_format_handler, "extract_media_segment_to_wav", fake_extract)

    assert database_api._write_audio_segment("/tmp/long-recognition.wav", 1000, 5000) == "/tmp/extracted-segment.wav"
    assert calls["extract"] == ("/tmp/long-recognition.wav", 1000, 5000)


def test_parse_upload_hotwords_supports_weighted_lines_and_json():
    line_terms = database_api._parse_upload_hotwords("真视通 80\n紫荆 60\n# ignored\nA")
    escaped_line_terms = database_api._parse_upload_hotwords("真视通 80\\n紫荆 60")
    json_terms = database_api._parse_upload_hotwords('{"博数智源": 90, "1": 100}')

    assert line_terms == {"真视通": 80, "紫荆": 60}
    assert escaped_line_terms == {"真视通": 80, "紫荆": 60}
    assert json_terms == {"博数智源": 90}


def test_parse_upload_corrections_requires_explicit_rules():
    assert database_api._load_upload_text_correction_pairs(use_default=True, include_config_file=False) == []

    pairs = database_api._parse_upload_corrections(
        "误词=>正确词\n另一个错词 -> 另一个正确词\n短词 长词"
    )

    assert ("误词", "正确词") in pairs
    assert ("另一个错词", "另一个正确词") in pairs
    assert ("短词", "长词") in pairs


def test_apply_uploaded_result_corrections_updates_segments_and_metadata():
    result = {
        "segments": [
            {"speaker": "说话人1", "text": "这里是误词", "mode": "uploaded-audio"},
            {"speaker": "说话人2", "text": "这里正常", "mode": "uploaded-audio"},
        ],
        "plain_text": "这里是误词。这里正常",
        "asr_metadata": {}
    }

    updated = database_api._apply_uploaded_result_corrections(
        result,
        extra_corrections={"误词": "正确词"},
        use_default=False,
        include_config_file=False
    )

    assert updated["segments"][0]["text"] == "这里是正确词"
    assert updated["segments"][1]["text"] == "这里正常"
    assert updated["plain_text"] == "这里是正确词。这里正常"
    assert updated["asr_metadata"]["text_correction_count"] == 2
    assert updated["asr_metadata"]["text_correction_details"] == [
        {"from": "误词", "to": "正确词", "count": 2}
    ]


def test_apply_uploaded_audio_corrections_endpoint(monkeypatch):
    saved = {}

    def fake_result(task_id):
        assert task_id == "task-1"
        return {
            "segments": [{"speaker": "说话人1", "text": "这里是误词", "mode": "uploaded-audio"}],
            "plain_text": "这里是误词",
            "asr_metadata": {}
        }

    def fake_save(task_id, result):
        saved["task_id"] = task_id
        saved["result"] = result
        return result

    monkeypatch.setattr(database_api, "_get_completed_upload_result", fake_result)
    monkeypatch.setattr(database_api, "_save_upload_result_for_task", fake_save)

    client = database_api.app.test_client()
    response = client.post(
        "/api/upload/audio/tasks/task-1/corrections",
        json={"corrections": {"误词": "正确词"}}
    )

    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert payload["correction_count"] == 2
    assert payload["result"]["segments"][0]["text"] == "这里是正确词"
    assert saved["task_id"] == "task-1"


def test_merge_uploaded_segments_semantically_merges_same_speaker_and_filters_fillers():
    segments = [
        {"speaker": "说话人1", "text": "嗯", "startMs": 0, "endMs": 300, "mode": "uploaded-audio"},
        {"speaker": "说话人1", "text": "我们先看项目", "startMs": 400, "endMs": 1400, "mode": "uploaded-audio"},
        {"speaker": "说话人1", "text": "进度", "startMs": 1500, "endMs": 2200, "mode": "uploaded-audio"},
        {"speaker": "说话人2", "text": "我来补充预算。", "startMs": 5000, "endMs": 5600, "mode": "uploaded-audio"},
    ]

    merged = database_api._merge_uploaded_segments_semantically(segments)

    assert len(merged) == 2
    assert merged[0]["speaker"] == "说话人1"
    assert merged[0]["text"] == "我们先看项目进度"
    assert merged[0]["startTime"] == "00:00:00"
    assert merged[0]["endTime"] == "00:00:02"


def test_merge_uploaded_segments_semantically_merges_adjacent_same_speaker_past_time_limit():
    segments = [
        {
            "speaker": "说话人1",
            "text": "现在打开他，你看主席已经打开这个话筒，系统会实时转写每一句发言，并在页面中显示当前识别结果。",
            "translation": "Now turn him on, you can see the chair's microphone is open and the system is transcribing each sentence.",
            "startMs": 2000,
            "endMs": 23000,
            "mode": "uploaded-audio"
        },
        {
            "speaker": "说话人1",
            "text": "随后还会做校准和最终整理，大家可以继续观察内容变化，确认每个字句都归到同一个说话人下面。",
            "translation": "It will then calibrate and finalize the content under the same speaker.",
            "startMs": 23000,
            "endMs": 44000,
            "mode": "uploaded-audio"
        },
    ]

    merged = database_api._merge_uploaded_segments_semantically(segments)

    assert len(merged) == 1
    assert merged[0]["speaker"] == "说话人1"
    assert merged[0]["startTime"] == "00:00:02"
    assert merged[0]["endTime"] == "00:00:44"
    assert merged[0]["text"] == segments[0]["text"] + segments[1]["text"]
    assert merged[0]["translation"] == f"{segments[0]['translation']} {segments[1]['translation']}"


def test_merge_uploaded_segments_semantically_recovers_time_from_timestamp():
    segments = [
        {
            "speaker": "说话人1",
            "text": "第一段。",
            "timestamp": [[2000, 23000]],
            "mode": "uploaded-audio"
        },
        {
            "speaker": "说话人1",
            "text": "第二段。",
            "timestamp": [[23000, 44000]],
            "mode": "uploaded-audio"
        },
    ]

    merged = database_api._merge_uploaded_segments_semantically(segments)

    assert len(merged) == 1
    assert merged[0]["startMs"] == 2000
    assert merged[0]["endMs"] == 44000
    assert merged[0]["startTime"] == "00:00:02"
    assert merged[0]["endTime"] == "00:00:44"
    assert merged[0]["timestamp"] == [[2000, 44000]]


def test_merge_uploaded_segments_semantically_does_not_emit_fake_zero_time():
    segments = [
        {
            "speaker": "说话人1",
            "text": "没有有效时间戳的内容。",
            "startMs": 0,
            "endMs": 0,
            "mode": "uploaded-audio"
        },
    ]

    merged = database_api._merge_uploaded_segments_semantically(segments)

    assert len(merged) == 1
    assert merged[0]["startMs"] is None
    assert merged[0]["endMs"] is None
    assert merged[0]["startTime"] is None
    assert merged[0]["endTime"] is None
    assert merged[0]["timestamp"] is None


def test_rename_uploaded_audio_segment_speaker_updates_only_one_segment(monkeypatch):
    saved = {}

    def fake_result(task_id):
        assert task_id == "task-1"
        return {
            "segments": [
                {"speaker": "说话人1", "text": "第一段。", "startMs": 0, "endMs": 1000, "mode": "uploaded-audio"},
                {"speaker": "说话人1", "text": "第二段。", "startMs": 1000, "endMs": 2000, "mode": "uploaded-audio"},
                {"speaker": "说话人2", "text": "第三段。", "startMs": 2000, "endMs": 3000, "mode": "uploaded-audio"},
            ],
            "plain_text": "第一段。第二段。第三段。",
            "asr_metadata": {}
        }

    def fake_save(task_id, result):
        saved["task_id"] = task_id
        saved["result"] = result
        return result

    monkeypatch.setattr(database_api, "_get_completed_upload_result", fake_result)
    monkeypatch.setattr(database_api, "_save_upload_result_for_task", fake_save)

    client = database_api.app.test_client()
    response = client.patch(
        "/api/upload/audio/tasks/task-1/segments/1/speaker",
        json={"name": "李四"}
    )

    assert response.status_code == 200
    result = response.get_json()["data"]["result"]
    assert [segment["speaker"] for segment in result["segments"]] == ["说话人1", "李四", "说话人2"]
    assert saved["task_id"] == "task-1"


def test_merge_uploaded_segments_semantically_keeps_one_character_speaker_reply():
    segments = [
        {"speaker": "说话人1", "text": "我们现在开始。", "startMs": 0, "endMs": 1200, "mode": "uploaded-audio"},
        {"speaker": "说话人2", "text": "好", "startMs": 1300, "endMs": 1700, "mode": "uploaded-audio"},
        {"speaker": "说话人1", "text": "那继续看下一项。", "startMs": 1800, "endMs": 3000, "mode": "uploaded-audio"},
    ]

    merged = database_api._merge_uploaded_segments_semantically(segments)

    assert len(merged) == 3
    assert merged[1]["speaker"] == "说话人2"
    assert merged[1]["text"] == "好"
    assert merged[1]["startTime"] == "00:00:01"
    assert merged[1]["endTime"] == "00:00:01"


def test_upload_transcript_postprocess_cleans_disfluencies_without_removing_normal_words():
    cleaned = database_api._postprocess_uploaded_transcript_text(
        "嗯嗯，然后那个你看现在主席就是打开打开的这个话筒，然后他就会实时的实时的去转写。",
        enable_disfluency_cleanup=True
    )

    assert cleaned == "你看现在主席就是打开的这个话筒，然后他就会实时的去转写。"
    assert database_api._postprocess_uploaded_transcript_text(
        "这个话筒可以打开。",
        enable_disfluency_cleanup=True
    ) == "这个话筒可以打开。"
    assert database_api._postprocess_uploaded_transcript_text(
        "是这样的。就是。咱们现在有个服务器。公司呃意思是这样的。",
        enable_disfluency_cleanup=True
    ) == "是这样的。咱们现在有个服务器。公司意思是这样的。"


def test_merge_uploaded_segments_semantically_applies_2pass_style_postprocess():
    segments = [
        {
            "speaker": "说话人1",
            "text": "嗯嗯，然后那个你看现在主席就是打开打开的这个话筒。",
            "startMs": 0,
            "endMs": 3000,
            "mode": "uploaded-audio"
        },
        {
            "speaker": "说话人1",
            "text": "对对对对，是这个意思。",
            "startMs": 3200,
            "endMs": 4200,
            "mode": "uploaded-audio"
        },
    ]

    merged = database_api._merge_uploaded_segments_semantically(segments)

    assert len(merged) == 1
    assert merged[0]["text"] == "你看现在主席就是打开的这个话筒。对，是这个意思。"


def test_needs_uploaded_embedding_diarization_respects_expected_speaker_count():
    segments = [
        {"speaker": "说话人1"},
        {"speaker": "说话人2"},
        {"speaker": "说话人3"},
    ]

    assert database_api._needs_uploaded_embedding_diarization(segments, expected_speakers=2) is True
    assert database_api._needs_uploaded_embedding_diarization(segments[:2], expected_speakers=2) is False


def test_parse_upload_speaker_bounds_supports_range_text():
    assert database_api._parse_upload_speaker_bounds("3") == (3, 3, 3)
    assert database_api._parse_upload_speaker_bounds("2-4") == (None, 2, 4)
    assert database_api._parse_upload_speaker_bounds("4~2") == (None, 2, 4)
    assert database_api._parse_upload_speaker_bounds("", 2, 4) == (None, 2, 4)
    assert database_api._parse_upload_speaker_bounds("1") == (None, None, None)


def test_needs_uploaded_embedding_diarization_respects_speaker_range():
    one_speaker = [{"speaker": "说话人1"}]
    two_speakers = [{"speaker": "说话人1"}, {"speaker": "说话人2"}]
    five_speakers = [{"speaker": f"说话人{index}"} for index in range(1, 6)]

    assert database_api._needs_uploaded_embedding_diarization(
        one_speaker,
        expected_speakers=None,
        min_speakers=2,
        max_speakers=4
    ) is True
    assert database_api._needs_uploaded_embedding_diarization(
        two_speakers,
        expected_speakers=None,
        min_speakers=2,
        max_speakers=4
    ) is False
    assert database_api._needs_uploaded_embedding_diarization(
        five_speakers,
        expected_speakers=None,
        min_speakers=2,
        max_speakers=4
    ) is True


def test_build_segments_from_speaker_ranges_preserves_full_file_asr_text():
    asr_segments = [
        {"text": "第一句，标点保留。", "start_ms": 0, "end_ms": 1000},
        {"text": "第二句也保留！", "start_ms": 1000, "end_ms": 2000},
    ]
    speaker_ranges = [
        {"speaker": "说话人1", "start_ms": 0, "end_ms": 900},
        {"speaker": "说话人2", "start_ms": 900, "end_ms": 2000},
    ]

    segments = database_api._build_uploaded_segments_from_asr_speaker_ranges(
        asr_segments,
        speaker_ranges
    )

    assert [segment["text"] for segment in segments] == ["第一句，标点保留。", "第二句也保留！"]
    assert [segment["speaker"] for segment in segments] == ["说话人1", "说话人2"]


def test_extract_asr_segments_falls_back_to_chunk_ranges_without_timestamps():
    segments = database_api._extract_asr_segments({
        "text": "第一段\n第二段",
        "timestamp": [],
        "sentence_info": [],
        "raw_result": {
            "chunks": [
                {"offset_ms": 0, "duration_ms": 30000, "text": "第一段"},
                {"offset_ms": 30000, "duration_ms": 12000, "text": "第二段"},
            ]
        }
    })

    assert segments == [
        {"text": "第一段", "speaker_key": "uploaded_audio", "start_ms": 0, "end_ms": 30000},
        {"text": "第二段", "speaker_key": "uploaded_audio", "start_ms": 30000, "end_ms": 42000},
    ]


def test_uploaded_asr_segment_source_prefers_sentence_info():
    assert database_api._uploaded_asr_segment_source({
        "sentence_info": [{"text": "第一段", "start": 0, "end": 1000, "spk": 0}],
        "timestamp": [],
        "raw_result": {"chunks": [{"text": "chunk"}]},
    }) == "funasr_sentence_info"
    assert database_api._uploaded_asr_segment_source({
        "sentence_info": [],
        "timestamp": [],
        "raw_result": {"chunks": [{"text": "chunk"}]},
    }) == "asr_chunk_ranges"


def test_rank_uploaded_voiceprint_segments_prefers_long_meaningful_samples():
    samples = database_api._rank_uploaded_voiceprint_segments(
        [
            {"text": "短句", "start_ms": 0, "end_ms": 800},
            {"text": "这一段内容更完整", "start_ms": 1000, "end_ms": 5200},
            {"text": "超长段落", "start_ms": 6000, "end_ms": 26000},
        ],
        sample_limit=2,
        min_duration_ms=2000,
        max_duration_ms=10000
    )

    assert len(samples) == 2
    assert samples[0]["start_ms"] == 1000
    assert samples[1]["start_ms"] == 6000
    assert samples[1]["end_ms"] == 16000


def test_aggregate_uploaded_voiceprint_results_accepts_stable_winner(monkeypatch):
    monkeypatch.setenv("UPLOAD_VOICEPRINT_MATCH_THRESHOLD", "0.8")
    monkeypatch.setenv("UPLOAD_VOICEPRINT_MATCH_MARGIN", "0.05")
    monkeypatch.setenv("UPLOAD_VOICEPRINT_MATCH_MIN_HITS", "2")

    result = database_api._aggregate_uploaded_voiceprint_results([
        {"success": True, "threshold": 0.8, "candidates": [
            {"speaker_name": "张三", "similarity": 0.91},
            {"speaker_name": "李四", "similarity": 0.73},
        ]},
        {"success": True, "threshold": 0.8, "candidates": [
            {"speaker_name": "张三", "similarity": 0.86},
            {"speaker_name": "李四", "similarity": 0.75},
        ]},
        {"success": True, "threshold": 0.8, "candidates": [
            {"speaker_name": "张三", "similarity": 0.88},
            {"speaker_name": "李四", "similarity": 0.76},
        ]},
    ])

    assert result["accepted"] is True
    assert result["best_match"]["speaker_name"] == "张三"
    assert result["candidates"][0]["speaker_name"] == "张三"


def test_aggregate_uploaded_voiceprint_results_rejects_close_margin(monkeypatch):
    monkeypatch.setenv("UPLOAD_VOICEPRINT_MATCH_THRESHOLD", "0.8")
    monkeypatch.setenv("UPLOAD_VOICEPRINT_MATCH_MARGIN", "0.08")
    monkeypatch.setenv("UPLOAD_VOICEPRINT_MATCH_MIN_HITS", "2")

    result = database_api._aggregate_uploaded_voiceprint_results([
        {"success": True, "threshold": 0.8, "candidates": [
            {"speaker_name": "张三", "similarity": 0.86},
            {"speaker_name": "李四", "similarity": 0.83},
        ]},
        {"success": True, "threshold": 0.8, "candidates": [
            {"speaker_name": "张三", "similarity": 0.84},
            {"speaker_name": "李四", "similarity": 0.82},
        ]},
    ])

    assert result["accepted"] is False
    assert result["best_match"] is None
    assert result["candidates"] == []
    assert result["aggregate_candidates"][0]["speaker_name"] == "张三"


def test_speaker_candidates_rank_samples_by_quality():
    candidates = database_api._speaker_candidate_rows_from_result("task-1", {
        "segments": [
            {
                "speaker": "说话人1",
                "text": "短句",
                "startMs": 0,
                "endMs": 900,
                "startTime": "00:00:00",
            },
            {
                "speaker": "说话人1",
                "text": "这一段内容更完整，适合注册声纹",
                "startMs": 1000,
                "endMs": 7000,
                "startTime": "00:00:01",
            },
            {
                "speaker": "说话人1",
                "text": "可用片段",
                "startMs": 8000,
                "endMs": 11000,
                "startTime": "00:00:08",
            },
        ]
    })

    samples = candidates[0]["sample_segments"]
    assert [sample["quality"] for sample in samples] == ["good", "usable", "short"]
    assert samples[0]["index"] == 1
    assert samples[0]["audio_url"] == "/api/upload/audio/tasks/task-1/segments/1/audio"
