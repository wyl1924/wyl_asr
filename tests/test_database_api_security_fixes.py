#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import zipfile
from io import BytesIO

import pytest

from src.modules.database import database_api
from src.modules.database.database_manager import DatabaseManager


def test_path_boundary_rejects_sibling_prefix_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    audio_dir = tmp_path / "data" / "audio"
    sibling_dir = tmp_path / "data" / "audio_evil"
    audio_dir.mkdir(parents=True)
    sibling_dir.mkdir(parents=True)
    safe_file = audio_dir / "safe.wav"
    evil_file = sibling_dir / "secret.wav"
    safe_file.write_bytes(b"safe")
    evil_file.write_bytes(b"evil")

    assert database_api._require_existing_file_in_dirs(str(safe_file), [database_api._get_audio_dir()]) == str(safe_file)

    with pytest.raises(database_api.APIError) as exc_info:
        database_api._require_existing_file_in_dirs(str(evil_file), [database_api._get_audio_dir()])

    assert exc_info.value.status_code == 400


def test_speaker_audio_file_path_is_limited_to_audio_and_upload_dirs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    audio_file = tmp_path / "data" / "audio" / "voice.wav"
    upload_file = tmp_path / "data" / "uploads" / "voice.wav"
    outside_file = tmp_path / "outside.wav"
    audio_file.parent.mkdir(parents=True)
    upload_file.parent.mkdir(parents=True)
    audio_file.write_bytes(b"audio")
    upload_file.write_bytes(b"upload")
    outside_file.write_bytes(b"outside")

    assert database_api._resolve_user_audio_input_path(str(audio_file)) == str(audio_file)
    assert database_api._resolve_user_audio_input_path(str(upload_file)) == str(upload_file)

    with pytest.raises(database_api.APIError) as exc_info:
        database_api._resolve_user_audio_input_path(str(outside_file))

    assert exc_info.value.status_code == 400


def test_document_download_url_uses_document_id_only():
    url = database_api._document_download_url({"id": 42, "file_path": "/tmp/internal.md"})

    assert url == "/api/meetings/documents/download?document_id=42"
    assert "file_path" not in url
    assert "/tmp/internal.md" not in url


def test_download_meeting_document_by_id_does_not_require_file_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    document_path = tmp_path / "data" / "documents" / "meeting.md"
    document_path.parent.mkdir(parents=True)
    document_path.write_text("# hello", encoding="utf-8")

    class FakeDB:
        def get_meeting_document_by_id(self, document_id):
            assert document_id == 7
            return {
                "id": 7,
                "file_name": "meeting.md",
                "file_path": str(document_path),
            }

    monkeypatch.setattr(database_api, "db", FakeDB())

    response = database_api.app.test_client().get("/api/meetings/documents/download?document_id=7")

    assert response.status_code == 200
    assert response.data == b"# hello"


def test_download_meeting_document_docx_conversion_by_id_exposes_filename(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    document_path = tmp_path / "data" / "documents" / "meeting.md"
    document_path.parent.mkdir(parents=True)
    document_path.write_text(
        "# hello\n\n**王延领** [00:00:00 - 00:00:07]\n正文",
        encoding="utf-8"
    )

    class FakeDB:
        def get_meeting_document_by_id(self, document_id):
            assert document_id == 7
            return {
                "id": 7,
                "file_name": "meeting.md",
                "file_path": str(document_path),
            }

    monkeypatch.setattr(database_api, "db", FakeDB())

    response = database_api.app.test_client().get(
        "/api/meetings/documents/download?document_id=7&format=docx",
        headers={"Origin": "http://127.0.0.1:5173"}
    )

    assert response.status_code == 200
    assert response.mimetype == database_api.DOCX_MIMETYPE
    assert response.data.startswith(b"PK")
    assert "meeting.docx" in response.headers["Content-Disposition"]
    assert "Content-Disposition" in response.headers["Access-Control-Expose-Headers"]
    with zipfile.ZipFile(BytesIO(response.data)) as docx:
        document_xml = docx.read("word/document.xml").decode("utf-8")
    assert '<w:r><w:rPr><w:b/></w:rPr><w:t xml:space="preserve">王延领</w:t></w:r>' in document_xml
    assert '<w:r><w:rPr><w:b/></w:rPr><w:t xml:space="preserve">[00:00:00 - 00:00:07]</w:t></w:r>' in document_xml


def test_download_meeting_document_pdf_conversion_by_id(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    document_path = tmp_path / "data" / "documents" / "meeting.md"
    document_path.parent.mkdir(parents=True)
    document_path.write_text("# hello\n\n正文", encoding="utf-8")

    class FakeDB:
        def get_meeting_document_by_id(self, document_id):
            assert document_id == 7
            return {
                "id": 7,
                "file_name": "meeting.md",
                "file_path": str(document_path),
            }

    monkeypatch.setattr(database_api, "db", FakeDB())

    response = database_api.app.test_client().get(
        "/api/meetings/documents/download?document_id=7&format=pdf"
    )

    assert response.status_code == 200
    assert response.mimetype == database_api.PDF_MIMETYPE
    assert response.data.startswith(b"%PDF")
    assert "meeting.pdf" in response.headers["Content-Disposition"]


def test_delete_meeting_document_rejects_database_path_outside_documents(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    outside_file = tmp_path / "outside.md"
    outside_file.write_text("do not delete", encoding="utf-8")

    class FakeDB:
        deleted = False

        def get_meeting_document_by_id(self, document_id):
            return {
                "id": document_id,
                "file_name": "outside.md",
                "file_path": str(outside_file),
            }

        def delete_meeting_document(self, document_id):
            self.deleted = True
            return 1

    fake_db = FakeDB()
    monkeypatch.setattr(database_api, "db", fake_db)

    response = database_api.app.test_client().delete("/api/meetings/documents/9")

    assert response.status_code == 400
    assert outside_file.exists()
    assert fake_db.deleted is False


def test_delete_meeting_cascades_documents_and_removes_safe_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    manager = DatabaseManager(str(tmp_path / "wyl_asr.db"))
    meeting_id = manager.create_meeting("安全清理会议")
    document_path = tmp_path / "data" / "documents" / "minutes.md"
    document_path.parent.mkdir(parents=True)
    document_path.write_text("minutes", encoding="utf-8")
    manager.save_meeting_document(meeting_id, "minutes", "minutes.md", str(document_path), document_path.stat().st_size)

    assert document_path.exists()

    assert manager.delete_meeting(meeting_id) == 1

    assert not document_path.exists()
    assert manager.get_meeting(meeting_id) is None
    assert manager.get_meeting_documents(meeting_id) == []


def test_uploaded_audio_segments_link_to_meeting_and_cascade_delete(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    manager = DatabaseManager(str(tmp_path / "wyl_asr.db"))
    monkeypatch.setattr(database_api, "db", manager)

    columns = {
        row["name"]
        for row in manager.execute_query("PRAGMA table_info(uploaded_audio_segments)")
    }
    assert "meeting_id" in columns

    audio_path = tmp_path / "data" / "audio" / "uploads" / "sample.wav"
    audio_path.parent.mkdir(parents=True)
    audio_path.write_bytes(b"audio")
    task_id = database_api._create_upload_task(
        file_name="sample.wav",
        saved_file_name="sample.wav",
        saved_path=str(audio_path),
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

    response = database_api.app.test_client().post(
        "/api/meetings/save-documents",
        json={
            "title": "上传识别会议",
            "transcriptionContent": "说话人1: 上传识别文本",
            "uploadTaskId": task_id,
        }
    )
    assert response.status_code == 201
    meeting_id = response.get_json()["data"]["meeting_id"]

    rows = manager.execute_query(
        "SELECT meeting_id, text FROM uploaded_audio_segments WHERE task_id = ?",
        (task_id,)
    )
    assert len(rows) == 1
    assert rows[0]["meeting_id"] == meeting_id

    database_api._save_upload_result_for_task(task_id, {
        "segments": [
            {
                "speaker": "说话人1",
                "text": "校正后的上传识别文本",
                "startMs": 0,
                "endMs": 1000,
                "mode": "uploaded-audio"
            }
        ],
        "plain_text": "校正后的上传识别文本"
    })
    rows = manager.execute_query(
        "SELECT meeting_id, text FROM uploaded_audio_segments WHERE task_id = ?",
        (task_id,)
    )
    assert rows[0]["meeting_id"] == meeting_id
    assert rows[0]["text"] == "校正后的上传识别文本"

    assert manager.delete_meeting(meeting_id) == 1
    assert manager.execute_query(
        "SELECT * FROM uploaded_audio_segments WHERE meeting_id = ?",
        (meeting_id,)
    ) == []
    assert manager.execute_query(
        "SELECT * FROM uploaded_audio_tasks WHERE task_id = ?",
        (task_id,)
    )


def test_llm_gateway_ssl_verification_defaults_to_enabled(monkeypatch):
    monkeypatch.delenv("LLM_CA_BUNDLE", raising=False)
    monkeypatch.delenv("LLM_VERIFY_SSL", raising=False)

    assert database_api._get_llm_verify_setting() is True

    monkeypatch.setenv("LLM_CA_BUNDLE", "/tmp/local-ca.pem")
    assert database_api._get_llm_verify_setting() == "/tmp/local-ca.pem"

    monkeypatch.delenv("LLM_CA_BUNDLE", raising=False)
    monkeypatch.setenv("LLM_VERIFY_SSL", "false")
    assert database_api._get_llm_verify_setting() is False
