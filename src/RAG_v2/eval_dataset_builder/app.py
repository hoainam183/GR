"""
RAG Evaluation Dataset Builder — Streamlit App.

Giao diện end-to-end cho flow:
1. Sidebar: cấu hình retrieval (Qdrant connection, collections, top_k, embedding model)
2. Main: nhập query → retrieve chunks → annotate (tick relevant, metadata)
3. Bottom: review annotations, preview CSV, export/download

Usage:
    cd d:\\GR\\src\\RAG_v2
    streamlit run eval_dataset_builder/app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure RAG_v2 root is importable
_RAG_V2_ROOT = str(Path(__file__).resolve().parent.parent)
if _RAG_V2_ROOT not in sys.path:
    sys.path.insert(0, _RAG_V2_ROOT)

import streamlit as st

from eval_dataset_builder.annotation.annotator import AnnotationSession
from eval_dataset_builder.config.retrieval_config import RetrievalConfigManager
from eval_dataset_builder.export.csv_exporter import CSVExporter
from eval_dataset_builder.models.schemas import (
    Difficulty,
    EmbeddingModel,
    QueryType,
    RetrievalConfig,
)
from eval_dataset_builder.retrieval.chunk_retriever import ChunkRetriever

# ======================================================================
# Page Config
# ======================================================================

st.set_page_config(
    page_title="RAG Eval Dataset Builder",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ======================================================================
# Session State Initialization
# ======================================================================


def init_session_state():
    """Initialize all session state variables."""
    if "qdrant_connected" not in st.session_state:
        st.session_state.qdrant_connected = False
    if "config_manager" not in st.session_state:
        st.session_state.config_manager = None
    if "retriever" not in st.session_state:
        st.session_state.retriever = None
    if "annotation_session" not in st.session_state:
        st.session_state.annotation_session = AnnotationSession()
    if "retrieved_chunks" not in st.session_state:
        st.session_state.retrieved_chunks = []
    if "current_query" not in st.session_state:
        st.session_state.current_query = ""
    if "config_set" not in st.session_state:
        st.session_state.config_set = False
    if "current_config" not in st.session_state:
        st.session_state.current_config = None
    if "editing_index" not in st.session_state:
        st.session_state.editing_index = None
    if "query_queue" not in st.session_state:
        st.session_state.query_queue = []
    if "query_queue_index" not in st.session_state:
        st.session_state.query_queue_index = 0
    if "current_expected_answer" not in st.session_state:
        st.session_state.current_expected_answer = ""
    if "last_imported_file_id" not in st.session_state:
        st.session_state.last_imported_file_id = None


init_session_state()

# ======================================================================
# SIDEBAR — Phase 1: Retrieval Config
# ======================================================================

with st.sidebar:
    st.header("⚙️ Cấu hình Retrieval")

    # -- Qdrant Connection --
    st.subheader("1. Kết nối Qdrant & Elasticsearch")
    col1, col2 = st.columns([3, 1])
    with col1:
        qdrant_host = st.text_input(
            "Qdrant Host", value="localhost", key="qdrant_host"
        )
    with col2:
        qdrant_port = st.number_input(
            "Port", value=6333, min_value=1, key="qdrant_port"
        )

    col3, col4 = st.columns([3, 1])
    with col3:
        es_host = st.text_input("ES Host", value="localhost", key="es_host")
    with col4:
        es_port = st.number_input(
            "ES Port", value=9200, min_value=1, key="es_port"
        )

    if st.button("🔌 Kết nối", use_container_width=True):
        try:
            manager = RetrievalConfigManager(
                qdrant_host=qdrant_host,
                qdrant_port=int(qdrant_port),
            )
            collections = manager.list_collections()
            st.session_state.config_manager = manager
            st.session_state.retriever = ChunkRetriever(
                qdrant_host=qdrant_host,
                qdrant_port=int(qdrant_port),
                es_host=es_host,
                es_port=int(es_port),
            )
            st.session_state.qdrant_connected = True
            st.success(
                f"✅ Đã kết nối! Tìm thấy {len(collections)} collections."
            )
        except Exception as e:
            st.error(f"❌ Lỗi kết nối: {e}")
            st.session_state.qdrant_connected = False

    # -- Collection & Config --
    if st.session_state.qdrant_connected and st.session_state.config_manager:
        manager: RetrievalConfigManager = st.session_state.config_manager

        st.divider()
        st.subheader("2. Chọn Collection & Config")

        collections = manager.list_collections()
        if not collections:
            st.warning("Không có collection nào trong Qdrant.")
        else:
            # Collection info
            selected_collections = st.multiselect(
                "Chọn Collection(s)",
                options=collections,
                default=collections[:1] if collections else [],
                key="selected_collections",
            )

            # Hiển thị info cho collection đã chọn
            if selected_collections:
                with st.expander("📋 Thông tin Collections", expanded=False):
                    for col_name in selected_collections:
                        try:
                            info = manager.get_collection_info(col_name)
                            st.markdown(
                                f"**{col_name}**: "
                                f"`{info['points_count']}` points, "
                                f"vectors: `{list(info['vectors_config'].keys())}`"
                            )
                        except Exception as e:
                            st.warning(f"{col_name}: {e}")

            # Top K
            top_k = st.number_input(
                "Top K (số chunks retrieve)",
                min_value=1,
                max_value=100,
                value=10,
                key="top_k",
            )

            # Embedding model
            embedding_model = st.selectbox(
                "Embedding Model",
                options=[e.value for e in EmbeddingModel],
                format_func=lambda x: {
                    "e5": "🔵 E5 Multilingual",
                    "bge_m3": "🟢 BGE-M3",
                    "hybrid": "🟡 Hybrid (Vector + Keyword)",
                }[x],
                key="embedding_model",
            )

            # -- Hybrid Search Config (chỉ hiện khi chọn hybrid) --
            hybrid_params = {}
            if embedding_model == "hybrid":
                with st.expander("🔧 Hybrid Search Config", expanded=True):
                    h_col1, h_col2 = st.columns(2)
                    with h_col1:
                        hybrid_params["vector_weight"] = st.number_input(
                            "Vector Weight",
                            min_value=0.0,
                            max_value=2.0,
                            value=1.0,
                            step=0.1,
                            key="vector_weight",
                        )
                    with h_col2:
                        hybrid_params["keyword_weight"] = st.number_input(
                            "Keyword Weight",
                            min_value=0.0,
                            max_value=2.0,
                            value=0.0,
                            step=0.1,
                            key="keyword_weight",
                        )

                    h_col3, h_col4 = st.columns(2)
                    with h_col3:
                        hybrid_params["vector_top_k"] = st.number_input(
                            "Vector Top K (per collection)",
                            min_value=1,
                            max_value=100,
                            value=20,
                            key="vector_top_k",
                        )
                    with h_col4:
                        hybrid_params["keyword_top_k"] = st.number_input(
                            "Keyword Top K (per collection)",
                            min_value=1,
                            max_value=100,
                            value=20,
                            key="keyword_top_k",
                        )

                    h_col5, h_col6 = st.columns(2)
                    with h_col5:
                        hybrid_params["vector_pool_k"] = st.number_input(
                            "Vector Pool K (global)",
                            min_value=1,
                            max_value=100,
                            value=15,
                            key="vector_pool_k",
                        )
                    with h_col6:
                        hybrid_params["keyword_pool_k"] = st.number_input(
                            "Keyword Pool K (global)",
                            min_value=1,
                            max_value=100,
                            value=15,
                            key="keyword_pool_k",
                        )

            # Set config button
            if st.button("✅ Áp dụng Config", use_container_width=True):
                if not selected_collections:
                    st.error("Phải chọn ít nhất 1 collection!")
                else:
                    try:
                        config = manager.set_config(
                            collections=selected_collections,
                            top_k=top_k,
                            embedding_model=EmbeddingModel(embedding_model),
                            **hybrid_params,
                        )
                        st.session_state.config_set = True
                        st.session_state.current_config = config
                        st.success(
                            f"✅ Config đã áp dụng!\n\n"
                            f"Collections: {config.collections}\n\n"
                            f"Top K: {config.top_k}\n\n"
                            f"Label: {config.config_label()}"
                        )
                    except Exception as e:
                        st.error(f"❌ Lỗi config: {e}")

    # -- Progress --
    st.divider()
    st.subheader("📊 Tiến độ")
    session: AnnotationSession = st.session_state.annotation_session
    progress = session.get_progress_summary()

    col_a, col_b = st.columns(2)
    col_a.metric("Queries", progress["total_queries"])
    col_b.metric("Relevant Chunks", progress["total_relevant_chunks"])

    if progress["queries_by_type"]:
        st.caption("**Theo loại:**")
        for qt, count in progress["queries_by_type"].items():
            st.caption(f"  • {qt}: {count}")
    if progress["queries_by_difficulty"]:
        st.caption("**Theo độ khó:**")
        for diff, count in progress["queries_by_difficulty"].items():
            st.caption(f"  • {diff}: {count}")

# ======================================================================
# MAIN AREA
# ======================================================================

st.title("📊 RAG Evaluation Dataset Builder")
st.caption("Xây dựng ground truth dataset để đánh giá hệ thống RAG")

if not st.session_state.qdrant_connected:
    st.info("👈 Vui lòng kết nối Qdrant ở sidebar trước.")
    st.stop()

if not st.session_state.config_set:
    st.info("👈 Vui lòng chọn collection và áp dụng config ở sidebar trước.")
    st.stop()

# ======================================================================
# TAB Layout
# ======================================================================

tab_annotate, tab_review, tab_export = st.tabs(
    [
        "📝 Annotate",
        "🔍 Review & Edit",
        "📤 Export CSV",
    ]
)

# ======================================================================
# TAB 1 — Annotate (Phase 2 + 3)
# ======================================================================

with tab_annotate:
    st.subheader("Bước 1: Nhập Query & Retrieve")

    config: RetrievalConfig = st.session_state.current_config

    # Hiển thị config hiện tại
    st.info(
        f"**Config:** collections=`{config.collections}`, "
        f"top_k=`{config.top_k}`, model=`{config.embedding_model.value}`"
    )

    # ── JSON Query Queue Import ──────────────────────────────────────
    with st.expander(
        "📂 Import danh sách câu hỏi từ JSON",
        expanded=bool(st.session_state.query_queue),
    ):
        import json as _json

        st.caption(
            'File JSON phải là mảng chuỗi `["câu hỏi 1", ...]` '
            'hoặc mảng object `[{"query": "...", "expected_output": "..."}]`. '
            "**Trường `expected_output` sẽ tự động điền vào Expected Answer.**"
        )
        uploaded_queries = st.file_uploader(
            "Chọn file JSON",
            type=["json"],
            key="upload_query_json",
            label_visibility="collapsed",
        )
        if (
            uploaded_queries is not None
            and uploaded_queries.file_id
            != st.session_state.last_imported_file_id
        ):
            try:
                raw = _json.loads(uploaded_queries.read().decode("utf-8"))
                if not isinstance(raw, list):
                    st.error("❌ File JSON phải là một mảng (array).")
                else:
                    parsed: list[dict] = []
                    for item in raw:
                        if isinstance(item, str):
                            q = item.strip()
                            if q:
                                parsed.append({"query": q})
                        elif isinstance(item, dict):
                            q = (
                                item.get("query") or item.get("question") or ""
                            ).strip()
                            if q:
                                entry = {"query": q}
                                ea = (
                                    item.get("expected_output")
                                    or item.get("expected_answer")
                                    or ""
                                ).strip()
                                if ea:
                                    entry["expected_output"] = ea
                                parsed.append(entry)
                    if not parsed:
                        st.error(
                            "❌ Không tìm thấy câu hỏi nào hợp lệ trong file."
                        )
                    else:
                        has_ea = sum(
                            1 for p in parsed if p.get("expected_output")
                        )
                        st.session_state.query_queue = parsed
                        st.session_state.query_queue_index = 0
                        st.session_state.last_imported_file_id = (
                            uploaded_queries.file_id
                        )
                        st.success(
                            f"✅ Đã import {len(parsed)} câu hỏi"
                            + (
                                f" ({has_ea} có expected_output)"
                                if has_ea
                                else ""
                            )
                            + "."
                        )
            except Exception as _e:
                st.error(f"❌ Lỗi đọc file JSON: {_e}")

        if st.session_state.query_queue:
            queue = st.session_state.query_queue
            idx = st.session_state.query_queue_index
            total = len(queue)

            st.markdown(
                f"**Queue:** {idx}/{total} đã xử lý — còn {total - idx} câu hỏi"
            )
            st.progress(idx / total if total else 0)

            # Hiện danh sách queries còn lại
            remaining = queue[idx:]
            if remaining:
                with st.expander(
                    f"📋 Danh sách {len(remaining)} câu hỏi chưa xử lý",
                    expanded=False,
                ):
                    for j, item in enumerate(remaining):
                        q_text = (
                            item["query"] if isinstance(item, dict) else item
                        )
                        has_ea = isinstance(item, dict) and bool(
                            item.get("expected_output")
                        )
                        st.markdown(
                            f"{idx + j + 1}. {q_text}"
                            + (" ✍️" if has_ea else "")
                        )

            def _q_text(item) -> str:
                return item["query"] if isinstance(item, dict) else item

            def _q_ea(item) -> str:
                return (
                    item.get("expected_output", "")
                    if isinstance(item, dict)
                    else ""
                )

            col_q1, col_q2, col_q3 = st.columns([2, 1, 1])
            with col_q1:
                if idx < total:
                    next_item = queue[idx]
                    st.info(
                        f"🔜 **Câu tiếp theo ({idx+1}/{total}):** {_q_text(next_item)}"
                        + (
                            " ✍️ *có expected answer*"
                            if _q_ea(next_item)
                            else ""
                        )
                    )
                else:
                    st.success("✅ Đã xử lý hết tất cả câu hỏi trong queue!")
            with col_q2:
                if idx < total and st.button(
                    "⏩ Load câu tiếp theo", use_container_width=True
                ):
                    next_item = queue[idx]
                    next_query = _q_text(next_item)
                    with st.spinner(f"Đang retrieve cho: {next_query[:50]}..."):
                        try:
                            retriever: ChunkRetriever = (
                                st.session_state.retriever
                            )
                            chunks = retriever.retrieve(
                                query=next_query, config=config
                            )
                            st.session_state.retrieved_chunks = chunks
                            st.session_state.current_query = next_query
                            st.session_state.current_expected_answer = _q_ea(
                                next_item
                            )
                            st.session_state.query_queue_index = idx + 1
                            st.success(f"✅ Tìm thấy {len(chunks)} chunks!")
                            st.rerun()
                        except Exception as _e:
                            st.error(f"❌ Lỗi retrieve: {_e}")
            with col_q3:
                if st.button(
                    "🗑️ Xóa Queue", use_container_width=True, type="secondary"
                ):
                    st.session_state.query_queue = []
                    st.session_state.query_queue_index = 0
                    st.session_state.current_expected_answer = ""
                    st.rerun()

    st.divider()

    # Query input (thủ công)
    query = st.text_area(
        "Nhập câu hỏi (hoặc dùng queue ở trên)",
        placeholder="Ví dụ: Điều kiện xét học bổng là gì?",
        key="query_input",
        value=(
            st.session_state.current_query
            if st.session_state.retrieved_chunks
            else ""
        ),
        height=80,
    )

    retrieve_btn = st.button("🔍 Retrieve Chunks", use_container_width=True)

    if retrieve_btn and query.strip():
        with st.spinner("Đang retrieve chunks..."):
            try:
                retriever: ChunkRetriever = st.session_state.retriever
                chunks = retriever.retrieve(query=query.strip(), config=config)
                st.session_state.retrieved_chunks = chunks
                st.session_state.current_query = query.strip()
                st.success(f"✅ Tìm thấy {len(chunks)} chunks!")
            except Exception as e:
                st.error(f"❌ Lỗi retrieve: {e}")
                st.session_state.retrieved_chunks = []
    elif retrieve_btn:
        st.warning("Vui lòng nhập câu hỏi trước khi retrieve.")

    # ----- Hiển thị Chunks + Annotation Form -----
    chunks = st.session_state.retrieved_chunks
    if chunks:
        st.divider()
        st.subheader(f"Bước 2: Review & Annotate ({len(chunks)} chunks)")
        st.markdown(f"**Query:** `{st.session_state.current_query}`")

        # Checkboxes for relevant chunks
        st.markdown("✅ **Tick chunks relevant:**")
        selected_chunk_ids = []

        for i, chunk in enumerate(chunks):
            with st.expander(
                f"#{i+1} | Score: {chunk.score:.4f} | ID: {chunk.chunk_id[:12]}... | "
                f"Collection: {chunk.collection}",
                expanded=i < 3,  # Mở 3 chunks đầu
            ):
                # Checkbox
                is_relevant = st.checkbox(
                    f"✅ Relevant",
                    key=f"chunk_relevant_{i}",
                    value=False,
                )
                if is_relevant:
                    selected_chunk_ids.append(chunk.chunk_id)

                # Chunk content
                st.markdown("**Nội dung:**")
                st.text_area(
                    "Text",
                    value=chunk.text,
                    height=150,
                    disabled=True,
                    key=f"chunk_text_{i}",
                    label_visibility="collapsed",
                )

                # Metadata
                if chunk.metadata:
                    st.markdown("**Metadata:**")
                    st.json(chunk.metadata)

        # ----- Annotation Metadata -----
        st.divider()
        st.subheader("Bước 3: Điền Metadata")

        col1, col2 = st.columns(2)
        with col1:
            query_type = st.selectbox(
                "📝 Query Type",
                options=[qt.value for qt in QueryType],
                key="query_type",
            )
        with col2:
            difficulty = st.radio(
                "📊 Difficulty",
                options=[d.value for d in Difficulty],
                horizontal=True,
                key="difficulty",
            )

        expected_answer = st.text_area(
            "💬 Expected Answer (optional)",
            placeholder="Để trống nếu chưa có câu trả lời tham chiếu...",
            key="expected_answer",
            value=st.session_state.current_expected_answer,
            height=120,
        )

        # ----- Save Button -----
        st.divider()
        save_col1, save_col2 = st.columns([3, 1])
        with save_col1:
            st.markdown(
                f"**Selected:** {len(selected_chunk_ids)} relevant chunk(s) "
                f"from {len(chunks)} retrieved"
            )
        with save_col2:
            save_btn = st.button(
                "💾 Lưu Annotation",
                use_container_width=True,
                type="primary",
            )

        if save_btn:
            if not selected_chunk_ids:
                st.error("❌ Phải tick ít nhất 1 chunk relevant!")
            else:
                try:
                    session: AnnotationSession = (
                        st.session_state.annotation_session
                    )
                    annotation = session.add_annotation(
                        query=st.session_state.current_query,
                        query_type=QueryType(query_type),
                        difficulty=Difficulty(difficulty),
                        relevant_doc_ids=selected_chunk_ids,
                        retrieved_chunks=chunks,
                        config=config,
                        expected_answer=(
                            expected_answer.strip()
                            if expected_answer.strip()
                            else None
                        ),
                    )
                    st.success(
                        f"✅ Đã lưu annotation #{session.count}!\n\n"
                        f"ID: `{annotation.id}`\n\n"
                        f"Relevant chunks: {len(selected_chunk_ids)}"
                    )
                    # Clear state for next query
                    st.session_state.retrieved_chunks = []
                    st.session_state.current_query = ""
                    st.session_state.current_expected_answer = ""
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Lỗi lưu: {e}")

# ======================================================================
# TAB 2 — Review & Edit (Phase 3 continued)
# ======================================================================

with tab_review:
    session: AnnotationSession = st.session_state.annotation_session
    st.subheader(f"📋 Annotations ({session.count})")

    if session.count == 0:
        st.info(
            "Chưa có annotation nào. Hãy annotate queries ở tab 📝 Annotate."
        )
    else:
        for i, aq in enumerate(session.annotations):
            with st.expander(
                f"#{i+1} | {aq.query[:60]}{'...' if len(aq.query)>60 else ''}"
                f" | {aq.query_type.value} | {aq.difficulty.value}"
                f" | {len(aq.relevant_doc_ids)} relevant",
                expanded=False,
            ):
                st.markdown(f"**ID:** `{aq.id}`")
                st.markdown(f"**Query:** {aq.query}")

                col1, col2, col3 = st.columns(3)
                col1.markdown(f"**Type:** {aq.query_type.value}")
                col2.markdown(f"**Difficulty:** {aq.difficulty.value}")
                col3.markdown(
                    f"**Relevant:** {len(aq.relevant_doc_ids)} chunks"
                )

                if aq.expected_answer:
                    st.markdown(f"**Expected Answer:** {aq.expected_answer}")

                st.markdown(
                    f"**Config:** top_k={aq.config.top_k}, model={aq.config.embedding_model.value}"
                )

                # Relevant chunk IDs
                st.markdown("**Relevant Doc IDs:**")
                st.code(str(aq.relevant_doc_ids))

                # Edit form
                st.markdown("---")
                st.markdown("**✏️ Chỉnh sửa:**")

                edit_col1, edit_col2 = st.columns(2)
                with edit_col1:
                    new_type = st.selectbox(
                        "Query Type",
                        options=[qt.value for qt in QueryType],
                        index=[qt.value for qt in QueryType].index(
                            aq.query_type.value
                        ),
                        key=f"edit_type_{i}",
                    )
                with edit_col2:
                    new_diff = st.selectbox(
                        "Difficulty",
                        options=[d.value for d in Difficulty],
                        index=[d.value for d in Difficulty].index(
                            aq.difficulty.value
                        ),
                        key=f"edit_diff_{i}",
                    )

                new_answer = st.text_area(
                    "Expected Answer",
                    value=aq.expected_answer or "",
                    key=f"edit_answer_{i}",
                    height=60,
                )

                btn_col1, btn_col2 = st.columns(2)
                with btn_col1:
                    if st.button("💾 Cập nhật", key=f"update_btn_{i}"):
                        try:
                            session.update_annotation(
                                index=i,
                                query_type=QueryType(new_type),
                                difficulty=Difficulty(new_diff),
                                expected_answer=(
                                    new_answer.strip()
                                    if new_answer.strip()
                                    else None
                                ),
                            )
                            st.success(f"✅ Đã cập nhật annotation #{i+1}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Lỗi: {e}")

                with btn_col2:
                    if st.button(
                        "🗑️ Xóa", key=f"delete_btn_{i}", type="secondary"
                    ):
                        session.delete_annotation(i)
                        st.success(f"✅ Đã xóa annotation #{i+1}")
                        st.rerun()

        # Session management buttons
        st.divider()
        mgmt_col1, mgmt_col2, mgmt_col3 = st.columns(3)

        with mgmt_col1:
            if st.button("💾 Lưu Session (JSON)", use_container_width=True):
                try:
                    output_dir = (
                        Path(_RAG_V2_ROOT) / "eval_dataset_builder" / "data"
                    )
                    filepath = session.save(output_dir)
                    st.success(f"✅ Session saved to `{filepath}`")
                except Exception as e:
                    st.error(f"❌ {e}")

        with mgmt_col2:
            uploaded_file = st.file_uploader(
                "📂 Load Session JSON",
                type=["json"],
                key="load_session",
                label_visibility="collapsed",
            )
            if uploaded_file:
                import tempfile, json

                try:
                    tmp_path = Path(tempfile.mkdtemp()) / uploaded_file.name
                    tmp_path.write_bytes(uploaded_file.read())
                    loaded = AnnotationSession.load(tmp_path)
                    st.session_state.annotation_session = loaded
                    st.success(f"✅ Loaded {loaded.count} annotations!")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ {e}")

        with mgmt_col3:
            if st.button(
                "🗑️ Clear All", use_container_width=True, type="secondary"
            ):
                session.clear()
                st.success("✅ Đã xóa tất cả annotations!")
                st.rerun()

# ======================================================================
# TAB 3 — Export CSV (Phase 4)
# ======================================================================

with tab_export:
    session: AnnotationSession = st.session_state.annotation_session
    st.subheader("📤 Export CSV")

    if session.count == 0:
        st.info("Chưa có annotation nào để export.")
    else:
        # Validate session
        errors = session.validate_session()
        if errors:
            st.error("❌ Session có lỗi cần sửa trước khi export:")
            for err in errors:
                st.markdown(f"  • {err}")
        else:
            st.success(
                f"✅ Session hợp lệ — {session.count} annotations sẵn sàng export."
            )

        # Preview table
        st.subheader("👁️ Preview")
        preview_data = CSVExporter.preview(
            session.annotations, include_eval_columns=False
        )
        if preview_data:
            st.dataframe(
                preview_data,
                use_container_width=True,
                hide_index=True,
            )

        # Full preview with eval columns
        with st.expander(
            "📋 Preview đầy đủ (bao gồm cột eval trống)", expanded=False
        ):
            full_preview = CSVExporter.preview(
                session.annotations, include_eval_columns=True
            )
            if full_preview:
                st.dataframe(
                    full_preview,
                    use_container_width=True,
                    hide_index=True,
                )

        st.divider()

        # Export options
        st.subheader("💾 Download")

        col1, col2 = st.columns(2)
        with col1:
            session_name = st.text_input(
                "Tên session (cho filename)",
                value=session.name,
                key="export_session_name",
            )
        with col2:
            filename = CSVExporter.generate_filename(
                prefix="rag_eval_dataset",
                session_name=session_name,
            )
            st.text_input(
                "Filename", value=filename, disabled=True, key="export_filename"
            )

        # Download button
        if not errors:
            try:
                csv_string = CSVExporter.export_to_string(session.annotations)
                st.download_button(
                    label=f"📥 Download CSV ({session.count} records)",
                    data=csv_string,
                    file_name=filename,
                    mime="text/csv",
                    use_container_width=True,
                    type="primary",
                )
            except Exception as e:
                st.error(f"❌ Lỗi export: {e}")

        # Save to file directly
        with st.expander("💾 Lưu trực tiếp vào đĩa", expanded=False):
            save_dir = st.text_input(
                "Thư mục output",
                value=str(Path(_RAG_V2_ROOT) / "eval_dataset_builder" / "data"),
                key="export_save_dir",
            )
            if st.button("💾 Lưu file CSV", use_container_width=True):
                try:
                    output_path = Path(save_dir) / filename
                    CSVExporter.export(session.annotations, output_path)
                    st.success(f"✅ Đã lưu: `{output_path}`")
                except Exception as e:
                    st.error(f"❌ {e}")
