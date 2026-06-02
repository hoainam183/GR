"""Regression tests for crawler HTML-to-text extraction."""

from __future__ import annotations


TUITION_HTML = """
<div class="col-md-9 col-xs-12">
  <h3>KẾ HOẠCH NỘP HỌC PHÍ KỲ 2 NĂM HỌC 2025-2026</h3>
  <span style="font-size:16px;">a) Sinh viên tra cứu học phí học kỳ 2 đợt 2 năm học 2025-2026 từ ngày <strong>01/06/2026</strong> bằng cách đăng nhập tài khoản trên Cổng thông tin sinh viên (ctt.hust.edu.vn), vào mục “<strong>Dịch vụ</strong>” và sau đó vào xem tại phần “<strong>Học phí – Công nợ</strong>”.<br>
  b) Học phí của mỗi học kỳ được tính toán theo 02 đợt: Đợt 1 tính toán sơ bộ học phí cần đóng, sau đó Đợt 2 sẽ tính lại chính xác học phí của học kỳ.<br>
  + Tổng số học phí cần đóng Đợt 2 này đã đúng hay chưa.</span>
</div>
"""


def test_auto_crawler_keeps_inline_tags_inline() -> None:
    from scripts.auto_crawler import GenericCrawler

    detail = GenericCrawler()._parse_detail(TUITION_HTML)
    content = detail["content_text"]

    assert "từ ngày 01/06/2026 bằng cách" in content
    assert "mục “Dịch vụ”" in content
    assert "phần “Học phí – Công nợ”." in content
    assert "\n01/06/2026\n" not in content
    assert "“\nDịch vụ\n”" not in content
    assert "\nb) Học phí" in content
    assert "\n+ Tổng số học phí" in content


def test_reprocess_content_text_uses_same_inline_safe_extraction() -> None:
    from data.kehoach.reprocess_content_text import reparse_content_text

    content = reparse_content_text(TUITION_HTML)

    assert "từ ngày 01/06/2026 bằng cách" in content
    assert "mục “Dịch vụ”" in content
    assert "\n01/06/2026\n" not in content
