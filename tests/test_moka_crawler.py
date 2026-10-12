"""MokaCrawler: WAF cookie dance, AES-CBC payload decryption, normalization."""

from __future__ import annotations

import base64
import json
from unittest.mock import Mock

import pytest
from Crypto.Cipher import AES

from findjobs.job_crawler_v2 import CRAWLERS, NAMES, DJICrawler, MokaCrawler, _strip_html

KEY = b"0123456789abcdef"
IV_STR = "fedcba9876543210"
IV = IV_STR.encode()


def _encrypt(obj: dict) -> dict:
    raw = json.dumps(obj, ensure_ascii=False).encode()
    pad = 16 - len(raw) % 16
    ct = AES.new(KEY, AES.MODE_CBC, IV).encrypt(raw + bytes([pad]) * pad)
    return {"data": base64.b64encode(ct).decode(), "necromancer": KEY.decode()}


def _crawler() -> MokaCrawler:
    return MokaCrawler("apply.example.com", "social-recruitment", "acme", "12345", "测试", max_jobs=5)


def _mock_request(inst, responses):
    """queue of (text, json_body) tuples; GETs and POSTs consume in order."""
    calls = []

    def fake_request(url, method="GET", **kwargs):
        calls.append((method, url))
        text, body = responses[len(calls) - 1]
        resp = Mock()
        resp.text = text
        resp.json = lambda: body
        return resp

    inst._request = fake_request
    return calls


def test_decrypt_round_trip():
    payload = _encrypt({"data": {"jobs": [{"title": "工程师"}], "jobStats": {"total": 1}}})
    out = MokaCrawler._decrypt(payload, IV_STR)
    assert out["data"]["jobs"][0]["title"] == "工程师"


def test_strip_html_keeps_text_and_breaks():
    assert _strip_html("<p>职责：</p><p>写代码<br>测代码</p>") == "职责：\n写代码\n测代码"


def test_get_aes_iv_retries_past_the_waf_stub_page():
    c = _crawler()
    full_page = 'x<input id="init-data" value="{&quot;aesIv&quot;:&quot;' + IV_STR + '&quot;}">y'
    calls = _mock_request(c, [("stub", {}), (full_page, {})])
    assert c._get_aes_iv() == IV_STR
    assert [m for m, _ in calls] == ["GET", "GET"]


def test_crawl_decrypts_and_normalizes():
    c = _crawler()
    page = '<input id="init-data" value="{&quot;aesIv&quot;:&quot;' + IV_STR + '&quot;}">'
    body = _encrypt({
        "code": 0,
        "data": {
            "jobStats": {"total": 2},
            "jobs": [
                {
                    "id": "abc-1",
                    "title": "高级后端工程师",
                    "jobDescription": "<p>做服务端</p>",
                    "locations": [{"cityName": "深圳市"}, {"cityName": "北京市"}, {"cityName": "深圳市"}],
                },
                {"id": "abc-2", "title": "产品经理", "jobDescription": "<p>定方向</p>", "locations": []},
            ],
        },
    })
    _mock_request(c, [(page, {}), ("", body)])
    jobs = c.crawl()

    assert len(jobs) == 2
    first = jobs[0]
    assert first["company_name"] == "测试"
    assert first["job_title"] == "高级后端工程师"
    assert first["job_id"] == "acme_abc-1"
    assert first["location"] == "深圳市 / 北京市"
    assert first["category"] == "社招"
    assert first["job_description"] == "做服务端"
    assert first["apply_url"] == "https://apply.example.com/social-recruitment/acme/12345#/job/abc-1"


def test_crawl_gives_up_cleanly_without_aes_iv():
    c = _crawler()
    _mock_request(c, [("no init data here", {}), ("still nothing", {})])
    assert c.crawl() == []


def test_registry_names_cover_every_adapter():
    assert set(CRAWLERS) == set(NAMES)
    for key, cls in CRAWLERS.items():
        inst = cls(max_jobs=1)
        assert inst.company_name == NAMES[key]


def test_dji_points_at_the_moka_site():
    dji = DJICrawler(max_jobs=1)
    assert dji.site_url == "https://apply.careers.dji.com/social-recruitment/dji/170070"
