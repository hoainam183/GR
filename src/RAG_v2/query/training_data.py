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
    ("Số tín chỉ tối đa được đăng ký mỗi kỳ", LABEL_QUYDINH),
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
    # học phí + tên ngành cụ thể → quydinh (mức thu theo tín chỉ thuộc quy định,
    # KHÔNG phải tra cứu chương trình đào tạo dù câu chứa "tín chỉ"/tên ngành).
    (
        "Học phí ngành Công nghệ thông tin Việt-Nhật bao nhiêu 1 tín chỉ?",
        LABEL_QUYDINH,
    ),
    ("Mức học phí trên một tín chỉ của ngành IT-E6?", LABEL_QUYDINH),
    ("Học phí mỗi tín chỉ ngành Khoa học Máy tính?", LABEL_QUYDINH),
    ("Một tín chỉ ngành Kỹ thuật Điện tử bao nhiêu tiền?", LABEL_QUYDINH),
    ("Ngành của tôi có học phí bao nhiêu?", LABEL_QUYDINH),
    ("Học phí ngành CNTT là bao nhiêu?", LABEL_QUYDINH),
    ("Ngành KHMT học phí mỗi tín chỉ bao nhiêu?", LABEL_QUYDINH),
    ("Học phí 1 tín chỉ ngành kỹ sư tài năng?", LABEL_QUYDINH),
    ("Mức học phí của chương trình tiên tiến?", LABEL_QUYDINH),
    ("Ngành IT-E7 có học phí bao nhiêu mỗi tín chỉ?", LABEL_QUYDINH),
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
    # Olympic/ĐMST — chính sách HỖ TRỢ đội tuyển (kinh phí/khen thưởng/chế độ).
    # Nội dung nằm trong quyết định/quy định của trường -> quydinh đơn nhãn.
    # Trước đây thiếu nhóm này nên câu "hỗ trợ SV thi Olympic" bị bật thêm
    # stsv/kehoach -> route Agent (xem eval-miss).
    (
        "Đại học Bách khoa hỗ trợ những gì cho sinh viên tham gia đội tuyển thi Olympic và ĐMST?",
        LABEL_QUYDINH,
    ),
    (
        "Nhà trường hỗ trợ gì cho sinh viên trong đội tuyển thi Olympic?",
        LABEL_QUYDINH,
    ),
    (
        "Kinh phí hỗ trợ đội tuyển thi Olympic và ĐMST được xác định thế nào?",
        LABEL_QUYDINH,
    ),
    ("Chế độ hỗ trợ cho sinh viên tham gia đội tuyển ĐMST", LABEL_QUYDINH),
    (
        "Sinh viên đoạt giải thi Olympic được khen thưởng như thế nào?",
        LABEL_QUYDINH,
    ),
    (
        "Mức thưởng cho sinh viên đạt giải Olympic và khởi nghiệp đổi mới sáng tạo",
        LABEL_QUYDINH,
    ),
    # Hard boundary: "hỗ trợ sinh viên" thường kéo về stsv (hỗ trợ khuyết tật/tài
    # chính). Khi gắn với đội tuyển/Olympic/ĐMST thì là chính sách -> quydinh.
    (
        "Sinh viên tham gia đội tuyển thi Olympic được nhà trường hỗ trợ kinh phí và trang thiết bị gì?",
        LABEL_QUYDINH,
    ),
    (
        "Chính sách hỗ trợ và khen thưởng sinh viên có thành tích trong các kỳ thi Olympic và ĐMST",
        LABEL_QUYDINH,
    ),
    (
        "Đội tuyển thi Olympic của trường được hưởng những chế độ hỗ trợ gì?",
        LABEL_QUYDINH,
    ),
    (
        "Sinh viên tham gia hoạt động đổi mới sáng tạo và khởi nghiệp được hỗ trợ những gì?",
        LABEL_QUYDINH,
    ),
    ("Quy định đánh giá môn quốc phòng an ninh", LABEL_QUYDINH),
    (
        "Sinh viên cần bao nhiêu tín chỉ để đủ điều kiện ra trường?",
        LABEL_QUYDINH,
    ),
    ("Quy định chuẩn ngoại ngữ từ K70", LABEL_QUYDINH),
    ("Quy định ngoại ngữ từ K68", LABEL_QUYDINH),
    # ── quydinh — quy đổi / công nhận / chuyển đổi tín chỉ & ECTS ───────────
    # "Quy đổi tương đương tín chỉ sang ECTS" là CHÍNH SÁCH (quyết định, hướng
    # dẫn của trường), KHÔNG phải tra cứu khối lượng môn trong CTĐT dù chứa
    # "tín chỉ"/"tương đương". Tài liệu thực tế nằm ở collection quydinh.
    (
        "Hướng dẫn quy đổi tương đương tín chỉ học tập sang hệ thống ECTS",
        LABEL_QUYDINH,
    ),
    (
        "Quy đổi tín chỉ Đại học Bách Khoa Hà Nội sang ECTS thế nào?",
        LABEL_QUYDINH,
    ),
    ("1 tín chỉ ĐHBK quy đổi bằng bao nhiêu ECTS?", LABEL_QUYDINH),
    ("Quy đổi tín chỉ tích lũy sang hệ thống tín chỉ Châu Âu", LABEL_QUYDINH),
    ("Quy định công nhận và chuyển đổi tín chỉ", LABEL_QUYDINH),
    (
        "Tín chỉ học tập ở Bách Khoa tương đương bao nhiêu tín chỉ Châu Âu?",
        LABEL_QUYDINH,
    ),
    ("Quy chế quy đổi tín chỉ giữa các hệ đào tạo", LABEL_QUYDINH),
    (
        "Hệ thống chuyển đổi và tích lũy tín chỉ Châu Âu áp dụng thế nào ở trường?",
        LABEL_QUYDINH,
    ),
    ("Quyết định ban hành hướng dẫn quy đổi tín chỉ sang ECTS", LABEL_QUYDINH),
    (
        "Cách quy đổi điểm và tín chỉ khi đi trao đổi sinh viên ở nước ngoài",
        LABEL_QUYDINH,
    ),
    ("Quy định công nhận tín chỉ học ở trường đối tác quốc tế", LABEL_QUYDINH),
    # ── ctdt — đồ án / ĐATN ────────────────────────────────────────────────
    ("Đồ án tốt nghiệp ngành CNTT bao nhiêu tín chỉ?", LABEL_CTDT),
    ("ĐATN ngành Điện tử viễn thông mấy tín chỉ?", LABEL_CTDT),
    ("Chọn giảng viên hướng dẫn đồ án như thế nào?", LABEL_CTDT),
    ("Đề tài đồ án tốt nghiệp lấy từ đâu?", LABEL_CTDT),
    ("Quy trình đăng ký đề tài đồ án", LABEL_CTDT),
    ("Đồ án chuyên ngành khác đồ án tốt nghiệp thế nào?", LABEL_CTDT),
    ("Số tín chỉ đồ án 1 và đồ án 2 ngành Cơ điện tử", LABEL_CTDT),
    ("Có thể thay đồ án tốt nghiệp bằng khoá luận không?", LABEL_CTDT),
    ("Đồ án tốt nghiệp ở Bách Khoa thực hiện mấy học kỳ?", LABEL_CTDT),
    ("Tiêu chí đánh giá đồ án tốt nghiệp", LABEL_CTDT),
    ("Ngành KHMT có bảo vệ đồ án hay làm luận văn?", LABEL_CTDT),
    ("Đồ án tốt nghiệp có thể làm theo nhóm không?", LABEL_CTDT),
    ("Cấu trúc báo cáo đồ án tốt nghiệp gồm những phần gì?", LABEL_CTDT),
    ("Đề cương đồ án tốt nghiệp cần có nội dung gì?", LABEL_CTDT),
    ("Ngành tự động hóa có môn thực tập tốt nghiệp riêng không?", LABEL_CTDT),
    # ── ctdt — học phần tương đương / thay thế ─────────────────────────────
    ("Môn nào có thể thay thế cho Giải tích 1?", LABEL_CTDT),
    ("Bảng học phần tương đương ngành CNTT", LABEL_CTDT),
    ("Môn Đại số tuyến tính có học phần tương đương không?", LABEL_CTDT),
    ("IT4062E tương đương với môn nào trong chương trình cũ?", LABEL_CTDT),
    (
        "Tôi đã học Xác suất thống kê ở trường khác, có được miễn không?",
        LABEL_CTDT,
    ),
    ("Học phần thay thế cho môn Vật lý 1 là gì?", LABEL_CTDT),
    ("Danh sách các môn tương đương trong chương trình K68 và K66", LABEL_CTDT),
    ("Môn tiếng Anh 1 có thể thay bằng môn nào?", LABEL_CTDT),
    (
        "Chuyển ngành thì những môn đã học có được công nhận tương đương không?",
        LABEL_CTDT,
    ),
    ("Quy trình xin công nhận học phần tương đương từ trường khác", LABEL_CTDT),
    ("Có bảng tra học phần thay thế cho sinh viên K67 không?", LABEL_CTDT),
    (
        "Môn Lập trình hướng đối tượng IT3100 tương đương môn nào mới?",
        LABEL_CTDT,
    ),
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
    ("Danh sách sinh viên được nhận học bổng khuyến khích", LABEL_KEHOACH),
    ("Thông báo danh sách nhận học bổng", LABEL_KEHOACH),
    ("Danh sách được nhận học bổng", LABEL_KEHOACH),
    ("Kết quả xét cấp học bổng học kỳ", LABEL_KEHOACH),
    (
        "Quyết định khen thưởng và cấp học bổng khuyến khích học tập",
        LABEL_KEHOACH,
    ),
    # ── kehoach — đăng ký học phần (chiếm 74.6% câu hỏi thực tế) ──────────
    ("Khi nào hệ thống mở đăng ký học phần học kỳ 1?", LABEL_KEHOACH),
    ("Đợt đăng ký tín chỉ học kỳ 20241 bắt đầu từ ngày nào?", LABEL_KEHOACH),
    ("Hệ thống đăng ký tín chỉ mở lúc mấy giờ?", LABEL_KEHOACH),
    ("Môn IT4062E kỳ này còn chỗ không?", LABEL_KEHOACH),
    ("Còn bao nhiêu slot trống cho môn Giải tích 1?", LABEL_KEHOACH),
    ("Kỳ này đã hết hạn đăng ký môn chưa?", LABEL_KEHOACH),
    ("Khi nào đóng cổng đăng ký học phần học kỳ 2?", LABEL_KEHOACH),
    ("Lịch các đợt đăng ký tín chỉ học kỳ này", LABEL_KEHOACH),
    ("Đợt 2 đăng ký học phần kỳ 2 khi nào?", LABEL_KEHOACH),
    ("Bao giờ có đợt đăng ký bổ sung môn học?", LABEL_KEHOACH),
    ("Thời hạn rút môn học mà không bị điểm W?", LABEL_KEHOACH),
    ("Deadline đăng ký học lại môn Vật lý 1?", LABEL_KEHOACH),
    ("Lịch đăng ký học phần học kỳ hè 2025", LABEL_KEHOACH),
    ("Khi nào sinh viên K68 được đăng ký tín chỉ?", LABEL_KEHOACH),
    ("Đợt ưu tiên đăng ký môn cho sinh viên năm 4 là bao giờ?", LABEL_KEHOACH),
    ("Thông báo lịch đăng ký học phần kỳ 20242", LABEL_KEHOACH),
    ("Bao giờ mở hệ thống đăng ký tín chỉ đợt 1?", LABEL_KEHOACH),
    ("Lịch các mốc đăng ký tín chỉ học kỳ 2 năm học 2024-2025", LABEL_KEHOACH),
    ("Hạn cuối đăng ký môn học kỳ 1 2024-2025?", LABEL_KEHOACH),
    ("Khi nào được phép rút môn mà không bị ảnh hưởng điểm?", LABEL_KEHOACH),
    # ── kehoach — đồ án / ĐATN timeline ────────────────────────────────────
    ("Hạn nộp đề cương đồ án tốt nghiệp kỳ này?", LABEL_KEHOACH),
    ("Lịch bảo vệ đồ án tốt nghiệp đợt tháng 1", LABEL_KEHOACH),
    ("Deadline nộp báo cáo đồ án tốt nghiệp học kỳ 1", LABEL_KEHOACH),
    ("Khi nào đăng ký đề tài đồ án tốt nghiệp?", LABEL_KEHOACH),
    ("Thời gian xét duyệt đề tài đồ án là bao lâu?", LABEL_KEHOACH),
    # ── kehoach — đăng ký học phần: thêm biến thể thực tế (chiếm 74.6%) ──────
    ("Còn slot môn IT3080 không?", LABEL_KEHOACH),
    ("Đăng ký được môn này chưa?", LABEL_KEHOACH),
    ("Mở đăng ký tín chỉ chưa?", LABEL_KEHOACH),
    ("Hệ thống đăng ký học phần mở lúc nào?", LABEL_KEHOACH),
    ("Bao giờ tới lượt K68 đăng ký?", LABEL_KEHOACH),
    ("Kỳ hè năm nay có mở đăng ký không và khi nào?", LABEL_KEHOACH),
    ("Khi nào hết hạn rút môn?", LABEL_KEHOACH),
    # ── ctdt — ĐATN nội dung (phân biệt với timeline ở trên) ─────────────────
    ("Đồ án tốt nghiệp gồm mấy học phần?", LABEL_CTDT),
    ("Cấu trúc học phần đồ án tốt nghiệp trong chương trình", LABEL_CTDT),
    ("Đồ án tốt nghiệp nằm ở học kỳ nào của chương trình?", LABEL_CTDT),
    (
        "Đồ án tốt nghiệp ngành KHMT có bao nhiêu tín chỉ và học vào kỳ mấy?",
        LABEL_CTDT,
    ),
    # ── ctdt — học phần tương đương / thay thế (thêm mẫu) ────────────────────
    ("Học phần nào tương đương với IT3080 trong chương trình mới?", LABEL_CTDT),
    ("Bảng tra học phần thay thế ngành Cơ điện tử K67", LABEL_CTDT),
    ("Môn Đại số tuyến tính cũ tương ứng học phần nào hiện nay?", LABEL_CTDT),
    ("Danh mục học phần tương đương giữa K66 và K68", LABEL_CTDT),
    # ── stsv (sinh viên: thủ tục, KTX, bảo hiểm, thẻ SV) ──────────────────
    ("Thủ tục xin giấy xác nhận sinh viên", LABEL_STSV),
    ("Làm thẻ sinh viên ở đâu?", LABEL_STSV),
    ("Mất thẻ sinh viên phải làm sao?", LABEL_STSV),
    ("Cách đăng ký KTX", LABEL_STSV),
    ("Ký túc xá ở đâu?", LABEL_STSV),
    ("Giá phòng KTX bao nhiêu?", LABEL_STSV),
    ("Đóng bảo hiểm y tế ở đâu?", LABEL_STSV),
    ("Cách đóng bảo hiểm y tế sinh viên", LABEL_STSV),
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
    # ── stsv — thực tập thủ tục ─────────────────────────────────────────────
    ("Thủ tục xin giấy giới thiệu thực tập doanh nghiệp", LABEL_STSV),
    ("Mẫu báo cáo thực tập lấy ở đâu?", LABEL_STSV),
    ("Cần giấy tờ gì để đăng ký thực tập ngoài trường?", LABEL_STSV),
    ("Xin xác nhận đang học để nộp cho công ty thực tập", LABEL_STSV),
    ("Thủ tục nộp báo cáo thực tập cuối kỳ", LABEL_STSV),
    # ── stsv — học phần tương đương thủ tục ─────────────────────────────────
    ("Nộp đơn xin công nhận học phần tương đương ở đâu?", LABEL_STSV),
    ("Thủ tục xin miễn học môn đã học ở trường khác", LABEL_STSV),
    # ── quydinh — GPA / điểm số ─────────────────────────────────────────────
    ("CPA tối thiểu để không bị cảnh báo học vụ là bao nhiêu?", LABEL_QUYDINH),
    ("GPA bao nhiêu thì được xếp loại khá?", LABEL_QUYDINH),
    ("Quy định cách tính điểm trung bình tích lũy CPA", LABEL_QUYDINH),
    ("Điểm D có được tính vào CPA không?", LABEL_QUYDINH),
    ("Bao nhiêu môn F thì bị cảnh báo học vụ?", LABEL_QUYDINH),
    (
        "Quy định điểm thành phần và thi cuối kỳ tính tỉ lệ thế nào?",
        LABEL_QUYDINH,
    ),
    ("CPA học kỳ và CPA tích lũy khác nhau thế nào?", LABEL_QUYDINH),
    ("Điểm I (incomplete) xử lý thế nào theo quy chế?", LABEL_QUYDINH),
    ("Thang điểm chữ A B C D F tương ứng với điểm số nào?", LABEL_QUYDINH),
    ("Quy định về bảo vệ điểm khi môn bị hủy lớp", LABEL_QUYDINH),
    # ── quydinh — thực tập ──────────────────────────────────────────────────
    ("Điều kiện được đăng ký thực tập doanh nghiệp", LABEL_QUYDINH),
    (
        "Sinh viên phải tích lũy bao nhiêu TC mới được đi thực tập?",
        LABEL_QUYDINH,
    ),
]


# ─── Hard negatives (single-label boundary cases) ─────────────────────────────
# Queries that look like one domain but belong to another.  These help the
# classifier learn sharper decision boundaries at the edges.
HARD_NEGATIVE_DATA: List[Tuple[str, str]] = [
    # registration: same surface keyword, different semantic domains
    ("Đăng ký học chương trình thứ hai khi nào?", LABEL_QUYDINH),
    ("Được đăng ký học chương trình thứ hai khi nào?", LABEL_QUYDINH),
    ("Bao giờ được đăng ký học chương trình thứ hai?", LABEL_QUYDINH),
    ("Thời điểm đăng ký học chương trình thứ hai là khi nào?", LABEL_QUYDINH),
    ("Sinh viên được học chương trình thứ hai khi nào?", LABEL_QUYDINH),
    ("Đăng ký học bằng thứ hai khi nào?", LABEL_QUYDINH),
    (
        "Khi nào được đăng ký học chương trình thứ hai theo quy chế?",
        LABEL_QUYDINH,
    ),
    (
        "Bao giờ sinh viên đủ điều kiện đăng ký chương trình thứ hai?",
        LABEL_QUYDINH,
    ),
    (
        "Điều kiện và thời điểm được đăng ký học chương trình thứ hai",
        LABEL_QUYDINH,
    ),
    ("Đăng ký chương trình thứ hai cần GPA bao nhiêu?", LABEL_QUYDINH),
    ("Quy chế cho phép đăng ký học bằng thứ hai khi nào?", LABEL_QUYDINH),
    ("Sinh viên năm mấy được học chương trình thứ hai?", LABEL_QUYDINH),
    ("Khi nào sinh viên được đăng ký học chương trình thứ hai?", LABEL_QUYDINH),
    ("Đăng ký học song ngành cần đạt CPA bao nhiêu?", LABEL_QUYDINH),
    ("Quy định học song ngành", LABEL_QUYDINH),
    ("Khi học ngành 2, nếu kết quả ngành 1 kém thì sao?", LABEL_QUYDINH),
    (
        "Khi học ngành 2, nếu kết quả học tập ngành 1 kém thì sao?",
        LABEL_QUYDINH,
    ),
    (
        "Nếu CPA ngành thứ nhất dưới trung bình khi học ngành 2 thì xử lý thế nào?",
        LABEL_QUYDINH,
    ),
    (
        "Bị cảnh báo học tập ở ngành 1 thì có bị dừng học chương trình thứ hai không?",
        LABEL_QUYDINH,
    ),
    ("Đăng ký tốt nghiệp sớm cần điều kiện gì?", LABEL_QUYDINH),
    ("Đăng ký đồ án tốt nghiệp cần điều kiện tín chỉ nào?", LABEL_QUYDINH),
    ("Học hai bằng đại học cùng lúc cần điều kiện gì?", LABEL_QUYDINH),
    (
        "Đăng ký song song hai ngành có bị giới hạn tín chỉ không?",
        LABEL_QUYDINH,
    ),
    (
        "Quy định điều chỉnh đăng ký kế hoạch học tập bao nhiêu lần?",
        LABEL_QUYDINH,
    ),
    ("Hướng dẫn đăng ký KTX", LABEL_STSV),
    ("Cách đăng ký bảo hiểm y tế sinh viên", LABEL_STSV),
    ("Đăng ký gửi xe máy ở đâu?", LABEL_STSV),
    ("Cần giấy tờ gì để đăng ký ở ký túc xá?", LABEL_STSV),
    ("Thủ tục đăng ký cấp lại thẻ sinh viên", LABEL_STSV),
    ("Hướng dẫn đăng ký tài khoản wifi sinh viên", LABEL_STSV),
    ("Lịch mở đăng ký KTX học kỳ này", LABEL_KEHOACH),
    ("Khi nào mở đăng ký bảo hiểm y tế sinh viên?", LABEL_KEHOACH),
    ("Thời hạn đăng ký gửi xe trong trường", LABEL_KEHOACH),
    ("Lịch đăng ký đồ án tốt nghiệp kỳ này", LABEL_KEHOACH),
    ("Mức đóng bảo hiểm y tế sinh viên là bao nhiêu?", LABEL_QUYDINH),
    ("Quy định mức thu bảo hiểm y tế sinh viên", LABEL_QUYDINH),
    (
        "Bảo hiểm y tế sinh viên năm nay đóng bao nhiêu tiền theo quy định?",
        LABEL_QUYDINH,
    ),
    ("Mức phí bảo hiểm y tế bắt buộc của sinh viên", LABEL_QUYDINH),
    ("Sinh viên phải đóng bao nhiêu tiền bảo hiểm y tế?", LABEL_QUYDINH),
    # graduate / doctoral regulations: policy rules, not CTDT or schedule
    ("Khi nào học viên thạc sĩ đăng ký đề tài luận văn?", LABEL_QUYDINH),
    ("Quy định về thời điểm đăng ký đề tài luận văn thạc sĩ", LABEL_QUYDINH),
    ("Có được thay đổi đề tài luận văn thạc sĩ không?", LABEL_QUYDINH),
    (
        "Thạc sĩ có được thay đổi đề tài luận văn trong quá trình thực hiện không?",
        LABEL_QUYDINH,
    ),
    ("Điều kiện để học viên thạc sĩ được bảo vệ luận văn", LABEL_QUYDINH),
    (
        "Thời hạn tối đa để hoàn thành chương trình đào tạo thạc sĩ",
        LABEL_QUYDINH,
    ),
    ("Chuẩn đầu ra ngoại ngữ của thạc sĩ là bậc mấy?", LABEL_QUYDINH),
    (
        "Luận văn thạc sĩ phải được nộp cho thư viện trong vòng bao nhiêu ngày?",
        LABEL_QUYDINH,
    ),
    (
        "Nghiên cứu sinh cần hoàn thành bao nhiêu chuyên đề tiến sĩ?",
        LABEL_QUYDINH,
    ),
    ("Nghiên cứu sinh phải hoàn thành mấy chuyên đề tiến sĩ?", LABEL_QUYDINH),
    ("Khi nào nghiên cứu sinh được rút ngắn thời gian học tập?", LABEL_QUYDINH),
    ("Quy định rút ngắn thời gian học tập của nghiên cứu sinh", LABEL_QUYDINH),
    (
        "Nghiên cứu sinh tập trung toàn thời gian cần đăng ký bao nhiêu tín chỉ một năm?",
        LABEL_QUYDINH,
    ),
    (
        "Nghiên cứu sinh bảo vệ luận án cấp cơ sở cần bao nhiêu phiếu đồng ý?",
        LABEL_QUYDINH,
    ),
    ("Điều kiện để nghiên cứu sinh bảo vệ luận án cấp Đại học", LABEL_QUYDINH),
    (
        "Nghiên cứu sinh có được chuyển trường khi còn 6 tháng không?",
        LABEL_QUYDINH,
    ),
    ("ĐHBK Hà Nội áp dụng mấy học kỳ chính trong năm?", LABEL_QUYDINH),
    ("Một năm học ở ĐHBK Hà Nội có mấy học kỳ chính?", LABEL_QUYDINH),
    (
        "Sinh viên năm mấy thì được phép đăng ký học lại dưới hình thức đồ án môn học?",
        LABEL_QUYDINH,
    ),
    (
        "Học viên kỹ sư được xét tốt nghiệp khi điểm trung bình tích lũy đạt bao nhiêu?",
        LABEL_QUYDINH,
    ),
    (
        "Học phần tương đương phải trùng lặp nội dung bao nhiêu phần trăm?",
        LABEL_QUYDINH,
    ),
    (
        "Sinh viên bị cảnh báo học tập mức 2 nếu có kết quả như thế nào?",
        LABEL_QUYDINH,
    ),
    ("Khi nào sinh viên được hạ mức cảnh báo học tập?", LABEL_QUYDINH),
    ("Sinh viên đang cảnh báo mức 3 có được hạ mức không?", LABEL_QUYDINH),
    ("Điều kiện hạ mức cảnh báo học tập là gì?", LABEL_QUYDINH),
    (
        "Số tín chỉ không đạt bao nhiêu thì sinh viên được hạ cảnh báo học tập?",
        LABEL_QUYDINH,
    ),
    # scholarship: procedure vs. condition vs. deadline vs. announcement/lists
    ("Học bổng kỳ này nộp đơn ở đâu?", LABEL_STSV),  # WHERE → procedure
    ("Nộp đơn học bổng kỳ này ở đâu?", LABEL_STSV),
    ("Hồ sơ học bổng nộp ở phòng nào?", LABEL_STSV),
    ("Học bổng doanh nghiệp nộp hồ sơ ở đâu?", LABEL_STSV),
    ("Xin học bổng thì nộp đơn ở đâu?", LABEL_STSV),
    ("Mẫu đơn học bổng lấy ở đâu và nộp ở đâu?", LABEL_STSV),
    ("Điều kiện học bổng kỳ này là gì?", LABEL_QUYDINH),  # condition → quydinh
    ("Deadline nộp học bổng kỳ này?", LABEL_KEHOACH),  # deadline → kehoach
    (
        "Danh sách được nhận học bổng",
        LABEL_KEHOACH,
    ),  # announcement/list → kehoach
    ("Mẫu đơn xin học bổng lấy ở đâu?", LABEL_STSV),
    ("Tiêu chí xét học bổng khuyến khích học tập", LABEL_QUYDINH),
    ("Thời hạn nộp hồ sơ học bổng học kỳ 2", LABEL_KEHOACH),
    ("Quyết định cấp học bổng kỳ vừa rồi ở đâu", LABEL_KEHOACH),
    # insurance: procedure vs. deadline
    ("Đăng ký bảo hiểm y tế ở đâu?", LABEL_STSV),  # WHERE → stsv
    ("Bao giờ hết hạn đăng ký bảo hiểm?", LABEL_KEHOACH),  # WHEN → kehoach
    ("Mức đóng bảo hiểm y tế sinh viên năm nay", LABEL_QUYDINH),
    ("Thủ tục hủy bảo hiểm y tế", LABEL_STSV),
    # credit limits: quydinh (rule, not curriculum content)
    ("Khung chương trình yêu cầu bao nhiêu tín chỉ mỗi kỳ?", LABEL_CTDT),
    ("Quy định đăng ký tối thiểu bao nhiêu tín chỉ?", LABEL_QUYDINH),
    # graduation: ctdt vs. quydinh
    ("Quy định số tín chỉ tích lũy để làm đồ án", LABEL_QUYDINH),
    ("Môn nào là tiên quyết của đồ án tốt nghiệp?", LABEL_CTDT),
    # "when/register" wording that points to policy rules, not schedule notices
    ("Khi nào sinh viên được đăng ký học chương trình thứ hai?", LABEL_QUYDINH),
    ("Khi nào học viên thạc sĩ đăng ký đề tài luận văn?", LABEL_QUYDINH),
    ("ĐHBK Hà Nội áp dụng mấy học kỳ chính trong năm?", LABEL_QUYDINH),
    # "ke hoach hoc tap" is a curriculum/study-plan phrase inside CTDT
    (
        "Kế hoạch học tập trong CTĐT ngành CNTT gồm những học phần nào?",
        LABEL_CTDT,
    ),
    ("Kế hoạch học tập của chương trình đào tạo có bao nhiêu kỳ?", LABEL_CTDT),
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
    # ── kehoach ↔ ctdt — ranh giới đăng ký học phần (chiếm 74.6%) ──────────
    # WHEN về môn cụ thể → kehoach; WHAT về môn đó → ctdt
    ("Khi nào mở đăng ký môn Giải tích 1?", LABEL_KEHOACH),
    ("Giải tích 1 có bao nhiêu tín chỉ?", LABEL_CTDT),
    (
        "Môn IT4062E dạy học kỳ nào?",
        LABEL_CTDT,
    ),  # thuộc CTDT (kế hoạch môn học)
    ("Kỳ này còn lớp IT4062E không?", LABEL_KEHOACH),  # WHEN/status → kehoach
    ("Môn Vật lý 1 mở lớp vào học kỳ nào trong năm?", LABEL_CTDT),
    ("Đợt đăng ký môn Vật lý 1 kỳ này khi nào?", LABEL_KEHOACH),
    # ── "kỳ mấy của môn" — vị trí trong kế hoạch học tập (ctdt), KHÔNG phải
    #    thời điểm mở đăng ký (kehoach). Động từ "học" hay "đăng ký" KHÔNG quyết
    #    định domain — câu hỏi WHICH-semester luôn là ctdt.
    ("Môn mạng máy tính được học vào kỳ mấy?", LABEL_CTDT),
    ("Môn mạng máy tính đăng ký vào kỳ mấy?", LABEL_CTDT),
    ("Học phần IT3080 nằm ở học kỳ nào trong chương trình?", LABEL_CTDT),
    ("Môn Giải tích 1 học vào kỳ mấy theo kế hoạch học tập?", LABEL_CTDT),
    ("Môn Triết học Mác-Lênin xếp vào học kỳ thứ mấy?", LABEL_CTDT),
    ("Học phần Mạng máy tính thuộc kỳ học nào của ngành?", LABEL_CTDT),
    ("Môn Vật lý đại cương đăng ký vào học kỳ mấy trong CTĐT?", LABEL_CTDT),
    ("IT3080 học ở kỳ mấy?", LABEL_CTDT),
    # giữ ranh giới: WHEN mở đăng ký vẫn là kehoach
    ("Khi nào mở đăng ký môn mạng máy tính kỳ này?", LABEL_KEHOACH),
    ("Bao giờ được đăng ký học phần IT3080?", LABEL_KEHOACH),
    ("Lập trình hướng đối tượng có mấy lớp học kỳ 2?", LABEL_KEHOACH),
    ("Lập trình hướng đối tượng thuộc khối kiến thức nào?", LABEL_CTDT),
    # ── kehoach ↔ ctdt — đồ án timeline vs. nội dung ───────────────────────
    ("Deadline nộp đề cương đồ án tốt nghiệp kỳ này?", LABEL_KEHOACH),
    ("Đề cương đồ án tốt nghiệp cần có những mục gì?", LABEL_CTDT),
    ("Bao giờ đăng ký đề tài đồ án tốt nghiệp kỳ 1 2025?", LABEL_KEHOACH),
    ("Quy trình chọn đề tài đồ án tốt nghiệp như thế nào?", LABEL_CTDT),
    # ── kehoach ↔ ctdt — học phần tương đương timeline vs. nội dung ─────────
    (
        "Hạn nộp đơn xin công nhận học phần tương đương học kỳ này?",
        LABEL_KEHOACH,
    ),
    ("Học phần tương đương của Đại số tuyến tính là gì?", LABEL_CTDT),
    # ── ctdt ↔ quydinh — thực tập ───────────────────────────────────────────
    ("Ngành CNTT có môn thực tập trong chương trình không?", LABEL_CTDT),
    ("Điều kiện tín chỉ để được đăng ký thực tập?", LABEL_QUYDINH),
    # ── ctdt ↔ quydinh — "tương đương": thay thế học phần vs. quy đổi tín chỉ ─
    # ctdt = môn này thay được môn nào trong khung chương trình;
    # quydinh = chính sách quy đổi/công nhận tín chỉ giữa các hệ / sang ECTS.
    ("Học phần tương đương của môn Đại số tuyến tính là gì?", LABEL_CTDT),
    ("Môn nào thay thế được Giải tích 1 trong chương trình?", LABEL_CTDT),
    ("Quy đổi tương đương tín chỉ sang hệ thống ECTS thế nào?", LABEL_QUYDINH),
    ("Tín chỉ của trường quy đổi sang ECTS theo tỷ lệ nào?", LABEL_QUYDINH),
    (
        "Quy định công nhận tín chỉ khi chuyển đổi giữa các chương trình",
        LABEL_QUYDINH,
    ),
    ("Bảng quy đổi tín chỉ tích lũy sang tín chỉ Châu Âu", LABEL_QUYDINH),
    # ── quydinh ↔ stsv — điểm số ────────────────────────────────────────────
    ("Quy định xử lý khi bị điểm F môn bắt buộc?", LABEL_QUYDINH),
    ("Xin phúc khảo điểm thi thì nộp đơn ở đâu?", LABEL_STSV),
    # ── kehoach: NỘI DUNG thông báo/bài viết (không có mốc thời gian) ──────────
    # Bộ kehoach hiện tại lệch hẳn về câu hỏi "khi nào/lịch/deadline". Các thông
    # báo (bài viết) nằm trong collection kehoach cũng bị hỏi về NỘI DUNG, không
    # kèm dấu hiệu thời gian — classifier đang route nhầm sang quydinh/stsv/ctdt.
    # (Đo được: kehoach recall ~0.50; xem evaluation/evaluate_domain_routing.py.)
    #
    # Tuyển dụng / ngày hội việc làm — bài viết thuần thông báo → kehoach
    (
        "Công ty trong đợt tuyển dụng này yêu cầu sinh viên năm mấy?",
        LABEL_KEHOACH,
    ),
    (
        "Mức lương thử việc của đợt tuyển dụng là bao nhiêu phần trăm lương chính thức?",
        LABEL_KEHOACH,
    ),
    (
        "Doanh nghiệp tham gia ngày hội việc làm hoạt động trong lĩnh vực gì?",
        LABEL_KEHOACH,
    ),
    (
        "Hồ sơ ứng tuyển chương trình tuyển dụng gửi về email nào?",
        LABEL_KEHOACH,
    ),
    (
        "Chỉ tiêu tuyển dụng của chương trình thực tập doanh nghiệp là bao nhiêu?",
        LABEL_KEHOACH,
    ),
    (
        "Địa điểm làm việc của công ty trong thông báo tuyển dụng ở đâu?",
        LABEL_KEHOACH,
    ),
    (
        "Chế độ nghỉ phép tại công ty tuyển dụng được quy định thế nào?",
        LABEL_KEHOACH,
    ),
    # Thông báo lịch nộp học phí — NỘI DUNG (đợt/đối tượng/cách kiểm tra) → kehoach
    ("Học phí kỳ này được chia làm mấy đợt nộp?", LABEL_KEHOACH),
    ("Đối tượng nào chưa được tính học phí trong đợt thu này?", LABEL_KEHOACH),
    (
        "Thông báo nộp học phí hướng dẫn kiểm tra thông tin ở đâu?",
        LABEL_KEHOACH,
    ),
    (
        "Liên hệ hỏi về học phí đợt này dùng email và tiêu đề thế nào?",
        LABEL_KEHOACH,
    ),
    # ── hard negative bảo vệ ranh giới: QUY ĐỊNH chung (không phải thông báo) ──
    (
        "Quy định về số tín chỉ tối đa được đăng ký mỗi học kỳ là gì?",
        LABEL_QUYDINH,
    ),
    ("Quy định mức học phí tính theo tín chỉ như thế nào?", LABEL_QUYDINH),
    (
        "Điều kiện chung để được xét học bổng khuyến khích học tập?",
        LABEL_QUYDINH,
    ),
    # ── hard negative: GOVERNANCE/trách nhiệm (ai/đơn vị/hội đồng/vai trò) → quydinh
    # Phân biệt với kehoach (khi nào/đợt/nội dung thông báo). Các câu hỏi về
    # trách nhiệm tổ chức, thành phần hội đồng, vai trò đơn vị là quy định quản
    # trị — dù có chữ "kế hoạch"/"tổ chức"/"học bổng".
    (
        "Đơn vị nào chịu trách nhiệm tổ chức kỳ thi và lập kế hoạch tham dự?",
        LABEL_QUYDINH,
    ),
    ("Hội đồng xét cấp học bổng gồm những thành phần nào?", LABEL_QUYDINH),
    ("Ai là chủ tịch hội đồng xét cấp học bổng?", LABEL_QUYDINH),
    (
        "Vai trò của phòng tài chính trong việc cấp kinh phí cho đội tuyển là gì?",
        LABEL_QUYDINH,
    ),
    (
        "Trách nhiệm của các đơn vị khi tổ chức đoàn tham dự kỳ thi được quy định thế nào?",
        LABEL_QUYDINH,
    ),
    (
        "Bộ phận nào phụ trách xếp lớp ban đầu cho sinh viên theo quy định?",
        LABEL_QUYDINH,
    ),
]


# ─── Multi-label training samples ─────────────────────────────────────────────
# Queries that genuinely span multiple domains.  Each label list is ordered
# from primary (most relevant) to secondary domain(s).
MULTI_LABEL_DATA: List[Tuple[str, List[str]]] = [
    (
        "Học kỳ 3 ngành KHMT học những môn gì và học phí tính thế nào?",
        ["ctdt", "quydinh"],
    ),
    (
        "Ngành CNTT cần bao nhiêu tín chỉ và điều kiện tốt nghiệp ra sao?",
        ["ctdt", "quydinh"],
    ),
    (
        "Môn học kỳ 1 ngành Điện tử và quy định điểm D tính thế nào?",
        ["ctdt", "quydinh"],
    ),
    (
        "Chương trình đào tạo kỹ sư tài năng và điều kiện xét tuyển vào",
        ["ctdt", "quydinh"],
    ),
    (
        "Số tín chỉ ngành KTMT và mức học phí mỗi tín chỉ",
        ["ctdt", "quydinh"],
    ),
    (
        "Lịch đăng ký môn học kỳ 2 ngành Cơ điện tử",
        ["ctdt", "kehoach"],
    ),
    (
        "Lịch đăng ký môn trong CTĐT ngành CNTT và số tín chỉ của môn đó",
        ["ctdt", "kehoach"],
    ),
    (
        "Khi nào đăng ký thực tập và điều kiện là gì?",
        ["ctdt", "kehoach"],
    ),
    (
        "Điều kiện nhận học bổng và nộp hồ sơ ở đâu?",
        ["quydinh", "stsv"],
    ),
    (
        "Quy định bảo lưu kết quả học tập và thủ tục xin bảo lưu",
        ["quydinh", "stsv"],
    ),
    (
        "Chính sách miễn giảm học phí và cách đăng ký",
        ["quydinh", "stsv"],
    ),
    (
        "Điều kiện được ở KTX và cách đăng ký phòng",
        ["quydinh", "stsv"],
    ),
    (
        "Quy định sinh viên nước ngoài và thủ tục nhập học",
        ["quydinh", "stsv"],
    ),
    (
        "Tiêu chuẩn xét học bổng khuyến khích và hướng dẫn nộp đơn",
        ["quydinh", "stsv"],
    ),
    (
        "Thông tin về học bổng",
        ["quydinh", "stsv"],
    ),
    (
        "Có bao nhiêu loại học bổng",
        ["quydinh", "stsv"],
    ),
    (
        "Có những loại học bổng nào",
        ["quydinh", "stsv"],
    ),
    (
        "Các loại học bổng của trường",
        ["quydinh", "stsv"],
    ),
    (
        "Trường có những học bổng gì",
        ["quydinh", "stsv"],
    ),
    (
        "Giới thiệu về các chương trình học bổng",
        ["quydinh", "stsv"],
    ),
    (
        "Tổng quan về học bổng tại trường",
        ["quydinh", "stsv"],
    ),
    (
        "Học bổng gồm những gì",
        ["quydinh", "stsv"],
    ),
    (
        "Danh mục các học bổng dành cho sinh viên",
        ["quydinh", "stsv"],
    ),
    (
        "Các chương trình học bổng hiện có",
        ["quydinh", "stsv"],
    ),
    (
        "Điều kiện phúc khảo bài thi và thời hạn nộp đơn",
        ["kehoach", "quydinh"],
    ),
    (
        "Quy trình đăng ký học lại và deadline đăng ký",
        ["kehoach", "quydinh"],
    ),
    (
        "Thời hạn nộp đơn phúc khảo và quy định điểm phúc khảo",
        ["kehoach", "quydinh"],
    ),
    (
        "Thời gian đăng ký KTX học kỳ tới và thủ tục",
        ["kehoach", "stsv"],
    ),
    (
        "Bao giờ đóng bảo hiểm y tế và đóng ở đâu?",
        ["kehoach", "stsv"],
    ),
    (
        "Lịch nhận bằng tốt nghiệp và cần mang giấy tờ gì?",
        ["kehoach", "stsv"],
    ),
    (
        "Thông báo nhận học bổng và thủ tục nhận ở đâu",
        ["kehoach", "stsv"],
    ),
    (
        "Điều kiện tín chỉ tích lũy để đăng ký đồ án tốt nghiệp ngành CNTT",
        ["ctdt", "quydinh"],
    ),
    (
        "Đồ án tốt nghiệp bao nhiêu TC và quy định điểm tối thiểu để qua?",
        ["ctdt", "quydinh"],
    ),
    (
        "Chương trình đào tạo kỹ sư tài năng có ĐATN riêng không và điều kiện xét?",
        ["ctdt", "quydinh"],
    ),
    (
        "Khi nào đăng ký đề tài đồ án tốt nghiệp và quy trình chọn GVHD?",
        ["ctdt", "kehoach"],
    ),
    (
        "Lịch bảo vệ đồ án tốt nghiệp và số tín chỉ của môn đó",
        ["ctdt", "kehoach"],
    ),
    (
        "Quy trình nộp báo cáo đồ án tốt nghiệp và mẫu báo cáo lấy ở đâu?",
        ["ctdt", "stsv"],
    ),
    (
        "Học phần tương đương",
        ["ctdt", "quydinh"],
    ),
    (
        "Học phần tương đương là gì?",
        ["ctdt", "quydinh"],
    ),
    (
        "Quy định về học phần tương đương",
        ["ctdt", "quydinh"],
    ),
    (
        "Thế nào là học phần tương đương?",
        ["ctdt", "quydinh"],
    ),
    (
        "Học phần tương đương và học phần thay thế khác nhau thế nào?",
        ["ctdt", "quydinh"],
    ),
    (
        "Điều kiện để được công nhận học phần tương đương từ trường khác",
        ["ctdt", "quydinh"],
    ),
    (
        "Bảng môn tương đương ngành CNTT và quy định nộp đơn xin miễn học",
        ["ctdt", "quydinh"],
    ),
    (
        "Điều kiện đăng ký thực tập doanh nghiệp và hạn đăng ký kỳ này",
        ["ctdt", "kehoach"],
    ),
    (
        "CPA bao nhiêu thì bị cảnh báo và thời hạn khắc phục?",
        ["kehoach", "quydinh"],
    ),
    (
        "Quy định phúc khảo bài thi và thủ tục nộp đơn phúc khảo",
        ["quydinh", "stsv"],
    ),
    (
        "Điều kiện điểm học tập để được xét học bổng tài trợ theo đợt là gì?",
        ["kehoach", "quydinh"],
    ),
    (
        "Mức học bổng của đợt xét này dành cho mỗi sinh viên là bao nhiêu?",
        ["kehoach", "quydinh"],
    ),
    (
        "Số tín chỉ tối đa và tối thiểu khi đăng ký học kỳ này là bao nhiêu?",
        ["kehoach", "quydinh"],
    ),
    (
        "Đăng ký xét tốt nghiệp đợt này thực hiện trên tài khoản nào?",
        ["kehoach", "stsv"],
    ),
    (
        "Sinh viên đăng ký kế hoạch học tập trên hệ thống nào và đăng nhập bằng tài khoản gì?",
        ["kehoach", "stsv"],
    ),
    (
        "Đăng ký tốt nghiệp đợt này kiểm tra điểm và gửi thắc mắc ở đâu?",
        ["kehoach", "stsv"],
    ),
    (
        "Thời hạn nộp đơn xin miễn học phần ngoại ngữ cơ bản là khi nào?",
        ["kehoach", "quydinh"],
    ),
    (
        "Chứng chỉ quốc tế cần làm gì trước khi xét miễn?",
        ["ctdt", "quydinh"],
    ),
    (
        "Kết quả TOEIC Placement dùng để xét chuẩn đầu ra không?",
        ["quydinh"],
    ),
    (
        "TOEFL iBT Home Edition có được công nhận không?",
        ["quydinh"],
    ),
    (
        "Sinh viên cần chuẩn bị gì trước khi nộp đơn miễn học?",
        ["quydinh", "stsv"],
    ),
    (
        "Quyết định 1515/QĐ-ĐHBK-ĐT về tổ chức dạy-học trực tuyến tại Bách khoa Hà Nội được ban hành vào ngày tháng năm nào?",
        ["quydinh"],
    ),
    (
        "Dạy-học trực tuyến theo thời gian thực tại Bách khoa Hà Nội ưu tiên sử dụng phần mềm nào?",
        ["quydinh"],
    ),
    (
        "Tại Bách khoa Hà Nội, dạy-học trực tuyến được áp dụng mấy hình thức và tên gọi của từng hình thức là gì?",
        ["quydinh"],
    ),
    (
        "Dạy-học trực tuyến không được áp dụng với loại học phần nào tại Bách khoa Hà Nội?",
        ["quydinh"],
    ),
    (
        "Học liệu số từ nguồn mở chỉ được dùng như thế nào trong B-Learning tại Bách khoa?",
        ["quydinh"],
    ),
    (
        "Trung tâm Mạng thông tin có vai trò gì trong hệ thống dạy-học trực tuyến tại Bách khoa?",
        ["quydinh"],
    ),
    (
        "Thời lượng video bài giảng B-Learning bao nhiêu phút tương đương 45 phút dạy-học trực tiếp trên lớp?",
        ["quydinh"],
    ),
    (
        "So sánh trách nhiệm của Phòng Đào tạo và Trung tâm Mạng thông tin trong việc triển khai B-Learning tại Bách khoa?",
        ["quydinh"],
    ),
    (
        "Quy trình đăng ký và thẩm định bài giảng B-Learning tại Bách khoa diễn ra trong bao nhiêu bước chính và ai thực hiện thẩm định cuối cùng?",
        ["quydinh"],
    ),
    (
        "Kết quả xét học bổng KKHT tại Bách khoa Hà Nội được công bố chậm nhất vào tuần học thứ mấy và ở đâu?",
        ["kehoach", "quydinh"],
    ),
    (
        "Sinh viên nhận học bổng KKHT tại Bách khoa sẽ biết kết quả vào thời điểm nào và nhận tiền bằng cách nào?",
        ["kehoach", "quydinh"],
    ),
    (
        "Điều kiện tín chỉ tích lũy tối thiểu để sinh viên được đăng ký học tích lũy trước các học phần bậc kỹ sư chuyên sâu là bao nhiêu?",
        ["kehoach", "quydinh"],
    ),
    (
        "Sinh viên đăng ký học tích lũy trước các học phần bậc kỹ sư chuyên sâu được tối đa bao nhiêu tín chỉ?",
        ["kehoach", "quydinh"],
    ),
    (
        "Sau khi đăng ký học tích hợp KSCS thành công, sinh viên được cấp gì?",
        ["kehoach", "quydinh"],
    ),
    (
        "Học phí các học phần bậc Kỹ sư chuyên sâu được tính như thế nào so với bậc cử nhân?",
        ["kehoach", "quydinh"],
    ),
    (
        "Sinh viên có thắc mắc về đăng ký học tích hợp Kỹ sư chuyên sâu HK 2025.2 điền thông tin vào form nào?",
        ["kehoach", "stsv"],
    ),
    (
        "Sinh viên đăng ký học tích hợp KSCS biết mình đăng ký thành công bằng cách nào?",
        ["kehoach", "stsv"],
    ),
    (
        "Khi nào sinh viên chuyển từ học viên kỹ sư tạm thời sang học viên kỹ sư chính thức?",
        ["ctdt", "kehoach"],
    ),
    (
        "Sinh viên chương trình Elitech muốn học lên bậc Kỹ sư chuyên sâu thì học theo chương trình nào?",
        ["ctdt", "kehoach"],
    ),
    (
        "Sinh viên muốn hủy đăng ký học tích hợp KSCS thực hiện thế nào?",
        ["kehoach", "quydinh", "stsv"],
    ),
    (
        "Đăng ký học học kỳ hè có bắt buộc không và sinh viên phải đóng bao nhiêu phần trăm học phí?",
        ["kehoach", "quydinh"],
    ),
    (
        "Sinh viên tra cứu Chương trình đào tạo (CTĐT) của mình để đăng ký đúng mã học phần theo hướng dẫn ra sao?",
        ["ctdt", "kehoach"],
    ),
    (
        "Sinh viên có sai sót về thông tin họ tên, ngày sinh trên văn bằng tốt nghiệp liên hệ ai để sửa?",
        ["kehoach", "stsv"],
    ),
    (
        "Lịch thi giữa kỳ 20251 có một số lớp đổi phòng từ D6-407 sang phòng nào?",
        ["kehoach", "stsv"],
    ),
    (
        "Sinh viên đăng ký lớp kỳ 2 năm học 2025-2026 trực tuyến tại địa chỉ nào?",
        ["kehoach", "stsv"],
    ),
    (
        "Khối lượng tín chỉ đăng ký tối đa kỳ 2 năm 2025-2026 với sinh viên chương trình Elitech là bao nhiêu?",
        ["kehoach", "quydinh"],
    ),
    (
        "Sinh viên có thắc mắc về miễn giảm chế độ chính sách học phí kỳ 1 năm 2025-2026 liên hệ ai?",
        ["kehoach", "quydinh", "stsv"],
    ),
    (
        "Sinh viên muốn đăng ký học tích hợp Kỹ sư chuyên sâu 2025.2 cần có điều kiện gì và đăng ký trên hệ thống nào?",
        ["kehoach", "quydinh"],
    ),
    (
        "Sinh viên chương trình chuẩn bị cảnh cáo học tập mức 3 đăng ký lớp kỳ 2 năm 2025-2026 được tối đa bao nhiêu TC và sau khi rút học phần phải đảm bảo tối thiểu bao nhiêu TC?",
        ["kehoach", "quydinh"],
    ),
    (
        "Học phí kỳ 2 năm 2025-2026 được tính theo mấy đợt và sinh viên cần kiểm tra điều gì ở đợt 2?",
        ["kehoach", "quydinh"],
    ),
    (
        "Sinh viên đăng ký tốt nghiệp đợt 2025.1 cần kiểm tra điểm ở đâu và nếu có thắc mắc về GD QP-AN liên hệ ai?",
        ["kehoach", "stsv"],
    ),
    (
        "Sinh viên K70 muốn biết mình học GDQP-AN vào tuần nào trong kỳ hè 20253 cần theo dõi thông tin ở đâu?",
        ["kehoach", "stsv"],
    ),
    (
        "Sinh viên đăng ký lớp kỳ 2 năm 2025-2026 không hoàn thành học phí sẽ bị xử lý thế nào và muốn mở thêm lớp cần làm gì?",
        ["kehoach", "quydinh"],
    ),
    (
        "Sinh viên học phần KSCS đang tích lũy trước bằng MSSV, nếu trong thời gian đó đăng ký xét tốt nghiệp cử nhân thành công thì kết quả học tập KSCS có được công nhận không?",
        ["kehoach", "quydinh"],
    ),
    (
        "Học phí kỳ 1 năm 2025-2026 đợt 2 sai sót về học phần tính ngoài CTĐT ảnh hưởng đến quyền lợi gì của sinh viên?",
        ["kehoach", "quydinh"],
    ),
    (
        "Khung đánh giá kết quả rèn luyện sinh viên năm học 2020 - 2021 được ban hành kèm theo quyết định số bao nhiêu?",
        ["kehoach", "quydinh"],
    ),
    (
        "Bản kế hoạch tổ chức đoàn tham dự kỳ thi Olympic môn học tại Bách khoa Hà Nội cần bao gồm những nội dung gì?",
        ["quydinh"],
    ),
    (
        "Sau khi kết thúc kỳ thi Olympic môn học, đơn vị chuyên môn tại Bách khoa Hà Nội phải làm gì?",
        ["quydinh"],
    ),
    (
        "Đơn vị nào chủ trì lập kế hoạch tuyển chọn và tổ chức đoàn tham dự kỳ thi Đổi mới sáng tạo và khởi nghiệp tại Bách khoa Hà Nội?",
        ["quydinh"],
    ),
    (
        "BK-Holdings có vai trò gì trong công tác tổ chức đội tuyển thi ĐMST tại Bách khoa Hà Nội?",
        ["quydinh"],
    ),
    (
        "Sau khi đội tuyển thi ĐMST kết thúc tham dự, đơn vị nào lập báo cáo và gửi đến ai?",
        ["quydinh"],
    ),
    (
        "Một năm học tại Đại học Bách khoa Hà Nội gồm bao nhiêu học kỳ và có tổ chức học kỳ hè không?",
        ["ctdt", "quydinh"],
    ),
    (
        "Điểm cuối kỳ của đồ án tốt nghiệp đại học tại Bách khoa được tính như thế nào?",
        ["ctdt", "quydinh"],
    ),
    (
        "Đại học Bách khoa Hà Nội xét tốt nghiệp đại học mấy đợt trong năm và vào thời điểm nào?",
        ["kehoach", "quydinh"],
    ),
    (
        "Học viên chương trình kỹ sư tại Bách khoa được giao đề tài ĐATN kỹ sư khi nào?",
        ["ctdt", "quydinh"],
    ),
    (
        "Chương trình ELITECH tại Đại học Bách khoa Hà Nội là viết tắt của cụm từ gì?",
        ["ctdt"],
    ),
    (
        "Chương trình đào tạo Tài năng tại Bách khoa Hà Nội được thiết kế nhằm mục đích gì?",
        ["ctdt"],
    ),
    (
        "So sánh chương trình kỹ sư tích hợp và chương trình kỹ sư thông thường tại Bách khoa về thời gian và số tín chỉ tối thiểu?",
        ["ctdt"],
    ),
    (
        "Chương trình đào tạo tích hợp tại Bách khoa Hà Nội được thiết kế như thế nào?",
        ["ctdt"],
    ),
    (
        "Khi gặp vướng mắc trong quá trình tổ chức thực hiện Thông tư liên tịch 18/2015, các đơn vị cần phản ánh về đâu?",
        ["quydinh", "stsv"],
    ),
    (
        "Lương thử việc tại Goertek Vina bằng bao nhiêu phần trăm lương chính thức và ước tính khoảng bao nhiêu tiền?",
        ["kehoach"],
    ),
    (
        "Goertek Vina được thành lập năm nào và ở đâu tại Việt Nam?",
        ["kehoach"],
    ),
    (
        "Điều kiện về tuổi đời khi tham gia đào tạo sĩ quan dự bị năm 2026 là gì?",
        ["kehoach", "quydinh"],
    ),
    (
        "Sinh viên đăng ký dự tuyển đào tạo sĩ quan dự bị năm 2026 tại Bách khoa Hà Nội ở đâu?",
        ["kehoach", "stsv"],
    ),
    (
        "Sinh viên được tuyển đào tạo sĩ quan dự bị có quyền lợi gì trong thời gian đào tạo?",
        ["kehoach", "quydinh"],
    ),
    (
        "Địa điểm làm việc của Công ty TNHH DAIZO TEC tại Hà Nội ở đâu?",
        ["kehoach"],
    ),
    (
        "Điều kiện điểm học tập để được xét Học bổng Trần Đại Nghĩa học kỳ II năm học 2025-2026 là bao nhiêu?",
        ["kehoach", "quydinh"],
    ),
    (
        "Mức học bổng Trần Đại Nghĩa dành cho sinh viên nhóm b khoản 1 là bao nhiêu?",
        ["kehoach", "quydinh"],
    ),
    (
        "Sinh viên nào bị loại khỏi xét học bổng Trần Đại Nghĩa kỳ 2025.2 do đã có học bổng khác?",
        ["kehoach", "quydinh"],
    ),
    (
        "Sinh viên có thắc mắc về cách đóng học phí kỳ 2 năm 2025-2026 liên hệ ai?",
        ["kehoach", "stsv"],
    ),
    (
        "Sinh viên có thắc mắc về điều kiện hoàn thành Giáo dục quốc phòng – an ninh (GD QP-AN) khi đăng ký tốt nghiệp liên hệ ai?",
        ["kehoach", "quydinh", "stsv"],
    ),
    (
        "Sinh viên không tham gia BHYT quá bao nhiêu tháng sẽ bị gián đoạn thời gian tham gia BHYT 5 năm liên tục?",
        ["kehoach", "quydinh"],
    ),
    (
        "Thẻ BHYT của sinh viên hiện nay được xem trên ứng dụng nào?",
        ["kehoach", "stsv"],
    ),
    (
        "Kết quả học bổng Trần Đại Nghĩa học kỳ I năm học 2025-2026, có bao nhiêu sinh viên được học bổng toàn phần?",
        ["kehoach", "quydinh"],
    ),
    (
        "Sinh viên không hoàn thành học phí kỳ 1 năm học 2025-2026 sau đợt 2 sẽ bị xử lý như thế nào?",
        ["kehoach", "quydinh"],
    ),
    (
        "Sinh viên có thắc mắc về học phí kỳ 1 năm 2025-2026 liên hệ trực tiếp tại phòng nào hoặc số điện thoại nào?",
        ["kehoach", "stsv"],
    ),
    (
        "Trường hợp nào không được xét học bổng Gắn kết quê hương do vi phạm kỷ luật?",
        ["kehoach", "quydinh"],
    ),
    (
        "Gentherm thuộc tập đoàn nào và được niêm yết trên sàn chứng khoán nào?",
        ["kehoach"],
    ),
    (
        "Chương trình tham quan Gentherm Việt Nam dành cho đối tượng sinh viên nào?",
        ["kehoach"],
    ),
    (
        "Địa điểm nhà máy tham quan của ASSA ABLOY Việt Nam ở đâu?",
        ["kehoach"],
    ),
    (
        "Số lượng sinh viên tối đa được tham quan ASSA ABLOY Việt Nam mỗi đợt là bao nhiêu?",
        ["kehoach"],
    ),
    (
        "Công ty TNHH DENSO Việt Nam hoạt động trong lĩnh vực gì và trụ sở ở đâu?",
        ["kehoach"],
    ),
    (
        "Công ty TNHH Linh kiện điện tử SEI (Việt Nam) tọa lạc ở đâu và thuộc tập đoàn nào?",
        ["kehoach"],
    ),
    (
        "Phòng Thiết kế máy tại DAIZO TEC phù hợp với sinh viên ngành nào?",
        ["kehoach"],
    ),
    (
        "Phòng Thiết kế điện tại DAIZO TEC phù hợp với sinh viên ngành nào?",
        ["kehoach"],
    ),
    (
        "Hồ sơ đăng ký học bổng Gắn kết quê hương gồm những gì?",
        ["kehoach", "quydinh"],
    ),
    (
        "Công ty Cổ phần Phòng Thử Nghiệm Phúc Gia (PGL) được thành lập vào ngày tháng năm nào?",
        ["kehoach"],
    ),
    (
        "Học bổng Trần Đại Nghĩa học kỳ II 2025-2026 yêu cầu điểm học tập tối thiểu bao nhiêu và mức học bổng tối đa cho sinh viên nhóm a là bao nhiêu?",
        ["kehoach", "quydinh"],
    ),
    (
        "Sinh viên nhận BHYT năm 2026 cần cài ứng dụng nào để xem thẻ, và tại sao không còn phát hành thẻ giấy?",
        ["kehoach", "stsv"],
    ),
    (
        "Chương trình tham quan tuyển dụng Goertek Vina có chế độ bảo hiểm xã hội như thế nào và sinh viên được hưởng phúc lợi gì về nghỉ phép?",
        ["kehoach"],
    ),
    (
        "Sinh viên thuộc diện chế độ chính sách khi đóng học phí kỳ 2 năm 2025-2026 được miễn giảm như thế nào và thắc mắc về số tiền học phí liên hệ ai?",
        ["kehoach", "quydinh"],
    ),
    (
        "Sinh viên quan tâm đến Phòng Thiết kế kết cấu của DAIZO TEC cần học ngành gì và công việc chính là gì?",
        ["kehoach"],
    ),
    (
        "Tọa đàm về bạo lực giới ngày 11/12/2025 nhằm thực hiện công ước nào và tập trung trao quyền cho thanh niên như thế nào?",
        ["kehoach", "quydinh"],
    ),
    (
        "Chương trình tham quan Gentherm cung cấp thông tin gì cho sinh viên và sinh viên có thể nhận được cơ hội gì từ Gentherm?",
        ["kehoach"],
    ),
    (
        "Phòng Thiết kế sản xuất (PM) tại DAIZO TEC sử dụng công cụ nào và dựa trên kết quả từ phòng nào?",
        ["kehoach"],
    ),
    (
        "Sinh viên có thắc mắc về BHYT kỳ 1 năm 2025-2026 liên hệ ai và qua email nào?",
        ["kehoach", "stsv"],
    ),
    (
        "ASSA ABLOY Việt Nam chuyên sản xuất sản phẩm gì và thuộc tập đoàn nào?",
        ["kehoach"],
    ),
    (
        "Học bổng Trần Đại Nghĩa kỳ II 2025-2026 cần hồ sơ gì và đăng ký trực tuyến ở đâu?",
        ["kehoach", "stsv"],
    ),
    (
        "Chương trình Rorze Robotech thuộc tập đoàn nào và được thành lập năm nào?",
        ["kehoach"],
    ),
    (
        "ASSA ABLOY có bao nhiêu đồng nghiệp trên toàn thế giới và hoạt động tại bao nhiêu quốc gia?",
        ["kehoach"],
    ),
    (
        "Sinh viên nào thuộc diện học bổng Gắn kết quê hương nếu đề tài ĐATN không được thực hiện ở trong nước?",
        ["kehoach", "quydinh"],
    ),
    (
        "Học bổng MB The Best of MB Chasing 2025 dành cho trường nào tại Bách khoa?",
        ["kehoach"],
    ),
    (
        "Phòng Thiết kế trang thiết bị tại DAIZO TEC phụ trách thiết kế những gì trên tàu?",
        ["kehoach"],
    ),
    (
        "SEI Việt Nam (SEEV) là doanh nghiệp bao nhiêu phần trăm vốn nước ngoài?",
        ["kehoach"],
    ),
    (
        "Học bổng The Best of MB Chasing 2025 ưu tiên sinh viên tuyển dụng vào chương trình nào của MB và đăng ký ở đâu?",
        ["kehoach", "stsv"],
    ),
    (
        "Kết quả thi nội bộ có giá trị bao lâu?",
        ["quydinh"],
    ),
    (
        "Chứng chỉ dùng xét tốt nghiệp phải như thế nào?",
        ["quydinh"],
    ),
    (
        "Kết quả thi nội bộ dùng để làm gì?",
        ["quydinh"],
    ),
    (
        "Vai trò của chứng chỉ nội bộ trong xét đầu ra?",
        ["quydinh"],
    ),
    (
        "CNTT Việt-Nhật và ICT khác nhau thế nào?",
        ["ctdt"],
    ),
    (
        "Theo mục tiêu chung của chương trình Công nghệ thông tin Việt-Nhật (IT-E6), sinh viên tốt nghiệp cần đạt trình độ tiếng Nhật tối thiểu là bậc nào?",
        ["ctdt"],
    ),
    (
        "Chuẩn đầu ra 2.3.3 của chương trình Công nghệ thông tin Việt-Nhật (IT-E6) yêu cầu sinh viên đạt chứng chỉ tiếng Nhật nào?",
        ["ctdt"],
    ),
    (
        "Sau khi hoàn thành học phần JP1110 và JP1120 (Tiếng Nhật 1, 2) trong chương trình Công nghệ thông tin Việt-Nhật (IT-E6), sinh viên hướng tới mục tiêu đạt bao nhiêu điểm trong kỳ thi thử trực tuyến trình độ N5?",
        ["ctdt"],
    ),
    (
        "Học phần Tiếng Nhật 5 (JP2126) trong chương trình Công nghệ thông tin Việt-Nhật (IT-E6) đặt mục tiêu tỷ lệ sinh viên đỗ kỳ thi N3 là bao nhiêu phần trăm?",
        ["ctdt"],
    ),
    (
        "Theo mục tiêu chung của chương trình Công nghệ thông tin toàn cầu (IT-E7), sinh viên tốt nghiệp cần đạt trình độ ngoại ngữ tiếng Anh ở mức nào?",
        ["ctdt"],
    ),
    (
        "Chuẩn đầu ra 2.3.3 của chương trình Công nghệ thông tin toàn cầu (IT-E7) yêu cầu sinh viên đạt trình độ tiếng Anh tối thiểu là bao nhiêu điểm TOEIC?",
        ["ctdt"],
    ),
    (
        "Học phần IT2120 – Kiến thức máy tính trong chương trình Công nghệ thông tin toàn cầu (IT-E7) có tỷ lệ đánh giá như thế nào?",
        ["ctdt"],
    ),
    (
        "Lần cập nhật 02 của chương trình Công nghệ thông tin toàn cầu (IT-E7) ký ngày 22/2/2022 đã thay đổi điều kiện của học phần nào?",
        ["ctdt"],
    ),
    (
        "Trượt học phần tiếng Anh cơ bản phải làm gì?",
        ["ctdt", "quydinh", "stsv"],
    ),
    (
        "Chứng nhận nội bộ có hiệu lực bao lâu?",
        ["quydinh"],
    ),
    (
        "Mối liên hệ giữa chuẩn đầu ra và đồ án?",
        ["ctdt", "quydinh"],
    ),
    (
        "Kết quả đánh giá điểm rèn luyện được công bố công khai trước bao nhiêu ngày trước khi ban hành quyết định chính thức?",
        ["kehoach", "quydinh"],
    ),
    (
        "Hệ thống sổ tay công tác sinh viên online hỗ trợ những chức năng gì trong việc đánh giá điểm rèn luyện tại Bách khoa?",
        ["kehoach", "quydinh"],
    ),
    (
        "Sinh viên Bách khoa thắc mắc về điểm học phần chưa được nhập gửi đến email nào trước tiên?",
        ["kehoach", "stsv"],
    ),
    (
        "Sinh viên Bách khoa bị giới hạn tín chỉ đăng ký do cảnh báo học tập hoặc do ngoại ngữ liên hệ ai?",
        ["quydinh", "stsv"],
    ),
    (
        "Sinh viên Bách khoa muốn tiếp nhận trở lại học sau khi nghỉ dài hạn cần nộp đơn trước bao lâu so với đầu học kỳ?",
        ["kehoach", "stsv"],
    ),
    (
        "Sinh viên Bách khoa đăng ký thi bù do hoãn thi cuối kỳ cần đăng ký muộn nhất bao nhiêu ngày trước ngày thi?",
        ["kehoach", "quydinh", "stsv"],
    ),
    (
        "Giấy chứng nhận tốt nghiệp tạm thời tại Bách khoa chỉ có thể cấp trong thời điểm nào?",
        ["kehoach", "stsv"],
    ),
    (
        "Sinh viên K70 Trường CNTT&TT (chương trình IT1) nộp hồ sơ nhập học vào khung giờ nào ngày nào?",
        ["kehoach", "stsv"],
    ),
    (
        "Sinh viên K70 Trường Điện – Điện tử (chương trình EE1, EE2) nộp hồ sơ nhập học vào khung giờ nào?",
        ["kehoach", "stsv"],
    ),
    (
        "Sinh viên K70 mới nhập học Bách khoa đóng BHYT trong bao nhiêu tháng và số tiền là bao nhiêu?",
        ["kehoach", "quydinh", "stsv"],
    ),
    (
        "Sinh viên Bách khoa mua BHYT bổ sung theo đợt 1 năm 2026 vào thời gian nào và thẻ có hiệu lực từ khi nào?",
        ["kehoach", "stsv"],
    ),
    (
        "Mã số BHYT của sinh viên Bách khoa được cấu trúc như thế nào?",
        ["quydinh", "stsv"],
    ),
    (
        "Lịch nộp Sổ đoàn cho Ban chấp hành Chi đoàn K70 tại Bách khoa dự kiến vào thời gian nào?",
        ["kehoach", "stsv"],
    ),
    (
        "Sinh viên Bách khoa thuộc đối tượng nào được vay vốn theo Quyết định 157/QĐ-TTg?",
        ["quydinh", "stsv"],
    ),
    (
        "Sinh viên ngành kỹ thuật (STEM) Bách khoa muốn vay vốn theo QĐ 29/2025/QĐ-TTg đăng ký trên hệ thống nào?",
        ["kehoach", "stsv"],
    ),
    (
        "Sinh viên Bách khoa thuộc đối tượng STEM để đủ điều kiện vay vốn, sinh viên năm thứ nhất cần đáp ứng điều kiện gì về học lực THPT?",
        ["quydinh", "stsv"],
    ),
    (
        "Hồ sơ nộp chậm nhất trong bao nhiêu tuần đầu học kỳ để được xét miễn giảm học phí tại Bách khoa?",
        ["kehoach", "stsv"],
    ),
    (
        "Mức giảm học phí của sinh viên thuộc đối tượng 7 (dân tộc thiểu số ở thôn/bản đặc biệt khó khăn) tại Bách khoa là bao nhiêu?",
        ["quydinh", "stsv"],
    ),
    (
        "Mức hỗ trợ chi phí học tập hàng tháng cho sinh viên dân tộc thiểu số hộ nghèo tại Bách khoa là bao nhiêu?",
        ["quydinh", "stsv"],
    ),
    (
        "Mức trợ cấp xã hội hàng tháng của sinh viên dân tộc ít người ở vùng cao tại Bách khoa là bao nhiêu?",
        ["quydinh", "stsv"],
    ),
    (
        "Tuần định hướng tân sinh viên K70 có bắt buộc không và sinh viên học trực tiếp mấy buổi?",
        ["kehoach", "quydinh", "stsv"],
    ),
    (
        "Buổi 1 sinh hoạt công dân đầu khóa K70 diễn ra vào ngày nào, giờ nào và nội dung gì?",
        ["kehoach", "stsv"],
    ),
    (
        "Để không bị xếp loại rèn luyện Yếu/Kém tại Bách khoa, sinh viên có GPA 1.5 cần đạt bao nhiêu điểm từ tiêu chí học tập?",
        ["quydinh", "stsv"],
    ),
    (
        "Sinh viên Bách khoa tải thủ công nhiều tệp từ OneDrive về máy tính được phép tải tối đa bao nhiêu mục mỗi lần?",
        ["quydinh", "stsv"],
    ),
    (
        "Điều kiện để sinh viên Bách khoa được kết nạp vào Đảng là gì?",
        ["stsv"],
    ),
    (
        "Đảng bộ Đại học Bách khoa Hà Nội có bao nhiêu chi bộ sinh viên?",
        ["stsv"],
    ),
    (
        "Chi bộ sinh viên Bách khoa họp định kỳ như thế nào?",
        ["stsv"],
    ),
    (
        "Đảng viên sinh viên Khoa Vật lý Kỹ thuật sinh hoạt tại Chi bộ sinh viên nào ở Bách khoa?",
        ["stsv"],
    ),
    (
        "Theo bảo hiểm thân thể tự nguyện K70 tại Bách khoa, tử vong do tai nạn được bảo hiểm chi trả bao nhiêu tiền?",
        ["quydinh", "stsv"],
    ),
    (
        "Sinh viên là con liệt sỹ, thương binh hoặc mồ côi cả cha lẫn mẹ có được bảo hiểm thân thể miễn phí không?",
        ["quydinh", "stsv"],
    ),
    (
        "Mục tiêu học tập tối thiểu được đề xuất cho sinh viên năm nhất Bách khoa trong kỳ học đầu tiên là bao nhiêu GPA?",
        ["quydinh", "stsv"],
    ),
    (
        "Sinh viên Bách khoa phúc tra điểm học phần cần thực hiện theo trình tự nào?",
        ["quydinh", "stsv"],
    ),
    (
        "Sinh viên Bách khoa cần thắc mắc về thời khóa biểu liên hệ email nào?",
        ["kehoach", "stsv"],
    ),
    (
        "Sinh viên muốn miễn học phần ngoại ngữ tại Bách khoa cần điều kiện gì về chứng chỉ thi ngoài trường?",
        ["quydinh", "stsv"],
    ),
    (
        "Sinh viên Bách khoa muốn đạt điểm rèn luyện loại Khá (65 điểm) với GPA 1.5, ngoài 28 điểm từ tiêu chí học tập, cần thêm gì?",
        ["quydinh", "stsv"],
    ),
    (
        "Sinh viên dân tộc thiểu số rất ít người ở Bách khoa được hưởng những quyền lợi tài chính gì (miễn, hỗ trợ)?",
        ["quydinh", "stsv"],
    ),
    (
        "Sinh viên Bách khoa muốn xin nghỉ học dài hạn (bảo lưu), nếu thuộc chương trình hợp tác với ĐH TROY thì quy trình có gì khác?",
        ["quydinh", "stsv"],
    ),
    (
        "Sinh viên STEM (ngành Cơ khí, Điện-Điện tử...) năm thứ nhất muốn vay vốn theo QĐ 29/2025 cần thỏa mãn điều kiện gì và đăng ký như thế nào?",
        ["quydinh", "stsv"],
    ),
    (
        "Tuần định hướng K70 tại Bách khoa có nội dung nào liên quan đến học tập và công nghệ thông tin?",
        ["kehoach", "stsv"],
    ),
    (
        "Sinh viên Bách khoa muốn đạt điểm rèn luyện Khá (65 điểm) trong học kỳ dù GPA chỉ 1.5, cần đạt điểm cụ thể ở từng nhóm tiêu chí như thế nào?",
        ["quydinh", "stsv"],
    ),
    (
        "Sinh viên mồ côi cả cha lẫn mẹ tại Bách khoa được hưởng những chính sách tài chính nào và mức hỗ trợ cụ thể?",
        ["quydinh", "stsv"],
    ),
    (
        "Sinh viên Bách khoa Trường Hóa và Khoa học sự sống (chương trình CH1, CH2, CH-E11) học buổi định hướng nào trực tiếp tại Hội trường C2?",
        ["ctdt", "stsv"],
    ),
    (
        "Cơ sở vật chất nào được trang bị cho sinh viên khuyết tật di chuyển trong khuôn viên Đại học Bách khoa Hà Nội?",
        ["quydinh", "stsv"],
    ),
    (
        "Phòng Công tác sinh viên cập nhật thông tin người học khuyết tật cho các đơn vị liên quan trong thời hạn bao lâu sau khi sinh viên trúng tuyển và hoàn tất thủ tục nhập học?",
        ["kehoach", "quydinh"],
    ),
    (
        "Phòng Công tác sinh viên phối hợp với đơn vị nào để tìm kiếm nguồn tài trợ và học bổng cho sinh viên khuyết tật?",
        ["quydinh", "stsv"],
    ),
    (
        "Phòng Công tác sinh viên hỗ trợ sinh viên khuyết tật như thế nào khi họ gặp vấn đề về tâm lý xã hội?",
        ["quydinh", "stsv"],
    ),
    (
        "Phòng Truyền thông và Quản trị thương hiệu tại Bách khoa có hoạt động gì để hỗ trợ tinh thần sinh viên khuyết tật?",
        ["quydinh", "stsv"],
    ),
    (
        "Phòng Cơ sở vật chất tại Bách khoa Hà Nội có vai trò gì trong hỗ trợ sinh viên khuyết tật?",
        ["quydinh", "stsv"],
    ),
    (
        "Sinh viên khuyết tật gặp vấn đề sức khỏe tâm thần tại Bách khoa Hà Nội có thể được hỗ trợ qua những kênh nào?",
        ["quydinh", "stsv"],
    ),
    (
        "Lưu học sinh trao đổi tại Bách khoa Hà Nội đăng ký thông tin cư trú với đơn vị nào?",
        ["quydinh", "stsv"],
    ),
    (
        "Lưu học sinh cần cấp, gia hạn hoặc thay đổi thị thực nhập cảnh gửi hồ sơ đến đơn vị nào tại Bách khoa?",
        ["quydinh", "stsv"],
    ),
    (
        "Lưu học sinh trao đổi đến Bách khoa Hà Nội cần nộp hồ sơ gồm những gì và đơn vị nào tiếp nhận và quản lý hồ sơ đó?",
        ["quydinh", "stsv"],
    ),
    (
        "Lưu học sinh đại học tại Bách khoa gặp vấn đề về học tập được hỗ trợ qua những kênh nào?",
        ["quydinh", "stsv"],
    ),
    (
        "Quyết định 1791/QĐ-ĐHBK-ĐT về tổ chức thi trực tuyến tại Bách khoa Hà Nội được ban hành vào ngày tháng năm nào?",
        ["quydinh"],
    ),
    (
        "Hệ thống thi trực tuyến tại Bách khoa Hà Nội bao gồm những phần mềm nào?",
        ["quydinh"],
    ),
    (
        "Có bao nhiêu hình thức thi trực tuyến được áp dụng tại Bách khoa Hà Nội và tên gọi của từng hình thức?",
        ["quydinh"],
    ),
    (
        "Đối với học phần có nhiều lớp và số lượng sinh viên lớn, hình thức thi trực tuyến nào được ưu tiên tại Bách khoa?",
        ["quydinh"],
    ),
    (
        "Khi thi tự luận trực tuyến tại Bách khoa, sinh viên nộp bài bằng cách nào và trong bao nhiêu phút sau hết giờ?",
        ["quydinh"],
    ),
    (
        "Sinh viên dự thi trực tuyến tại Bách khoa cần đăng nhập bằng tài khoản gì và cần xuất trình giấy tờ nào?",
        ["quydinh"],
    ),
    (
        "Thời gian thi tự luận trực tuyến tại Bách khoa là trong khoảng bao nhiêu phút?",
        ["quydinh"],
    ),
    (
        "Thời gian thi trắc nghiệm trực tuyến tại Bách khoa là trong khoảng bao nhiêu phút?",
        ["quydinh"],
    ),
    (
        "Thời gian thi vấn đáp trực tuyến tối thiểu cho mỗi sinh viên tại Bách khoa là bao nhiêu phút?",
        ["quydinh"],
    ),
    (
        "Bài tập lớn/tiểu luận để thi vấn đáp kết hợp phải nộp trước lịch thi học phần bao nhiêu ngày?",
        ["kehoach", "quydinh"],
    ),
    (
        "Trong quy trình thi tự luận trực tuyến tại Bách khoa, CBCT cần có mặt trong phòng thi trực tuyến trước giờ thi bao lâu?",
        ["quydinh"],
    ),
    (
        "Trong thi trắc nghiệm trực tuyến tại Bách khoa, CBCT và sinh viên cần có mặt trong phòng thi trực tuyến trước bao lâu?",
        ["quydinh"],
    ),
    (
        "So sánh thời gian phải có mặt trước buổi thi trực tuyến giữa hình thức thi tự luận/vấn đáp và thi trắc nghiệm/ngoại ngữ tại Bách khoa?",
        ["quydinh"],
    ),
    (
        "Sinh viên thi trắc nghiệm trực tuyến tại Bách khoa đăng nhập vào hệ thống thi bằng tài khoản gì và nhận mật khẩu bài thi từ ai?",
        ["quydinh"],
    ),
    (
        "Để thi vấn đáp trực tuyến tại Bách khoa, sinh viên chuẩn bị câu trả lời trong bao lâu và phải nộp gì trước khi bước vào phần hỏi-đáp?",
        ["quydinh"],
    ),
    (
        "Điểm thi vấn đáp trực tuyến tại Bách khoa được thông báo cho sinh viên vào thời điểm nào, khác gì so với thi tự luận?",
        ["quydinh"],
    ),
    (
        "Phòng Đào tạo và bộ môn có phân công lập lịch thi trực tuyến ra sao đối với các hình thức thi khác nhau tại Bách khoa?",
        ["quydinh"],
    ),
    (
        "Bài thi tự luận và bài thi trắc nghiệm trực tuyến tại Bách khoa được lưu trữ ở đâu và trong bao lâu?",
        ["quydinh"],
    ),
    (
        "Kết thúc kíp thi ngoại ngữ trực tuyến tại Bách khoa, CBCT phải thực hiện những công việc gì?",
        ["quydinh"],
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
