# Chartora — Screenshot + Historical Research

This version supports two workflows:

1. **Screenshot scanner:** upload a trading chart screenshot and get a visual estimate of trend, candle-color bias, structure and relative chart levels.
2. **Historical market analysis:** enter the ticker and compare the current market data against historical price structures.

## Run

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m uvicorn backend.main:app --reload
```

Open http://127.0.0.1:8000

### Screenshot workflow

Upload a PNG/JPG/WEBP screenshot, click **ANALYZE SCREENSHOT**, and review:

- detected trend
- visual confidence
- green/red candle-pixel balance
- recent-vs-earlier structure
- relative horizontal levels

### Important limitation

The screenshot scanner is a local computer-vision baseline. It does **not** know the exact price values from the screenshot, and its relative support/resistance levels are screen positions. For exact price levels and reliable historical matching, use the ticker cross-check.

A future production version can add OCR + a multimodal vision model to recover ticker, timeframe, price labels, indicators and candle structure more accurately. Historical results should always be validated with leakage-safe walk-forward testing and transaction costs.


## Public deployment
This project includes Render deployment configuration. After deployment, the host provides a public HTTPS URL that can be shared with other people.
