"""modelFactory/model.py — LSTM + Temporal Attention LightningModule."""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

try:
    import lightning as L
except ImportError:  # pragma: no cover
    import pytorch_lightning as L  # type: ignore[no-redef]

from torchmetrics.classification import (
    BinaryAccuracy, BinaryAUROC, BinaryPrecision, BinaryRecall,
    MulticlassAccuracy, MulticlassF1Score,
)


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
    """LightningModule wrapping the LSTM+Attention classifier.

    Supports ``num_classes=2`` (binary) and ``num_classes=3`` (ternary long/flat/short).
    """

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
        self._num_classes = num_classes

        # Class weights for imbalanced ternary targets
        class_weights = None
        if num_classes == 3:
            # Give more weight to minority classes (short/long vs flat)
            class_weights = torch.tensor([1.0, 1.5, 1.0], dtype=torch.float32)  # short, flat, long
        self.criterion = nn.CrossEntropyLoss(weight=class_weights)

        # Metrics — adaptés au nombre de classes
        if num_classes == 3:
            self.train_acc = MulticlassAccuracy(num_classes=3, average="macro")
            self.val_acc = MulticlassAccuracy(num_classes=3, average="macro")
            self.val_f1 = MulticlassF1Score(num_classes=3, average="macro")
            self.test_acc = MulticlassAccuracy(num_classes=3, average="macro")
            self.test_f1 = MulticlassF1Score(num_classes=3, average="macro")
            self.val_precision = None
            self.val_recall = None
            self.val_auc = None
            self.test_precision = None
            self.test_recall = None
            self.test_auc = None
        else:
            self.train_acc = BinaryAccuracy()
            self.val_acc = BinaryAccuracy()
            self.val_precision = BinaryPrecision()
            self.val_recall = BinaryRecall()
            self.val_auc = BinaryAUROC()
            self.test_acc = BinaryAccuracy()
            self.test_precision = BinaryPrecision()
            self.test_recall = BinaryRecall()
            self.test_auc = BinaryAUROC()
            self.val_f1 = None
            self.test_f1 = None

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        return self.net(x)

    def _shared_step(self, batch: tuple[torch.Tensor, torch.Tensor]) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        x, y = batch
        logits, _ = self.net(x)
        if self._num_classes == 3:
            # y est {-1, 0, 1}, on le décale en {0, 1, 2} pour CrossEntropyLoss
            y_shifted = y + 1
            loss = self.criterion(logits, y_shifted)
            probs = F.softmax(logits, dim=1)
            preds = torch.argmax(probs, dim=1)
            return loss, preds, y_shifted
        else:
            loss = self.criterion(logits, y)
            probs = F.softmax(logits, dim=1)
            probs_class1 = probs[:, 1]
            return loss, probs_class1, y

    def training_step(self, batch: tuple[torch.Tensor, torch.Tensor], batch_idx: int) -> torch.Tensor:
        loss, output, y = self._shared_step(batch)
        self.train_acc(output, y)
        self.log("train_loss", loss, prog_bar=True)
        self.log("train_acc", self.train_acc, prog_bar=True)
        return loss

    def validation_step(self, batch: tuple[torch.Tensor, torch.Tensor], batch_idx: int) -> None:
        loss, output, y = self._shared_step(batch)
        self.val_acc(output, y)
        if self.val_precision is not None:
            self.val_precision(output, y)
        if self.val_recall is not None:
            self.val_recall(output, y)
        if self.val_auc is not None:
            self.val_auc(output, y)
        if self.val_f1 is not None:
            self.val_f1(output, y)
        self.log("val_loss", loss, prog_bar=True)
        self.log("val_acc", self.val_acc, prog_bar=True)
        if self.val_precision is not None:
            self.log("val_precision", self.val_precision)
        if self.val_recall is not None:
            self.log("val_recall", self.val_recall)
        if self.val_auc is not None:
            self.log("val_auc", self.val_auc)
        if self.val_f1 is not None:
            self.log("val_f1", self.val_f1)

    def test_step(self, batch: tuple[torch.Tensor, torch.Tensor], batch_idx: int) -> None:
        loss, output, y = self._shared_step(batch)
        self.test_acc(output, y)
        if self.test_precision is not None:
            self.test_precision(output, y)
        if self.test_recall is not None:
            self.test_recall(output, y)
        if self.test_auc is not None:
            self.test_auc(output, y)
        if self.test_f1 is not None:
            self.test_f1(output, y)
        self.log("test_loss", loss)
        self.log("test_acc", self.test_acc)
        if self.test_precision is not None:
            self.log("test_precision", self.test_precision)
        if self.test_recall is not None:
            self.log("test_recall", self.test_recall)
        if self.test_auc is not None:
            self.log("test_auc", self.test_auc)
        if self.test_f1 is not None:
            self.log("test_f1", self.test_f1)

    def configure_optimizers(self) -> torch.optim.Optimizer:  # type: ignore[override]
        return torch.optim.AdamW(
            self.parameters(),
            lr=self.hparams.learning_rate,  # type: ignore[attr-defined]
            weight_decay=self.hparams.weight_decay,  # type: ignore[attr-defined]
        )
