"""
RetrievalConfigManager — Quản lý cấu hình retrieval.

Phase 1: Chọn collection, top_k, embedding model.
Config được lưu kèm từng record để phục vụ so sánh sau.

Tích hợp trực tiếp với Qdrant để:
- List available collections
- Hiển thị thông tin chi tiết (số points, vector configs)
- Validate collection tồn tại
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from qdrant_client import QdrantClient

from ..models.schemas import EmbeddingModel, RetrievalConfig

logger = logging.getLogger(__name__)


class RetrievalConfigManager:
    """Quản lý cấu hình retrieval cho dataset builder.

    Responsibilities:
    - Kết nối Qdrant để list available collections
    - Validate collection tồn tại và có data
    - Lưu trữ config hiện tại
    - Cung cấp config cho ChunkRetriever

    Attributes:
        qdrant_client: QdrantClient instance.
        current_config: Config hiện tại (None nếu chưa cấu hình).
    """

    def __init__(
        self,
        qdrant_host: str = "localhost",
        qdrant_port: int = 6333,
    ) -> None:
        """Khởi tạo manager với Qdrant connection.

        Args:
            qdrant_host: Qdrant server host.
            qdrant_port: Qdrant server port.
        """
        self.qdrant_client = QdrantClient(host=qdrant_host, port=qdrant_port)
        self.current_config: Optional[RetrievalConfig] = None
        logger.info(
            "RetrievalConfigManager initialized — Qdrant at %s:%d",
            qdrant_host,
            qdrant_port,
        )

    # ------------------------------------------------------------------
    # Collection discovery
    # ------------------------------------------------------------------

    def list_collections(self) -> List[str]:
        """List tất cả collections có trong Qdrant.

        Returns:
            Danh sách tên collections.
        """
        collections_response = self.qdrant_client.get_collections()
        names = [col.name for col in collections_response.collections]
        logger.info("Found %d collections: %s", len(names), names)
        return names

    def get_collection_info(self, collection_name: str) -> Dict[str, Any]:
        """Lấy thông tin chi tiết của một collection.

        Args:
            collection_name: Tên collection.

        Returns:
            dict với keys: name, points_count, vectors_config, status.

        Raises:
            ValueError: Nếu collection không tồn tại.
        """
        available = self.list_collections()
        if collection_name not in available:
            raise ValueError(
                f"Collection '{collection_name}' không tồn tại. "
                f"Available: {available}"
            )

        info = self.qdrant_client.get_collection(collection_name)
        vectors_config = {}
        if info.config and info.config.params and info.config.params.vectors:
            vecs = info.config.params.vectors
            if isinstance(vecs, dict):
                for vec_name, vec_params in vecs.items():
                    vectors_config[vec_name] = {
                        "size": vec_params.size,
                        "distance": str(vec_params.distance),
                    }

        return {
            "name": collection_name,
            "points_count": info.points_count,
            "vectors_count": info.vectors_count,
            "vectors_config": vectors_config,
            "status": str(info.status),
        }

    def get_all_collections_info(self) -> List[Dict[str, Any]]:
        """Lấy thông tin chi tiết của tất cả collections.

        Returns:
            List[dict] mỗi dict có: name, points_count, vectors_config, status.
        """
        names = self.list_collections()
        infos = []
        for name in names:
            try:
                infos.append(self.get_collection_info(name))
            except Exception as e:
                logger.warning("Failed to get info for '%s': %s", name, e)
                infos.append({"name": name, "error": str(e)})
        return infos

    # ------------------------------------------------------------------
    # Config management
    # ------------------------------------------------------------------

    def set_config(
        self,
        collections: List[str],
        top_k: int,
        embedding_model: EmbeddingModel,
        vector_weight: float = 1.0,
        keyword_weight: float = 0.0,
        vector_top_k: int = 20,
        keyword_top_k: int = 20,
        vector_pool_k: int = 15,
        keyword_pool_k: int = 15,
    ) -> RetrievalConfig:
        """Thiết lập config retrieval.

        Validates:
        - top_k > 0
        - Tất cả collections tồn tại trong Qdrant
        - Embedding model hợp lệ

        Args:
            collections: Danh sách collection names.
            top_k: Số chunks kết quả cuối cùng.
            embedding_model: Embedding model.
            vector_weight: Weight cho vector score (hybrid).
            keyword_weight: Weight cho keyword score (hybrid).
            vector_top_k: Candidates từ Qdrant mỗi collection.
            keyword_top_k: Candidates từ ES mỗi collection.
            vector_pool_k: Pool vector toàn cục.
            keyword_pool_k: Pool keyword toàn cục.

        Returns:
            RetrievalConfig đã validate.

        Raises:
            ValueError: Nếu config không hợp lệ.
        """
        # Validate collections exist
        available = self.list_collections()
        missing = [c for c in collections if c not in available]
        if missing:
            raise ValueError(
                f"Collections không tồn tại: {missing}. "
                f"Available: {available}"
            )

        config = RetrievalConfig(
            collections=collections,
            top_k=top_k,
            embedding_model=embedding_model,
            vector_weight=vector_weight,
            keyword_weight=keyword_weight,
            vector_top_k=vector_top_k,
            keyword_top_k=keyword_top_k,
            vector_pool_k=vector_pool_k,
            keyword_pool_k=keyword_pool_k,
        )

        self.current_config = config
        logger.info(
            "Config set — collections=%s, top_k=%d, model=%s, label=%s",
            config.collections,
            config.top_k,
            config.embedding_model.value,
            config.config_label(),
        )
        return config

    def get_config(self) -> Optional[RetrievalConfig]:
        """Trả về config hiện tại.

        Returns:
            RetrievalConfig hoặc None nếu chưa cấu hình.
        """
        return self.current_config

    def is_configured(self) -> bool:
        """Kiểm tra đã cấu hình chưa.

        Returns:
            True nếu đã set config.
        """
        return self.current_config is not None

    def reset_config(self) -> None:
        """Reset config về None."""
        self.current_config = None
        logger.info("Config reset.")
