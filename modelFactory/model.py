"""modelFactory/model.py — LSTM + Temporal Attention LightningModule."""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

try:
    import lightning as L
except ImportError:  # pragma: no cover
    import pytorch_lightning as L  # type: ignore[no-redef]

from torchmetrics.classification import BinaryAccuracy, BinaryAUROC, BinaryPrecision, BinaryRecall


# ---------------------------------------------------------------------------
# Temporal Attention
# ---------------------------------------------------------------------------

class TemporalAttention(nn.Module):
    """Soft-attention sur l'axe temporel des hidden states LSTM."""

    def __init__(self, hidden_size: int) -> None:
        super().__init__()
        self.attn = nn.Linear(hidden_size, 1, bias=False)

    def forward(self, lstm_out: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """
        Args:
            lstm_out: [batch, seq_len, hidden_size]
        Returns:
            context: [batch, hidden_size]
            weights: [batch, seq_len]  (somment à 1 sur l'axe temporel)
        """
        scores = self.attn(lstm_out).squeeze(-1)          # [batch, seq_len]
        weights = F.softmax(scores, dim=1)                 # [batch, seq_len]
        context = torch.bmm(weights.unsqueeze(1), lstm_out).squeeze(1)  # [batch, hidden]
        return context, weights


# ---------------------------------------------------------------------------
# LSTM + Attention backbone
# ---------------------------------------------------------------------------

class LSTMAttentionClassifier(nn.Module):
    """LSTM multi-couche + attention temporelle + classification head."""

    def __init__(self, input_size: int, hidden_size: int, num_layers: int, dropout: float, num_classes: int = 2) -> None:
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            dropout=dropout if num_layers > 1 else 0.0,
            batch_first=True,
        )
        self.attention = TemporalAttention(hidden_size)
        self.dropout = nn.Dropout(dropout)
        self.classifier = nn.Linear(hidden_size, num_classes)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """
        Args:
            x: [batch, seq_len, input_size]
        Returns:
            logits: [batch, num_classes]
            attn_weights: [batch, seq_len]
        """
        lstm_out, _ = self.lstm(x)                         # [batch, seq_len, hidden]
        context, attn_weights = self.attention(lstm_out)   # [batch, hidden], [batch, seq_len]
        context = self.dropout(context)
        logits = self.classifier(context)                  # [batch, num_classes]
        return logits, attn_weights


# ---------------------------------------------------------------------------
# Lightning Module
# ---------------------------------------------------------------------------

class LSTMAttentionModule(L.LightningModule):
    """LightningModule wrapping the LSTM+Attention classifier."""

    def __init__(
        self,
        input_size: int,
        hidden_size: int = 128,
        num_layers: int = 2,
        dropout: float = 0.3,
        learning_rate: float = 1e-3,
        weight_decay: float = 1e-5,
        num_classes: int = 2,
    ) -> None:
        super().__init__()
        self.save_hyperparameters()
        self.net = LSTMAttentionClassifier(input_size, hidden_size, num_layers, dropout, num_classes)
        self.criterion = nn.CrossEntropyLoss()

        # Metrics
        self.train_acc = BinaryAccuracy()
        self.val_acc = BinaryAccuracy()
        self.val_precision = BinaryPrecision()
        self.val_recall = BinaryRecall()
        self.val_auc = BinaryAUROC()

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        return self.net(x)

    def _shared_step(self, batch: tuple[torch.Tensor, torch.Tensor]) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        x, y = batch
        logits, _ = self.net(x)
        loss = self.criterion(logits, y)
        probs = F.softmax(logits, dim=1)[:, 1]
        return loss, probs, y

    def training_step(self, batch: tuple[torch.Tensor, torch.Tensor], batch_idx: int) -> torch.Tensor:
        loss, probs, y = self._shared_step(batch)
        self.train_acc(probs, y)
        self.log("train_loss", loss, prog_bar=True)
        self.log("train_acc", self.train_acc, prog_bar=True)
        return loss

    def validation_step(self, batch: tuple[torch.Tensor, torch.Tensor], batch_idx: int) -> None:
        loss, probs, y = self._shared_step(batch)
        self.val_acc(probs, y)
        self.val_precision(probs, y)
        self.val_recall(probs, y)
        self.val_auc(probs, y)
        self.log("val_loss", loss, prog_bar=True)
        self.log("val_acc", self.val_acc, prog_bar=True)
        self.log("val_precision", self.val_precision)
        self.log("val_recall", self.val_recall)
        self.log("val_auc", self.val_auc)

    def test_step(self, batch: tuple[torch.Tensor, torch.Tensor], batch_idx: int) -> None:
        loss, probs, y = self._shared_step(batch)
        self.log("test_loss", loss)
        self.log("test_acc", self.val_acc(probs, y))

    def configure_optimizers(self):  # type: ignore[override]
        return torch.optim.AdamW(
            self.parameters(),
            lr=self.hparams.learning_rate,  # type: ignore[attr-defined]
            weight_decay=self.hparams.weight_decay,  # type: ignore[attr-defined]
        )

