from pathlib import Path
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .data import get_market_data
from .indicators import add_indicators
from .patterns import find_matches, summarize_matches
from .screenshot import analyze_screenshot

BASE = Path(__file__).resolve().parent.parent
FRONTEND = BASE / "frontend"

app = FastAPI(title="Market Pattern AI", version="1.0.0")

app.mount("/static", StaticFiles(directory=str(FRONTEND)), name="static")


@app.get("/")
def home():
    return FileResponse(FRONTEND / "index.html")


def fmt_date(x):
    return pd.Timestamp(x).strftime("%Y-%m-%d")


def safe_float(x, digits=4):
    if x is None or pd.isna(x):
        return None
    return round(float(x), digits)


@app.get("/api/analyze")
def analyze(
    symbol: str = "BTC-USD",
    period: str = "5y",
    interval: str = "1d",
    window: int = 60,
    forward: int = 20,
    top_n: int = 10,
):
    try:
        if not (20 <= window <= 300):
            raise ValueError("Pattern window must be between 20 and 300 candles.")
        if not (5 <= forward <= 100):
            raise ValueError("Forward outcome window must be between 5 and 100 candles.")
        if not (3 <= top_n <= 20):
            raise ValueError("Number of matches must be between 3 and 20.")

        raw = get_market_data(symbol, period, interval)
        df = add_indicators(raw)

        minimum = window + forward + 250
        if len(df) < minimum:
            raise ValueError(
                f"Only {len(df)} candles are available. At least {minimum} are recommended. "
                "Choose a longer period or a shorter pattern window."
            )

        matches = find_matches(df, window, forward, top_n)
        summary = summarize_matches(matches)

        latest = df.iloc[-1]
        prev = df.iloc[-2]

        close = float(latest["Close"])
        atr = float(latest["ATR14"]) if pd.notna(latest["ATR14"]) else 0.0
        atr_pct = float(latest["ATR_Pct"]) if pd.notna(latest["ATR_Pct"]) else 0.0
        rsi = float(latest["RSI14"]) if pd.notna(latest["RSI14"]) else 50.0
        vol = float(latest["Volatility20"]) if pd.notna(latest["Volatility20"]) else 0.0

        if close > float(latest["SMA50"]) > float(latest["SMA200"]):
            trend = "Bullish"
        elif close < float(latest["SMA50"]) < float(latest["SMA200"]):
            trend = "Bearish"
        else:
            trend = "Mixed"

        if atr_pct >= 4:
            volatility_label = "High"
        elif atr_pct >= 2:
            volatility_label = "Medium"
        else:
            volatility_label = "Low"

        volume_ratio = float(latest["VolumeRatio"]) if pd.notna(latest["VolumeRatio"]) else 1.0
        momentum = "Positive" if rsi >= 55 else "Negative" if rsi <= 45 else "Neutral"

        # Scenario levels are ATR-based research levels, not recommendations.
        entry = close
        target = close + (1.5 * atr if summary["average_return"] is None or summary["average_return"] >= 0 else -1.5 * atr)
        invalidation = close - atr if target >= close else close + atr

        # Keep the chart compact for browser performance.
        chart_df = df.tail(min(250, len(df))).copy()
        chart = []
        for idx, row in chart_df.iterrows():
            chart.append({
                "time": fmt_date(idx),
                "open": safe_float(row["Open"], 6),
                "high": safe_float(row["High"], 6),
                "low": safe_float(row["Low"], 6),
                "close": safe_float(row["Close"], 6),
                "volume": safe_float(row["Volume"], 2),
                "sma20": safe_float(row["SMA20"], 6),
                "sma50": safe_float(row["SMA50"], 6),
            })

        return {
            "symbol": symbol.upper(),
            "interval": interval,
            "period": period,
            "data_points": len(df),
            "last_candle": fmt_date(df.index[-1]),
            "price": safe_float(close, 8),
            "trend": trend,
            "volatility": volatility_label,
            "volatility_percent": safe_float(vol, 3),
            "atr_percent": safe_float(atr_pct, 3),
            "rsi": safe_float(rsi, 2),
            "momentum": momentum,
            "volume_ratio": safe_float(volume_ratio, 2),
            "pattern_similarity": matches[0]["score"] if matches else None,
            "historical": summary,
            "scenario": {
                "entry": safe_float(entry, 8),
                "target": safe_float(target, 8),
                "invalidation": safe_float(invalidation, 8),
            },
            "matches": matches,
            "chart": chart,
        }

    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/analyze-screenshot")
async def analyze_uploaded_screenshot(file: UploadFile = File(...)):
    """Analyze a trading-chart screenshot using local computer-vision heuristics."""
    allowed = {"image/png", "image/jpeg", "image/webp", "image/jpg"}
    if file.content_type not in allowed:
        raise HTTPException(status_code=400, detail="Please upload a PNG, JPG, or WEBP chart screenshot.")

    try:
        data = await file.read()
        if len(data) > 12 * 1024 * 1024:
            raise ValueError("Image is too large. Please keep it below 12 MB.")
        return analyze_screenshot(data, file.filename or "chart.png")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
