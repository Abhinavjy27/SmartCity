"""
Unified Spatial-Temporal Forecasting Models for Hyderabad CAAQMS Network.

First-Run Graph Construction Disclosure (Issue 2):
In the initial run, the GAT graph was fully connected (complete graph K_13) and unweighted
by adjacency thresholding. All 13 stations attended to each other with an unconstrained soft
penalty -|lambda| * (D_ij / mean_D) applied to dot-product logits. It was neither thresholded
nor sparse, allowing distant stations (e.g. Bollaram to Zoo Park, 39.05 km) direct dense
attention paths.

Corrected Implementations:
1. SpatialTemporalGATGRU (Weighted Adjacency Retry):
   - Adjacency matrix constructed via Gaussian kernel on Haversine distance:
     A_ij = exp(-D_ij^2 / (2 * sigma^2)) with sigma = 12.0 km.
   - Non-edges strictly pruned where D_ij > 25.0 km (unless j is in KNN(i, 3)),
     and masked to -1e9 in attention logits (giving 0.0 attention weight).
   - Additive distance prior alpha * log(A_ij) biases attention inversely with distance.
2. TemporalGRU_KNNCovariate (Simpler Spatial Baseline):
   - Isolates whether ANY spatial signal helps before concluding GAT does or doesn't.
   - Computes distance-weighted KNN (k=3) average of neighboring stations' 6 criteria
     pollutant concentrations and appends them as 6 spatial covariates (total 24 features)
     into a 2-layer Temporal GRU.
3. TemporalOnlyGRU:
   - Pure temporal baseline with 18 local features and no spatial cross-talk.
4. Chronos2CovariateForecaster:
   - Official amazon/chronos-2 foundation model in multivariate mode with
     meteorological past_covariates (AT, RH, WS, BP, SR).
5. PersistenceForecaster: Naive persistence baseline.
6. SeasonalNaiveForecaster: 7-day lag seasonal baseline.
"""
import math
from typing import Optional, Dict, Any, List

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from .config import (
    NUM_STATIONS,
    NUM_FEATURES,
    NUM_TARGETS,
    FORECAST_HORIZON,
    DISTANCE_MATRIX,
)


def compute_gaussian_adjacency(
    sigma_km: float = 12.0,
    max_dist_km: float = 25.0,
    k_nearest: int = 3,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Computes:
    1. Distance-weighted Gaussian adjacency matrix A_ij = exp(-D_ij^2 / (2*sigma^2))
    2. Adjacency binary mask (retaining edges <= max_dist_km and top-k neighbors)
    3. Log-adjacency for attention logit modulation
    4. KNN (k=3) neighbor indices and normalized inverse-distance weights
    """
    dist = DISTANCE_MATRIX
    gauss = np.exp(-(dist ** 2) / (2.0 * (sigma_km ** 2)))
    adj = np.zeros_like(gauss)

    knn_indices = []
    knn_weights = []

    for i in range(NUM_STATIONS):
        sorted_nbrs = np.argsort(dist[i])  # 0 is self
        top_k = sorted_nbrs[1 : k_nearest + 1]
        knn_indices.append(top_k)

        inv_d = 1.0 / (dist[i, top_k] + 1e-3)
        w = inv_d / np.sum(inv_d)
        knn_weights.append(w)

        for j in range(NUM_STATIONS):
            if i == j or dist[i, j] <= max_dist_km or j in top_k:
                adj[i, j] = gauss[i, j]

    adj_mask = (adj > 0.0)
    log_adj = np.where(adj_mask, np.log(adj + 1e-8), -1e9)

    return (
        adj.astype(np.float32),
        adj_mask,
        log_adj.astype(np.float32),
        np.array(knn_indices, dtype=np.int64),
        np.array(knn_weights, dtype=np.float32),
    )


ADJ_MATRIX, ADJ_MASK, LOG_ADJ, KNN_INDICES, KNN_WEIGHTS = compute_gaussian_adjacency()


class DistanceWeightedGraphAttentionLayer(nn.Module):
    """
    Multi-Head Graph Attention Layer with physical geodesic Gaussian distance-weighted adjacency.
    Nodes: 13 Hyderabad CAAQMS stations.
    Graph is NOT fully connected: edges with distance > 25 km (not in top-3 KNN) are masked to -1e9.
    Attention weights are inversely proportional to Haversine distance.
    """

    def __init__(
        self,
        in_dim: int,
        out_dim: int,
        num_heads: int = 4,
        dropout: float = 0.1,
    ):
        super().__init__()
        assert out_dim % num_heads == 0, "out_dim must be divisible by num_heads"
        self.num_heads = num_heads
        self.head_dim = out_dim // num_heads
        self.scale = 1.0 / math.sqrt(self.head_dim)

        self.q_proj = nn.Linear(in_dim, out_dim)
        self.k_proj = nn.Linear(in_dim, out_dim)
        self.v_proj = nn.Linear(in_dim, out_dim)
        self.out_proj = nn.Linear(out_dim, out_dim)

        self.dropout = nn.Dropout(dropout)

        # Learnable distance prior scaling factor (constrained positive)
        self.distance_scale = nn.Parameter(torch.tensor(0.5, dtype=torch.float32))

        # Register buffers for Gaussian log-adjacency and edge mask
        self.register_buffer("log_adj", torch.tensor(LOG_ADJ, dtype=torch.float32))
        self.register_buffer("adj_mask", torch.tensor(ADJ_MASK, dtype=torch.bool))

    def forward(self, h: torch.Tensor) -> torch.Tensor:
        """
        h: (Batch, Num_Stations=13, In_Dim)
        Returns: (Batch, Num_Stations=13, Out_Dim)
        """
        B, N, _ = h.shape

        q = self.q_proj(h).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)  # (B, H, N, d)
        k = self.k_proj(h).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)  # (B, H, N, d)
        v = self.v_proj(h).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)  # (B, H, N, d)

        # Scaled Dot-Product Attention: (B, H, N, N)
        attn_scores = torch.matmul(q, k.transpose(-2, -1)) * self.scale

        # Distance-weighted prior: Gaussian kernel log-weight biases attention inversely with distance
        spatial_bias = torch.abs(self.distance_scale) * self.log_adj.unsqueeze(0).unsqueeze(0)
        attn_scores = attn_scores + spatial_bias

        # Strict topological masking: non-edges masked to -1e9 (0.0 softmax weight)
        attn_scores = attn_scores.masked_fill(~self.adj_mask.unsqueeze(0).unsqueeze(0), -1e9)

        attn_weights = F.softmax(attn_scores, dim=-1)
        attn_weights = self.dropout(attn_weights)

        # Aggregate neighbor representations
        out = torch.matmul(attn_weights, v)  # (B, H, N, d)
        out = out.transpose(1, 2).contiguous().view(B, N, self.num_heads * self.head_dim)
        return self.out_proj(out)


class SpatialTemporalGATGRU(nn.Module):
    """
    Spatial-Temporal Graph Neural Network with distance-weighted adjacency.
    Combines per-station temporal GRU encoding with distance-weighted Graph Attention.
    """

    def __init__(
        self,
        num_stations: int = NUM_STATIONS,
        in_features: int = NUM_FEATURES,
        hidden_dim: int = 64,
        num_gru_layers: int = 2,
        num_gat_heads: int = 4,
        horizon: int = FORECAST_HORIZON,
        num_targets: int = NUM_TARGETS,
        dropout: float = 0.15,
    ):
        super().__init__()
        self.num_stations = num_stations
        self.horizon = horizon
        self.num_targets = num_targets

        self.temporal_gru = nn.GRU(
            input_size=in_features,
            hidden_size=hidden_dim,
            num_layers=num_gru_layers,
            batch_first=True,
            dropout=dropout if num_gru_layers > 1 else 0.0,
        )

        self.gat = DistanceWeightedGraphAttentionLayer(
            in_dim=hidden_dim,
            out_dim=hidden_dim,
            num_heads=num_gat_heads,
            dropout=dropout,
        )
        self.norm = nn.LayerNorm(hidden_dim)

        self.head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, horizon * num_targets),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        x: (Batch, Num_Stations=13, Context_Len=14, Features=18)
        Returns: (Batch, Num_Stations=13, Horizon=7, Targets=6)
        """
        B, N, C, F_dim = x.shape
        x_flat = x.view(B * N, C, F_dim)
        out_gru, _ = self.temporal_gru(x_flat)
        h_temp = out_gru[:, -1, :].view(B, N, -1)  # (B, 13, hidden_dim)

        h_spatial = self.gat(h_temp)
        z = self.norm(h_temp + h_spatial)

        preds_flat = self.head(z)
        return preds_flat.view(B, N, self.horizon, self.num_targets)


class TemporalOnlyGRU(nn.Module):
    """
    Pure Temporal Baseline: Exact same GRU architecture as SpatialTemporalGATGRU,
    without any spatial communication (no-graph ablation).
    """

    def __init__(
        self,
        num_stations: int = NUM_STATIONS,
        in_features: int = NUM_FEATURES,
        hidden_dim: int = 64,
        num_gru_layers: int = 2,
        horizon: int = FORECAST_HORIZON,
        num_targets: int = NUM_TARGETS,
        dropout: float = 0.15,
    ):
        super().__init__()
        self.num_stations = num_stations
        self.horizon = horizon
        self.num_targets = num_targets

        self.temporal_gru = nn.GRU(
            input_size=in_features,
            hidden_size=hidden_dim,
            num_layers=num_gru_layers,
            batch_first=True,
            dropout=dropout if num_gru_layers > 1 else 0.0,
        )

        self.head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, horizon * num_targets),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        x: (Batch, Num_Stations=13, Context_Len=14, Features=18)
        Returns: (Batch, Num_Stations=13, Horizon=7, Targets=6)
        """
        B, N, C, F_dim = x.shape
        x_flat = x.view(B * N, C, F_dim)
        out_gru, _ = self.temporal_gru(x_flat)
        last_h = out_gru[:, -1, :].view(B, N, -1)

        preds_flat = self.head(last_h)
        return preds_flat.view(B, N, self.horizon, self.num_targets)


class TemporalGRU_KNNCovariate(nn.Module):
    """
    Simpler Spatial Baseline (Issue 2):
    Calculates a distance-weighted k-nearest-neighbors average (k=3) of neighboring
    stations' criteria pollutant values (PM2.5, PM10, NO2, SO2, CO, O3) and appends
    them as 6 spatial covariate features to TemporalOnlyGRU (total 18 + 6 = 24 features).
    Isolates whether ANY spatial signal helps without the full GAT parameter overhead.
    """

    def __init__(
        self,
        num_stations: int = NUM_STATIONS,
        base_features: int = NUM_FEATURES,
        knn_features: int = NUM_TARGETS,
        hidden_dim: int = 64,
        num_gru_layers: int = 2,
        horizon: int = FORECAST_HORIZON,
        num_targets: int = NUM_TARGETS,
        dropout: float = 0.15,
    ):
        super().__init__()
        self.num_stations = num_stations
        self.horizon = horizon
        self.num_targets = num_targets
        in_features = base_features + knn_features  # 18 + 6 = 24

        # Register precomputed KNN neighbor indices and inverse-distance weights
        self.register_buffer("knn_indices", torch.tensor(KNN_INDICES, dtype=torch.long))  # (13, 3)
        self.register_buffer("knn_weights", torch.tensor(KNN_WEIGHTS, dtype=torch.float32))  # (13, 3)

        self.temporal_gru = nn.GRU(
            input_size=in_features,
            hidden_size=hidden_dim,
            num_layers=num_gru_layers,
            batch_first=True,
            dropout=dropout if num_gru_layers > 1 else 0.0,
        )

        self.head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, horizon * num_targets),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        x: (Batch, Num_Stations=13, Context_Len=14, Features=18)
        Returns: (Batch, Num_Stations=13, Horizon=7, Targets=6)
        """
        B, N, C, F_dim = x.shape

        # Extract criteria pollutants (first 6 features) from all stations: (B, 13, 14, 6)
        # Gather neighbors for each station: (B, 13, 3, 14, 6)
        nbrs = x[:, self.knn_indices, :, : self.num_targets]

        # Weight by normalized inverse geodesic distances: (1, 13, 3, 1, 1)
        w_expanded = self.knn_weights.unsqueeze(0).unsqueeze(-1).unsqueeze(-1)
        spatial_covariates = (nbrs * w_expanded).sum(dim=2)  # (B, 13, 14, 6)

        # Concatenate 6 spatial covariates to 18 local features -> (B, 13, 14, 24)
        x_aug = torch.cat([x, spatial_covariates], dim=-1)

        x_flat = x_aug.view(B * N, C, -1)
        out_gru, _ = self.temporal_gru(x_flat)
        last_h = out_gru[:, -1, :].view(B, N, -1)

        preds_flat = self.head(last_h)
        return preds_flat.view(B, N, self.horizon, self.num_targets)


class PersistenceForecaster:
    """
    Naive Persistence: Forecasts Day t+1 to t+7 as the last observed value at day t.
    """

    def __init__(self, horizon: int = FORECAST_HORIZON):
        self.horizon = horizon

    def predict(self, x: np.ndarray, target_indices: Optional[List[int]] = None) -> np.ndarray:
        """
        x: (Batch, Stations=13, Context=14, Features=18)
        Returns: (Batch, Stations=13, Horizon=7, Targets=6)
        """
        target_idx = target_indices or list(range(NUM_TARGETS))
        last_vals = x[:, :, -1, target_idx]  # (Batch, 13, 6)
        return np.repeat(last_vals[:, :, np.newaxis, :], self.horizon, axis=2)


class SeasonalNaiveForecaster:
    """
    Seasonal Naive: Forecasts Day t+h as Day t+h-7 (weekly cycle lag).
    """

    def __init__(self, horizon: int = FORECAST_HORIZON):
        self.horizon = horizon

    def predict(self, x: np.ndarray, target_indices: Optional[List[int]] = None) -> np.ndarray:
        """
        x: (Batch, Stations=13, Context=14, Features=18)
        Returns: (Batch, Stations=13, Horizon=7, Targets=6)
        """
        target_idx = target_indices or list(range(NUM_TARGETS))
        B, N, C, _ = x.shape
        preds = np.zeros((B, N, self.horizon, len(target_idx)), dtype=np.float32)

        for h in range(self.horizon):
            lag_idx = C - 7 + h
            if 0 <= lag_idx < C:
                preds[:, :, h, :] = x[:, :, lag_idx, target_idx]
            else:
                preds[:, :, h, :] = x[:, :, -1, target_idx]
        return preds


class Chronos2CovariateForecaster:
    """
    Official Pretrained Baseline (Issue 3):
    Runs amazon/chronos-2 foundation model in multivariate mode with
    meteorological past_covariates (AT, RH, WS, BP, SR).
    Replaces earlier unflagged substitution of chronos-bolt-tiny.
    """

    def __init__(
        self,
        model_name: str = "amazon/chronos-2",
        horizon: int = FORECAST_HORIZON,
        batch_size: int = 52,
    ):
        self.model_name = model_name
        self.horizon = horizon
        self.batch_size = batch_size
        self.pipeline = None

    def load(self):
        if self.pipeline is None:
            from chronos import Chronos2Pipeline
            self.pipeline = Chronos2Pipeline.from_pretrained(
                self.model_name,
                local_files_only=True,
                device_map="cpu",
                dtype=torch.float32,
            )

    def predict(self, x: np.ndarray, target_indices: Optional[List[int]] = None) -> np.ndarray:
        """
        x: (Batch, Stations=13, Context=14, Features=18)
        Returns: (Batch, Stations=13, Horizon=7, Targets=6)
        """
        self.load()
        target_idx = target_indices or list(range(NUM_TARGETS))
        B, N, C, _ = x.shape
        T_len = len(target_idx)

        # Prepare inputs with meteorological past covariates for each pollutant target
        # Feature mapping: 0..6 pollutants (target_idx are 0..5), 7..11 meteo
        items = []
        for b in range(B):
            for s in range(N):
                past_covs = {
                    "AT": torch.tensor(x[b, s, :, 7], dtype=torch.float32),
                    "RH": torch.tensor(x[b, s, :, 8], dtype=torch.float32),
                    "WS": torch.tensor(x[b, s, :, 9], dtype=torch.float32),
                    "BP": torch.tensor(x[b, s, :, 10], dtype=torch.float32),
                    "SR": torch.tensor(x[b, s, :, 11], dtype=torch.float32),
                }
                for t in target_idx:
                    items.append({
                        "target": torch.tensor(x[b, s, :, t], dtype=torch.float32),
                        "past_covariates": past_covs,
                    })

        with torch.no_grad():
            fcsts = self.pipeline.predict(
                items,
                prediction_length=self.horizon,
                batch_size=128,
            )

        # Reconstruct (B, N, Horizon=7, Targets=6)
        # Each fcsts[idx] has shape (1, 21, 7) where index 10 is median (0.50) point prediction
        preds = np.zeros((B, N, self.horizon, T_len), dtype=np.float32)
        idx = 0
        for b in range(B):
            for s in range(N):
                for t_pos in range(T_len):
                    median_point = fcsts[idx][0, 10, :].cpu().numpy()  # (7,)
                    preds[b, s, :, t_pos] = np.clip(median_point, 0.0, None)
                    idx += 1

        return preds
