# FlowForensics_Flow (v1.2) — intraday lower panel WITH buy/sell signals
#
# The "beneath the surface" panel behind FlowForensics_Signals, carrying the
# full v1.2 signal logic so it stands alone: rolling tick-rule flow imbalance
# (zone-colored histogram), day-anchored imbalance, relative volume, and the
# same BUY/SELL arrows the upper study fires (drawn at the threshold lines).
#
# v1.2 fixes: all windows are TIME-BASED via GetAggregationPeriod() (works on
# any intraday timeframe); prior-day close/VWAP and 3-day run-up are derived
# from the session stream (no secondary aggregation); the distribution SELL no
# longer requires a VWAP retouch. Turn on debugMode to loosen the gates.
# Best on 1-min / 5-min RTH charts. Educational tool — not investment advice.

declare lower;

input imbWindowMin = 30;
input buyThresh = 0.20;
input sellThresh = -0.30;
input relVolFastMin = 10;
input relVolSlowMin = 50;
input relVolThresh = 1.25;
input clvSmoothMin = 10;
input openWindowMin = 75;
input openHighMin = 15;
input belowVwapMin = 15;
input cooldownMin = 30;
input buyCutoffTime = 1500;
input runupGate = 0.10;
input marketOpen = 0930;
input marketClose = 1600;
input debugMode = no;

# ---------------------------------------------------------------- timeframe
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
def vwapA = if cumV > 0 then cumPV / cumV else close;
def aboveVWAP = close > vwapA;

# ---------------------------------------------------------------- order flow
def sv = if !isRTH or newSession then 0 else Sign(close - close[1]) * volume;
def imbRaw = if Sum(volume, imbBars) > 0
             then Sum(sv, imbBars) / Sum(volume, imbBars) else 0;
def dayCumSV = CompoundValue(1,
    if !isRTH then dayCumSV[1]
    else if newSession then sv
    else dayCumSV[1] + sv, sv);
def dayImbRaw = if cumV > 0 then dayCumSV / cumV else 0;
def cumSVHigh = CompoundValue(1,
    if !isRTH then cumSVHigh[1]
    else if newSession then dayCumSV
    else Max(cumSVHigh[1], dayCumSV), dayCumSV);
def relVolRaw = if Average(volume, slowBars) > 0
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
def failedReclaim = Highest(if !aboveVWAP and high >= vwapA then 1 else 0, 10) > 0;

def sessionOpen = CompoundValue(1, if newSession then open else sessionOpen[1], open);
def priorClose = CompoundValue(1, if newSession then close[1] else priorClose[1], close);
def priorVWAP = CompoundValue(1,
    if newSession and cumV[1] > 0 then cumPV[1] / cumV[1] else priorVWAP[1], Double.NaN);
def sc1 = CompoundValue(1, if newSession then priorClose else sc1[1], Double.NaN);
def sc2 = CompoundValue(1, if newSession then sc1[1] else sc2[1], Double.NaN);
def sc3 = CompoundValue(1, if newSession then sc2[1] else sc3[1], Double.NaN);
def runup3 = if !IsNaN(sc3) and sc3 != 0 then sc1 / sc3 - 1 else 0;
def gapUp = sessionOpen >= priorClose;

def buyThr = if debugMode then buyThresh * 0.7 else buyThresh;
def sellThr = if debugMode then sellThresh * 0.7 else sellThresh;
def relThr = if debugMode then 1.0 else relVolThresh;
def runGate = if debugMode then 100 else runupGate;
def priorGateOK = debugMode or IsNaN(priorVWAP) or close < priorVWAP;
def gapGateOK = debugMode or gapUp;
def hodGateOK = debugMode or hodMin <= openHighMin;

# ---------------------------------------------------------------- signals (v1.2)
def buyCond = isRTH and minOfDay >= imbWindowMin
    and SecondsTillTime(buyCutoffTime) > 0
    and runup3 <= runGate
    and aboveVWAP and imbRaw >= buyThr and relVolRaw >= relThr
    and clvS > 0 and dayCumSV >= cumSVHigh;
def sellCond = (isRTH and minOfDay >= 5 and minOfDay <= openWindowMin
        and hodGateOK and gapGateOK and priorGateOK
        and !aboveVWAP and dayImbRaw <= sellThr and relVolRaw >= relThr)
    or (isRTH and belowStreak >= belowBars and imbRaw <= sellThr
        and clvS < 0 and (failedReclaim or dayImbRaw <= sellThr));

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
BuySignal.SetLineWeight(5);
plot SellSignal = if sellFire then buyThresh else Double.NaN;
SellSignal.SetPaintingStrategy(PaintingStrategy.ARROW_DOWN);
SellSignal.SetDefaultColor(Color.RED);
SellSignal.SetLineWeight(5);

AddLabel(yes, "flow " + AsPercent(imbRaw),
    if imbRaw >= buyThresh then Color.GREEN
    else if imbRaw <= sellThresh then Color.RED else Color.GRAY);
AddLabel(yes, "imb win " + imbBars + " bars; RelVol = ratio - 1", Color.GRAY);
AddLabel(debugMode, "DEBUG: gates loosened", Color.YELLOW);

Alert(buyFire, "FlowForensics BUY (flow panel)", Alert.BAR, Sound.Ding);
Alert(sellFire, "FlowForensics SELL (flow panel)", Alert.BAR, Sound.Bell);
