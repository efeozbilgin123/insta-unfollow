import json
import os
import time

import pytest

from istek_geri_cek.zip_reader import ExportError, find_export_zip, read_usernames

P = "connections/followers_and_following/"


def test_json_pending_value_field(make_zip):
    z = make_zip({P + "pending_follow_requests.json": json.dumps({"relationships_follow_requests_sent": [
        {"title": "", "string_list_data": [{"href": "https://www.instagram.com/Ali.Veli", "value": "Ali.Veli", "timestamp": 1}]}]})})
    assert read_usernames(z) == ["ali.veli"]


def test_json_title_and_u_href_fallback(make_zip):
    z = make_zip({"x/pending_follow_requests.json": json.dumps({"relationships_follow_requests_sent": [
        {"title": "zeynep_99", "string_list_data": [{"href": "https://www.instagram.com/_u/zeynep_99/"}]},
        {"title": "", "string_list_data": [{"href": "https://www.instagram.com/_u/mehmet.k/"}]}]})})
    assert read_usernames(z) == ["zeynep_99", "mehmet.k"]


def test_merges_recent_and_dedupes(make_zip):
    def doc(key, names):
        return json.dumps({key: [{"title": "", "string_list_data": [{"value": n}]} for n in names]})
    z = make_zip({
        P + "pending_follow_requests.json": doc("relationships_follow_requests_sent", ["a"]),
        P + "recent_follow_requests.json": doc("relationships_permanent_follow_requests", ["A", "b"]),
    })
    assert read_usernames(z) == ["a", "b"]


def test_html_format(make_zip):
    z = make_zip({P + "pending_follow_requests.html":
        '<html><body><a href="https://www.instagram.com/ayse.y">ayse.y</a>'
        '<a href="https://www.instagram.com/_u/can_01/">can_01</a>'
        '<a href="https://help.instagram.com/123">yardım</a></body></html>'})
    assert read_usernames(z) == ["ayse.y", "can_01"]


def test_nested_top_folder(make_zip):
    z = make_zip({"instagram-ali-2026-11-15/" + P + "pending_follow_requests.json":
        json.dumps({"relationships_follow_requests_sent": [{"title": "", "string_list_data": [{"value": "x_y"}]}]})})
    assert read_usernames(z) == ["x_y"]


def test_not_a_zip(tmp_path):
    p = tmp_path / "x.zip"
    p.write_text("hello")
    with pytest.raises(ExportError) as e:
        read_usernames(p)
    assert e.value.kind == "not_zip"


def test_zip_without_requests(make_zip):
    z = make_zip({P + "followers_1.json": "[]"})
    with pytest.raises(ExportError) as e:
        read_usernames(z)
    assert e.value.kind == "no_requests"


def test_find_export_zip_picks_newest(tmp_path):
    old = tmp_path / "instagram-ali-2026-01-01.zip"
    new = tmp_path / "instagram-ali-2026-11-15.zip"
    other = tmp_path / "foo.zip"
    for f in (old, new, other):
        f.write_bytes(b"x")
    now = time.time()
    os.utime(old, (now - 100, now - 100))
    os.utime(new, (now - 50, now - 50))
    os.utime(other, (now, now))
    assert find_export_zip(tmp_path) == new
    assert find_export_zip(tmp_path / "missing") is None


def test_non_string_fields_are_ignored(make_zip):
    z = make_zip({P + "pending_follow_requests.json": json.dumps({"relationships_follow_requests_sent": [
        {"title": 5, "string_list_data": [{"value": None, "href": "https://www.instagram.com/ok_user"}]},
        {"title": ["x"], "string_list_data": [{"value": 12}]}]})})
    assert read_usernames(z) == ["ok_user"]


def test_unreadable_member_is_not_zip(tmp_path):
    import zipfile
    p = tmp_path / "instagram-bad.zip"
    with zipfile.ZipFile(p, "w", zipfile.ZIP_STORED) as z:
        z.writestr(P + "pending_follow_requests.json", '{"a": "' + "x" * 200 + '"}')
    raw = bytearray(p.read_bytes())
    i = raw.index(b"xxxx")
    raw[i:i + 4] = b"yyyy"  # bozuk CRC
    p.write_bytes(bytes(raw))
    with pytest.raises(ExportError) as e:
        read_usernames(p)
    assert e.value.kind == "not_zip"
