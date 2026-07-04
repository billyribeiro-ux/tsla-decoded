# FlowForensics_Daily_Flow — daily lower panel with the daily signals
#
# The daily "beneath the surface" panel behind FlowForensics_Daily: N-day
# tick-rule flow imbalance (zone-colored histogram), relative volume, 3-day
# run-up vs the exhaustion/reversal gates, plus the same daily BUY/SELL arrows.
# Same formulas and defaults as FlowForensics_Daily (validated on TSLA EOD:
# exactly BUY 2026-06-29 and SELL 2026-07-02 fired in 64 sessions).
# For DAY charts. Educational tool — not investment advice.

declare lower;

input imbDays = 10;
input buyImb = 0.10;
input sellImb = -0.15;
input clvBuy = 0.5;
input clvSell = -0.5;
input relVolAvg = 20;
input relVolThresh = 1.15;
input emaLen = 10;
input runupGate = 0.10;
input reversalRunup = 0.08;

def clv = if high == low then 0 else ((close - low) - (high - close)) / (high - low);
def relVolRaw = if Average(volume, relVolAvg) > 0
                then volume / Average(volume, relVolAvg) else 1;
def sv = Sign(close - close[1]) * volume;
def imbRaw = if Sum(volume, imbDays) > 0
             then Sum(sv, imbDays) / Sum(volume, imbDays) else 0;
def emaC = ExpAverage(close, emaLen);
def gapUp = open >= close[1];
def runup3raw = if !IsNaN(close[4]) and close[4] != 0 then close[1] / close[4] - 1 else 0;

def buyCond = close > close[1] and clv >= clvBuy and relVolRaw >= relVolThresh
    and imbRaw >= buyImb and close > emaC and runup3raw <= runupGate;
def sellCond = (gapUp and close < open and clv <= clvSell
        and relVolRaw >= relVolThresh and runup3raw >= reversalRunup)
    or (close < low[1] and relVolRaw >= relVolThresh and imbRaw <= sellImb);

plot Imbalance = imbRaw;
Imbalance.SetPaintingStrategy(PaintingStrategy.HISTOGRAM);
Imbalance.DefineColor("Accum", Color.GREEN);
Imbalance.DefineColor("Distrib", Color.RED);
Imbalance.DefineColor("Neutral", Color.GRAY);
Imbalance.AssignValueColor(
    if imbRaw >= buyImb then Imbalance.Color("Accum")
    else if imbRaw <= sellImb then Imbalance.Color("Distrib")
    else Imbalance.Color("Neutral"));

plot RelVol = relVolRaw - 1;
RelVol.SetDefaultColor(Color.ORANGE);
RelVol.SetStyle(Curve.SHORT_DASH);

plot Runup3 = runup3raw;
Runup3.SetDefaultColor(Color.CYAN);
Runup3.SetLineWeight(2);

plot BuyLine = buyImb;
BuyLine.SetDefaultColor(Color.DARK_GREEN);
plot SellLine = sellImb;
SellLine.SetDefaultColor(Color.DARK_RED);
plot ReversalGate = reversalRunup;
ReversalGate.SetDefaultColor(Color.DARK_ORANGE);
ReversalGate.SetStyle(Curve.LONG_DASH);
plot Zero = 0;
Zero.SetDefaultColor(Color.GRAY);

plot BuySignal = if buyCond then sellImb else Double.NaN;
BuySignal.SetPaintingStrategy(PaintingStrategy.ARROW_UP);
BuySignal.SetDefaultColor(Color.GREEN);
BuySignal.SetLineWeight(4);
plot SellSignal = if sellCond then buyImb else Double.NaN;
SellSignal.SetPaintingStrategy(PaintingStrategy.ARROW_DOWN);
SellSignal.SetDefaultColor(Color.RED);
SellSignal.SetLineWeight(4);

AddLabel(yes, "RelVol and run-up plotted on the imbalance scale; RelVol = ratio - 1",
    Color.GRAY);

Alert(buyCond and !buyCond[1], "FlowForensics DAILY BUY (flow panel)", Alert.BAR, Sound.Ding);
Alert(sellCond and !sellCond[1], "FlowForensics DAILY SELL (flow panel)", Alert.BAR, Sound.Bell);
