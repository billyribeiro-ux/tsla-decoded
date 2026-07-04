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
#              failed VWAP reclaim with weak closes.
# Default thresholds were tuned bar-for-bar against the actual 1-minute data
# (see output/signal_validation.md). Best on 1-min or 5-min intraday charts,
# regular-trading-hours session. Educational tool — not investment advice.

declare upper;

input imbWindow = 30;         # bars in the rolling flow-imbalance window
input buyThresh = 0.20;       # imbalance >= this -> accumulation side
input sellThresh = -0.30;     # day-anchored imbalance <= this -> distribution side
input relVolFast = 10;
input relVolSlow = 50;
input relVolThresh = 1.25;    # fast/slow volume ratio gate
input clvSmooth = 10;
input openWindowMin = 75;     # opening-rejection valid inside first N minutes
input openHighMin = 15;       # day high must be set within first N minutes
input belowVwapBars = 15;     # consecutive bars below VWAP for distribution trigger
input cooldownBars = 30;      # min bars between same-side signals
input buyCutoffTime = 1500;   # EST HHMM — no fresh BUY after this (no runway left)
input runupGate = 0.10;       # no BUY when the 3-day run-up exceeds this (exhaustion)
input marketOpen = 0930;      # EST, HHMM
input marketClose = 1600;     # EST, HHMM
input paintBars = no;
input showCloud = yes;
input showLabels = yes;

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
def imb = if Sum(volume, imbWindow) > 0
          then Sum(sv, imbWindow) / Sum(volume, imbWindow) else 0;
def dayCumSV = CompoundValue(1,
    if !isRTH then dayCumSV[1]
    else if newSession then sv
    else dayCumSV[1] + sv, sv);
def dayImb = if cumV > 0 then dayCumSV / cumV else 0;
def cumSVHigh = CompoundValue(1,
    if !isRTH then cumSVHigh[1]
    else if newSession then dayCumSV
    else Max(cumSVHigh[1], dayCumSV), dayCumSV);

def relVol = if Average(volume, relVolSlow) > 0
             then Average(volume, relVolFast) / Average(volume, relVolSlow) else 1;
def clv = if high == low then 0 else ((close - low) - (high - close)) / (high - low);
def clvS = Average(clv, clvSmooth);

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
def gapUp = open(period = AggregationPeriod.DAY)
            >= close(period = AggregationPeriod.DAY)[1];

# v1.1 audit gates -----------------------------------------------------------
# prior session's final anchored VWAP: captured at each session's first bar
def prevDayVWAP = CompoundValue(1,
    if newSession and cumV[1] > 0 then cumPV[1] / cumV[1] else prevDayVWAP[1],
    Double.NaN);
# 3-day run-up ending at the prior close (exhaustion context)
def closeD = close(period = AggregationPeriod.DAY);
def runup3 = if !IsNaN(closeD[4]) and closeD[4] != 0
             then closeD[1] / closeD[4] - 1 else 0;

# ---------------------------------------------------------------- signals
def buyCond = isRTH and minOfDay >= imbWindow
    and SecondsTillTime(buyCutoffTime) > 0
    and runup3 <= runupGate
    and aboveVWAP
    and imb >= buyThresh
    and relVol >= relVolThresh
    and clvS > 0
    and dayCumSV >= cumSVHigh;

def sellOpenRejection = isRTH and minOfDay >= 5 and minOfDay <= openWindowMin
    and hodMin <= openHighMin
    and gapUp
    and (IsNaN(prevDayVWAP) or close < prevDayVWAP)
    and !aboveVWAP
    and dayImb <= sellThresh
    and relVol >= relVolThresh;

def sellDistribution = isRTH and belowStreak >= belowVwapBars
    and imb <= sellThresh
    and failedReclaim
    and clvS < 0;

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
plot BuySignal = if buyFire then low else Double.NaN;
BuySignal.SetPaintingStrategy(PaintingStrategy.ARROW_UP);
BuySignal.SetDefaultColor(Color.GREEN);
BuySignal.SetLineWeight(3);

plot SellSignal = if sellFire then high else Double.NaN;
SellSignal.SetPaintingStrategy(PaintingStrategy.ARROW_DOWN);
SellSignal.SetDefaultColor(Color.RED);
SellSignal.SetLineWeight(3);

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

Alert(buyFire, "FlowForensics BUY: accumulation signature", Alert.BAR, Sound.Ding);
Alert(sellFire, "FlowForensics SELL: distribution/rejection signature", Alert.BAR, Sound.Bell);
