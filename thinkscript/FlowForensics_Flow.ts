# FlowForensics_Flow — lower "beneath the surface" panel
#
# The order-flow evidence panel behind FlowForensics_Signals: rolling tick-rule
# flow imbalance (histogram), day-anchored cumulative imbalance (line), and
# relative volume (line, right-hand scale of ~1.0). Thresholds match the
# defaults tuned on the measured TSLA data. Educational tool — not advice.

declare lower;

input imbWindow = 30;
input buyThresh = 0.20;
input sellThresh = -0.30;
input relVolFast = 10;
input relVolSlow = 50;
input marketOpen = 0930;
input marketClose = 1600;

def isRTH = SecondsFromTime(marketOpen) >= 0 and SecondsTillTime(marketClose) > 0;
def newSession = isRTH and (!isRTH[1] or GetYYYYMMDD() != GetYYYYMMDD()[1]);

def sv = if !isRTH or newSession then 0 else Sign(close - close[1]) * volume;
def imbRaw = if Sum(volume, imbWindow) > 0
             then Sum(sv, imbWindow) / Sum(volume, imbWindow) else 0;

def dayCumSV = CompoundValue(1,
    if !isRTH then dayCumSV[1]
    else if newSession then sv
    else dayCumSV[1] + sv, sv);
def cumV = CompoundValue(1,
    if !isRTH then cumV[1]
    else if newSession then volume
    else cumV[1] + volume, volume);

plot Imbalance = if isRTH then imbRaw else Double.NaN;
Imbalance.SetPaintingStrategy(PaintingStrategy.HISTOGRAM);
Imbalance.DefineColor("Accum", Color.GREEN);
Imbalance.DefineColor("Distrib", Color.RED);
Imbalance.DefineColor("Neutral", Color.GRAY);
Imbalance.AssignValueColor(
    if imbRaw >= buyThresh then Imbalance.Color("Accum")
    else if imbRaw <= sellThresh then Imbalance.Color("Distrib")
    else Imbalance.Color("Neutral"));

plot DayImbalance = if isRTH and cumV > 0 then dayCumSV / cumV else Double.NaN;
DayImbalance.SetDefaultColor(Color.CYAN);
DayImbalance.SetLineWeight(2);

plot RelVol = if isRTH and Average(volume, relVolSlow) > 0
              then Average(volume, relVolFast) / Average(volume, relVolSlow) - 1
              else Double.NaN;
RelVol.SetDefaultColor(Color.ORANGE);
RelVol.SetStyle(Curve.SHORT_DASH);

plot BuyLine = buyThresh;
BuyLine.SetDefaultColor(Color.DARK_GREEN);
plot SellLine = sellThresh;
SellLine.SetDefaultColor(Color.DARK_RED);
plot Zero = 0;
Zero.SetDefaultColor(Color.GRAY);

AddLabel(yes, "RelVol plotted as (ratio - 1); 0 = normal volume", Color.GRAY);
