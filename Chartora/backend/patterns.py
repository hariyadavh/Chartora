import numpy as np
import pandas as pd


def zscore(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    s = np.std(x)
    if s < 1e-12:
        return np.zeros_like(x)
    return (x - np.mean(x)) / s


def normalized_shape(close: np.ndarray) -> np.ndarray:
    # Log-return accumulation removes most of the absolute price-level difference.
    close = np.asarray(close, dtype=float)
    base = max(close[0], 1e-12)
    return zscore(np.log(close / base))


def correlation(a: np.ndarray, b: np.ndarray) -> float:
    if np.std(a) < 1e-12 or np.std(b) < 1e-12:
        return 0.0
    c = np.corrcoef(a, b)[0, 1]
    return float(np.nan_to_num(c, nan=0.0))


def similarity_score(current: np.ndarray, candidate: np.ndarray) -> float:
    a = normalized_shape(current)
    b = normalized_shape(candidate)
    corr = max(-1.0, min(1.0, correlation(a, b)))
    distance = float(np.mean((a - b) ** 2))
    distance_score = 1.0 / (1.0 + distance)
    # Correlation captures shape; distance keeps extreme shape mismatches down.
    score = 0.72 * ((corr + 1) / 2) + 0.28 * distance_score
    return float(score)


def find_matches(
    df: pd.DataFrame,
    window: int = 60,
    forward: int = 20,
    top_n: int = 10,
    min_gap: int | None = None,
):
    if min_gap is None:
        min_gap = max(10, window // 3)

    if len(df) < window + forward + 50:
        raise ValueError("Not enough historical candles for this pattern window.")

    current = df["Close"].iloc[-window:].to_numpy(dtype=float)
    last_candidate_end = len(df) - window - forward

    candidates = []
    for end in range(window, last_candidate_end + 1):
        start = end - window
        score = similarity_score(current, df["Close"].iloc[start:end].to_numpy(dtype=float))

        # Exclude candidates too close to the current window.
        if end >= len(df) - window - min_gap:
            continue

        candidates.append((score, start, end))

    candidates.sort(reverse=True, key=lambda x: x[0])

    selected = []
    for score, start, end in candidates:
        if all(abs(end - other_end) >= min_gap for _, _, other_end in selected):
            selected.append((score, start, end))
        if len(selected) >= top_n:
            break

    matches = []
    for rank, (score, start, end) in enumerate(selected, start=1):
        entry = float(df["Close"].iloc[end - 1])
        future = df["Close"].iloc[end : end + forward].to_numpy(dtype=float)
        future_returns = future / entry - 1.0

        max_favorable = float(np.max(future_returns)) if len(future_returns) else 0.0
        max_adverse = float(np.min(future_returns)) if len(future_returns) else 0.0
        final_return = float(future_returns[-1]) if len(future_returns) else 0.0

        matches.append(
            {
                "rank": rank,
                "score": round(score * 100, 2),
                "date_start": str(df.index[start].date()),
                "date_end": str(df.index[end - 1].date()),
                "entry": entry,
                "return_after_window": round(final_return * 100, 3),
                "max_favorable": round(max_favorable * 100, 3),
                "max_adverse": round(max_adverse * 100, 3),
            }
        )

    return matches


def summarize_matches(matches):
    if not matches:
        return {
            "sample_size": 0,
            "up_probability": None,
            "down_probability": None,
            "flat_probability": None,
            "average_return": None,
            "median_return": None,
            "average_favorable": None,
            "average_adverse": None,
        }

    returns = np.array([m["return_after_window"] for m in matches], dtype=float)
    up = np.mean(returns > 0.5) * 100
    down = np.mean(returns < -0.5) * 100
    flat = 100 - up - down

    return {
        "sample_size": len(matches),
        "up_probability": round(float(up), 1),
        "down_probability": round(float(down), 1),
        "flat_probability": round(float(flat), 1),
        "average_return": round(float(np.mean(returns)), 3),
        "median_return": round(float(np.median(returns)), 3),
        "average_favorable": round(float(np.mean([m["max_favorable"] for m in matches])), 3),
        "average_adverse": round(float(np.mean([m["max_adverse"] for m in matches])), 3),
    }
