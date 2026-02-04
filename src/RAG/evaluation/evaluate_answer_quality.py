"""
Answer Quality Evaluation Script
Đánh giá chất lượng câu trả lời của RAG system bằng cách so sánh với ground truth.

Hỗ trợ các metrics:
1. Semantic Similarity (Embedding-based)
2. BLEU Score (N-gram precision)
3. ROUGE Score (Recall-oriented)
4. F1 Score (Token-level)
5. Exact Match

Usage:
    python evaluate_answer_quality.py
    python evaluate_answer_quality.py --limit 10  # Test với 10 samples
    python evaluate_answer_quality.py --no-hybrid --no-rerank  # Semantic only
"""

import csv
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Optional tqdm for progress bar
try:
    from tqdm import tqdm

    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

    def tqdm(iterable, **kwargs):
        """Fallback when tqdm is not installed"""
        desc = kwargs.get("desc", "")
        if desc:
            print(f"  {desc}...")
        return iterable


# Add parent paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from embedding.embedding import create_pipeline
from embedding.hybrid_search import create_hybrid_searcher
from embedding.reranker import create_reranker

# Optional libraries for advanced metrics
try:
    from sentence_transformers import SentenceTransformer, util

    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False
    print(
        "⚠️ sentence-transformers not installed. Semantic similarity will be limited."
    )

try:
    from rouge_score import rouge_scorer

    HAS_ROUGE = True
except ImportError:
    HAS_ROUGE = False
    print("⚠️ rouge-score not installed. ROUGE metrics will be skipped.")
    print("   Install with: pip install rouge-score")


@dataclass
class EvaluationSample:
    """Single evaluation sample from dataset"""

    question: str
    ground_truth_answer: str
    expected_source: str
    question_type: str
    difficulty: str
    relevant_context: str


@dataclass
class AnswerMetrics:
    """Metrics for answer quality evaluation"""

    # Semantic similarity (embedding-based)
    semantic_similarity: float = 0.0

    # BLEU Score (1-4 gram)
    bleu_1: float = 0.0
    bleu_2: float = 0.0
    bleu_3: float = 0.0
    bleu_4: float = 0.0
    bleu_avg: float = 0.0

    # ROUGE Score
    rouge_1_f: float = 0.0
    rouge_2_f: float = 0.0
    rouge_l_f: float = 0.0

    # Token-level F1
    token_precision: float = 0.0
    token_recall: float = 0.0
    token_f1: float = 0.0

    # Exact match
    exact_match: bool = False

    # Normalized exact match (lowercase, remove punctuation)
    normalized_exact_match: bool = False


@dataclass
class AnswerEvalResult:
    """Result for single answer evaluation"""

    question: str
    ground_truth: str
    generated_answer: str
    expected_source: str
    retrieved_sources: List[str]
    retrieved_scores: List[float]

    # Retrieval metrics
    retrieval_hit: bool
    retrieval_rank: int
    retrieval_mrr: float

    # Answer metrics
    answer_metrics: AnswerMetrics

    # Metadata
    question_type: str
    difficulty: str
    question_id: int = 0  # ID of question in dataset


@dataclass
class AnswerEvalReport:
    """Overall answer evaluation report"""

    total_samples: int
    top_k: int

    # Configuration
    use_hybrid: bool = False
    use_reranker: bool = False

    # Retrieval metrics (aggregated)
    hit_rate: float = 0.0
    mrr: float = 0.0

    # Answer metrics (aggregated)
    avg_semantic_similarity: float = 0.0
    avg_bleu_1: float = 0.0
    avg_bleu_2: float = 0.0
    avg_bleu_3: float = 0.0
    avg_bleu_4: float = 0.0
    avg_bleu_avg: float = 0.0
    avg_rouge_1_f: float = 0.0
    avg_rouge_2_f: float = 0.0
    avg_rouge_l_f: float = 0.0
    avg_token_f1: float = 0.0
    exact_match_rate: float = 0.0

    # By question type
    metrics_by_type: Dict[str, Dict[str, float]] = field(default_factory=dict)

    # By difficulty
    metrics_by_difficulty: Dict[str, Dict[str, float]] = field(
        default_factory=dict
    )

    # Individual results
    results: List[AnswerEvalResult] = field(default_factory=list)


class AnswerMetricsCalculator:
    """Calculate various answer quality metrics"""

    def __init__(self, use_semantic: bool = True):
        self.use_semantic = use_semantic and HAS_SENTENCE_TRANSFORMERS

        if self.use_semantic:
            print(
                "📦 Loading sentence-transformers model for semantic similarity..."
            )
            # Multilingual model that works well with Vietnamese
            self.semantic_model = SentenceTransformer(
                "paraphrase-multilingual-MiniLM-L12-v2"
            )
            print("   ✅ Semantic model loaded!")

        # ROUGE scorer
        if HAS_ROUGE:
            self.rouge_scorer = rouge_scorer.RougeScorer(
                ["rouge1", "rouge2", "rougeL"], use_stemmer=False
            )
        else:
            self.rouge_scorer = None

    def normalize_text(self, text: str) -> str:
        """Normalize text for comparison"""
        # Lowercase
        text = text.lower()
        # Remove extra whitespace
        text = " ".join(text.split())
        # Remove punctuation (keep Vietnamese characters)
        text = re.sub(r"[^\w\s]", "", text)
        return text.strip()

    def tokenize(self, text: str) -> List[str]:
        """Simple tokenization for Vietnamese"""
        # Normalize first
        text = self.normalize_text(text)
        # Split by whitespace
        return text.split()

    def calculate_semantic_similarity(
        self, reference: str, candidate: str
    ) -> float:
        """Calculate semantic similarity using embeddings"""
        if not self.use_semantic:
            return self._jaccard_similarity(reference, candidate)

        embeddings = self.semantic_model.encode(
            [reference, candidate], convert_to_tensor=True
        )
        sim = util.cos_sim(embeddings[0], embeddings[1]).item()
        return max(0, sim)

    def _jaccard_similarity(self, text1: str, text2: str) -> float:
        """Jaccard similarity as fallback"""
        words1 = set(self.tokenize(text1))
        words2 = set(self.tokenize(text2))

        if not words1 or not words2:
            return 0.0

        intersection = words1 & words2
        union = words1 | words2

        return len(intersection) / len(union)

    def calculate_bleu(
        self, reference: str, candidate: str, max_n: int = 4
    ) -> Dict[str, float]:
        """
        Calculate BLEU score (simplified version)

        BLEU measures n-gram precision of candidate against reference
        """
        ref_tokens = self.tokenize(reference)
        cand_tokens = self.tokenize(candidate)

        if not cand_tokens:
            return {f"bleu_{i}": 0.0 for i in range(1, max_n + 1)}

        bleu_scores = {}

        for n in range(1, max_n + 1):
            # Get n-grams
            ref_ngrams = self._get_ngrams(ref_tokens, n)
            cand_ngrams = self._get_ngrams(cand_tokens, n)

            if not cand_ngrams:
                bleu_scores[f"bleu_{n}"] = 0.0
                continue

            # Count matches
            ref_counter = Counter(ref_ngrams)
            cand_counter = Counter(cand_ngrams)

            matches = 0
            for ngram, count in cand_counter.items():
                matches += min(count, ref_counter.get(ngram, 0))

            # Precision
            precision = matches / len(cand_ngrams)
            bleu_scores[f"bleu_{n}"] = precision

        # Average BLEU
        bleu_scores["bleu_avg"] = sum(bleu_scores.values()) / max_n

        return bleu_scores

    def _get_ngrams(self, tokens: List[str], n: int) -> List[tuple]:
        """Extract n-grams from token list"""
        if len(tokens) < n:
            return []
        return [tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)]

    def calculate_rouge(
        self, reference: str, candidate: str
    ) -> Dict[str, float]:
        """
        Calculate ROUGE scores

        ROUGE measures recall of n-grams from reference in candidate
        """
        if not self.rouge_scorer:
            # Fallback: simple overlap
            ref_tokens = set(self.tokenize(reference))
            cand_tokens = set(self.tokenize(candidate))

            if not ref_tokens:
                return {"rouge_1_f": 0.0, "rouge_2_f": 0.0, "rouge_l_f": 0.0}

            overlap = len(ref_tokens & cand_tokens) / len(ref_tokens)
            return {
                "rouge_1_f": overlap,
                "rouge_2_f": overlap * 0.8,  # Approximate
                "rouge_l_f": overlap * 0.9,
            }

        scores = self.rouge_scorer.score(reference, candidate)

        return {
            "rouge_1_f": scores["rouge1"].fmeasure,
            "rouge_2_f": scores["rouge2"].fmeasure,
            "rouge_l_f": scores["rougeL"].fmeasure,
        }

    def calculate_token_f1(
        self, reference: str, candidate: str
    ) -> Dict[str, float]:
        """
        Calculate token-level precision, recall, F1

        This is commonly used in QA evaluation
        """
        ref_tokens = self.tokenize(reference)
        cand_tokens = self.tokenize(candidate)

        if not ref_tokens or not cand_tokens:
            return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

        ref_counter = Counter(ref_tokens)
        cand_counter = Counter(cand_tokens)

        # Count common tokens
        common = 0
        for token, count in cand_counter.items():
            common += min(count, ref_counter.get(token, 0))

        precision = common / len(cand_tokens) if cand_tokens else 0.0
        recall = common / len(ref_tokens) if ref_tokens else 0.0

        if precision + recall > 0:
            f1 = 2 * precision * recall / (precision + recall)
        else:
            f1 = 0.0

        return {"precision": precision, "recall": recall, "f1": f1}

    def calculate_exact_match(
        self, reference: str, candidate: str
    ) -> Dict[str, bool]:
        """Check exact match and normalized exact match"""
        exact = reference.strip() == candidate.strip()
        normalized = self.normalize_text(reference) == self.normalize_text(
            candidate
        )

        return {"exact_match": exact, "normalized_exact_match": normalized}

    def calculate_all_metrics(
        self, reference: str, candidate: str
    ) -> AnswerMetrics:
        """Calculate all answer quality metrics"""
        # Semantic similarity
        semantic_sim = self.calculate_semantic_similarity(reference, candidate)

        # BLEU
        bleu_scores = self.calculate_bleu(reference, candidate)

        # ROUGE
        rouge_scores = self.calculate_rouge(reference, candidate)

        # Token F1
        token_scores = self.calculate_token_f1(reference, candidate)

        # Exact match
        exact_scores = self.calculate_exact_match(reference, candidate)

        return AnswerMetrics(
            semantic_similarity=semantic_sim,
            bleu_1=bleu_scores["bleu_1"],
            bleu_2=bleu_scores["bleu_2"],
            bleu_3=bleu_scores["bleu_3"],
            bleu_4=bleu_scores["bleu_4"],
            bleu_avg=bleu_scores["bleu_avg"],
            rouge_1_f=rouge_scores["rouge_1_f"],
            rouge_2_f=rouge_scores["rouge_2_f"],
            rouge_l_f=rouge_scores["rouge_l_f"],
            token_precision=token_scores["precision"],
            token_recall=token_scores["recall"],
            token_f1=token_scores["f1"],
            exact_match=exact_scores["exact_match"],
            normalized_exact_match=exact_scores["normalized_exact_match"],
        )


class AnswerQualityEvaluator:
    """Evaluator for both retrieval and answer quality"""

    def __init__(
        self,
        top_k: int = 5,
        verbose: bool = True,
        use_hybrid: bool = True,
        use_reranker: bool = True,
        llm_provider: str = "gemini",
        api_key: str = None,
    ):
        self.top_k = top_k
        self.verbose = verbose
        self.use_hybrid = use_hybrid
        self.use_reranker = use_reranker
        self.llm_provider = llm_provider
        self.api_key = api_key

        self.pipeline = None
        self.hybrid_searcher = None
        self.reranker = None
        self.rag_system = None
        self.metrics_calculator = None

    def load_components(self):
        """Load all components: pipeline, hybrid searcher, reranker, LLM"""
        if self.verbose:
            print("📦 Loading components...")

        # Load embedding pipeline
        if self.verbose:
            print("   Loading embedding pipeline...")

        self.pipeline = create_pipeline()

        try:
            self.pipeline.load_vector_store()
            stats = self.pipeline.vector_store.get_statistics()

            if self.verbose:
                print(
                    f"   ✅ Loaded vector store ({stats['total_documents']} documents)"
                )

        except FileNotFoundError:
            raise RuntimeError(
                "❌ Vector store not found! Please run embedding first."
            )

        # Setup hybrid searcher
        if self.use_hybrid:
            if self.verbose:
                print("   Setting up hybrid searcher...")
            self.hybrid_searcher = create_hybrid_searcher(
                semantic_weight=0.5, fusion_method="rrf"
            )
            if self.verbose:
                print("   ✅ Hybrid search enabled")

        # Setup reranker
        if self.use_reranker:
            try:
                if self.verbose:
                    print("   Loading reranker model...")

                self.reranker = create_reranker(
                    model_name="BAAI/bge-reranker-v2-m3",
                    device="cpu",
                    enable_deduplication=True,
                    enable_reranking=True,
                )

                if self.verbose:
                    print("   ✅ Reranker loaded")

            except Exception as e:
                print(f"   ⚠️ Failed to load reranker: {e}")
                self.use_reranker = False
                self.reranker = None

        # Load LLM for answer generation
        if self.verbose:
            print("   Loading LLM for answer generation...")

        try:
            # Add LLM path to sys.path
            llm_path = Path(__file__).parent.parent / "LLM"
            if str(llm_path) not in sys.path:
                sys.path.insert(0, str(llm_path))

            from ..LLM import GeminiRAG

            import os
            from dotenv import load_dotenv

            # Load API key
            env_path = Path(__file__).parent.parent.parent.parent / ".env"
            load_dotenv(dotenv_path=env_path)

            api_key = self.api_key or os.getenv("GEMINI_API_KEY")

            if not api_key:
                raise ValueError("GEMINI_API_KEY not found")

            self.rag_system = GeminiRAG(api_key=api_key, pipeline=self.pipeline)

            if self.verbose:
                print("   ✅ LLM (Gemini) loaded")

        except Exception as e:
            print(f"   ❌ Failed to load LLM: {e}")
            raise

        # Load metrics calculator
        if self.verbose:
            print("   Loading metrics calculator...")

        self.metrics_calculator = AnswerMetricsCalculator(use_semantic=True)

        if self.verbose:
            print("   ✅ All components loaded!")

    def load_dataset(self, csv_path: str) -> List[EvaluationSample]:
        """Load evaluation dataset from CSV"""
        samples = []

        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                sample = EvaluationSample(
                    question=row["question"],
                    ground_truth_answer=row["answer"],
                    expected_source=row["document_source"],
                    question_type=row.get("question_type", "unknown"),
                    difficulty=row.get("difficulty", "unknown"),
                    relevant_context=row.get("relevant_context", ""),
                )
                samples.append(sample)

        return samples

    def normalize_source_name(self, source: str) -> str:
        """Normalize source file name for comparison"""
        source = source.lower()
        source = source.replace("\\", "/").split("/")[-1]
        source = source.replace("_converted", "").replace(".md", "")
        source = source.strip()
        return source

    def check_source_match(
        self, expected: str, retrieved_list: List[str]
    ) -> Tuple[bool, int]:
        """Check if expected source is in retrieved list"""
        expected_norm = self.normalize_source_name(expected)

        for i, retrieved in enumerate(retrieved_list):
            retrieved_norm = self.normalize_source_name(retrieved)

            if expected_norm == retrieved_norm:
                return True, i + 1

            if (
                expected_norm in retrieved_norm
                or retrieved_norm in expected_norm
            ):
                return True, i + 1

            # Handle variations
            expected_simple = (
                expected_norm.replace("đ", "d")
                .replace("ă", "a")
                .replace("â", "a")
            )
            retrieved_simple = (
                retrieved_norm.replace("đ", "d")
                .replace("ă", "a")
                .replace("â", "a")
            )

            if (
                expected_simple in retrieved_simple
                or retrieved_simple in expected_simple
            ):
                return True, i + 1

        return False, 0

    def retrieve_and_answer(
        self, question: str
    ) -> Tuple[str, List[str], List[float]]:
        """
        Retrieve documents and generate answer

        Returns:
            answer: Generated answer
            sources: List of source file names
            scores: List of similarity scores
        """
        # Get answer from RAG system
        result = self.rag_system.answer(
            question=question,
            top_k=self.top_k,
            stream=False,
            verbose=False,
        )

        answer = result["answer"]

        # Extract sources and scores
        sources = []
        scores = []

        for source in result["sources"]:
            source_file = source.metadata.get("source_file", "unknown")
            sources.append(source_file)
            scores.append(source.score)

        return answer, sources, scores

    def evaluate_single(
        self, sample: EvaluationSample, question_id: int = 0
    ) -> AnswerEvalResult:
        """Evaluate single sample"""
        # Retrieve and generate answer
        answer, sources, scores = self.retrieve_and_answer(sample.question)

        # Check retrieval
        hit, rank = self.check_source_match(sample.expected_source, sources)
        mrr = 1.0 / rank if rank > 0 else 0.0

        # Calculate answer metrics
        answer_metrics = self.metrics_calculator.calculate_all_metrics(
            reference=sample.ground_truth_answer,
            candidate=answer,
        )

        return AnswerEvalResult(
            question=sample.question,
            ground_truth=sample.ground_truth_answer,
            generated_answer=answer,
            expected_source=sample.expected_source,
            retrieved_sources=sources,
            retrieved_scores=scores,
            retrieval_hit=hit,
            retrieval_rank=rank,
            retrieval_mrr=mrr,
            answer_metrics=answer_metrics,
            question_type=sample.question_type,
            difficulty=sample.difficulty,
            question_id=question_id,
        )

    def evaluate(
        self, samples: List[EvaluationSample], start_id: int = 1
    ) -> AnswerEvalReport:
        """Run full evaluation on all samples

        Args:
            samples: List of samples to evaluate
            start_id: Starting question ID (for batch processing)
        """
        results = []

        iterator = (
            tqdm(samples, desc="Evaluating", initial=0)
            if self.verbose
            else samples
        )

        for i, sample in enumerate(iterator):
            question_id = start_id + i
            result = self.evaluate_single(sample, question_id=question_id)
            results.append(result)

            if self.verbose and HAS_TQDM:
                status = "✅" if result.retrieval_hit else "❌"
                iterator.set_postfix(
                    {
                        "hit": status,
                        "sim": f"{result.answer_metrics.semantic_similarity:.2f}",
                        "f1": f"{result.answer_metrics.token_f1:.2f}",
                    }
                )

        # Aggregate metrics
        n = len(results)

        hit_rate = sum(1 for r in results if r.retrieval_hit) / n
        mrr = sum(r.retrieval_mrr for r in results) / n

        avg_semantic = (
            sum(r.answer_metrics.semantic_similarity for r in results) / n
        )
        avg_bleu_1 = sum(r.answer_metrics.bleu_1 for r in results) / n
        avg_bleu_2 = sum(r.answer_metrics.bleu_2 for r in results) / n
        avg_bleu_3 = sum(r.answer_metrics.bleu_3 for r in results) / n
        avg_bleu_4 = sum(r.answer_metrics.bleu_4 for r in results) / n
        avg_bleu_avg = sum(r.answer_metrics.bleu_avg for r in results) / n
        avg_rouge_1 = sum(r.answer_metrics.rouge_1_f for r in results) / n
        avg_rouge_2 = sum(r.answer_metrics.rouge_2_f for r in results) / n
        avg_rouge_l = sum(r.answer_metrics.rouge_l_f for r in results) / n
        avg_token_f1 = sum(r.answer_metrics.token_f1 for r in results) / n
        exact_match_rate = (
            sum(1 for r in results if r.answer_metrics.normalized_exact_match)
            / n
        )

        # Metrics by question type
        metrics_by_type = self._aggregate_by_field(results, "question_type")

        # Metrics by difficulty
        metrics_by_difficulty = self._aggregate_by_field(results, "difficulty")

        return AnswerEvalReport(
            total_samples=n,
            top_k=self.top_k,
            use_hybrid=self.use_hybrid,
            use_reranker=self.use_reranker,
            hit_rate=hit_rate,
            mrr=mrr,
            avg_semantic_similarity=avg_semantic,
            avg_bleu_1=avg_bleu_1,
            avg_bleu_2=avg_bleu_2,
            avg_bleu_3=avg_bleu_3,
            avg_bleu_4=avg_bleu_4,
            avg_bleu_avg=avg_bleu_avg,
            avg_rouge_1_f=avg_rouge_1,
            avg_rouge_2_f=avg_rouge_2,
            avg_rouge_l_f=avg_rouge_l,
            avg_token_f1=avg_token_f1,
            exact_match_rate=exact_match_rate,
            metrics_by_type=metrics_by_type,
            metrics_by_difficulty=metrics_by_difficulty,
            results=results,
        )

    def _aggregate_by_field(
        self, results: List[AnswerEvalResult], field: str
    ) -> Dict[str, Dict[str, float]]:
        """Aggregate metrics by a specific field"""
        groups: Dict[str, List[AnswerEvalResult]] = {}

        for r in results:
            key = getattr(r, field)
            if key not in groups:
                groups[key] = []
            groups[key].append(r)

        aggregated = {}
        for key, group in groups.items():
            n = len(group)
            aggregated[key] = {
                "count": n,
                "hit_rate": sum(1 for r in group if r.retrieval_hit) / n,
                "mrr": sum(r.retrieval_mrr for r in group) / n,
                "semantic_similarity": sum(
                    r.answer_metrics.semantic_similarity for r in group
                )
                / n,
                "bleu_avg": sum(r.answer_metrics.bleu_avg for r in group) / n,
                "rouge_l_f": sum(r.answer_metrics.rouge_l_f for r in group) / n,
                "token_f1": sum(r.answer_metrics.token_f1 for r in group) / n,
            }

        return aggregated


def print_report(report: AnswerEvalReport):
    """Print formatted evaluation report"""
    print("\n" + "=" * 80)
    print("📊 ANSWER QUALITY EVALUATION REPORT")
    print("=" * 80)

    # Configuration
    print(f"\n⚙️  CONFIGURATION")
    print("-" * 60)
    print(f"   • Hybrid Search (BM25): {'✅' if report.use_hybrid else '❌'}")
    print(
        f"   • Reranking (Cross-encoder): {'✅' if report.use_reranker else '❌'}"
    )

    # Overall metrics
    print(
        f"\n📈 OVERALL METRICS (n={report.total_samples}, top_k={report.top_k})"
    )
    print("-" * 60)

    print("\n🔍 RETRIEVAL METRICS:")
    print(f"   • Hit Rate@{report.top_k}:    {report.hit_rate:.2%}")
    print(f"   • MRR:             {report.mrr:.4f}")

    print("\n📝 ANSWER QUALITY METRICS:")
    print(f"   • Semantic Similarity: {report.avg_semantic_similarity:.4f}")
    print(f"   • Token F1:            {report.avg_token_f1:.4f}")
    print(f"   • Exact Match Rate:    {report.exact_match_rate:.2%}")

    print(f"\n   BLEU Scores:")
    print(f"      BLEU-1: {report.avg_bleu_1:.4f}")
    print(f"      BLEU-2: {report.avg_bleu_2:.4f}")
    print(f"      BLEU-3: {report.avg_bleu_3:.4f}")
    print(f"      BLEU-4: {report.avg_bleu_4:.4f}")
    print(f"      BLEU-Avg: {report.avg_bleu_avg:.4f}")

    print(f"\n   ROUGE Scores:")
    print(f"      ROUGE-1 F1: {report.avg_rouge_1_f:.4f}")
    print(f"      ROUGE-2 F1: {report.avg_rouge_2_f:.4f}")
    print(f"      ROUGE-L F1: {report.avg_rouge_l_f:.4f}")

    # By question type
    print(f"\n📊 METRICS BY QUESTION TYPE")
    print("-" * 60)
    for qtype, metrics in sorted(report.metrics_by_type.items()):
        print(f"\n   {qtype} (n={metrics['count']}):")
        print(
            f"      Hit Rate: {metrics['hit_rate']:.2%} | "
            f"Semantic: {metrics['semantic_similarity']:.3f} | "
            f"F1: {metrics['token_f1']:.3f}"
        )

    # By difficulty
    print(f"\n📊 METRICS BY DIFFICULTY")
    print("-" * 60)

    difficulty_order = {"easy": 0, "medium": 1, "hard": 2}
    sorted_difficulties = sorted(
        report.metrics_by_difficulty.items(),
        key=lambda x: difficulty_order.get(x[0], 99),
    )

    for diff, metrics in sorted_difficulties:
        print(f"\n   {diff} (n={metrics['count']}):")
        print(
            f"      Hit Rate: {metrics['hit_rate']:.2%} | "
            f"Semantic: {metrics['semantic_similarity']:.3f} | "
            f"F1: {metrics['token_f1']:.3f}"
        )

    # Sample results
    print(f"\n📋 SAMPLE RESULTS (first 3)")
    print("-" * 60)
    for i, r in enumerate(report.results[:3], 1):
        print(f"\n   [{i}] Q: {r.question[:60]}...")
        print(f"       Ground Truth: {r.ground_truth[:60]}...")
        print(f"       Generated:    {r.generated_answer[:60]}...")
        print(
            f"       Metrics: Semantic={r.answer_metrics.semantic_similarity:.3f}, "
            f"F1={r.answer_metrics.token_f1:.3f}, "
            f"BLEU={r.answer_metrics.bleu_avg:.3f}"
        )

    print("\n" + "=" * 80)


def save_results_csv(report: AnswerEvalReport, output_path: str):
    """Save detailed results to CSV"""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)

        # Header
        writer.writerow(
            [
                "question",
                "ground_truth",
                "generated_answer",
                "expected_source",
                "retrieved_sources",
                "retrieval_hit",
                "retrieval_rank",
                "mrr",
                "semantic_similarity",
                "bleu_1",
                "bleu_2",
                "bleu_3",
                "bleu_4",
                "bleu_avg",
                "rouge_1_f",
                "rouge_2_f",
                "rouge_l_f",
                "token_precision",
                "token_recall",
                "token_f1",
                "exact_match",
                "question_type",
                "difficulty",
            ]
        )

        # Data rows
        for r in report.results:
            m = r.answer_metrics
            writer.writerow(
                [
                    r.question,
                    r.ground_truth,
                    r.generated_answer,
                    r.expected_source,
                    "|".join(r.retrieved_sources),
                    r.retrieval_hit,
                    r.retrieval_rank,
                    f"{r.retrieval_mrr:.4f}",
                    f"{m.semantic_similarity:.4f}",
                    f"{m.bleu_1:.4f}",
                    f"{m.bleu_2:.4f}",
                    f"{m.bleu_3:.4f}",
                    f"{m.bleu_4:.4f}",
                    f"{m.bleu_avg:.4f}",
                    f"{m.rouge_1_f:.4f}",
                    f"{m.rouge_2_f:.4f}",
                    f"{m.rouge_l_f:.4f}",
                    f"{m.token_precision:.4f}",
                    f"{m.token_recall:.4f}",
                    f"{m.token_f1:.4f}",
                    m.normalized_exact_match,
                    r.question_type,
                    r.difficulty,
                ]
            )

    print(f"\n💾 Detailed results saved to: {path}")


def save_summary_csv(report: AnswerEvalReport, output_path: str):
    """Save summary metrics to CSV"""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)

        # Configuration
        writer.writerow(["CONFIGURATION"])
        writer.writerow(["Setting", "Value"])
        writer.writerow(
            ["Hybrid Search", "Enabled" if report.use_hybrid else "Disabled"]
        )
        writer.writerow(
            ["Reranking", "Enabled" if report.use_reranker else "Disabled"]
        )
        writer.writerow([])

        # Overall metrics
        writer.writerow(["OVERALL METRICS"])
        writer.writerow(["Metric", "Value"])
        writer.writerow(["Total Samples", report.total_samples])
        writer.writerow(["Top K", report.top_k])
        writer.writerow([])

        writer.writerow(["RETRIEVAL METRICS"])
        writer.writerow([f"Hit Rate@{report.top_k}", f"{report.hit_rate:.4f}"])
        writer.writerow(["MRR", f"{report.mrr:.4f}"])
        writer.writerow([])

        writer.writerow(["ANSWER QUALITY METRICS"])
        writer.writerow(
            ["Semantic Similarity", f"{report.avg_semantic_similarity:.4f}"]
        )
        writer.writerow(["Token F1", f"{report.avg_token_f1:.4f}"])
        writer.writerow(["Exact Match Rate", f"{report.exact_match_rate:.4f}"])
        writer.writerow(["BLEU-1", f"{report.avg_bleu_1:.4f}"])
        writer.writerow(["BLEU-2", f"{report.avg_bleu_2:.4f}"])
        writer.writerow(["BLEU-3", f"{report.avg_bleu_3:.4f}"])
        writer.writerow(["BLEU-4", f"{report.avg_bleu_4:.4f}"])
        writer.writerow(["BLEU-Avg", f"{report.avg_bleu_avg:.4f}"])
        writer.writerow(["ROUGE-1 F1", f"{report.avg_rouge_1_f:.4f}"])
        writer.writerow(["ROUGE-2 F1", f"{report.avg_rouge_2_f:.4f}"])
        writer.writerow(["ROUGE-L F1", f"{report.avg_rouge_l_f:.4f}"])
        writer.writerow([])

        # By question type
        writer.writerow(["METRICS BY QUESTION TYPE"])
        writer.writerow(
            ["Type", "Count", "Hit Rate", "Semantic", "BLEU", "ROUGE-L", "F1"]
        )
        for qtype, metrics in sorted(report.metrics_by_type.items()):
            writer.writerow(
                [
                    qtype,
                    metrics["count"],
                    f"{metrics['hit_rate']:.4f}",
                    f"{metrics['semantic_similarity']:.4f}",
                    f"{metrics['bleu_avg']:.4f}",
                    f"{metrics['rouge_l_f']:.4f}",
                    f"{metrics['token_f1']:.4f}",
                ]
            )
        writer.writerow([])

        # By difficulty
        writer.writerow(["METRICS BY DIFFICULTY"])
        writer.writerow(
            [
                "Difficulty",
                "Count",
                "Hit Rate",
                "Semantic",
                "BLEU",
                "ROUGE-L",
                "F1",
            ]
        )
        for diff, metrics in sorted(report.metrics_by_difficulty.items()):
            writer.writerow(
                [
                    diff,
                    metrics["count"],
                    f"{metrics['hit_rate']:.4f}",
                    f"{metrics['semantic_similarity']:.4f}",
                    f"{metrics['bleu_avg']:.4f}",
                    f"{metrics['rouge_l_f']:.4f}",
                    f"{metrics['token_f1']:.4f}",
                ]
            )

    print(f"💾 Summary saved to: {path}")


def run_evaluation(
    dataset_path: str = None,
    top_k: int = 5,
    limit: int = None,
    start: int = None,
    end: int = None,
    output_dir: str = None,
    use_hybrid: bool = True,
    use_reranker: bool = True,
    api_key: str = None,
    append: bool = False,
):
    """
    Run answer quality evaluation

    Args:
        dataset_path: Path to evaluation CSV
        top_k: Number of documents to retrieve
        limit: Limit number of samples (for testing)
        start: Start index (1-based) for batch evaluation
        end: End index (1-based) for batch evaluation
        output_dir: Directory to save results
        use_hybrid: Enable hybrid search (BM25 + Semantic)
        use_reranker: Enable reranking (Cross-encoder)
        api_key: Gemini API key
        append: Append results to existing file
    """
    # Default paths
    if dataset_path is None:
        dataset_path = (
            Path(__file__).parent.parent.parent.parent
            / "rag_evaluation_dataset_expanded.csv"
        )

    if output_dir is None:
        output_dir = Path(__file__).parent / "answer_quality_results"

    print("🚀 Answer Quality Evaluation Script")
    print("=" * 60)
    print(f"   Dataset:       {dataset_path}")
    print(f"   Top K:         {top_k}")
    print(f"   Hybrid (BM25): {'✅ Enabled' if use_hybrid else '❌ Disabled'}")
    print(
        f"   Reranking:     {'✅ Enabled' if use_reranker else '❌ Disabled'}"
    )
    print("=" * 60)

    # Initialize evaluator
    evaluator = AnswerQualityEvaluator(
        top_k=top_k,
        verbose=True,
        use_hybrid=use_hybrid,
        use_reranker=use_reranker,
        api_key=api_key,
    )

    # Load components
    evaluator.load_components()

    # Load samples
    all_samples = evaluator.load_dataset(str(dataset_path))
    print(f"\n📚 Loaded {len(all_samples)} total samples")

    # Handle batch selection with start/end
    start_idx = 0
    end_idx = len(all_samples)
    start_id = 1  # Question ID starts from 1

    if start is not None:
        start_idx = max(0, start - 1)  # Convert to 0-based
        start_id = start

    if end is not None:
        end_idx = min(len(all_samples), end)

    if limit is not None:
        end_idx = min(start_idx + limit, len(all_samples))

    samples = all_samples[start_idx:end_idx]

    print(
        f"\n📊 Evaluating samples {start_idx + 1} to {end_idx} ({len(samples)} samples)"
    )
    if start or end:
        print(
            f"   ⚠️  Batch mode: Questions #{start_id} to #{start_id + len(samples) - 1}"
        )
        if append:
            print(f"   📌 Results will be APPENDED to existing file")

    # Run evaluation
    print("\n🔍 Running evaluation...")
    report = evaluator.evaluate(samples, start_id=start_id)

    # Print results
    print_report(report)

    # Save results
    # Add config suffix to filename
    config_suffix = ""
    if use_hybrid:
        config_suffix += "_hybrid"
    if use_reranker:
        config_suffix += "_rerank"
    if not config_suffix:
        config_suffix = "_semantic_only"

    output_dir = Path(output_dir)

    # Use fixed filenames for appending
    detailed_filename = f"answer_detailed{config_suffix}.csv"
    summary_filename = f"answer_summary{config_suffix}.csv"

    # Save detailed results (append if requested)
    save_results_csv(
        report,
        str(output_dir / detailed_filename),
        append=append,
    )

    # Save summary (always overwrite with latest batch info)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    batch_info = (
        f"_batch_{start_id}-{start_id + len(samples) - 1}"
        if (start or end)
        else ""
    )
    save_summary_csv(
        report,
        str(
            output_dir
            / f"answer_summary{config_suffix}{batch_info}_{timestamp}.csv"
        ),
    )

    return report


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Evaluate Answer Quality")
    parser.add_argument(
        "--dataset",
        type=str,
        default=None,
        help="Path to evaluation dataset CSV",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of documents to retrieve (default: 5)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of samples to evaluate (for testing)",
    )
    parser.add_argument(
        "--start",
        type=int,
        default=None,
        help="Start question number (1-based) for batch evaluation (e.g., 1, 21, 41)",
    )
    parser.add_argument(
        "--end",
        type=int,
        default=None,
        help="End question number (1-based) for batch evaluation (e.g., 20, 40, 60)",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append results to existing detailed CSV file (for multi-day evaluation)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Directory to save results",
    )
    parser.add_argument(
        "--no-hybrid",
        action="store_true",
        help="Disable hybrid search (BM25 + Semantic)",
    )
    parser.add_argument(
        "--no-rerank",
        action="store_true",
        help="Disable reranking (Cross-encoder)",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="Gemini API key (or set GEMINI_API_KEY env var)",
    )

    args = parser.parse_args()

    run_evaluation(
        dataset_path=args.dataset,
        top_k=args.top_k,
        limit=args.limit,
        start=args.start,
        end=args.end,
        output_dir=args.output_dir,
        use_hybrid=not args.no_hybrid,
        use_reranker=not args.no_rerank,
        api_key=args.api_key,
        append=args.append,
    )


if __name__ == "__main__":
    main()
