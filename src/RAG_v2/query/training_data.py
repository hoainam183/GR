"""Labeled training data for the domain classifier.

Each sample is a (query, labels) tuple where labels is a list. Labels:
- ``chitchat``: greetings, small talk, thanks, unrelated topics
- ``tool_search``: requires real-time / external web data
- ``ctdt``: chương trình đào tạo, môn học, tín chỉ, khoa/viện
- ``quydinh``: quy chế, quy định, điều kiện, kỷ luật, học bổng
- ``kehoach``: lịch thi, lịch học, thông báo, đăng ký môn, sự kiện
- ``stsv``: thủ tục sinh viên, KTX, bảo hiểm, thẻ SV, hỗ trợ

Multi-label samples (lists with >1 element) represent genuinely cross-domain
queries where retrieval from multiple collections is needed.
"""

from __future__ import annotations

from typing import List, Tuple, Union

# ─── Label constants ────────────────────────────────────────────────────────────
LABEL_CHITCHAT = "chitchat"
LABEL_TOOL_SEARCH = "tool_search"
LABEL_CTDT = "ctdt"
LABEL_QUYDINH = "quydinh"
LABEL_KEHOACH = "kehoach"
LABEL_STSV = "stsv"

ALL_LABELS = [
    LABEL_CHITCHAT,
    LABEL_TOOL_SEARCH,
    LABEL_CTDT,
    LABEL_QUYDINH,
    LABEL_KEHOACH,
    LABEL_STSV,
]

# Labels that map to intent="rag"
RAG_LABELS = {LABEL_CTDT, LABEL_QUYDINH, LABEL_KEHOACH, LABEL_STSV}

# ─── Training samples (single-label) ──────────────────────────────────────────
# Kept as List[Tuple[str, str]] intentionally; get_training_data() converts them
# to the multi-label format List[Tuple[str, List[str]]] at call time.
TRAINING_DATA: List[Tuple[str, str]] = [
    # ── chitchat ────────────────────────────────────────────────────────────
    ("Xin chào!", LABEL_CHITCHAT),
    ("Hello!", LABEL_CHITCHAT),
    ("Chào bạn", LABEL_CHITCHAT),
    ("Hi, bạn khỏe không?", LABEL_CHITCHAT),
    ("Cảm ơn bạn nhiều nhé", LABEL_CHITCHAT),
    ("Cảm ơn nha", LABEL_CHITCHAT),
    ("Tạm biệt", LABEL_CHITCHAT),
    ("Bye bye", LABEL_CHITCHAT),
    ("Hẹn gặp lại", LABEL_CHITCHAT),
    ("Bạn tên gì?", LABEL_CHITCHAT),
    ("Bạn là ai vậy?", LABEL_CHITCHAT),
    ("Bạn có thể làm gì?", LABEL_CHITCHAT),
    ("Kể cho mình nghe một câu chuyện đi", LABEL_CHITCHAT),
    ("Kể chuyện cười đi", LABEL_CHITCHAT),
    ("Hôm nay bạn thế nào?", LABEL_CHITCHAT),
    ("Mình buồn quá", LABEL_CHITCHAT),
    ("Bạn ơi", LABEL_CHITCHAT),
    ("Ok cảm ơn", LABEL_CHITCHAT),
    ("Được rồi, cảm ơn nhiều", LABEL_CHITCHAT),
    ("Ừ mình hiểu rồi", LABEL_CHITCHAT),
    ("Tuyệt vời", LABEL_CHITCHAT),
    ("Hay quá", LABEL_CHITCHAT),
    ("Bạn giỏi thật", LABEL_CHITCHAT),
    ("Mình không hiểu lắm", LABEL_CHITCHAT),
    ("Nói lại đi", LABEL_CHITCHAT),
    ("Bạn nói tiếng Anh được không?", LABEL_CHITCHAT),
    ("Can you speak English?", LABEL_CHITCHAT),
    ("Chào buổi sáng", LABEL_CHITCHAT),
    ("Chúc ngủ ngon", LABEL_CHITCHAT),
    ("Xin lỗi nha", LABEL_CHITCHAT),
    ("Mình muốn hỏi cái này", LABEL_CHITCHAT),
    ("Ê bạn ơi", LABEL_CHITCHAT),
    ("Alo", LABEL_CHITCHAT),
    ("Haha", LABEL_CHITCHAT),
    ("Vui quá", LABEL_CHITCHAT),
    ("Bạn có biết gì về AI không?", LABEL_CHITCHAT),
    ("Thích ăn gì?", LABEL_CHITCHAT),
    ("Bạn thích màu gì?", LABEL_CHITCHAT),
    ("Mình chán quá", LABEL_CHITCHAT),
    ("Wow", LABEL_CHITCHAT),
    ("Bạn ở đâu?", LABEL_CHITCHAT),
    ("Bạn bao nhiêu tuổi?", LABEL_CHITCHAT),
    ("Thank you", LABEL_CHITCHAT),
    ("Thanks", LABEL_CHITCHAT),
    ("Cảm ơn bạn đã giúp đỡ", LABEL_CHITCHAT),
    ("Bạn giúp mình được gì?", LABEL_CHITCHAT),
    ("OK", LABEL_CHITCHAT),
    ("Rồi", LABEL_CHITCHAT),
    ("Ừm", LABEL_CHITCHAT),
    ("Mình hiểu rồi cảm ơn bạn", LABEL_CHITCHAT),
    # ── tool_search ─────────────────────────────────────────────────────────
    ("Thời tiết hôm nay thế nào?", LABEL_TOOL_SEARCH),
    ("Nhiệt độ Hà Nội hôm nay bao nhiêu?", LABEL_TOOL_SEARCH),
    ("Dự báo thời tiết tuần này", LABEL_TOOL_SEARCH),
    (
        "Tìm giúp mình thông tin mới nhất về học phí trên mạng",
        LABEL_TOOL_SEARCH,
    ),
    ("Tin tức mới nhất hôm nay là gì?", LABEL_TOOL_SEARCH),
    ("Tỷ giá USD hôm nay bao nhiêu?", LABEL_TOOL_SEARCH),
    ("Giá vàng hôm nay", LABEL_TOOL_SEARCH),
    ("Kết quả bóng đá tối qua", LABEL_TOOL_SEARCH),
    ("Tra cứu thông tin trên Google giúp mình", LABEL_TOOL_SEARCH),
    ("Tìm trên mạng giúp mình về chủ đề này", LABEL_TOOL_SEARCH),
    ("Search trên web giúp mình", LABEL_TOOL_SEARCH),
    ("Mới có thông tin gì mới về tuyển sinh không?", LABEL_TOOL_SEARCH),
    ("Có sự kiện gì mới ở Bách Khoa không?", LABEL_TOOL_SEARCH),
    ("Tìm trên internet giúp mình đi", LABEL_TOOL_SEARCH),
    ("Tra giúp mình thông tin real-time", LABEL_TOOL_SEARCH),
    ("Cập nhật mới nhất về COVID", LABEL_TOOL_SEARCH),
    ("Bao giờ có kết quả xổ số?", LABEL_TOOL_SEARCH),
    ("Chứng khoán hôm nay thế nào?", LABEL_TOOL_SEARCH),
    ("Tra cứu điểm thi THPT trên mạng", LABEL_TOOL_SEARCH),
    ("Tìm bài báo mới nhất về AI", LABEL_TOOL_SEARCH),
    ("Xem lịch chiếu phim hôm nay", LABEL_TOOL_SEARCH),
    ("Tìm đường đi từ nhà đến trường Bách Khoa", LABEL_TOOL_SEARCH),
    ("Giá xăng hôm nay bao nhiêu?", LABEL_TOOL_SEARCH),
    ("Tra cứu thông tin chuyến bay", LABEL_TOOL_SEARCH),
    ("Điểm chuẩn năm nay của các trường", LABEL_TOOL_SEARCH),
    ("Xem review nhà hàng gần trường", LABEL_TOOL_SEARCH),
    ("Tìm phòng trọ gần Bách Khoa", LABEL_TOOL_SEARCH),
    ("Tra thông tin xe buýt đi qua trường", LABEL_TOOL_SEARCH),
    ("Lịch nghỉ lễ quốc gia năm nay", LABEL_TOOL_SEARCH),
    ("Tìm giúp mình link đăng ký cuộc thi trên mạng", LABEL_TOOL_SEARCH),
    # ── ctdt (chương trình đào tạo) ────────────────────────────────────────
    ("Chương trình đào tạo ngành CNTT có bao nhiêu tín chỉ?", LABEL_CTDT),
    ("Ngành kỹ thuật điện tử học những môn gì?", LABEL_CTDT),
    ("Danh sách môn học ngành cơ khí", LABEL_CTDT),
    ("Đề cương môn Giải tích 1", LABEL_CTDT),
    ("Môn tiên quyết của Trí tuệ nhân tạo là gì?", LABEL_CTDT),
    ("Tổng số tín chỉ ngành Tự động hóa", LABEL_CTDT),
    ("Khoa Điện có những ngành nào?", LABEL_CTDT),
    ("Viện CNTT&TT đào tạo những chuyên ngành gì?", LABEL_CTDT),
    ("Ngành nào thuộc viện Công nghệ thông tin?", LABEL_CTDT),
    ("Chương trình tiên tiến là gì?", LABEL_CTDT),
    ("Chương trình kỹ sư tài năng khác gì chương trình chuẩn?", LABEL_CTDT),
    ("Lộ trình học ngành Khoa học máy tính", LABEL_CTDT),
    ("Có bao nhiêu tín chỉ tự chọn trong CTDT ngành CNTT?", LABEL_CTDT),
    ("Môn đồ án tốt nghiệp có bao nhiêu tín chỉ?", LABEL_CTDT),
    ("Điều kiện làm đồ án tốt nghiệp là gì?", LABEL_CTDT),
    ("Khi nào được đăng ký thực tập doanh nghiệp?", LABEL_CTDT),
    ("Chương trình đào tạo mới có thay đổi gì?", LABEL_CTDT),
    ("Ngành an toàn thông tin học các môn nào?", LABEL_CTDT),
    ("Có chương trình liên kết quốc tế nào không?", LABEL_CTDT),
    ("Chương trình đào tạo ICT là gì?", LABEL_CTDT),
    ("Khung chương trình K68 ngành CNTT", LABEL_CTDT),
    ("Có bao nhiêu khoa/viện ở Bách Khoa?", LABEL_CTDT),
    ("Ngành nào có chương trình tiếng Anh?", LABEL_CTDT),
    ("Đào tạo song ngành ở Bách Khoa như thế nào?", LABEL_CTDT),
    ("Chuyển ngành có được không?", LABEL_CTDT),
    ("Quy trình chuyển ngành", LABEL_CTDT),
    ("Học chuyển tiếp kỹ sư là gì?", LABEL_CTDT),
    ("Chương trình 180 tín chỉ kỹ sư", LABEL_CTDT),
    ("Môn nào là bắt buộc cho sinh viên năm nhất?", LABEL_CTDT),
    ("Danh sách môn đại cương", LABEL_CTDT),
    ("Có được học vượt không?", LABEL_CTDT),
    ("Ngành Điện tử viễn thông có bao nhiêu chuyên ngành?", LABEL_CTDT),
    ("Trường có đào tạo thạc sĩ không?", LABEL_CTDT),
    ("Chương trình đào tạo thạc sĩ CNTT", LABEL_CTDT),
    ("Điều kiện học song bằng", LABEL_CTDT),
    ("CTDT ngành vật liệu", LABEL_CTDT),
    ("Số tín chỉ tối thiểu mỗi kỳ", LABEL_CTDT),
    ("Số tín chỉ tối đa được đăng ký mỗi kỳ", LABEL_CTDT),
    ("Ngành cơ điện tử có triển vọng không?", LABEL_CTDT),
    ("Năm nhất học những gì?", LABEL_CTDT),
    ("Chương trình SIE là chương trình gì?", LABEL_CTDT),
    ("Có chương trình đào tạo từ xa không?", LABEL_CTDT),
    ("Khoa học dữ liệu và trí tuệ nhân tạo học gì?", LABEL_CTDT),
    ("Khác nhau giữa ngành CNTT và KHMT", LABEL_CTDT),
    ("Có ngành Robotics không?", LABEL_CTDT),
    ("Ngành logistics học ở viện nào?", LABEL_CTDT),
    ("Môn thay thế tốt nghiệp là gì?", LABEL_CTDT),
    ("Có được thay đồ án bằng môn học không?", LABEL_CTDT),
    ("Tín chỉ thực hành và lý thuyết khác nhau không?", LABEL_CTDT),
    ("CT đào tạo có cập nhật theo ABET không?", LABEL_CTDT),
    ("Chương trình đào tạo chuẩn quốc tế", LABEL_CTDT),
    ("Viện Toán ứng dụng dạy gì?", LABEL_CTDT),
    ("Ngành Kỹ thuật hóa học có mấy chuyên ngành?", LABEL_CTDT),
    ("Lộ trình hoàn thành ngành CNTT trong 4 năm", LABEL_CTDT),
    ("Có chương trình kiến trúc không?", LABEL_CTDT),
    ("Ngành quản lý công nghiệp thuộc viện nào?", LABEL_CTDT),
    ("Đồ án chuyên ngành khác đồ án tốt nghiệp như thế nào?", LABEL_CTDT),
    ("Trường có ngành y sinh không?", LABEL_CTDT),
    ("Chương trình đào tạo ngành môi trường", LABEL_CTDT),
    ("Có ngành kinh tế ở Bách Khoa không?", LABEL_CTDT),
    # ── quydinh (quy chế, quy định) ────────────────────────────────────────
    ("Quy chế đào tạo mới có gì thay đổi?", LABEL_QUYDINH),
    ("Điều kiện xét học bổng khuyến khích là gì?", LABEL_QUYDINH),
    ("Điểm trung bình tích lũy bao nhiêu thì bị buộc thôi học?", LABEL_QUYDINH),
    ("Quy định về nghỉ học tạm thời", LABEL_QUYDINH),
    ("Điều kiện bảo lưu kết quả học tập", LABEL_QUYDINH),
    ("Bao nhiêu điểm thì được học bổng?", LABEL_QUYDINH),
    ("Chính sách học bổng tài trợ", LABEL_QUYDINH),
    ("Quy định về đánh giá điểm rèn luyện", LABEL_QUYDINH),
    ("Thang điểm 4 quy đổi thế nào?", LABEL_QUYDINH),
    ("Điểm F có được học lại không?", LABEL_QUYDINH),
    ("Bao nhiêu lần được học lại một môn?", LABEL_QUYDINH),
    ("Điều kiện xét tốt nghiệp", LABEL_QUYDINH),
    ("GPA bao nhiêu thì được tốt nghiệp loại giỏi?", LABEL_QUYDINH),
    ("Quy định kỷ luật sinh viên", LABEL_QUYDINH),
    ("Vi phạm quy chế thi bị xử lý thế nào?", LABEL_QUYDINH),
    ("Gian lận trong thi cử bị kỷ luật gì?", LABEL_QUYDINH),
    ("Sinh viên vi phạm nội quy KTX bị xử lý thế nào?", LABEL_QUYDINH),
    ("Quy định ngoại ngữ đầu ra", LABEL_QUYDINH),
    ("IELTS bao nhiêu thì đủ điều kiện tốt nghiệp?", LABEL_QUYDINH),
    ("Quy định về miễn học phí", LABEL_QUYDINH),
    ("Sinh viên nước ngoài có quy định gì riêng?", LABEL_QUYDINH),
    ("Chính sách hỗ trợ sinh viên khuyết tật", LABEL_QUYDINH),
    ("Điều kiện nghỉ học tạm thời vì lý do sức khỏe", LABEL_QUYDINH),
    ("Thời gian tối đa để hoàn thành chương trình", LABEL_QUYDINH),
    ("Sinh viên có được phép đi làm thêm không?", LABEL_QUYDINH),
    ("Quy định QP-AN", LABEL_QUYDINH),
    ("Điều kiện miễn môn Quốc phòng an ninh", LABEL_QUYDINH),
    ("Điểm rèn luyện tính thế nào?", LABEL_QUYDINH),
    ("Khung đánh giá điểm rèn luyện", LABEL_QUYDINH),
    ("Quy chế công tác sinh viên", LABEL_QUYDINH),
    ("Quy định xử lý vi phạm trong phòng thi", LABEL_QUYDINH),
    ("Sinh viên bị cảnh báo học vụ khi nào?", LABEL_QUYDINH),
    ("Quy định về Giáo dục thể chất", LABEL_QUYDINH),
    ("Quy định thi trực tuyến", LABEL_QUYDINH),
    ("Quy định tổ chức dạy học trực tuyến", LABEL_QUYDINH),
    ("Điều kiện được cấp bằng kỹ sư", LABEL_QUYDINH),
    ("Quy chế đào tạo đại học chính quy 2025", LABEL_QUYDINH),
    ("QCDT 2025 có quy định gì mới?", LABEL_QUYDINH),
    ("Quy định học phí theo tín chỉ", LABEL_QUYDINH),
    ("Có được phúc khảo bài thi không?", LABEL_QUYDINH),
    ("Quy trình phúc khảo điểm thi", LABEL_QUYDINH),
    ("Chính sách giảm học phí cho sinh viên nghèo", LABEL_QUYDINH),
    ("Điều kiện nhận học bổng doanh nghiệp", LABEL_QUYDINH),
    ("Xếp loại tốt nghiệp dựa vào tiêu chí gì?", LABEL_QUYDINH),
    ("Quy định đăng ký tín chỉ tối thiểu mỗi kỳ", LABEL_QUYDINH),
    ("Sinh viên diện chính sách được ưu tiên gì?", LABEL_QUYDINH),
    ("Điều kiện chuyển trường", LABEL_QUYDINH),
    ("Quy định về nghỉ phép không chính đáng", LABEL_QUYDINH),
    ("Thời gian gia hạn học phí", LABEL_QUYDINH),
    ("Bị buộc thôi học có được phúc khảo không?", LABEL_QUYDINH),
    ("Quy định Olympic và đổi mới sáng tạo", LABEL_QUYDINH),
    ("Điều kiện xét tham gia Olympic cấp trường", LABEL_QUYDINH),
    ("Quy định đánh giá môn quốc phòng an ninh", LABEL_QUYDINH),
    (
        "Sinh viên cần bao nhiêu tín chỉ để đủ điều kiện ra trường?",
        LABEL_QUYDINH,
    ),
    ("Quy định chuẩn ngoại ngữ từ K70", LABEL_QUYDINH),
    ("Quy định ngoại ngữ từ K68", LABEL_QUYDINH),
    # ── kehoach (lịch, thông báo, đăng ký) ─────────────────────────────────
    ("Lịch thi cuối kỳ khi nào?", LABEL_KEHOACH),
    ("Bao giờ đăng ký môn học kỳ tới?", LABEL_KEHOACH),
    ("Thời gian đăng ký tín chỉ học kỳ 2", LABEL_KEHOACH),
    ("Lịch học kỳ hè năm nay", LABEL_KEHOACH),
    ("Khi nào bắt đầu học kỳ mới?", LABEL_KEHOACH),
    ("Hạn nộp học phí kỳ này", LABEL_KEHOACH),
    ("Lịch nghỉ Tết", LABEL_KEHOACH),
    ("Lịch thi giữa kỳ", LABEL_KEHOACH),
    ("Lịch đăng ký môn bổ sung", LABEL_KEHOACH),
    ("Bao giờ công bố điểm thi?", LABEL_KEHOACH),
    ("Thời gian rút môn học", LABEL_KEHOACH),
    ("Lịch bảo vệ đồ án tốt nghiệp", LABEL_KEHOACH),
    ("Khi nào nộp đơn xin nghỉ học?", LABEL_KEHOACH),
    ("Lịch nhận bằng tốt nghiệp", LABEL_KEHOACH),
    ("Lịch đăng ký KTX", LABEL_KEHOACH),
    ("Thời gian xét học bổng kỳ này", LABEL_KEHOACH),
    ("Khi nào có lịch thi chính thức?", LABEL_KEHOACH),
    ("Đăng ký tín chỉ qua hệ thống nào?", LABEL_KEHOACH),
    ("Hướng dẫn đăng ký môn học trên cổng SV", LABEL_KEHOACH),
    ("Sự kiện tuyển dụng sắp tới", LABEL_KEHOACH),
    ("Ngày hội việc làm của trường khi nào?", LABEL_KEHOACH),
    ("Lịch seminar tuần này", LABEL_KEHOACH),
    ("Khi nào thi Olympic toán?", LABEL_KEHOACH),
    ("Hạn đăng ký cuộc thi ICPC", LABEL_KEHOACH),
    ("Lịch hoạt động Đoàn thanh niên", LABEL_KEHOACH),
    ("Workshop AI khi nào?", LABEL_KEHOACH),
    ("Thời gian họp lớp", LABEL_KEHOACH),
    ("Lịch thi Tiếng Anh chuẩn đầu ra", LABEL_KEHOACH),
    ("Lịch nộp báo cáo thực tập", LABEL_KEHOACH),
    ("Kỳ thi phụ dự kiến khi nào?", LABEL_KEHOACH),
    ("Lịch xét tốt nghiệp đợt tháng 6", LABEL_KEHOACH),
    ("Khi nào được xem điểm trên hệ thống?", LABEL_KEHOACH),
    ("Đăng ký tốt nghiệp có hạn không?", LABEL_KEHOACH),
    ("Hạn cuối nộp đơn đăng ký thực tập", LABEL_KEHOACH),
    ("Khi nào bắt đầu kỳ thực tập hè?", LABEL_KEHOACH),
    ("Thời gian phúc khảo bài thi", LABEL_KEHOACH),
    ("Lịch cấp bảng điểm", LABEL_KEHOACH),
    ("Khi nào hết hạn đăng ký bảo hiểm?", LABEL_KEHOACH),
    ("Thời gian tổ chức lễ tốt nghiệp", LABEL_KEHOACH),
    ("Ngày khai giảng năm nay", LABEL_KEHOACH),
    ("Semester 1 bắt đầu từ ngày nào?", LABEL_KEHOACH),
    ("Lịch nộp luận văn thạc sĩ", LABEL_KEHOACH),
    ("Bao giờ có kết quả phân ngành?", LABEL_KEHOACH),
    ("Lịch phân ngành cho K69", LABEL_KEHOACH),
    ("Đăng ký dự thi tiếng Anh khi nào?", LABEL_KEHOACH),
    ("Workshop CV writing khi nào diễn ra?", LABEL_KEHOACH),
    ("Hạn cuối rút môn không bị điểm F", LABEL_KEHOACH),
    ("Lịch sinh hoạt tuần sinh viên mới", LABEL_KEHOACH),
    ("Lịch thi thể dục thể chất", LABEL_KEHOACH),
    ("Bao giờ đóng học phí kỳ hè?", LABEL_KEHOACH),
    # ── stsv (sinh viên: thủ tục, KTX, bảo hiểm, thẻ SV) ──────────────────
    ("Thủ tục xin giấy xác nhận sinh viên", LABEL_STSV),
    ("Làm thẻ sinh viên ở đâu?", LABEL_STSV),
    ("Mất thẻ sinh viên phải làm sao?", LABEL_STSV),
    ("Cách đăng ký KTX", LABEL_STSV),
    ("Ký túc xá ở đâu?", LABEL_STSV),
    ("Giá phòng KTX bao nhiêu?", LABEL_STSV),
    ("Đóng bảo hiểm y tế ở đâu?", LABEL_STSV),
    ("Bảo hiểm y tế sinh viên bao nhiêu tiền?", LABEL_STSV),
    ("Thủ tục nhập học cho tân sinh viên", LABEL_STSV),
    ("Giấy tờ cần khi nhập học", LABEL_STSV),
    ("Sinh viên nước ngoài cần giấy tờ gì để nhập học?", LABEL_STSV),
    ("Cách xin giấy giới thiệu thực tập", LABEL_STSV),
    ("Thủ tục xin nghỉ học tạm thời", LABEL_STSV),
    ("Cách nộp đơn bảo lưu", LABEL_STSV),
    ("Thủ tục chuyển ngành", LABEL_STSV),
    ("Làm thẻ thư viện như thế nào?", LABEL_STSV),
    ("Cách đăng ký email sinh viên", LABEL_STSV),
    ("Quên mật khẩu cổng sinh viên phải làm sao?", LABEL_STSV),
    ("Liên hệ phòng công tác sinh viên ở đâu?", LABEL_STSV),
    ("Số điện thoại phòng đào tạo", LABEL_STSV),
    ("Cần gì khi chuyển KTX?", LABEL_STSV),
    ("Xin giấy chứng nhận đi đường", LABEL_STSV),
    ("Thủ tục vay vốn sinh viên", LABEL_STSV),
    ("Cách nhận học bổng qua tài khoản ngân hàng", LABEL_STSV),
    ("Đăng ký tham gia CLB ở đâu?", LABEL_STSV),
    ("Hỗ trợ sức khỏe tinh thần sinh viên", LABEL_STSV),
    ("Phòng y tế trường ở đâu?", LABEL_STSV),
    ("Cách xin giấy xác nhận vay vốn", LABEL_STSV),
    ("Thủ tục thanh toán học phí online", LABEL_STSV),
    ("Nộp học phí qua ngân hàng nào?", LABEL_STSV),
    ("Cách đăng ký wifi trường", LABEL_STSV),
    ("Tài khoản Microsoft 365 cho sinh viên", LABEL_STSV),
    ("Cần mang gì khi ở KTX?", LABEL_STSV),
    ("Thủ tục xin ra KTX", LABEL_STSV),
    ("Chỗ gửi xe trong trường", LABEL_STSV),
    ("Phí gửi xe ở trường bao nhiêu?", LABEL_STSV),
    ("Cách đăng ký suất ăn canteen", LABEL_STSV),
    ("Hỗ trợ sinh viên gặp khó khăn tài chính", LABEL_STSV),
    ("Thủ tục xin cấp lại bảng điểm", LABEL_STSV),
    ("Làm sao để cấp lại bằng tốt nghiệp?", LABEL_STSV),
    ("Phòng tư vấn tâm lý sinh viên ở đâu?", LABEL_STSV),
    ("Cách truy cập thư viện điện tử", LABEL_STSV),
    ("Đăng ký phòng tự học ở thư viện", LABEL_STSV),
    ("Cách sử dụng hệ thống quản lý học tập LMS", LABEL_STSV),
    ("Hướng dẫn sử dụng cổng thông tin sinh viên", LABEL_STSV),
    ("Thủ tục xin giấy hoãn nghĩa vụ quân sự", LABEL_STSV),
    ("Xin xác nhận tạm trú cho sinh viên", LABEL_STSV),
    ("Thủ tục làm đơn xin việc có xác nhận trường", LABEL_STSV),
    ("Nơi in ấn tài liệu trong trường", LABEL_STSV),
    ("Cách liên hệ cố vấn học tập", LABEL_STSV),
]


# ─── Hard negatives (single-label boundary cases) ─────────────────────────────
# Queries that look like one domain but belong to another.  These help the
# classifier learn sharper decision boundaries at the edges.
HARD_NEGATIVE_DATA: List[Tuple[str, str]] = [
    # scholarship: procedure vs. condition vs. deadline
    ("Học bổng kỳ này nộp đơn ở đâu?", LABEL_STSV),  # WHERE → procedure
    ("Điều kiện học bổng kỳ này là gì?", LABEL_QUYDINH),  # condition → quydinh
    ("Deadline nộp học bổng kỳ này?", LABEL_KEHOACH),  # deadline → kehoach
    ("Mẫu đơn xin học bổng lấy ở đâu?", LABEL_STSV),
    ("Tiêu chí xét học bổng khuyến khích học tập", LABEL_QUYDINH),
    ("Thời hạn nộp hồ sơ học bổng học kỳ 2", LABEL_KEHOACH),
    # insurance: procedure vs. deadline
    ("Đăng ký bảo hiểm y tế ở đâu?", LABEL_STSV),  # WHERE → stsv
    ("Bao giờ hết hạn đăng ký bảo hiểm?", LABEL_KEHOACH),  # WHEN → kehoach
    ("Mức đóng bảo hiểm y tế sinh viên năm nay", LABEL_QUYDINH),
    ("Thủ tục hủy bảo hiểm y tế", LABEL_STSV),
    # credit limits: ctdt vs. quydinh
    ("Số tín chỉ tối đa được đăng ký mỗi kỳ", LABEL_QUYDINH),  # rule → quydinh
    ("Khung chương trình yêu cầu bao nhiêu tín chỉ mỗi kỳ?", LABEL_CTDT),
    ("Quy định đăng ký tối thiểu bao nhiêu tín chỉ?", LABEL_QUYDINH),
    # graduation: ctdt vs. quydinh
    ("Điều kiện làm đồ án tốt nghiệp là gì?", LABEL_CTDT),  # part of ctdt
    ("Quy định số tín chỉ tích lũy để làm đồ án", LABEL_QUYDINH),
    ("Môn nào là tiên quyết của đồ án tốt nghiệp?", LABEL_CTDT),
    # kehoach vs. stsv (registrations with both when/where angles)
    ("Đăng ký KTX ở đâu?", LABEL_STSV),
    ("Lịch mở đăng ký KTX học kỳ tới", LABEL_KEHOACH),
    ("Thời gian đóng học phí là khi nào?", LABEL_KEHOACH),
    ("Nộp học phí bằng cách nào?", LABEL_STSV),
    # enterprise scholarship (quydinh vs. stsv)
    ("Điều kiện nhận học bổng doanh nghiệp ABC", LABEL_QUYDINH),
    ("Nộp hồ sơ học bổng doanh nghiệp ở phòng nào?", LABEL_STSV),
    # academic warning
    ("Sinh viên bị cảnh báo học vụ cần làm gì?", LABEL_STSV),
    ("Điểm GPA bao nhiêu thì bị cảnh báo học vụ?", LABEL_QUYDINH),
    # context-sensitive short queries (chatbot follow-ups)
    ("Còn điều kiện tiên quyết là gì?", LABEL_CTDT),
    ("Deadline là khi nào?", LABEL_KEHOACH),
    ("Nộp ở đâu?", LABEL_STSV),
    ("Bao nhiêu tín chỉ?", LABEL_CTDT),
    ("Mức phí là bao nhiêu?", LABEL_QUYDINH),
]


# ─── Multi-label training samples ─────────────────────────────────────────────
# Queries that genuinely span multiple domains.  Each label list is ordered
# from primary (most relevant) to secondary domain(s).
MULTI_LABEL_DATA: List[Tuple[str, List[str]]] = [
    # ctdt + quydinh
    (
        "Học kỳ 3 ngành KHMT học những môn gì và học phí tính thế nào?",
        [LABEL_CTDT, LABEL_QUYDINH],
    ),
    (
        "Ngành CNTT cần bao nhiêu tín chỉ và điều kiện tốt nghiệp ra sao?",
        [LABEL_CTDT, LABEL_QUYDINH],
    ),
    (
        "Môn học kỳ 1 ngành Điện tử và quy định điểm D tính thế nào?",
        [LABEL_CTDT, LABEL_QUYDINH],
    ),
    (
        "Chương trình đào tạo kỹ sư tài năng và điều kiện xét tuyển vào",
        [LABEL_CTDT, LABEL_QUYDINH],
    ),
    (
        "Số tín chỉ ngành KTMT và mức học phí mỗi tín chỉ",
        [LABEL_CTDT, LABEL_QUYDINH],
    ),
    # ctdt + kehoach
    (
        "Lịch đăng ký môn học kỳ 2 ngành Cơ điện tử",
        [LABEL_KEHOACH, LABEL_CTDT],
    ),
    (
        "Khi nào đăng ký thực tập và điều kiện là gì?",
        [LABEL_KEHOACH, LABEL_CTDT],
    ),
    # quydinh + stsv
    (
        "Điều kiện nhận học bổng và nộp hồ sơ ở đâu?",
        [LABEL_QUYDINH, LABEL_STSV],
    ),
    (
        "Quy định bảo lưu kết quả học tập và thủ tục xin bảo lưu",
        [LABEL_QUYDINH, LABEL_STSV],
    ),
    (
        "Chính sách miễn giảm học phí và cách đăng ký",
        [LABEL_QUYDINH, LABEL_STSV],
    ),
    (
        "Điều kiện được ở KTX và cách đăng ký phòng",
        [LABEL_QUYDINH, LABEL_STSV],
    ),
    (
        "Quy định sinh viên nước ngoài và thủ tục nhập học",
        [LABEL_QUYDINH, LABEL_STSV],
    ),
    (
        "Tiêu chuẩn xét học bổng khuyến khích và hướng dẫn nộp đơn",
        [LABEL_QUYDINH, LABEL_STSV],
    ),
    # quydinh + kehoach
    (
        "Điều kiện phúc khảo bài thi và thời hạn nộp đơn",
        [LABEL_QUYDINH, LABEL_KEHOACH],
    ),
    (
        "Quy trình đăng ký học lại và deadline đăng ký",
        [LABEL_QUYDINH, LABEL_KEHOACH],
    ),
    # kehoach + stsv
    (
        "Thời gian đăng ký KTX học kỳ tới và thủ tục",
        [LABEL_KEHOACH, LABEL_STSV],
    ),
    (
        "Bao giờ đóng bảo hiểm y tế và đóng ở đâu?",
        [LABEL_KEHOACH, LABEL_STSV],
    ),
    (
        "Lịch nhận bằng tốt nghiệp và cần mang giấy tờ gì?",
        [LABEL_KEHOACH, LABEL_STSV],
    ),
]


def get_training_data() -> List[Tuple[str, List[str]]]:
    """Return all training data in multi-label format.

    Single-label entries are wrapped in a one-element list for a uniform
    interface with :class:`~query.domain_classifier.DomainClassifier`.
    """
    single_as_multi: List[Tuple[str, List[str]]] = [
        (q, [lbl]) for q, lbl in TRAINING_DATA
    ]
    hard_negatives_multi: List[Tuple[str, List[str]]] = [
        (q, [lbl]) for q, lbl in HARD_NEGATIVE_DATA
    ]
    return single_as_multi + hard_negatives_multi + MULTI_LABEL_DATA
