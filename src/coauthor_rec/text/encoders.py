"""Encoders textuais para artigos (título + abstract).

Interface única ``BaseTextEncoder.encode(texts) -> np.ndarray [N, d]``, com backends:
  - TfidfEncoder        — TF-IDF + TruncatedSVD (baseline clássico, sem download).
  - HFEncoder           — transformers (BERT, SciBERT, SPECTER…) com pooling mean/cls.

Os embeddings são comparados via um recomendador text-only (similaridade do cosseno).
A CNN 1D da proposta (§4.4.1) é uma cabeça treinável da fusão end-to-end (ciclo seguinte);
aqui comparamos os encoders pré-treinados que a alimentam.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np


class BaseTextEncoder(ABC):
    name: str = "base"
    @abstractmethod
    def encode(self, texts: list[str]) -> np.ndarray:
        """Retorna matriz [N, d] de embeddings (uma linha por texto)."""


class TfidfEncoder(BaseTextEncoder):
    """TF-IDF reduzido por SVD (LSA). Rápido, sem download — baseline textual."""
    def __init__(self, dim: int = 256, max_features: int = 50000, seed: int = 42):
        self.name = f"tfidf-{dim}"
        self.dim = dim
        self.max_features = max_features
        self.seed = seed

    def encode(self, texts: list[str]) -> np.ndarray:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.decomposition import TruncatedSVD
        vec = TfidfVectorizer(max_features=self.max_features, stop_words="english",
                              ngram_range=(1, 2), min_df=2)
        X = vec.fit_transform(texts)
        dim = min(self.dim, X.shape[1] - 1) if X.shape[1] > 1 else 1
        svd = TruncatedSVD(n_components=dim, random_state=self.seed)
        return svd.fit_transform(X).astype(np.float32)


class HFEncoder(BaseTextEncoder):
    """Encoder via HuggingFace transformers, com pooling mean ou cls (token [CLS])."""
    def __init__(self, model_name: str, pooling: str = "mean", max_length: int = 256,
                 batch_size: int = 32, device: str | None = None, label: str | None = None):
        self.model_name = model_name
        self.pooling = pooling
        self.max_length = max_length
        self.batch_size = batch_size
        self.device = device
        self.name = label or model_name.split("/")[-1]
        self._tok = None
        self._model = None

    def _ensure(self):
        if self._model is not None:
            return
        import torch
        from transformers import AutoTokenizer, AutoModel
        self._torch = torch
        self.device = self.device or ("mps" if torch.backends.mps.is_available()
                                      else "cuda" if torch.cuda.is_available() else "cpu")
        self._tok = AutoTokenizer.from_pretrained(self.model_name)
        self._model = AutoModel.from_pretrained(self.model_name).to(self.device).eval()

    def encode(self, texts: list[str]) -> np.ndarray:
        self._ensure()
        torch = self._torch
        out = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            enc = self._tok(batch, padding=True, truncation=True,
                            max_length=self.max_length, return_tensors="pt").to(self.device)
            with torch.no_grad():
                hidden = self._model(**enc).last_hidden_state  # [B, T, H]
            if self.pooling == "cls":
                vec = hidden[:, 0]
            else:  # mean pooling mascarado
                mask = enc["attention_mask"].unsqueeze(-1).float()
                vec = (hidden * mask).sum(1) / mask.sum(1).clamp(min=1e-9)
            out.append(vec.float().cpu().numpy())
        return np.vstack(out).astype(np.float32)

    def encode_sequences(self, texts: list[str], seq_len: int) -> tuple[np.ndarray, np.ndarray]:
        """Embeddings token-level (sequência) p/ a CNN 1D. Retorna (emb [N, L, H] fp16,
        mask [N, L] uint8), com L = seq_len fixo (pad/trunca)."""
        self._ensure()
        torch = self._torch
        embs, masks = [], []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            enc = self._tok(batch, padding="max_length", truncation=True,
                            max_length=seq_len, return_tensors="pt").to(self.device)
            with torch.no_grad():
                hidden = self._model(**enc).last_hidden_state  # [B, L, H]
            embs.append(hidden.half().cpu().numpy())
            masks.append(enc["attention_mask"].to(torch.uint8).cpu().numpy())
        return np.concatenate(embs).astype(np.float16), np.concatenate(masks).astype(np.uint8)


# Registro de encoders nomeados usados na comparação.
_REGISTRY = {
    "tfidf": lambda: TfidfEncoder(dim=256),
    "bert": lambda: HFEncoder("bert-base-uncased", pooling="mean", label="bert-base"),
    "scibert": lambda: HFEncoder("allenai/scibert_scivocab_uncased", pooling="mean", label="scibert"),
    "specter": lambda: HFEncoder("allenai/specter", pooling="cls", label="specter"),
}


def get_encoder(name: str) -> BaseTextEncoder:
    """Resolve um encoder pelo apelido (tfidf|bert|scibert|specter) ou nome HF cru."""
    if name in _REGISTRY:
        return _REGISTRY[name]()
    return HFEncoder(name, pooling="mean")  # qualquer modelo HF por mean pooling


def available_encoders() -> list[str]:
    return list(_REGISTRY)
