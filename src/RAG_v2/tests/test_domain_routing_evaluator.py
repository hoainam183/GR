from __future__ import annotations

import pytest

from evaluation.evaluate_domain_routing import RoutingEvalCase, evaluate_cases
from retrieval.collection_selector import CollectionSelector


class FakeRouter:
    def __init__(self, routes):
        self.routes = routes

    def route(self, query):
        return self.routes[query]


def test_routing_evaluator_reports_stage_metrics() -> None:
    cases = [
        RoutingEvalCase("ctdt_ok", "ctdt query", ["ctdt"]),
        RoutingEvalCase("kehoach_lock", "lich dang ky hoc ky moi nhat", ["kehoach"]),
        RoutingEvalCase("policy_widen", "khi nao dang ky hoc chuong trinh thu hai", ["quydinh"]),
    ]
    router = FakeRouter(
        {
            "ctdt query": {
                "intent": "rag",
                "domain": "ctdt",
                "domains": ["ctdt"],
                "confidence": 0.90,
                "probabilities": {"ctdt": 0.90, "kehoach": 0.05},
            },
            "lich dang ky hoc ky moi nhat": {
                "intent": "rag",
                "domain": "kehoach",
                "domains": ["kehoach"],
                "confidence": 0.52,
                "probabilities": {"kehoach": 0.52, "ctdt": 0.18},
            },
            "khi nao dang ky hoc chuong trinh thu hai": {
                "intent": "rag",
                "domain": "kehoach",
                "domains": ["kehoach"],
                "confidence": 0.40,
                "probabilities": {"kehoach": 0.40, "quydinh": 0.38, "ctdt": 0.10},
            },
        }
    )

    report = evaluate_cases(
        cases,
        router=router,
        selector=CollectionSelector(confidence_threshold=0.55),
    )

    assert report["case_count"] == 3
    assert report["stages"]["raw_classifier"]["missing_domain_rate"] == pytest.approx(1 / 3, abs=1e-4)
    assert report["stages"]["selector"]["set_recall"] == 1.0
    assert report["stages"]["final_pipeline"]["exact_set_accuracy"] == pytest.approx(2 / 3, abs=1e-4)
    assert report["stages"]["final_pipeline"]["kehoach_false_negative_rate"] == 0.0
    assert report["stages"]["selector"]["low_confidence_fallback_rate"] == pytest.approx(2 / 3, abs=1e-4)
    assert "0.35-0.55" in report["confidence_buckets"]
