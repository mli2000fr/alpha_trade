"""Research-only global LSTM path classifier. No production dispatch or SQL."""
from dataclasses import dataclass, asdict
from pathlib import Path
import json
import os
import time
from uuid import uuid4

import numpy as np
import pandas as pd
import torch

from modelFactory.model import LSTMAttentionClassifier
from modelFactory.oracle.train import roc_auc
from modelFactory.oracle_path.train import atomic_json, digest


@dataclass(frozen=True)
class SequenceSpec:
    length: int = 40
    hidden_size: int = 64
    num_layers: int = 1
    dropout: float = .1
    batch_size: int = 512
    max_epochs: int = 10
    patience: int = 3
    learning_rate: float = .001
    weight_decay: float = .00001
    clip_standardized: float = 10.
    seed: int = 42
    threads: int = 6

    def __post_init__(self):
        if any(getattr(self, k) < 1 for k in ("length", "hidden_size", "num_layers", "batch_size", "max_epochs", "patience", "threads")):
            raise ValueError("Dimensions/budget LSTM doivent être positifs")
        if not 0 <= self.dropout < 1 or self.learning_rate <= 0 or self.clip_standardized <= 0 or self.weight_decay < 0:
            raise ValueError("Paramètres LSTM invalides")


def sequence_eligibility(meta, sessions, length, registry):
    """Exactly consecutive NYSE observations of ONE identity, ending at J."""
    if length < 1 or meta.duplicated(["symbol", "date"]).any():
        raise ValueError("Séquences invalides ou clés dupliquées")
    ordered = meta.sort_values(["symbol", "date"]).reset_index(drop=True)
    if not meta[["symbol", "date"]].reset_index(drop=True).equals(ordered[["symbol", "date"]]):
        raise ValueError("Matrice à trier par symbole/date avant séquences")
    result = np.full(len(meta), "INSUFFICIENT_SEQUENCE", dtype=object)
    session_index = pd.DatetimeIndex(sessions).get_indexer(meta.date)
    if (session_index < 0).any():
        raise ValueError("Observation hors séance NYSE")
    for symbol, group in meta.groupby("symbol", sort=False):
        index = group.index.to_numpy()
        if len(index) < length:
            continue
        ends = index[length-1:]
        starts = index[:len(ends)]
        good = (session_index[ends]-session_index[starts]) == length-1
        reasons = np.where(good, "", "MISSING_SESSION_IN_SEQUENCE").astype(object)
        for column in ("instrument_id", "data_source", "data_adjustment"):
            codes = pd.factorize(group[column])[0]
            windows = np.lib.stride_tricks.sliding_window_view(codes, length)
            stable = (windows >= 0).all(axis=1) & (windows == windows[:, :1]).all(axis=1)
            if column != "instrument_id":
                invalid = group[column].astype(str).str.upper().isin(["UNKNOWN", "", "NONE", "NAN"]).to_numpy()
                stable &= ~np.lib.stride_tricks.sliding_window_view(invalid, length).any(axis=1)
            reasons[(reasons=="") & ~stable] = f"UNKNOWN_OR_CHANGED_{column.upper()}"
        if "feature_present" in group:
            present = np.lib.stride_tricks.sliding_window_view(group.feature_present.to_numpy(bool), length).all(axis=1)
            reasons[(reasons=="") & ~present] = "EMPTY_FEATURE_ROW_IN_SEQUENCE"
        for e in registry.get(symbol, ()):
            crossed = (meta.date.iloc[starts].to_numpy() <= np.datetime64(e.last_predecessor_date)) & (
                meta.date.iloc[ends].to_numpy() >= np.datetime64(e.first_successor_date))
            reasons[(reasons=="") & crossed] = "KNOWN_IDENTITY_BREAK_IN_SEQUENCE"
        result[ends] = reasons
    return result == "", result


def fit_scaler(matrix, indices):
    """Finite-feature means/stds using ONLY the purged train endpoints."""
    if not len(indices):
        raise ValueError("Train vide pour le scaler")
    count = np.zeros(matrix.shape[1], dtype=np.int64)
    total = np.zeros(matrix.shape[1], dtype=np.float64)
    square = np.zeros(matrix.shape[1], dtype=np.float64)
    for offset in range(0, len(indices), 50000):
        block = np.asarray(matrix[indices[offset:offset+50000]], dtype=np.float64)
        finite = np.isfinite(block)
        block = np.where(finite, block, 0.)
        count += finite.sum(axis=0)
        total += block.sum(axis=0)
        square += (block*block).sum(axis=0)
    mean = total/np.maximum(count, 1)
    variance = np.maximum(0., square/np.maximum(count, 1)-mean*mean)
    scale = np.sqrt(variance)
    scale[(scale < 1e-6) | (count==0)] = 1.
    return dict(mean=mean.tolist(), scale=scale.tolist(), finite_train_counts=count.tolist())


def sequence_batch(matrix, endpoints, scaler, spec):
    if not len(endpoints) or (np.asarray(endpoints) < spec.length-1).any():
        raise ValueError("Extrémités de séquence invalides")
    offsets = np.arange(-spec.length+1, 1, dtype=np.int64)
    raw = np.asarray(matrix[np.asarray(endpoints)[:, None]+offsets], dtype=np.float32)
    present = np.isfinite(raw)
    mean = np.asarray(scaler["mean"], dtype=np.float32)
    scale = np.asarray(scaler["scale"], dtype=np.float32)
    with np.errstate(over="ignore", invalid="ignore"):
        values = (np.where(present, raw, mean)-mean)/scale
    values = np.clip(values, -spec.clip_standardized, spec.clip_standardized)
    # NaN -> training mean -> standardized zero; the mask is explicit, not invented prices.
    return np.concatenate((values, (~present).astype(np.float32)), axis=2)


def new_model(features, spec):
    return LSTMAttentionClassifier(features*2, spec.hidden_size, spec.num_layers, spec.dropout, num_classes=2)


def atomic_torch(path, value):
    path = Path(path)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        torch.save(value, temporary)
        for attempt in range(6):
            try:
                os.replace(temporary, path)
                return
            except PermissionError:
                if attempt == 5:
                    raise
                time.sleep(.1*2**attempt)
    finally:
        temporary.unlink(missing_ok=True)


def predict(model, matrix, endpoints, scaler, spec, device):
    model.eval()
    result = np.empty(len(endpoints), dtype=np.float64)
    with torch.inference_mode():
        for offset in range(0, len(endpoints), spec.batch_size):
            batch = sequence_batch(matrix, endpoints[offset:offset+spec.batch_size], scaler, spec)
            logits, _ = model(torch.from_numpy(batch).to(device))
            result[offset:offset+len(batch)] = torch.softmax(logits, dim=1)[:, 1].cpu().numpy()
    if not np.isfinite(result).all() or ((result<0)|(result>1)).any():
        raise ValueError("Scores LSTM invalides")
    return result


def fit(matrix, targets, train_indices, val_indices, spec, folder, device, progress):
    """Train-only scaler; validation AUC checkpoint selection; no test arguments."""
    for indices in (train_indices, val_indices):
        if not len(indices) or set(np.unique(targets[indices])) != {0., 1.}:
            raise ValueError("Train/validation LSTM non binaires ou constants")
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    scaler = fit_scaler(matrix, train_indices)
    scaler_path = folder/"scaler.json"
    if scaler_path.exists() and json.loads(scaler_path.read_text(encoding="utf-8")) != scaler:
        raise ValueError("Scaler modifié pendant reprise")
    atomic_json(scaler_path, scaler)
    torch.manual_seed(spec.seed)
    if device == "cuda":
        torch.cuda.manual_seed_all(spec.seed)
    model = new_model(matrix.shape[1], spec).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=spec.learning_rate, weight_decay=spec.weight_decay)
    loss_fn = torch.nn.CrossEntropyLoss()
    epoch, best_auc, stale, history = 0, -1., 0, []
    marker = folder/"epoch_state.json"
    if marker.exists():
        state_meta = json.loads(marker.read_text(encoding="utf-8"))
        checkpoint = folder/state_meta["file"]
        if digest(checkpoint) != state_meta["sha256"] or state_meta["spec"] != asdict(spec):
            raise ValueError("Checkpoint LSTM corrompu/incompatible")
        state = torch.load(checkpoint, map_location="cpu", weights_only=True)
        model.load_state_dict(state["weights"])
        optimizer.load_state_dict(state["optimizer"])
        torch.set_rng_state(state["rng"])
        if device == "cuda":
            torch.cuda.set_rng_state_all(state["cuda_rng"])
        epoch, best_auc, stale, history = state_meta["epoch"], state_meta["best_auc"], state_meta["stale"], state_meta["history"]
        best_meta = state_meta["best"]
        if digest(folder/best_meta["file"]) != best_meta["sha256"]:
            raise ValueError("Meilleurs poids LSTM corrompus")
    started = time.perf_counter()
    while epoch < spec.max_epochs and stale < spec.patience:
        model.train()
        order = np.random.default_rng(spec.seed+epoch).permutation(train_indices)
        losses, samples = 0., 0
        epoch_started = time.perf_counter()
        for offset in range(0, len(order), spec.batch_size):
            endpoints = order[offset:offset+spec.batch_size]
            x = torch.from_numpy(sequence_batch(matrix, endpoints, scaler, spec)).to(device)
            y = torch.from_numpy(targets[endpoints].astype(np.int64)).to(device)
            optimizer.zero_grad(set_to_none=True)
            logits, _ = model(x)
            loss = loss_fn(logits, y)
            if not torch.isfinite(loss):
                raise ValueError("Loss LSTM non finie")
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.)
            optimizer.step()
            losses += float(loss.detach())*len(endpoints)
            samples += len(endpoints)
            if (offset//spec.batch_size) % 200 == 0:
                progress("training", epoch+1, samples, len(order), dict(best_validation_auc=best_auc,
                    elapsed_epoch_seconds=round(time.perf_counter()-epoch_started, 1)))
        probabilities = predict(model, matrix, val_indices, scaler, spec, device)
        val_auc = roc_auc(targets[val_indices], probabilities)
        if val_auc is None:
            raise ValueError("Validation AUC LSTM indisponible")
        epoch += 1
        history.append(dict(epoch=epoch, train_loss=losses/samples, validation_auc=val_auc,
            seconds=round(time.perf_counter()-epoch_started, 2)))
        if val_auc > best_auc:
            best_auc, stale = val_auc, 0
            filename = f"lstm_best_epoch_{epoch}.pt"
            atomic_torch(folder/filename, dict(weights=model.state_dict()))
            best_meta = dict(epoch=epoch, validation_auc=val_auc, file=filename, sha256=digest(folder/filename))
        else:
            stale += 1
        checkpoint = folder/f"epoch_state_{epoch}.pt"
        atomic_torch(checkpoint, dict(weights=model.state_dict(), optimizer=optimizer.state_dict(),
            rng=torch.get_rng_state(), cuda_rng=torch.cuda.get_rng_state_all() if device=="cuda" else []))
        atomic_json(marker, dict(epoch=epoch, best_auc=best_auc, stale=stale, history=history,
            spec=asdict(spec), file=checkpoint.name, sha256=digest(checkpoint), best=best_meta))
        progress("epoch_completed", epoch, samples, len(order), history[-1])
    best = torch.load(folder/best_meta["file"], map_location=device, weights_only=True)
    model.load_state_dict(best["weights"])
    atomic_torch(folder/"lstm_best.pt", dict(weights=model.state_dict()))
    atomic_json(folder/"best.json", best_meta)
    return model, scaler, dict(best_validation_auc=best_auc, history=history,
        best_epoch=best_meta["epoch"], epochs_completed=epoch, seconds=round(time.perf_counter()-started, 2))
