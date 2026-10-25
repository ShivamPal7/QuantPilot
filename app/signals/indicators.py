"""Pure technical and statistical indicators.

Per Section 8.1 of agent.md:
Zero side effects, zero I/O, deterministic, pure mathematical functions.
Operates on lists of numbers or Candle sequences strictly up to current candle.
"""

from __future__ import annotations

import math
from decimal import Decimal
from typing import Sequence

from app.core.contracts import Candle


def _to_float_list(values: Sequence[float | Decimal]) -> list[float]:
    return [float(v) for v in values]


def sma(values: Sequence[float | Decimal], period: int) -> list[float]:
    """Compute Simple Moving Average across sequence.

    Indices before period - 1 return float('nan').
    """
    floats = _to_float_list(values)
    n = len(floats)
    result = [float("nan")] * n
    if period <= 0 or n < period:
        return result

    running_sum = sum(floats[:period])
    result[period - 1] = running_sum / period

    for i in range(period, n):
        running_sum += floats[i] - floats[i - period]
        result[i] = running_sum / period

    return result


def sma_latest(values: Sequence[float | Decimal], period: int) -> float:
    """Compute latest SMA value over the last `period` elements."""
    if len(values) < period or period <= 0:
        return float("nan")
    subset = [float(v) for v in values[-period:]]
    return sum(subset) / period


def ema(values: Sequence[float | Decimal], period: int) -> list[float]:
    """Compute Exponential Moving Average across sequence using alpha = 2 / (period + 1).

    First value at index period - 1 is seeded by SMA.
    """
    floats = _to_float_list(values)
    n = len(floats)
    result = [float("nan")] * n
    if period <= 0 or n < period:
        return result

    alpha = 2.0 / (period + 1.0)
    # Seed with SMA
    current_ema = sum(floats[:period]) / period
    result[period - 1] = current_ema

    for i in range(period, n):
        current_ema = alpha * floats[i] + (1.0 - alpha) * current_ema
        result[i] = current_ema

    return result


def ema_latest(values: Sequence[float | Decimal], period: int) -> float:
    """Compute latest EMA value."""
    res = ema(values, period)
    return res[-1] if res else float("nan")


def true_range(candles: Sequence[Candle]) -> list[float]:
    """Compute True Range sequence for candles."""
    n = len(candles)
    if n == 0:
        return []
    tr_list: list[float] = [float(candles[0].high - candles[0].low)]
    for i in range(1, n):
        curr = candles[i]
        prev = candles[i - 1]
        hl = float(curr.high - curr.low)
        hc = abs(float(curr.high - prev.close))
        lc = abs(float(curr.low - prev.close))
        tr_list.append(max(hl, hc, lc))
    return tr_list


def atr(candles: Sequence[Candle], period: int = 14) -> list[float]:
    """Compute Wilder's Average True Range.

    Indices before period - 1 return float('nan').
    """
    n = len(candles)
    result = [float("nan")] * n
    if period <= 0 or n < period:
        return result

    tr = true_range(candles)
    # First ATR is simple average of first `period` true ranges
    current_atr = sum(tr[:period]) / period
    result[period - 1] = current_atr

    for i in range(period, n):
        current_atr = (current_atr * (period - 1) + tr[i]) / period
        result[i] = current_atr

    return result


def atr_latest(candles: Sequence[Candle], period: int = 14) -> float:
    """Compute latest ATR value."""
    res = atr(candles, period)
    return res[-1] if res else float("nan")


def rolling_std(values: Sequence[float | Decimal], period: int) -> list[float]:
    """Compute rolling population standard deviation over period."""
    floats = _to_float_list(values)
    n = len(floats)
    result = [float("nan")] * n
    if period <= 1 or n < period:
        return result

    for i in range(period - 1, n):
        window = floats[i - period + 1 : i + 1]
        mean = sum(window) / period
        variance = sum((x - mean) ** 2 for x in window) / period
        result[i] = math.sqrt(variance)

    return result


def rolling_std_latest(values: Sequence[float | Decimal], period: int) -> float:
    """Compute latest standard deviation over the last `period` elements."""
    if len(values) < period or period <= 1:
        return float("nan")
    window = [float(x) for x in values[-period:]]
    mean = sum(window) / period
    variance = sum((x - mean) ** 2 for x in window) / period
    return math.sqrt(variance)


def z_score(values: Sequence[float | Decimal], period: int) -> float:
    """Compute z-score of the latest value relative to mean and std over the lookback window.

    Returns:
        float: (latest - mean) / std, or 0.0 if standard deviation is zero.
    """
    if len(values) < period or period <= 1:
        return 0.0

    window = [float(x) for x in values[-period:]]
    latest = window[-1]
    mean = sum(window) / period
    variance = sum((x - mean) ** 2 for x in window) / period
    std = math.sqrt(variance)

    if std < 1e-9:
        return 0.0
    return (latest - mean) / std


def variance_ratio(values: Sequence[float | Decimal], k: int = 2, period: int = 20) -> float:
    """Compute Lo-MacKinlay Variance Ratio test for mean reversion vs random walk.

    VR(k) = Var(r_k) / (k * Var(r_1))
    - VR(k) < 1.0: Mean reverting (negative autocorrelation)
    - VR(k) = 1.0: Random walk
    - VR(k) > 1.0: Trending / Momentum (positive autocorrelation)
    """
    if len(values) < period + k or period <= 2 or k <= 1:
        return 1.0

    floats = [float(v) for v in values[-(period + k) :]]

    # 1-period returns
    r1 = [floats[i] - floats[i - 1] for i in range(1, len(floats))]
    # k-period returns
    rk = [floats[i] - floats[i - k] for i in range(k, len(floats))]

    if len(r1) < 2 or len(rk) < 2:
        return 1.0

    mean_r1 = sum(r1) / len(r1)
    var_r1 = sum((x - mean_r1) ** 2 for x in r1) / (len(r1) - 1)

    mean_rk = sum(rk) / len(rk)
    var_rk = sum((x - mean_rk) ** 2 for x in rk) / (len(rk) - 1)

    if var_r1 < 1e-12:
        return 1.0

    vr = var_rk / (float(k) * var_r1)
    return vr


def adx(candles: Sequence[Candle], period: int = 14) -> float:
    """Compute Wilder's Average Directional Index (ADX) over candles."""
    n = len(candles)
    if n < period * 2:
        return 20.0  # Default neutral reading if insufficient data

    tr_list = []
    pdm_list = []
    mdm_list = []

    for i in range(1, n):
        curr = candles[i]
        prev = candles[i - 1]

        h_diff = float(curr.high - prev.high)
        l_diff = float(prev.low - curr.low)

        pdm = h_diff if (h_diff > l_diff and h_diff > 0) else 0.0
        mdm = l_diff if (l_diff > h_diff and l_diff > 0) else 0.0

        hl = float(curr.high - curr.low)
        hc = abs(float(curr.high - prev.close))
        lc = abs(float(curr.low - prev.close))
        tr = max(hl, hc, lc)

        tr_list.append(tr)
        pdm_list.append(pdm)
        mdm_list.append(mdm)

    if len(tr_list) < period:
        return 20.0

    # Initial sum
    smooth_tr = sum(tr_list[:period])
    smooth_pdm = sum(pdm_list[:period])
    smooth_mdm = sum(mdm_list[:period])

    dx_list = []
    for i in range(period, len(tr_list)):
        smooth_tr = smooth_tr - (smooth_tr / period) + tr_list[i]
        smooth_pdm = smooth_pdm - (smooth_pdm / period) + pdm_list[i]
        smooth_mdm = smooth_mdm - (smooth_mdm / period) + mdm_list[i]

        pdi = (smooth_pdm / smooth_tr * 100.0) if smooth_tr > 1e-9 else 0.0
        mdi = (smooth_mdm / smooth_tr * 100.0) if smooth_tr > 1e-9 else 0.0

        denom = pdi + mdi
        dx = (abs(pdi - mdi) / denom * 100.0) if denom > 1e-9 else 0.0
        dx_list.append(dx)

    if not dx_list:
        return 20.0

    if len(dx_list) < period:
        return sum(dx_list) / len(dx_list)

    adx_val = sum(dx_list[:period]) / period
    for i in range(period, len(dx_list)):
        adx_val = (adx_val * (period - 1) + dx_list[i]) / period

    return adx_val

