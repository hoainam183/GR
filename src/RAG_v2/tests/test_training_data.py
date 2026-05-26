from __future__ import annotations


def test_rerun_incorrect_quydinh_boundaries_are_training_examples() -> None:
    from query.training_data import LABEL_QUYDINH, get_training_data

    labels_by_query = {query: labels for query, labels in get_training_data()}
    expected_quydinh = [
        "Khi nào sinh viên được đăng ký học chương trình thứ hai?",
        "Khi học ngành 2, nếu kết quả ngành 1 kém thì sao?",
        "Sinh viên đang cảnh báo mức 3 có được hạ mức không?",
        "Khi nào học viên thạc sĩ đăng ký đề tài luận văn?",
        "Có được thay đổi đề tài luận văn thạc sĩ không?",
        "Chuẩn đầu ra ngoại ngữ của thạc sĩ là bậc mấy?",
        "Nghiên cứu sinh cần hoàn thành bao nhiêu chuyên đề tiến sĩ?",
        "ĐHBK Hà Nội áp dụng mấy học kỳ chính trong năm?",
        "Sinh viên bị cảnh báo học tập mức 2 nếu có kết quả như thế nào?",
        "Khi nào sinh viên được hạ mức cảnh báo học tập?",
    ]

    for query in expected_quydinh:
        assert labels_by_query.get(query) == [LABEL_QUYDINH]
