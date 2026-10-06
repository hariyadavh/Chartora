
const $ = id => document.getElementById(id);
let latestMarket = null;

const money = x => x == null ? "—" : Number(x).toLocaleString(undefined,{maximumFractionDigits:4});
const pct = x => x == null ? "—" : `${Number(x).toFixed(1)}%`;
const set = (id,v) => { if ($(id)) $(id).textContent = v; };

function showLoading(title, text){
  $("loadingTitle").textContent = title;
  $("loadingText").textContent = text;
  $("loading").classList.remove("hidden");
}
function hideLoading(){ $("loading").classList.add("hidden"); }
function showError(msg){ $("error").textContent = msg; $("error").classList.remove("hidden"); }
function clearError(){ $("error").classList.add("hidden"); }

function renderScreenshot(d){
  set("visualTrend", d.trend);
  set("quality", d.chart_detection.quality.toUpperCase());
  set("quality2", d.chart_detection.quality.toUpperCase());
  set("confidence", `${d.trend_confidence}%`);
  set("score", `${d.trend_confidence}%`);
  set("scoreSmall", `${Math.round(d.trend_confidence)}%`);
  set("scoreBar", "");
  $("scoreBar").style.width = `${d.trend_confidence}%`;
  set("candleBias", d.candle_bias.replace(" candle bias",""));
  set("structureShort", d.structure.replace("Price structure is ","").replace("Price ",""));
  set("coverage", `${d.chart_detection.colored_pixel_coverage}%`);
  set("dimensions", `${d.image.width} × ${d.image.height}`);
  set("stateTrend", d.trend);
  set("stateBias", d.candle_bias);
  set("stateStructure", d.structure);
  set("greenPixels", d.green_candle_pixels.toLocaleString());
  set("redPixels", d.red_candle_pixels.toLocaleString());

  const levels = $("levels");
  levels.innerHTML = "";
  if (!d.levels.length){
    levels.innerHTML = `<div class="level-empty">No strong horizontal chart levels were detected.</div>`;
  } else {
    d.levels.forEach((l,i)=>{
      const div = document.createElement("div");
      div.className = "level-card";
      div.innerHTML = `<span>LEVEL ${i+1}</span><strong>${l.relative_level}%</strong><small>relative screen height · strength ${l.strength}</small>`;
      levels.appendChild(div);
    });
  }
}

async function scanScreenshot(){
  clearError();
  const file = $("chartFile").files[0];
  if (!file){ showError("Choose a chart screenshot first."); return; }
  const fd = new FormData();
  fd.append("file", file);
  showLoading("Analyzing screenshot", "Detecting visible candles, trend and chart structure...");
  $("scan").disabled = true;
  try{
    const r = await fetch("/api/analyze-screenshot", {method:"POST", body:fd});
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || "Screenshot analysis failed.");
    renderScreenshot(d);
  }catch(e){ showError(e.message); }
  finally{ $("scan").disabled=false; hideLoading(); }
}

async function marketAnalyze(){
  clearError();
  showLoading("Comparing historical patterns", "Downloading market data and searching prior structures...");
  $("marketAnalyze").disabled=true;
  const q = new URLSearchParams({
    symbol:$("symbol").value.trim(),
    period:$("period").value,
    interval:$("interval").value,
    window:$("window").value,
    forward:$("forward").value,
    top_n:"10"
  });
  try{
    const r=await fetch(`/api/analyze?${q}`), d=await r.json();
    if(!r.ok) throw new Error(d.detail||"Historical analysis failed.");
    latestMarket=d;
    $("marketResults").classList.remove("hidden");
    set("assetName",d.symbol); set("price",money(d.price)); set("trend",d.trend);
    set("rsi",d.rsi); set("momentum",d.momentum); set("volatility",d.volatility);
    set("similarity", d.pattern_similarity == null ? "—" : `${d.pattern_similarity}%`);
    $("marketBar").style.width = `${Math.min(100, Math.max(0, d.pattern_similarity || 0))}%`;
    set("cases",d.historical.sample_size);
    const bias=d.historical.up_probability>d.historical.down_probability?"BULLISH":d.historical.down_probability>d.historical.up_probability?"BEARISH":"MIXED";
    set("bias",bias);
    set("up",pct(d.historical.up_probability)); set("down",pct(d.historical.down_probability)); set("flat",pct(d.historical.flat_probability));
    set("avgReturn",pct(d.historical.average_return)); set("medianReturn",pct(d.historical.median_return));
    set("favorable",pct(d.historical.average_favorable)); set("adverse",pct(d.historical.average_adverse));
    set("entry",money(d.scenario.entry)); set("target",money(d.scenario.target)); set("invalidation",money(d.scenario.invalidation));
    $("marketResults").scrollIntoView({behavior:"smooth",block:"start"});
  }catch(e){ showError(e.message); }
  finally{ $("marketAnalyze").disabled=false; hideLoading(); }
}

$("chartFile").addEventListener("change", e=>{
  const f=e.target.files[0];
  if(!f) return;
  set("fileName", f.name);
  $("preview").src=URL.createObjectURL(f);
  $("previewWrap").classList.remove("hidden");
});
$("dropzone").addEventListener("dragover",e=>{e.preventDefault();$("dropzone").classList.add("dragging")});
$("dropzone").addEventListener("dragleave",()=>$("dropzone").classList.remove("dragging"));
$("dropzone").addEventListener("drop",e=>{
  e.preventDefault(); $("dropzone").classList.remove("dragging");
  const f=e.dataTransfer.files[0];
  if(!f) return;
  const dt=new DataTransfer(); dt.items.add(f); $("chartFile").files=dt.files;
  set("fileName",f.name); $("preview").src=URL.createObjectURL(f); $("previewWrap").classList.remove("hidden");
});
$("scan").onclick=scanScreenshot;
$("marketAnalyze").onclick=marketAnalyze;
