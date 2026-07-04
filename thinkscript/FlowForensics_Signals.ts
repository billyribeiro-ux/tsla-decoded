# FlowForensics_Signals — intraday accumulation / distribution signals
#
# Derived from measured TSLA order-flow signatures (repo: tsla-decoded):
#   BUY  = the 2026-06-29 accumulation signature: price above anchored VWAP,
#          rolling tick-rule flow imbalance >= +0.20, swelling relative volume,
#          closes near bar highs (CLV > 0), day-cumulative signed volume at highs.
#   SELL = the 2026-07-02 liquidation signature, two triggers:
#          (a) opening rejection — gap-up open, day high set in the first minutes,
#              price loses VWAP with day-anchored imbalance <= -0.30 on heavy volume;
#          (b) distribution — sustained bars below VWAP, one-sided sell imbalance,
#              weak closes (failed VWAP reclaim OR strong day-anchored sell flow).
#
# v1.2: all windows are TIME-BASED (minutes) via GetAggregationPeriod(), so the
# study behaves identically on 1-min, 2-min, 5-min, etc. Prior-day close / VWAP
# and the 3-day run-up are derived from the intraday session stream itself — NO
# secondary (daily) aggregation, which previously returned NaN on charts with
# little history and silently suppressed all SELL arrows.
# Turn on debugMode to loosen the gates and drop chart bubbles for confirmation.
# Best on 1-min or 5-min RTH charts. Educational tool — not investment advice.

declare upper;

input imbWindowMin = 30;      # MINUTES in the rolling flow-imbalance window
input buyThresh = 0.20;       # imbalance >= this -> accumulation side
input sellThresh = -0.30;     # day-anchored imbalance <= this -> distribution side
input relVolFastMin = 10;     # MINUTES, fast volume average
input relVolSlowMin = 50;     # MINUTES, slow volume average
input relVolThresh = 1.25;    # fast/slow volume ratio gate
input clvSmoothMin = 10;      # MINUTES, CLV smoothing
input openWindowMin = 75;     # opening-rejection valid inside first N minutes
input openHighMin = 15;       # day high must be set within first N minutes
input belowVwapMin = 15;      # MINUTES below VWAP for the distribution trigger
input cooldownMin = 30;       # minutes between same-side signals
input buyCutoffTime = 1500;   # EST HHMM — no fresh BUY after this (no runway left)
input runupGate = 0.10;       # no BUY when the 3-day run-up exceeds this (exhaustion)
input marketOpen = 0930;      # EST, HHMM
input marketClose = 1600;     # EST, HHMM
input paintBars = no;
input showCloud = yes;
input showLabels = yes;
input debugMode = no;         # loosen gates + draw bubbles to confirm the study is live

# ---------------------------------------------------------------- timeframe
# bars-per-minute from the chart aggregation (ms/bar); fallback to 1 for >= daily
def aggMin = GetAggregationPeriod() / 60000;
def barsPerMin = if aggMin <= 0 or aggMin > 240 then 1 else 1 / aggMin;
def imbBars = Max(Round(imbWindowMin * barsPerMin, 0), 1);
def fastBars = Max(Round(relVolFastMin * barsPerMin, 0), 1);
def slowBars = Max(Round(relVolSlowMin * barsPerMin, 0), 1);
def clvBars = Max(Round(clvSmoothMin * barsPerMin, 0), 1);
def belowBars = Max(Round(belowVwapMin * barsPerMin, 0), 1);
def cooldownBars = Max(Round(cooldownMin * barsPerMin, 0), 1);

# ---------------------------------------------------------------- session
def isRTH = SecondsFromTime(marketOpen) >= 0 and SecondsTillTime(marketClose) > 0;
def newSession = isRTH and (!isRTH[1] or GetYYYYMMDD() != GetYYYYMMDD()[1]);
def minOfDay = if isRTH then Floor(SecondsFromTime(marketOpen) / 60) else 0;

# ---------------------------------------------------------------- anchored VWAP
def tp = (high + low + close) / 3;
def cumPV = CompoundValue(1,
    if !isRTH then cumPV[1]
    else if newSession then tp * volume
    else cumPV[1] + tp * volume, tp * volume);
def cumV = CompoundValue(1,
    if !isRTH then cumV[1]
    else if newSession then volume
    else cumV[1] + volume, volume);
plot AnchoredVWAP = if cumV > 0 then cumPV / cumV else Double.NaN;
AnchoredVWAP.SetDefaultColor(Color.PLUM);
AnchoredVWAP.SetStyle(Curve.MEDIUM_DASH);

def aboveVWAP = close > AnchoredVWAP;

# ---------------------------------------------------------------- order flow
def sv = if !isRTH or newSession then 0 else Sign(close - close[1]) * volume;
def imb = if Sum(volume, imbBars) > 0
          then Sum(sv, imbBars) / Sum(volume, imbBars) else 0;
def dayCumSV = CompoundValue(1,
    if !isRTH then dayCumSV[1]
    else if newSession then sv
    else dayCumSV[1] + sv, sv);
def dayImb = if cumV > 0 then dayCumSV / cumV else 0;
def cumSVHigh = CompoundValue(1,
    if !isRTH then cumSVHigh[1]
    else if newSession then dayCumSV
    else Max(cumSVHigh[1], dayCumSV), dayCumSV);

def relVol = if Average(volume, slowBars) > 0
             then Average(volume, fastBars) / Average(volume, slowBars) else 1;
def clv = if high == low then 0 else ((close - low) - (high - close)) / (high - low);
def clvS = Average(clv, clvBars);

# ---------------------------------------------------------------- day context
def dayHigh = CompoundValue(1,
    if !isRTH then dayHigh[1]
    else if newSession then high
    else Max(dayHigh[1], high), high);
def hodMin = CompoundValue(1,
    if !isRTH then hodMin[1]
    else if newSession or high >= dayHigh then minOfDay
    else hodMin[1], 0);
def belowStreak = CompoundValue(1,
    if !isRTH or newSession or aboveVWAP then 0
    else belowStreak[1] + 1, 0);
def touchedFromBelow = if !aboveVWAP and high >= AnchoredVWAP then 1 else 0;
def failedReclaim = Highest(touchedFromBelow, 10) > 0;

# ---- self-contained daily context (NO secondary aggregation) ---------------
# session open captured at the first RTH bar of each day
def sessionOpen = CompoundValue(1, if newSession then open else sessionOpen[1], open);
# prior session's close: the close of the bar right before this session started
def priorClose = CompoundValue(1, if newSession then close[1] else priorClose[1], close);
# prior session's final anchored VWAP
def priorVWAP = CompoundValue(1,
    if newSession and cumV[1] > 0 then cumPV[1] / cumV[1] else priorVWAP[1], Double.NaN);
# last-3-session close chain, shifted only at session boundaries
def sc1 = CompoundValue(1, if newSession then priorClose else sc1[1], Double.NaN);
def sc2 = CompoundValue(1, if newSession then sc1[1] else sc2[1], Double.NaN);
def sc3 = CompoundValue(1, if newSession then sc2[1] else sc3[1], Double.NaN);
def runup3 = if !IsNaN(sc3) and sc3 != 0 then sc1 / sc3 - 1 else 0;
def gapUp = sessionOpen >= priorClose;

# ---------------------------------------------------------------- gate helpers
def buyThr = if debugMode then buyThresh * 0.7 else buyThresh;
def sellThr = if debugMode then sellThresh * 0.7 else sellThresh;
def relThr = if debugMode then 1.0 else relVolThresh;
def runGate = if debugMode then 100 else runupGate;          # off in debug
def priorGateOK = debugMode or IsNaN(priorVWAP) or close < priorVWAP;
def gapGateOK = debugMode or gapUp;
def hodGateOK = debugMode or hodMin <= openHighMin;

# ---------------------------------------------------------------- signals
def buyCond = isRTH and minOfDay >= imbWindowMin
    and SecondsTillTime(buyCutoffTime) > 0
    and runup3 <= runGate
    and aboveVWAP
    and imb >= buyThr
    and relVol >= relThr
    and clvS > 0
    and dayCumSV >= cumSVHigh;

def sellOpenRejection = isRTH and minOfDay >= 5 and minOfDay <= openWindowMin
    and hodGateOK
    and gapGateOK
    and priorGateOK
    and !aboveVWAP
    and dayImb <= sellThr
    and relVol >= relThr;

# distribution: sustained below-VWAP + one-sided sell + weak closes; a runaway
# liquidation that never retouches VWAP still qualifies via strong day imbalance
def sellDistribution = isRTH and belowStreak >= belowBars
    and imb <= sellThr
    and clvS < 0
    and (failedReclaim or dayImb <= sellThr);

def sellCond = sellOpenRejection or sellDistribution;
def buyEdge = buyCond and !buyCond[1];
def sellEdge = sellCond and !sellCond[1];

def sinceBuy = CompoundValue(1,
    if buyEdge and sinceBuy[1] >= cooldownBars then 0 else sinceBuy[1] + 1, cooldownBars);
def sinceSell = CompoundValue(1,
    if sellEdge and sinceSell[1] >= cooldownBars then 0 else sinceSell[1] + 1, cooldownBars);
def buyFire = buyEdge and sinceBuy == 0;
def sellFire = sellEdge and sinceSell == 0;

# ---------------------------------------------------------------- plots & UX
plot BuySignal = if buyFire then low * 0.999 else Double.NaN;
BuySignal.SetPaintingStrategy(PaintingStrategy.ARROW_UP);
BuySignal.SetDefaultColor(Color.GREEN);
BuySignal.SetLineWeight(5);

plot SellSignal = if sellFire then high * 1.001 else Double.NaN;
SellSignal.SetPaintingStrategy(PaintingStrategy.ARROW_DOWN);
SellSignal.SetDefaultColor(Color.RED);
SellSignal.SetLineWeight(5);

AddChartBubble(debugMode and buyFire, low, "BUY", Color.GREEN, no);
AddChartBubble(debugMode and sellFire, high, "SELL", Color.RED, yes);

AddCloud(if showCloud and isRTH then close else Double.NaN, AnchoredVWAP,
         Color.LIGHT_GREEN, Color.LIGHT_RED);

AssignPriceColor(
    if !paintBars then Color.CURRENT
    else if isRTH and aboveVWAP and imb >= buyThresh then Color.DARK_GREEN
    else if isRTH and !aboveVWAP and imb <= sellThresh then Color.DARK_RED
    else Color.GRAY);

AddLabel(showLabels, "flow " + AsPercent(imb), if imb >= buyThresh then Color.GREEN
    else if imb <= sellThresh then Color.RED else Color.GRAY);
AddLabel(showLabels, "day flow " + AsPercent(dayImb),
    if dayImb > 0 then Color.GREEN else Color.RED);
AddLabel(showLabels, "relVol " + Round(relVol, 2),
    if relVol >= relVolThresh then Color.ORANGE else Color.GRAY);
AddLabel(showLabels, if aboveVWAP then "above VWAP" else "below VWAP",
    if aboveVWAP then Color.GREEN else Color.RED);
AddLabel(showLabels, "imb win " + imbBars + " bars", Color.GRAY);
AddLabel(debugMode, "DEBUG: gates loosened", Color.YELLOW);

Alert(buyFire, "FlowForensics BUY: accumulation signature", Alert.BAR, Sound.Ding);
Alert(sellFire, "FlowForensics SELL: distribution/rejection signature", Alert.BAR, Sound.Bell);
