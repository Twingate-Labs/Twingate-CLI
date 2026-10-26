"""Text files and streams that behave the same on Windows as elsewhere."""

from __future__ import annotations

import io

import pytest

from tgcli.textio import TextFileError, check_writable, decode_text, ensure_utf8_output, read_text

GREEK = "Ελληνικά 日本語 😀"


class TestDecodeText:
    @pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "utf-16", "utf-16-le", "utf-16-be", "utf-32"])
    def test_the_encodings_windows_tools_save_files_in(self, encoding):
        data = GREEK.encode(encoding)
        if encoding in ("utf-16-le", "utf-16-be"):
            data = (b"\xff\xfe" if encoding.endswith("le") else b"\xfe\xff") + data  # a mark, as PowerShell writes
        assert decode_text(data) == GREEK

    def test_plain_ascii_and_empty(self):
        assert decode_text(b"abc, def\n") == "abc, def\n" and decode_text(b"") == ""

    def test_a_byte_order_mark_is_not_left_in_the_text(self):
        assert decode_text(b"\xef\xbb\xbf" + b"id1,id2") == "id1,id2"
        assert not decode_text("x".encode("utf-16")).startswith("﻿")

    def test_bytes_that_are_not_text_in_any_of_them_raise(self):
        with pytest.raises(UnicodeDecodeError):
            decode_text(b"\xc3\x28")


class TestReadText:
    def test_reads_a_file_whatever_saved_it(self, tmp_path):
        for name, data in {"a": GREEK.encode(), "b": b"\xef\xbb\xbf" + GREEK.encode(), "c": GREEK.encode("utf-16")}.items():
            (tmp_path / name).write_bytes(data)
            assert read_text(tmp_path / name) == GREEK

    def test_a_file_that_is_not_text_is_a_friendly_error_naming_the_file(self, tmp_path):
        path = tmp_path / "bad.txt"
        path.write_bytes(b"\xc3\x28 bad")
        with pytest.raises(TextFileError, match=r"bad\.txt is not valid UTF-8 text.*Save it as UTF-8"):
            read_text(path)

    def test_a_missing_file_is_still_an_oserror_for_callers_to_handle(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            read_text(tmp_path / "nope")


class _Stream(io.TextIOWrapper):
    pass


class TestEnsureUtf8Output:
    def narrow(self, encoding="cp1252"):
        raw = io.BytesIO()
        return _Stream(raw, encoding=encoding, newline=""), raw

    def test_a_narrow_stream_that_would_crash_now_writes_utf_8(self, monkeypatch):
        stream, raw = self.narrow()
        with pytest.raises(UnicodeEncodeError):
            stream.write(GREEK)
        stream, raw = self.narrow()
        monkeypatch.setattr("sys.stdout", stream)
        monkeypatch.setattr("sys.stderr", stream)
        ensure_utf8_output()
        stream.write(GREEK)
        stream.flush()
        assert raw.getvalue().decode("utf-8") == GREEK

    def test_even_a_character_utf_8_cannot_encode_is_escaped_instead_of_raising(self, monkeypatch):
        stream, raw = self.narrow()
        monkeypatch.setattr("sys.stdout", stream)
        monkeypatch.setattr("sys.stderr", stream)
        ensure_utf8_output()
        stream.write("ok \ud800 ok")  # a lone surrogate, as an undecodable filename byte can produce
        stream.flush()
        assert raw.getvalue() == b"ok \\ud800 ok"

    def test_an_ascii_stream_too(self, monkeypatch):
        stream, raw = self.narrow("ascii")
        monkeypatch.setattr("sys.stdout", stream)
        monkeypatch.setattr("sys.stderr", stream)
        ensure_utf8_output()
        stream.write(GREEK)
        stream.flush()
        assert raw.getvalue().decode("utf-8") == GREEK

    def test_a_stream_that_is_already_utf_8_is_left_alone(self, monkeypatch):
        class Spy:
            encoding = "UTF-8"
            def reconfigure(self, **kw):
                raise AssertionError("must not be touched")
        monkeypatch.setattr("sys.stdout", Spy())
        monkeypatch.setattr("sys.stderr", Spy())
        ensure_utf8_output()

    @pytest.mark.parametrize("spelling", ["utf-8", "UTF-8", "utf8", "UTF8", "Utf_8"])
    def test_every_spelling_of_utf_8_counts(self, spelling, monkeypatch):
        class Spy:
            encoding = spelling
            def reconfigure(self, **kw):
                raise AssertionError("must not be touched")
        monkeypatch.setattr("sys.stdout", Spy())
        monkeypatch.setattr("sys.stderr", Spy())
        ensure_utf8_output()

    def test_streams_that_cannot_be_reconfigured_or_do_not_exist_do_not_crash(self, monkeypatch):
        class NoReconfigure:
            encoding = "cp1252"
        monkeypatch.setattr("sys.stdout", NoReconfigure())
        monkeypatch.setattr("sys.stderr", None)
        ensure_utf8_output()

    def test_a_refusal_to_reconfigure_is_ignored(self, monkeypatch):
        class Refuses:
            encoding = "cp1252"
            def reconfigure(self, **kw):
                raise ValueError("no")
        monkeypatch.setattr("sys.stdout", Refuses())
        monkeypatch.setattr("sys.stderr", Refuses())
        ensure_utf8_output()


class TestCheckWritable:
    def test_a_path_that_can_be_written_is_not_left_behind(self, tmp_path):
        target = tmp_path / "report.csv"
        check_writable(target)
        assert not target.exists()

    def test_an_existing_file_is_left_exactly_as_it_was(self, tmp_path):
        target = tmp_path / "report.csv"
        target.write_text("keep me", encoding="utf-8")
        check_writable(target)
        assert target.read_text(encoding="utf-8") == "keep me"

    def test_a_missing_folder_raises_before_anything_else_happens(self, tmp_path):
        with pytest.raises(OSError):
            check_writable(tmp_path / "no-such-folder" / "report.csv")

    def test_a_folder_in_place_of_a_file_raises(self, tmp_path):
        with pytest.raises(OSError):
            check_writable(tmp_path)
