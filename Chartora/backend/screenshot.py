
from io import BytesIO
from PIL import Image
import numpy as np


def _mask_stats(arr):
    r = arr[:, :, 0].astype(np.int16)
    g = arr[:, :, 1].astype(np.int16)
    b = arr[:, :, 2].astype(np.int16)

    green = (g > 105) & (g > r * 1.12) & (g > b * 1.04)
    red = (r > 105) & (r > g * 1.20) & (r > b * 1.08)
    return green, red


def _x_centers(mask):
    h, w = mask.shape
    points = []
    for x in range(w):
        ys = np.flatnonzero(mask[:, x])
        if len(ys) >= 2:
            points.append((x, float(np.median(ys))))
    return points


def _trend(points, h):
    if len(points) < 20:
        return "Unclear", 0.0, 0.0

    xs = np.array([p[0] for p in points], dtype=float)
    ys = np.array([p[1] for p in points], dtype=float)
    slope = np.polyfit(xs, ys, 1)[0]
    # Positive price trend means screen y moves downward less / becomes smaller.
    normalized = -slope * len(xs) / max(h, 1)

    if normalized > 0.025:
        label = "Bullish"
    elif normalized < -0.025:
        label = "Bearish"
    else:
        label = "Sideways"

    residual = ys - np.polyval(np.polyfit(xs, ys, 1), xs)
    consistency = 1.0 - min(1.0, float(np.std(residual)) / max(h * 0.18, 1))
    strength = min(100.0, abs(normalized) * 900.0)
    confidence = min(100.0, 35 + strength * 0.55 + consistency * 25)
    return label, round(confidence, 1), round(normalized, 4)


def _levels(mask, h):
    ys = np.flatnonzero(mask)
    if len(ys) < 30:
        return []

    hist, edges = np.histogram(ys, bins=24, range=(0, h))
    # Pick the three strongest separated bins.
    candidates = np.argsort(hist)[::-1]
    chosen = []
    for idx in candidates:
        if hist[idx] == 0:
            continue
        center = (edges[idx] + edges[idx + 1]) / 2
        if all(abs(center - c) > h * 0.08 for c in chosen):
            chosen.append(center)
        if len(chosen) == 3:
            break

    # Convert screen position to a relative chart level:
    # 100 = top/high, 0 = bottom/low.
    return [
        {
            "relative_level": round(float((1 - c / h) * 100), 1),
            "screen_y": round(float(c), 1),
            "strength": int(hist[int(min(len(hist) - 1, max(0, np.searchsorted(edges, c) - 1)))]),
        }
        for c in chosen
    ]


def analyze_screenshot(file_bytes: bytes, filename: str = "chart.png"):
    try:
        image = Image.open(BytesIO(file_bytes)).convert("RGB")
    except Exception as exc:
        raise ValueError("The uploaded file is not a valid image.") from exc

    # Downsample for fast browser uploads while preserving chart structure.
    max_w = 1800
    if image.width > max_w:
        new_h = int(image.height * max_w / image.width)
        image = image.resize((max_w, new_h))

    arr = np.asarray(image)
    h, w = arr.shape[:2]

    # Ignore a little of the UI chrome around the edges.
    y0, y1 = int(h * 0.06), int(h * 0.94)
    x0, x1 = int(w * 0.03), int(w * 0.97)
    crop = arr[y0:y1, x0:x1]
    ch, cw = crop.shape[:2]

    green, red = _mask_stats(crop)
    green_count = int(green.sum())
    red_count = int(red.sum())
    total_colored = green_count + red_count

    green_points = _x_centers(green)
    red_points = _x_centers(red)
    all_points = _x_centers(green | red)

    trend, confidence, slope = _trend(all_points, ch)

    if total_colored < max(80, int(cw * 0.10)):
        quality = "Low"
        confidence = min(confidence, 35.0)
    elif total_colored < max(250, int(cw * 0.30)):
        quality = "Medium"
    else:
        quality = "Good"

    if green_count > red_count * 1.25:
        candle_bias = "Bullish candle bias"
    elif red_count > green_count * 1.25:
        candle_bias = "Bearish candle bias"
    else:
        candle_bias = "Balanced candle bias"

    # Recent-vs-earlier direction from colored-pixel median position.
    recent = all_points[int(len(all_points) * 0.65):] if all_points else []
    earlier = all_points[:int(len(all_points) * 0.35)] if all_points else []
    structure = "Not enough chart pixels"
    if len(recent) > 8 and len(earlier) > 8:
        recent_y = np.median([p[1] for p in recent])
        earlier_y = np.median([p[1] for p in earlier])
        delta = earlier_y - recent_y
        if delta > ch * 0.035:
            structure = "Price structure is higher on the right side"
        elif delta < -ch * 0.035:
            structure = "Price structure is lower on the right side"
        else:
            structure = "Price structure is broadly range-bound"

    levels = _levels(green | red, ch)

    if levels:
        # In screenshot-only mode these are relative chart levels, not prices.
        support = min(levels, key=lambda x: x["relative_level"])
        resistance = max(levels, key=lambda x: x["relative_level"])
    else:
        support = resistance = None

    return {
        "filename": filename,
        "image": {"width": int(image.width), "height": int(image.height)},
        "chart_detection": {
            "quality": quality,
            "confidence": round(float(confidence), 1),
            "colored_pixel_coverage": round(float(total_colored / max(1, ch * cw) * 100), 3),
        },
        "trend": trend,
        "trend_confidence": round(float(confidence), 1),
        "candle_bias": candle_bias,
        "green_candle_pixels": green_count,
        "red_candle_pixels": red_count,
        "structure": structure,
        "levels": levels,
        "relative_support": support,
        "relative_resistance": resistance,
        "notes": [
            "Screenshot analysis estimates visual structure from chart pixels; it does not recover exact OHLC values.",
            "Relative support/resistance levels are screen-position estimates, not price values.",
            "For exact historical pattern matching, enter the ticker and run the market-data analysis too.",
        ],
    }
