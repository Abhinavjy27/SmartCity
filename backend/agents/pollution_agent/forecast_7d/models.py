"""
Forecasting models for Hyderabad 7-day multi-horizon air quality prediction.
Implements:
1. Persistence Baseline
2. Seasonal-Naive Baseline
3. Classical Multi-Output Ridge Regression
4. Multi-Output GRU / LSTM
5. Temporal Convolutional Network (TCN)
6. PatchTST / Channel-Independent Linear Transformer
"""
import math
from typing import Optional, Tuple, Dict, Any

import numpy as np
import torch
import torch.nn as nn
from sklearn.linear_model import Ridge

from .config import FORECAST_HORIZON, NUM_TARGETS


# ── 1. Persistence Baseline ──
class PersistenceForecaster:
    """Predicts future 7 days as the last observed value of each target pollutant."""

    def __init__(self, horizon: int = FORECAST_HORIZON):
        self.horizon = horizon

    def predict(self, X: np.ndarray, target_indices: Optional[list] = None) -> np.ndarray:
        """
        X: (N, C, F)
        Returns: (N, horizon, 6)
        """
        target_idx = target_indices or list(range(NUM_TARGETS))
        # Last time step of context window for target pollutants
        last_vals = X[:, -1, target_idx]  # (N, 6)
        # Repeat across 7 forecast horizons
        return np.repeat(last_vals[:, np.newaxis, :], self.horizon, axis=1)


# ── 2. Seasonal-Naive Baseline ──
class SeasonalNaiveForecaster:
    """Predicts day t+h using the value from day t+h-7 (weekly cycle)."""

    def __init__(self, horizon: int = FORECAST_HORIZON):
        self.horizon = horizon

    def predict(self, X: np.ndarray, target_indices: Optional[list] = None) -> np.ndarray:
        """
        X: (N, C, F)
        Returns: (N, horizon, 6)
        """
        target_idx = target_indices or list(range(NUM_TARGETS))
        N, C, F = X.shape
        preds = np.zeros((N, self.horizon, len(target_idx)), dtype=np.float32)

        for h in range(self.horizon):
            # 7 days prior in context: index C - 7 + h
            lag_idx = C - 7 + h
            if 0 <= lag_idx < C:
                preds[:, h, :] = X[:, lag_idx, target_idx]
            else:
                preds[:, h, :] = X[:, -1, target_idx]
        return preds


# ── 3. Classical Multi-Output Ridge Regression ──
class RidgeForecaster:
    """Multi-output linear model with L2 regularization over flattened context features."""

    def __init__(self, alpha: float = 10.0, horizon: int = FORECAST_HORIZON):
        self.alpha = alpha
        self.horizon = horizon
        self.model = Ridge(alpha=alpha, fit_intercept=True)
        self.is_fitted = False

    def fit(self, X: np.ndarray, Y: np.ndarray):
        """
        X: (N, C, F)
        Y: (N, horizon, 6)
        """
        N, C, F = X.shape
        X_flat = X.reshape(N, C * F)
        Y_flat = Y.reshape(N, self.horizon * NUM_TARGETS)
        self.model.fit(X_flat, Y_flat)
        self.is_fitted = True

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Returns: (N, horizon, 6)"""
        N, C, F = X.shape
        X_flat = X.reshape(N, C * F)
        pred_flat = self.model.predict(X_flat)
        return pred_flat.reshape(N, self.horizon, NUM_TARGETS)


# ── 4. Deep Learning: Multi-Output GRU ──
class GRUForecaster(nn.Module):
    """Multi-layer Gated Recurrent Unit with direct multi-horizon projection head."""

    def __init__(
        self,
        input_dim: int,
        hidden_dim: int = 64,
        num_layers: int = 2,
        dropout: float = 0.2,
        horizon: int = FORECAST_HORIZON,
        num_targets: int = NUM_TARGETS,
    ):
        super().__init__()
        self.horizon = horizon
        self.num_targets = num_targets
        self.gru = nn.GRU(
            input_size=input_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )
        self.head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, horizon * num_targets),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        x: (B, C, F)
        Returns: (B, horizon, 6)
        """
        out, _ = self.gru(x)
        # Use final context hidden state
        last_hidden = out[:, -1, :]  # (B, hidden_dim)
        preds_flat = self.head(last_hidden)  # (B, horizon * 6)
        return preds_flat.view(-1, self.horizon, self.num_targets)


# ── 5. Deep Learning: Temporal Convolutional Network (TCN) ──
class Chomp1d(nn.Module):
    """Trims trailing padding to ensure causality (no future leakage)."""

    def __init__(self, chomp_size: int):
        super().__init__()
        self.chomp_size = chomp_size

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x[:, :, :-self.chomp_size].contiguous() if self.chomp_size > 0 else x


class TemporalBlock(nn.Module):
    """Dilated causal residual block for TCN."""

    def __init__(
        self,
        n_inputs: int,
        n_outputs: int,
        kernel_size: int,
        stride: int,
        dilation: int,
        padding: int,
        dropout: float = 0.2,
    ):
        super().__init__()
        self.conv1 = nn.Conv1d(
            n_inputs, n_outputs, kernel_size,
            stride=stride, padding=padding, dilation=dilation
        )
        self.chomp1 = Chomp1d(padding)
        self.relu1 = nn.GELU()
        self.dropout1 = nn.Dropout(dropout)

        self.conv2 = nn.Conv1d(
            n_outputs, n_outputs, kernel_size,
            stride=stride, padding=padding, dilation=dilation
        )
        self.chomp2 = Chomp1d(padding)
        self.relu2 = nn.GELU()
        self.dropout2 = nn.Dropout(dropout)

        self.net = nn.Sequential(
            self.conv1, self.chomp1, self.relu1, self.dropout1,
            self.conv2, self.chomp2, self.relu2, self.dropout2,
        )
        self.downsample = nn.Conv1d(n_inputs, n_outputs, 1) if n_inputs != n_outputs else None
        self.relu = nn.GELU()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = self.net(x)
        res = x if self.downsample is None else self.downsample(x)
        return self.relu(out + res)


class TCNForecaster(nn.Module):
    """Causal Temporal Convolutional Network for multi-horizon forecasting."""

    def __init__(
        self,
        input_dim: int,
        num_channels: list = [32, 64, 64],
        kernel_size: int = 3,
        dropout: float = 0.2,
        horizon: int = FORECAST_HORIZON,
        num_targets: int = NUM_TARGETS,
    ):
        super().__init__()
        self.horizon = horizon
        self.num_targets = num_targets

        layers = []
        num_levels = len(num_channels)
        for i in range(num_levels):
            dilation_size = 2 ** i
            in_channels = input_dim if i == 0 else num_channels[i - 1]
            out_channels = num_channels[i]
            padding = (kernel_size - 1) * dilation_size
            layers.append(
                TemporalBlock(
                    in_channels, out_channels, kernel_size,
                    stride=1, dilation=dilation_size, padding=padding, dropout=dropout
                )
            )

        self.network = nn.Sequential(*layers)
        self.head = nn.Sequential(
            nn.Linear(num_channels[-1], 64),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(64, horizon * num_targets),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        x: (B, C, F) -> permute to (B, F, C) for 1D convolutions
        """
        x_perm = x.permute(0, 2, 1)
        out = self.network(x_perm)  # (B, hidden, C)
        last_step = out[:, :, -1]   # (B, hidden)
        preds_flat = self.head(last_step)
        return preds_flat.view(-1, self.horizon, self.num_targets)


# ── 6. Modern Deep Learning: PatchTST / Linear Transformer ──
class PatchEmbedding(nn.Module):
    """Extracts overlapping patches along the time dimension for each channel."""

    def __init__(self, patch_len: int = 6, stride: int = 3, d_model: int = 48):
        super().__init__()
        self.patch_len = patch_len
        self.stride = stride
        self.proj = nn.Linear(patch_len, d_model)

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, int]:
        """
        x: (B, C_len) for single channel
        Returns: (B, num_patches, d_model)
        """
        B, C_len = x.shape
        # Unfold into patches
        patches = x.unfold(dimension=-1, size=self.patch_len, step=self.stride)  # (B, num_patches, patch_len)
        num_patches = patches.size(1)
        embeddings = self.proj(patches)  # (B, num_patches, d_model)
        return embeddings, num_patches


class PatchTSTForecaster(nn.Module):
    """
    Patch Time Series Transformer with channel-independence and multi-head attention.
    State-of-the-art long-term and multi-horizon time-series representation.
    """

    def __init__(
        self,
        input_dim: int,
        context_length: int = 30,
        patch_len: int = 6,
        stride: int = 3,
        d_model: int = 48,
        n_heads: int = 4,
        num_layers: int = 2,
        dropout: float = 0.2,
        horizon: int = FORECAST_HORIZON,
        num_targets: int = NUM_TARGETS,
    ):
        super().__init__()
        self.input_dim = input_dim
        self.horizon = horizon
        self.num_targets = num_targets
        self.context_length = context_length

        # Channel-independent patching
        self.patch_embed = PatchEmbedding(patch_len=patch_len, stride=stride, d_model=d_model)

        # Calculate number of patches
        num_patches = (context_length - patch_len) // stride + 1
        self.pos_embed = nn.Parameter(torch.zeros(1, num_patches, d_model))
        nn.init.trunc_normal_(self.pos_embed, std=0.02)

        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=n_heads,
            dim_feedforward=d_model * 2,
            dropout=dropout,
            activation="gelu",
            batch_first=True,
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)

        # Multi-channel flattening projection to target horizons
        self.head = nn.Sequential(
            nn.Flatten(start_dim=1),
            nn.Linear(input_dim * num_patches * d_model, 128),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(128, horizon * num_targets),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        x: (B, C_len, F)
        """
        B, C_len, F = x.shape
        # Channel-independent patch representation
        channel_tokens = []
        for f in range(F):
            x_f = x[:, :, f]  # (B, C_len)
            tokens, _ = self.patch_embed(x_f)  # (B, num_patches, d_model)
            tokens = tokens + self.pos_embed
            tokens = self.transformer(tokens)  # (B, num_patches, d_model)
            channel_tokens.append(tokens)

        # Stack channels: (B, F, num_patches, d_model)
        stacked = torch.stack(channel_tokens, dim=1)
        preds_flat = self.head(stacked)  # (B, horizon * num_targets)
        return preds_flat.view(-1, self.horizon, self.num_targets)
