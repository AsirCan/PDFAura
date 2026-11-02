"""Comprehensive Adversarial Stress & Red-Team Security Tests for PDFAura.

Probes:
1. Null-byte injection in paths (path\\x00.pdf) and directory breakout attempts.
2. Massive inputs (100k+ chars, deeply nested brackets, pathological regex inputs).
3. Corrupt, empty (0-byte), or pseudo-PDF files fed to all tools (must raise friendly errors or return gracefully, never crash or leave locks).
4. Rapid multi-threaded start/cancel cycles on AI and security jobs to verify zero deadlocks and zero dangling threads.
5. Unicode edge cases: RTL override characters (U+202E), zero-width spaces, mixed scripts in passwords/watermarks/filenames.
6. Read-only destinations, missing input files, non-existent directories.
"""
from __future__ import annotations

import io
import os
import shutil
import stat
import tempfile
import threading
import time
from pathlib import Path

import pytest
from pypdf import PdfWriter

from src.ai import action_runner, intent_parser, rag_engine, summarizer, presentation, student_mode
from src.ai.document_loader import file_hash, load_document, LoadedDocument, PageText
from src.app import tools
from src.cli import _require_input
from src.core import compare, redact, security, smart_namer, tables, updater
from src.core.errors import friendly_error
from src.core.task_manager import CancelledError, TaskContext


# ── Helpers ─────────────────────────────────────────────────────────────────

def _make_dummy_pdf(path: str | Path, pages: int = 2, content: str = "PDFAura Security Test") -> str:
    """Create a minimal valid PDF with selectable text."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        import fitz
        doc = fitz.open()
        for i in range(pages):
            page = doc.new_page(width=595, height=842)
            page.insert_text((72, 72), f"{content} - Page {i + 1}\nFatura No: FAT-2026-001\nTarih: 2026-11-02", fontsize=12)
        doc.save(str(p))
        doc.close()
    except Exception:
        writer = PdfWriter()
        for _ in range(pages):
            writer.add_blank_page(width=595, height=842)
        with open(p, "wb") as f:
            writer.write(f)
    return str(p)


@pytest.fixture
def temp_workspace(tmp_path):
    """Provide an isolated workspace with pre-created dummy PDFs."""
    sample_pdf = _make_dummy_pdf(tmp_path / "sample.pdf", pages=3)
    empty_pdf = tmp_path / "empty_0byte.pdf"
    empty_pdf.write_bytes(b"")

    corrupt_pdf = tmp_path / "corrupt.pdf"
    corrupt_pdf.write_bytes(b"%PDF-1.4\n%corrupt truncated binary junk without trailer")

    pseudo_pdf = tmp_path / "pseudo.pdf"
    pseudo_pdf.write_text("This is plain text pretending to be a PDF file", encoding="utf-8")

    return {
        "root": tmp_path,
        "sample": sample_pdf,
        "empty": str(empty_pdf),
        "corrupt": str(corrupt_pdf),
        "pseudo": str(pseudo_pdf),
    }


# ── 1. NULL-BYTE INJECTION & DIRECTORY BREAKOUT TESTS ───────────────────────

class TestNullByteAndDirectoryBreakout:
    """Actively probes null-byte injection and directory traversal attacks."""

    def test_action_runner_null_byte_input(self, temp_workspace):
        intent = {
            "input_file": "document\x00.pdf",
            "action_chain": [{"action": "compress", "kwargs": {"quality": "screen"}}],
        }
        res = action_runner.execute_intent(intent)
        assert res["ok"] is False
        assert "error" in res and res["error"]

    def test_action_runner_null_byte_extra_paths(self, temp_workspace):
        intent = {
            "input_file": temp_workspace["sample"],
            "input_files": [temp_workspace["sample"], "evil\x00merge.pdf"],
            "action_chain": [{"action": "merge", "kwargs": {}}],
        }
        res = action_runner.execute_intent(intent)
        assert res["ok"] is False
        assert res["error"]

    def test_action_runner_null_byte_output_target(self, temp_workspace):
        intent = {
            "input_file": temp_workspace["sample"],
            "output_target": str(temp_workspace["root"]) + "\x00/sub",
            "action_chain": [{"action": "compress", "kwargs": {"quality": "ebook"}}],
        }
        res = action_runner.execute_intent(intent)
        # Should gracefully fall back to safe directory or report error, never crash
        assert "error" in res

    def test_tools_require_file_rejects_null_byte(self):
        err = tools.check("compress", {"input": "sample\x00.pdf", "output": "out.pdf", "quality": "ebook"})
        assert err is not None
        with pytest.raises(tools.Invalid):
            tools.get("compress").check("sample\x00.pdf", "out.pdf", "ebook")

    def test_tools_require_value_rejects_null_byte(self, temp_workspace):
        err = tools.check("compress", {"input": temp_workspace["sample"], "output": "out\x00.pdf", "quality": "ebook"})
        assert err is not None
        with pytest.raises(tools.Invalid):
            tools.get("compress").check(temp_workspace["sample"], "out\x00.pdf", "ebook")

    def test_security_encrypt_decrypt_null_byte(self, temp_workspace):
        with pytest.raises(ValueError, match="null character"):
            security.encrypt_pdf("in\x00.pdf", str(temp_workspace["root"] / "out.pdf"), "pass123")
        with pytest.raises(ValueError, match="null character"):
            security.encrypt_pdf(temp_workspace["sample"], "out\x00.pdf", "pass123")
        with pytest.raises(ValueError, match="null character"):
            security.decrypt_pdf("in\x00.pdf", str(temp_workspace["root"] / "out.pdf"), "pass123")

    def test_security_watermark_null_byte(self, temp_workspace):
        with pytest.raises(ValueError, match="null character"):
            security.add_watermark_to_pdf("in\x00.pdf", "out.pdf", "WATERMARK")
        with pytest.raises(ValueError):
            security.add_watermark_to_pdf(temp_workspace["sample"], "out.pdf", "WATERMARK", image_path="logo\x00.png")

    def test_security_decrypt_many_null_byte(self, temp_workspace):
        with pytest.raises(ValueError, match="null character"):
            security.decrypt_many([temp_workspace["sample"]], "pass", "out\x00_dir")

    def test_security_check_password_null_byte(self):
        with pytest.raises(ValueError, match="null character"):
            security.check_new_password("secret\x00pass")

    def test_smart_namer_null_byte_handling(self, temp_workspace):
        assert smart_namer.extract_first_page_text("sample\x00.pdf") == ""
        plan = smart_namer.plan_batch_rename("folder\x00")
        assert plan == []
        with pytest.raises(ValueError, match="null character"):
            smart_namer.plan_batch_rename(temp_workspace["root"], output_folder="out\x00dir")

    def test_smart_namer_apply_batch_rename_null_byte(self, temp_workspace):
        plan = [
            {"old_path": "fake\x00.pdf", "new_path": "safe.pdf", "type": "fatura"},
            {"old_path": temp_workspace["sample"], "new_path": "valid_aura.pdf", "type": "fatura"},
        ]
        results = smart_namer.apply_batch_rename(plan)
        assert len(results) == 2
        assert results[0]["success"] is False
        assert "null character" in str(results[0]["error"])
        assert results[1]["success"] is True

    def test_tables_null_byte_rejection(self, temp_workspace):
        with pytest.raises(ValueError, match="null character"):
            tables.extract_tables("path\x00.pdf")
        with pytest.raises(ValueError, match="null character"):
            tables.export_csv([], "out\x00_dir")
        with pytest.raises(ValueError, match="null character"):
            tables.export_xlsx([{"page": 1, "rows": [["a"]]}], "out\x00.xlsx")

    def test_compare_null_byte_rejection(self, temp_workspace):
        with pytest.raises(ValueError, match="null character"):
            compare.compare_pdfs("a\x00.pdf", temp_workspace["sample"])

    def test_document_loader_null_byte(self, temp_workspace):
        with pytest.raises(ValueError, match="null character"):
            file_hash("test\x00.pdf")
        with pytest.raises(ValueError, match="null character"):
            load_document("test\x00.pdf")

    def test_cli_require_input_null_byte(self):
        with pytest.raises(ValueError, match="null character"):
            _require_input("test\x00.pdf")

    def test_directory_traversal_tables_csv(self, temp_workspace):
        # Attempt breakout via custom path
        out_dir = temp_workspace["root"] / "csv_out"
        out_dir.mkdir()
        dummy_tables = [{"page": 1, "rows": [["Col1", "Col2"], ["Val1", "Val2"]]}]
        written = tables.export_csv(dummy_tables, str(out_dir))
        for p in written:
            assert Path(p).resolve().is_relative_to(out_dir.resolve())

    def test_directory_traversal_smart_namer_apply(self, temp_workspace):
        out_dir = temp_workspace["root"] / "target_dir"
        out_dir.mkdir()
        plan = [{
            "old_path": temp_workspace["sample"],
            "new_path": "../../escaped.pdf",
            "type": "fatura",
        }]
        results = smart_namer.apply_batch_rename(plan, output_folder=str(out_dir))
        assert len(results) == 1
        # The filename sanitizer or traversal guard must prevent escape
        applied = Path(results[0]["applied_path"]).resolve()
        assert applied.is_relative_to(out_dir.resolve())

    def test_updater_safe_filename_traversal(self):
        assert updater._safe_filename("../../../Windows/System32/calc.exe") == "calc.exe"
        assert updater._safe_filename("..\\..\\Windows\\System32\\cmd.exe") == "cmd.exe"
        assert updater._safe_filename("malicious.sh", fallback="PDFAura-Setup.exe") == "PDFAura-Setup.exe"


# ── 2. MASSIVE & PATHOLOGICAL INPUTS ────────────────────────────────────────

class TestMassiveAndPathologicalInputs:
    """Probes 100k+ char inputs, deeply nested brackets, and ReDoS resistance."""

    def test_intent_parser_massive_100k_chars(self):
        massive_text = "deneme.pdf dosyasını sıkıştır " + ("ve böl " * 20000)
        assert len(massive_text) > 100000

        t0 = time.perf_counter()
        intent = intent_parser.parse_intent(massive_text, use_llm=False)
        duration = time.perf_counter() - t0

        assert duration < 2.0  # Must parse within 2 seconds, no ReDoS
        assert isinstance(intent, dict)
        assert intent.get("input_file") == "deneme.pdf"

    def test_intent_parser_deeply_nested_brackets(self):
        nested = "[" * 2000 + "{" * 2000 + "deneme.pdf dosyasını sıkıştır" + "}" * 2000 + "]" * 2000
        t0 = time.perf_counter()
        intent = intent_parser.parse_intent(nested, use_llm=False)
        duration = time.perf_counter() - t0
        assert duration < 1.0
        assert isinstance(intent, dict)

    def test_parse_watermark_text_massive_100k(self):
        massive = "filigran metni: " + ("GİZLİ " * 15000)
        t0 = time.perf_counter()
        text = intent_parser.parse_watermark_text(massive)
        duration = time.perf_counter() - t0
        assert duration < 1.0
        assert isinstance(text, str)
        assert len(text) <= 60

    def test_parse_password_massive_100k(self):
        massive = "şifre: " + ("A" * 100000)
        t0 = time.perf_counter()
        pwd = intent_parser.parse_password(massive)
        duration = time.perf_counter() - t0
        assert duration < 1.0

    def test_parse_target_folder_massive_100k(self):
        massive = "Masaüstü klasörüne kaydet " + ("detay " * 20000)
        t0 = time.perf_counter()
        folder = intent_parser.parse_target_folder(massive)
        duration = time.perf_counter() - t0
        assert duration < 1.0
        assert folder is not None

    def test_redact_validators_massive_100k(self):
        huge_str = "9" * 100000
        # Check all validators terminate in microseconds without hang
        t0 = time.perf_counter()
        assert redact.is_valid_tc_kimlik(huge_str) is False
        assert redact.is_valid_iban(huge_str) is False
        assert redact.normalize_phone(huge_str) is None
        assert redact.is_valid_tax_number(huge_str) is False
        assert redact.is_valid_credit_card(huge_str) is False
        assert redact._is_valid_email("user@" + ("a" * 100000) + ".com") is True or False
        duration = time.perf_counter() - t0
        assert duration < 0.2

    def test_security_check_password_massive_100k(self):
        huge_pwd = "P" * 100000
        with pytest.raises(ValueError, match="too long"):
            security.check_new_password(huge_pwd)

    def test_smart_namer_heuristics_massive_100k(self):
        massive = "Fatura Belgesi " + ("Elektrik ve su tüketim bedeli " * 5000)
        t0 = time.perf_counter()
        doc_type = smart_namer._classify_document_type(massive)
        date_str = smart_namer._extract_date_from_text(massive)
        subj = smart_namer._extract_subject_from_text(massive, doc_type)
        duration = time.perf_counter() - t0
        assert duration < 1.0
        assert doc_type == "fatura"

    def test_smart_namer_sanitize_filename_massive(self):
        massive_name = ("a" * 10000) + ".pdf"
        sanitized = smart_namer.sanitize_filename(massive_name)
        assert len(sanitized) <= 204  # 200 stem + .pdf

    def test_rag_engine_massive_question_100k(self, temp_workspace):
        engine = rag_engine.RagEngine(use_llm=False)
        massive_q = "Nedir? " + ("detay sorusu " * 15000)
        ans = engine.ask(temp_workspace["sample"], massive_q)
        assert isinstance(ans, rag_engine.RagAnswer)


# ── 3. CORRUPT, EMPTY (0-BYTE), AND PSEUDO-PDF TESTS ────────────────────────

class TestCorruptEmptyAndPseudoPdfs:
    """Verifies that 0-byte and damaged files yield friendly errors without leaks."""

    def test_zero_byte_pdf_document_loader(self, temp_workspace):
        with pytest.raises(Exception) as exc_info:
            load_document(temp_workspace["empty"], use_cache=False)
        assert friendly_error(exc_info.value) is not None

    def test_corrupt_pdf_document_loader(self, temp_workspace):
        with pytest.raises(Exception) as exc_info:
            load_document(temp_workspace["corrupt"], use_cache=False)
        msg = friendly_error(exc_info.value)
        assert "bozuk" in msg.lower() or "damaged" in msg.lower() or "broken" in msg.lower()

    def test_zero_byte_pdf_in_tables(self, temp_workspace):
        with pytest.raises(Exception) as exc_info:
            tables.extract_tables(temp_workspace["empty"])
        msg = friendly_error(exc_info.value)
        assert msg

    def test_corrupt_pdf_in_tables(self, temp_workspace):
        with pytest.raises(Exception) as exc_info:
            tables.extract_tables(temp_workspace["corrupt"])
        msg = friendly_error(exc_info.value)
        assert msg

    def test_zero_byte_pdf_in_compare(self, temp_workspace):
        with pytest.raises(Exception) as exc_info:
            compare.compare_pdfs(temp_workspace["empty"], temp_workspace["sample"])
        msg = friendly_error(exc_info.value)
        assert msg

    def test_zero_byte_pdf_in_security_tools(self, temp_workspace):
        out = str(temp_workspace["root"] / "out_sec.pdf")
        with pytest.raises(Exception) as exc1:
            security.encrypt_pdf(temp_workspace["empty"], out, "pass123")
        assert friendly_error(exc1.value)

        with pytest.raises(Exception) as exc2:
            security.decrypt_pdf(temp_workspace["empty"], out, "pass123")
        assert friendly_error(exc2.value)

        with pytest.raises(Exception) as exc3:
            security.add_watermark_to_pdf(temp_workspace["empty"], out, "GIZLI")
        assert friendly_error(exc3.value)

    def test_zero_byte_pdf_in_smart_namer(self, temp_workspace):
        # Should gracefully return empty text or diger without crash
        text = smart_namer.extract_first_page_text(temp_workspace["empty"])
        assert text == ""
        meta = smart_namer.extract_metadata_fields(temp_workspace["empty"])
        assert meta["document_type"] == "diger"

    def test_corrupt_pdf_in_smart_namer(self, temp_workspace):
        text = smart_namer.extract_first_page_text(temp_workspace["corrupt"])
        assert text == ""
        meta = smart_namer.extract_metadata_fields(temp_workspace["corrupt"])
        assert meta["document_type"] == "diger"

    def test_pseudo_pdf_in_summarizer(self, temp_workspace):
        with pytest.raises(Exception) as exc_info:
            summarizer.summarize(temp_workspace["pseudo"], use_llm=False)
        assert friendly_error(exc_info.value)

    def test_zero_byte_pdf_in_presentation(self, temp_workspace):
        with pytest.raises(Exception) as exc_info:
            presentation.generate_presentation_outline(temp_workspace["empty"], use_llm=False)
        assert friendly_error(exc_info.value)

    def test_zero_byte_pdf_in_student_mode(self, temp_workspace):
        with pytest.raises(Exception) as exc_info:
            student_mode.generate_study_pack(temp_workspace["empty"], use_llm=False)
        assert friendly_error(exc_info.value)

    def test_no_file_lock_leak_on_failure(self, temp_workspace):
        """Verify that after a failure, the input file can be immediately removed."""
        probe_file = temp_workspace["root"] / "probe_lock.pdf"
        probe_file.write_bytes(b"%PDF-1.4 truncated corrupt")
        with pytest.raises(Exception):
            security.encrypt_pdf(str(probe_file), str(temp_workspace["root"] / "unused.pdf"), "p")

        # Windows will fail with PermissionError if any file handle was left open!
        probe_file.unlink()
        assert not probe_file.exists()


# ── 4. RAPID MULTI-THREADED START/CANCEL CYCLES ─────────────────────────────

class TestConcurrencyAndThreadSafety:
    """Verifies that rapid concurrent jobs and cancellations cause zero deadlocks."""

    def test_rapid_task_context_concurrency(self):
        """Spawns 20 threads rapidly checking, notifying, and cancelling contexts."""
        errors: list[Exception] = []

        def worker(idx: int):
            ctx = TaskContext()
            try:
                for step in range(50):
                    if step == 25 and idx % 2 == 0:
                        ctx.cancel()
                    ctx.report_progress(step, 50, f"Step {step}")
                    time.sleep(0.001)
            except CancelledError:
                pass
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)
            assert not t.is_alive(), "Dangling thread detected!"

        assert len(errors) == 0

    def test_rapid_cancellation_cycles_in_action_runner(self, temp_workspace):
        """Tests rapid start and cancel cycles on execute_intent."""
        errors: list[Exception] = []

        def cancel_immediately():
            return True

        for _ in range(15):
            intent = {
                "input_file": temp_workspace["sample"],
                "action_chain": [
                    {"action": "split", "kwargs": {"start": 1, "end": 2}},
                    {"action": "compress", "kwargs": {"quality": "screen"}},
                ],
            }
            res = action_runner.execute_intent(intent, cancel_check=cancel_immediately)
            assert res["ok"] is False
            assert res["cancelled"] is True

    def test_rapid_rag_engine_cancellation(self, temp_workspace):
        """Tests cancelling RagEngine during search/load."""
        engine = rag_engine.RagEngine(use_llm=False)
        ctx = TaskContext()
        ctx.cancel()

        with pytest.raises(CancelledError):
            engine.ask(temp_workspace["sample"], "Test question", cancel=ctx)


# ── 5. UNICODE & RTL EDGE CASES ─────────────────────────────────────────────

class TestUnicodeAndRtlEdgeCases:
    """Tests RTL overrides, zero-width spaces, and mixed scripts."""

    def test_rtl_override_u202e_in_passwords(self, temp_workspace):
        # RTL override character embedded in password
        rtl_password = "safe\u202Eexe.pdf"
        out_enc = str(temp_workspace["root"] / "rtl_enc.pdf")
        out_dec = str(temp_workspace["root"] / "rtl_dec.pdf")

        security.encrypt_pdf(temp_workspace["sample"], out_enc, rtl_password)
        assert os.path.exists(out_enc)

        security.decrypt_pdf(out_enc, out_dec, rtl_password)
        assert os.path.exists(out_dec)

    def test_rtl_override_in_watermark(self, temp_workspace):
        rtl_text = "CONFIDENTIAL\u202ETEXT"
        out_wm = str(temp_workspace["root"] / "rtl_wm.pdf")
        security.add_watermark_to_pdf(temp_workspace["sample"], out_wm, rtl_text)
        assert os.path.exists(out_wm)

    def test_zero_width_spaces_and_special_unicode(self, temp_workspace):
        # Zero-width space U+200B and non-breaking spaces
        odd_string = "G\u200Bİ\u200BZ\u200BL\u200Bİ\uFEFF"
        out_wm = str(temp_workspace["root"] / "zw_wm.pdf")
        security.add_watermark_to_pdf(temp_workspace["sample"], out_wm, odd_string)
        assert os.path.exists(out_wm)

    def test_mixed_scripts_in_filenames_and_sanitization(self):
        # Arabic + Chinese + Cyrillic + Emoji + Turkish
        complex_name = "تقرير_报告_Отчет_🚀_Görüşme_#12?.pdf"
        sanitized = smart_namer.sanitize_filename(complex_name)
        assert not any(c in sanitized for c in '<>:"/\\|?*\x00')
        assert sanitized.endswith(".pdf")

    def test_unicode_normalization_in_intent_parser(self):
        # Combining characters vs precomposed
        text1 = "sözleşme.pdf"
        text2 = "so\u0308zles\u0327me.pdf"
        parsed1 = intent_parser.parse_input_files(text1)
        parsed2 = intent_parser.parse_input_files(text2)
        assert len(parsed1) == 1
        assert len(parsed2) == 1


# ── 6. FILESYSTEM EDGE CASES: READ-ONLY & NON-EXISTENT DIRS ─────────────────

class TestFilesystemEdgeCases:
    """Tests read-only destinations, missing files, and unmapped paths."""

    def test_missing_input_file_friendly_errors(self, temp_workspace):
        missing = str(temp_workspace["root"] / "does_not_exist_404.pdf")
        with pytest.raises(FileNotFoundError) as exc_info:
            security.encrypt_pdf(missing, "out.pdf", "pass")
        friendly = friendly_error(exc_info.value)
        assert "bulunamadı" in friendly.lower() or "missing" in friendly.lower() or "not found" in friendly.lower()

    def test_missing_input_in_cli(self):
        with pytest.raises(FileNotFoundError):
            _require_input("nonexistent_random_file_xyz.pdf")

    def test_read_only_destination_handling(self, temp_workspace):
        ro_file = temp_workspace["root"] / "readonly_dest.pdf"
        _make_dummy_pdf(ro_file, pages=1)
        # Mark file as read-only on Windows
        os.chmod(str(ro_file), stat.S_IREAD)
        try:
            with pytest.raises((PermissionError, OSError)):
                security.encrypt_pdf(temp_workspace["sample"], str(ro_file), "pass123")
        finally:
            # Restore write permission for cleanup
            os.chmod(str(ro_file), stat.S_IWRITE | stat.S_IREAD)
