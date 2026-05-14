import hashlib
import logging
import os
from typing import Iterable

from event_sentiment.models import ContextualSentimentRecord, NormalizedNewsArticle, SentimentRecord

LOGGER = logging.getLogger(__name__)
HF_TOKEN_ENV_VAR = "HUHHING_FACE_TOKEN"
HF_TOKEN_ENV_VARS = (
    HF_TOKEN_ENV_VAR,
    "HF_TOKEN",
    "HUGGINGFACE_HUB_TOKEN",
)


class FinBERTSentimentService:
    def __init__(
        self,
        model_name: str = "ProsusAI/finbert",
        model_version: str = "finbert_v1",
        batch_size: int = 16,
        max_length: int = 256,
        model_revision: str | None = None,
    ) -> None:
        self.model_name = model_name
        self.model_version = model_version
        self.model_revision = model_revision
        self.batch_size = batch_size
        self.max_length = max_length
        self.gpu_oom_batch_fallbacks: list[int] = []
        self.device = None
        self.tokenizer = None
        self.model = None
        self.id2label: dict[int, str] = {}
        self._fingerprint_cache: str | None = None

    @property
    def model_fingerprint(self) -> str:
        """SHA256[:16] stable du couple (model_name, revision, config FinBERT).

        Phase 4.1.c — permet de tracer le checkpoint exact consommé pour
        chaque enregistrement ``news_sentiment`` (col. ``model_fingerprint``).
        """
        if self._fingerprint_cache is not None:
            return self._fingerprint_cache
        revision_part = self.model_revision if self.model_revision else "HEAD"
        config_items = sorted({
            "model_version": self.model_version,
            "max_length": int(self.max_length),
        }.items())
        payload = f"{self.model_name}:{revision_part}:{config_items}"
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
        self._fingerprint_cache = digest
        return digest

    @staticmethod
    def _get_torch_module():
        import torch

        return torch

    @staticmethod
    def _get_transformers_classes():
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        return AutoModelForSequenceClassification, AutoTokenizer

    @staticmethod
    def _is_cuda_runtime_error(exc: RuntimeError) -> bool:
        message = str(exc).lower()
        return "cuda" in message or "cublas" in message or "cudnn" in message

    @staticmethod
    def _is_cuda_oom_error(exc: RuntimeError) -> bool:
        message = str(exc).lower()
        return "out of memory" in message or "cuda out of memory" in message

    @classmethod
    def _next_smaller_gpu_batch_size(cls, current_batch_size: int) -> int | None:
        for candidate in (64, 32, 16):
            if candidate < int(current_batch_size):
                return candidate
        return None

    @staticmethod
    def _resolve_hf_token() -> str | None:
        for env_var in HF_TOKEN_ENV_VARS:
            token = os.environ.get(env_var)
            if token and token.strip():
                return token.strip()
        return None

    @staticmethod
    def _export_hf_token_aliases(token: str | None) -> None:
        if token is None:
            return
        for env_var in HF_TOKEN_ENV_VARS:
            os.environ[env_var] = token

    def _clear_cuda_cache(self) -> None:
        try:
            torch = self._get_torch_module()
            if hasattr(torch, "cuda") and hasattr(torch.cuda, "empty_cache"):
                torch.cuda.empty_cache()
        except Exception:
            return

    def _load_model_for_device(self, device: str, force_reload: bool = False) -> None:
        if not force_reload and self.model is not None and self.tokenizer is not None and self.device == device:
            return

        torch = self._get_torch_module()
        auto_model_cls, auto_tokenizer_cls = self._get_transformers_classes()

        self.device = device
        load_kwargs: dict[str, object] = {}
        if self.model_revision:
            load_kwargs["revision"] = self.model_revision
        token = self._resolve_hf_token()
        self._export_hf_token_aliases(token)
        if token is not None:
            load_kwargs["token"] = token
        self.tokenizer = auto_tokenizer_cls.from_pretrained(self.model_name, **load_kwargs)
        self.model = auto_model_cls.from_pretrained(self.model_name, **load_kwargs)
        self.model.to(self.device)
        self.model.eval()
        config_labels = getattr(self.model.config, "id2label", {}) or {}
        self.id2label = {int(key): str(value).lower() for key, value in config_labels.items()}
        LOGGER.info("FinBERT model loaded | device=%s", self.device)

    def _ensure_model_loaded(self) -> None:
        if self.model is not None and self.tokenizer is not None:
            return

        torch = self._get_torch_module()
        initial_device = "cuda" if torch.cuda.is_available() else "cpu"
        self._load_model_for_device(initial_device)

    def adopt_runtime_from(self, other: "FinBERTSentimentService") -> None:
        """Réutilise un runtime FinBERT déjà chargé.

        Permet d'éviter un second chargement du même modèle/tokenizer quand le
        scoring contextuel est activé dans la même exécution du pipeline.
        """
        if other.model is None or other.tokenizer is None or other.device is None:
            return
        self.model = other.model
        self.tokenizer = other.tokenizer
        self.device = other.device
        self.id2label = dict(other.id2label)
        self._fingerprint_cache = other._fingerprint_cache
        self.batch_size = int(getattr(other, "batch_size", self.batch_size) or self.batch_size)
        self.gpu_oom_batch_fallbacks = list(getattr(other, "gpu_oom_batch_fallbacks", []) or [])

    def _infer_probabilities(self, batch_texts: list[str]):
        """
        Tokenise et infère les probabilités FinBERT pour un batch de textes.

        Retourne un tuple (probs_tensor, token_counts) :
          - probs_tensor : Tensor softmax (batch, 3) sur CPU
          - token_counts : list[int] — nb de tokens par texte (incluant [CLS]/[SEP])
            Calculé depuis input_ids.shape pour éviter toute double tokenisation.
        """
        torch = self._get_torch_module()

        assert self.tokenizer is not None
        assert self.model is not None
        assert self.device is not None

        encoded = self.tokenizer(
            batch_texts,
            truncation=True,
            max_length=self.max_length,
            padding=True,
            return_tensors="pt",
        )
        attention = encoded["attention_mask"]  # (batch, seq_len)
        if hasattr(attention, "sum"):
            # Torch tensor réel
            token_counts = attention.sum(dim=1).tolist()  # liste d'int, un par texte
        else:
            # Fake tensor de tests / objets minimalistes
            attention_values = getattr(attention, "values", attention)
            attention_rows = attention_values if isinstance(attention_values, (list, tuple)) else []
            token_counts = [
                int(sum(row))
                for row in attention_rows
                if isinstance(row, (list, tuple))
            ]

        encoded = {key: value.to(self.device) for key, value in encoded.items()}

        with torch.no_grad():
            logits = self.model(**encoded).logits
            probs = torch.softmax(logits, dim=-1).cpu()

        return probs, token_counts

    def _choose_text(self, article: NormalizedNewsArticle) -> tuple[str, str]:
        headline = (article.headline or "").strip()
        summary = (article.summary or "").strip()
        content = (article.content or "").strip()

        if content:
            text = " [SEP] ".join(part for part in [headline, summary, content] if part)
            return text, "content_full"
        if summary:
            return " [SEP] ".join(part for part in [headline, summary] if part), "headline_summary"
        return headline, "headline_only"

    def _infer_next_batch(self, texts: list[str], start: int):
        current_batch_size = max(int(self.batch_size), 1)
        while True:
            end = min(start + current_batch_size, len(texts))
            batch_texts = texts[start:end]
            try:
                probs, token_counts = self._infer_probabilities(batch_texts)
                self.batch_size = current_batch_size
                return batch_texts, probs, token_counts, end
            except RuntimeError as exc:
                if self.device == "cuda" and self._is_cuda_oom_error(exc):
                    next_batch_size = self._next_smaller_gpu_batch_size(current_batch_size)
                    self._clear_cuda_cache()
                    if next_batch_size is not None:
                        LOGGER.warning(
                            "FinBERT CUDA OOM | batch_size=%s -> retry batch_size=%s",
                            current_batch_size,
                            next_batch_size,
                        )
                        current_batch_size = next_batch_size
                        self.batch_size = next_batch_size
                        if next_batch_size not in self.gpu_oom_batch_fallbacks:
                            self.gpu_oom_batch_fallbacks.append(next_batch_size)
                        continue
                    LOGGER.warning(
                        "FinBERT CUDA OOM persistant | batch_size=%s | fallback CPU",
                        current_batch_size,
                    )
                    self._load_model_for_device("cpu", force_reload=True)
                    continue
                if self.device == "cuda" and self._is_cuda_runtime_error(exc):
                    self._clear_cuda_cache()
                    LOGGER.warning(
                        "FinBERT CUDA failure detected | error=%s | device=cpu (fallback after CUDA failure)",
                        exc,
                    )
                    self._load_model_for_device("cpu", force_reload=True)
                    continue
                raise

    def score_articles(self, articles: Iterable[NormalizedNewsArticle]) -> list[SentimentRecord]:
        article_list = list(articles)
        if not article_list:
            return []

        self._ensure_model_loaded()
        torch = self._get_torch_module()

        assert self.tokenizer is not None
        assert self.model is not None
        assert self.device is not None

        # Passe 1 — sélection du texte uniquement (aucune tokenisation ici)
        texts: list[str] = []
        strategies: list[str] = []
        for article in article_list:
            text, strategy = self._choose_text(article)
            texts.append(text)
            strategies.append(strategy)

        records: list[SentimentRecord] = []
        start = 0
        while start < len(article_list):
            batch_texts, probs, batch_token_counts, end = self._infer_next_batch(texts, start)
            batch_articles = article_list[start:end]
            batch_strategies = strategies[start:end]

            for idx, article in enumerate(batch_articles):
                row = probs[idx].tolist()
                label_map = {self.id2label.get(i, str(i)): row[i] for i in range(len(row))}
                positive = float(label_map.get("positive", 0.0))
                neutral = float(label_map.get("neutral", 0.0))
                negative = float(label_map.get("negative", 0.0))
                max_idx = int(torch.argmax(probs[idx]).item())
                sentiment_label = self.id2label.get(max_idx, "neutral")
                text_hash = hashlib.sha256(batch_texts[idx].encode("utf-8")).hexdigest()
                # token_count issu des tenseurs encodés (pas de re-tokenisation)
                token_count = int(batch_token_counts[idx])

                records.append(
                    SentimentRecord(
                        article_id=article.article_id,
                        model_name=self.model_name,
                        model_version=self.model_version,
                        text_strategy=batch_strategies[idx],
                        text_hash=text_hash,
                        truncated=int(token_count >= self.max_length),
                        max_length_tokens=self.max_length,
                        sentiment_label=sentiment_label,
                        positive_score=positive,
                        neutral_score=neutral,
                        negative_score=negative,
                        sentiment_confidence=max(positive, neutral, negative),
                        sentiment_net_score=positive - negative,
                        model_fingerprint=self.model_fingerprint,
                    )
                )

            start = end

        LOGGER.info("FinBERT scoring | articles=%s", len(records))
        return records


#: Version du prompt contextuel (Niveau 4). Stocké dans
#: ``news_ticker_sentiment.scoring_version`` pour invalider et re-scorer en
#: cas d'évolution de la stratégie de prompt.
CONTEXTUAL_SCORING_VERSION = "contextual_v1"


def _choose_contextual_text(
    article: NormalizedNewsArticle,
    symbol: str,
    company_name: str | None,
) -> tuple[str, str]:
    """Construit le prompt contextuel (article, symbole) injecté dans FinBERT.

    Trois stratégies (par ordre décroissant d'information) :

    * ``contextual_company`` : ``f"For {company_name} ({symbol}): {headline} [SEP] {summary}"``
    * ``contextual_symbol_only`` : ``f"For {symbol}: {headline} [SEP] {summary}"``
    * ``contextual_headline_only`` : fallback minimal headline + symbole.
    """
    headline = (article.headline or "").strip()
    summary = (article.summary or "").strip()
    content = (article.content or "").strip()
    # EODHD ne fournit pas de ``summary`` distinct ; dans ce cas on retombe
    # sur ``content`` pour ne pas perdre l'essentiel du texte côté scoring
    # contextuel.
    secondary_text = summary or content
    body_parts = [part for part in [headline, secondary_text] if part]
    body = " [SEP] ".join(body_parts) if body_parts else headline
    name = (company_name or "").strip()
    sym = (symbol or "").strip().upper()
    if name:
        return f"For {name} ({sym}): {body}", "contextual_company"
    if body:
        return f"For {sym}: {body}", "contextual_symbol_only"
    return f"For {sym}: {headline or sym}", "contextual_headline_only"


class ContextualFinBERTScorer(FinBERTSentimentService):
    """Variante de :class:`FinBERTSentimentService` qui produit un score
    par couple ``(article, symbol)`` (Niveau 4).

    Réutilise tout le pipeline batch + fallback CUDA→CPU de la classe parente
    (``_infer_probabilities``). Seule la fabrique de texte change : on
    injecte un préfixe contextualisant le ticker et son ``company_name``.
    """

    def score_pairs(
        self,
        pairs: Iterable[tuple[NormalizedNewsArticle, str, str | None]],
    ) -> list[ContextualSentimentRecord]:
        pair_list = list(pairs)
        if not pair_list:
            return []

        self._ensure_model_loaded()
        torch = self._get_torch_module()

        assert self.tokenizer is not None
        assert self.model is not None
        assert self.device is not None

        texts: list[str] = []
        strategies: list[str] = []
        for article, symbol, company_name in pair_list:
            text, strategy = _choose_contextual_text(article, symbol, company_name)
            texts.append(text)
            strategies.append(strategy)

        records: list[ContextualSentimentRecord] = []
        start = 0
        while start < len(pair_list):
            batch_texts, probs, batch_token_counts, end = self._infer_next_batch(texts, start)
            batch_pairs = pair_list[start:end]
            batch_strategies = strategies[start:end]

            for idx, (article, symbol, _company_name) in enumerate(batch_pairs):
                row = probs[idx].tolist()
                label_map = {self.id2label.get(i, str(i)): row[i] for i in range(len(row))}
                positive = float(label_map.get("positive", 0.0))
                neutral = float(label_map.get("neutral", 0.0))
                negative = float(label_map.get("negative", 0.0))
                max_idx = int(torch.argmax(probs[idx]).item())
                sentiment_label = self.id2label.get(max_idx, "neutral")
                text_hash = hashlib.sha256(batch_texts[idx].encode("utf-8")).hexdigest()
                token_count = int(batch_token_counts[idx])

                records.append(
                    ContextualSentimentRecord(
                        article_id=article.article_id,
                        symbol=str(symbol).strip().upper(),
                        model_name=self.model_name,
                        model_version=self.model_version,
                        text_strategy=batch_strategies[idx],
                        text_hash=text_hash,
                        truncated=int(token_count >= self.max_length),
                        max_length_tokens=self.max_length,
                        sentiment_label=sentiment_label,
                        positive_score=positive,
                        neutral_score=neutral,
                        negative_score=negative,
                        sentiment_confidence=max(positive, neutral, negative),
                        sentiment_net_score=positive - negative,
                        model_fingerprint=self.model_fingerprint,
                        scoring_version=CONTEXTUAL_SCORING_VERSION,
                    )
                )

            start = end

        LOGGER.info("ContextualFinBERT scoring | pairs=%s", len(records))
        return records


