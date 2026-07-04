# FlowForensics_Flow (v1.1) — intraday lower panel WITH buy/sell signals
#
# The "beneath the surface" panel behind FlowForensics_Signals, now carrying the
# full v1.1 signal logic so it stands alone: rolling tick-rule flow imbalance
# (zone-colored histogram), day-anchored imbalance, relative volume, and the
# same BUY/SELL arrows the upper study fires (drawn at the threshold lines).
# Signal logic and defaults are identical to FlowForensics_Signals v1.1 —
# validated bar-for-bar on TSLA 1-min data (output/signal_validation.md).
# Best on 1-min / 5-min RTH charts. Educational tool — not investment advice.

declare lower;

input imbWindow = 30;
input buyThresh = 0.20;
input sellThresh = -0.30;
input relVolFast = 10;
input relVolSlow = 50;
input relVolThresh = 1.25;
input clvSmooth = 10;
input openWindowMin = 75;
input openHighMin = 15;
input belowVwapBars = 15;
input cooldownBars = 30;
input buyCutoffTime = 1500;
input runupGate = 0.10;
input marketOpen = 0930;
input marketClose = 1600;

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
def vwapA = if cumV > 0 then cumPV / cumV else close;
def aboveVWAP = close > vwapA;
def prevDayVWAP = CompoundValue(1,
    if newSession and cumV[1] > 0 then cumPV[1] / cumV[1] else prevDayVWAP[1],
    Double.NaN);

# ---------------------------------------------------------------- order flow
def sv = if !isRTH or newSession then 0 else Sign(close - close[1]) * volume;
def imbRaw = if Sum(volume, imbWindow) > 0
             then Sum(sv, imbWindow) / Sum(volume, imbWindow) else 0;
def dayCumSV = CompoundValue(1,
    if !isRTH then dayCumSV[1]
    else if newSession then sv
    else dayCumSV[1] + sv, sv);
def dayImbRaw = if cumV > 0 then dayCumSV / cumV else 0;
def cumSVHigh = CompoundValue(1,
    if !isRTH then cumSVHigh[1]
    else if newSession then dayCumSV
    else Max(cumSVHigh[1], dayCumSV), dayCumSV);
def relVolRaw = if Average(volume, relVolSlow) > 0
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
def failedReclaim = Highest(if !aboveVWAP and high >= vwapA then 1 else 0, 10) > 0;
def gapUp = open(period = AggregationPeriod.DAY)
            >= close(period = AggregationPeriod.DAY)[1];
def closeD = close(period = AggregationPeriod.DAY);
def runup3 = if !IsNaN(closeD[4]) and closeD[4] != 0
             then closeD[1] / closeD[4] - 1 else 0;

# ---------------------------------------------------------------- signals (v1.1)
def buyCond = isRTH and minOfDay >= imbWindow
    and SecondsTillTime(buyCutoffTime) > 0
    and runup3 <= runupGate
    and aboveVWAP
    and imbRaw >= buyThresh
    and relVolRaw >= relVolThresh
    and clvS > 0
    and dayCumSV >= cumSVHigh;
def sellCond = (isRTH and minOfDay >= 5 and minOfDay <= openWindowMin
        and hodMin <= openHighMin and gapUp
        and (IsNaN(prevDayVWAP) or close < prevDayVWAP)
        and !aboveVWAP
        and dayImbRaw <= sellThresh and relVolRaw >= relVolThresh)
    or (isRTH and belowStreak >= belowVwapBars and imbRaw <= sellThresh
        and failedReclaim and clvS < 0);

def buyEdge = buyCond and !buyCond[1];
def sellEdge = sellCond and !sellCond[1];
def sinceBuy = CompoundValue(1,
    if buyEdge and sinceBuy[1] >= cooldownBars then 0 else sinceBuy[1] + 1, cooldownBars);
def sinceSell = CompoundValue(1,
    if sellEdge and sinceSell[1] >= cooldownBars then 0 else sinceSell[1] + 1, cooldownBars);
def buyFire = buyEdge and sinceBuy == 0;
def sellFire = sellEdge and sinceSell == 0;

# ---------------------------------------------------------------- panel plots
plot Imbalance = if isRTH then imbRaw else Double.NaN;
Imbalance.SetPaintingStrategy(PaintingStrategy.HISTOGRAM);
Imbalance.DefineColor("Accum", Color.GREEN);
Imbalance.DefineColor("Distrib", Color.RED);
Imbalance.DefineColor("Neutral", Color.GRAY);
Imbalance.AssignValueColor(
    if imbRaw >= buyThresh then Imbalance.Color("Accum")
    else if imbRaw <= sellThresh then Imbalance.Color("Distrib")
    else Imbalance.Color("Neutral"));

plot DayImbalance = if isRTH then dayImbRaw else Double.NaN;
DayImbalance.SetDefaultColor(Color.CYAN);
DayImbalance.SetLineWeight(2);

plot RelVol = if isRTH then relVolRaw - 1 else Double.NaN;
RelVol.SetDefaultColor(Color.ORANGE);
RelVol.SetStyle(Curve.SHORT_DASH);

plot BuyLine = buyThresh;
BuyLine.SetDefaultColor(Color.DARK_GREEN);
plot SellLine = sellThresh;
SellLine.SetDefaultColor(Color.DARK_RED);
plot Zero = 0;
Zero.SetDefaultColor(Color.GRAY);

# signal arrows drawn at the threshold lines so they sit inside the panel scale
plot BuySignal = if buyFire then sellThresh else Double.NaN;
BuySignal.SetPaintingStrategy(PaintingStrategy.ARROW_UP);
BuySignal.SetDefaultColor(Color.GREEN);
BuySignal.SetLineWeight(4);
plot SellSignal = if sellFire then buyThresh else Double.NaN;
SellSignal.SetPaintingStrategy(PaintingStrategy.ARROW_DOWN);
SellSignal.SetDefaultColor(Color.RED);
SellSignal.SetLineWeight(4);

AddLabel(yes, "flow " + AsPercent(imbRaw),
    if imbRaw >= buyThresh then Color.GREEN
    else if imbRaw <= sellThresh then Color.RED else Color.GRAY);
AddLabel(yes, "RelVol plotted as (ratio - 1); 0 = normal volume", Color.GRAY);

Alert(buyFire, "FlowForensics BUY (flow panel)", Alert.BAR, Sound.Ding);
Alert(sellFire, "FlowForensics SELL (flow panel)", Alert.BAR, Sound.Bell);
