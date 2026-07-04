# FlowForensics_Absorption_Panel — the distribution-footprint meter (lower study)
#
# Companion to FlowForensics_Absorption. Plots the OHLCV "footprint score" that
# stands in for order flow you can't see: relative volume weighted by upper-wick
# rejection (supply capping a push up) plus below-VWAP weak closes (distribution).
# When this meter spikes red while price tests a high, a large passive seller is
# most likely working the offer — the retail-visible shadow of the iceberg.
# Validated: it peaked on 2026-07-02's open (footprint 67 vs <27 other days).
# Educational tool — not investment advice.

declare lower;

input relVolAvgMin = 50;
input marketOpen = 0930;
input marketClose = 1600;
input alertLevel = 3.0;

def aggMin = GetAggregationPeriod() / 60000;
def barsPerMin = if aggMin <= 0 or aggMin > 240 then 1 else 1 / aggMin;
def slowBars = Max(Round(relVolAvgMin * barsPerMin, 0), 1);

def isRTH = SecondsFromTime(marketOpen) >= 0 and SecondsTillTime(marketClose) > 0;
def newSession = isRTH and (!isRTH[1] or GetYYYYMMDD() != GetYYYYMMDD()[1]);
def tp = (high + low + close) / 3;
def cumPV = CompoundValue(1, if !isRTH then cumPV[1] else if newSession then tp*volume
    else cumPV[1] + tp*volume, tp*volume);
def cumV = CompoundValue(1, if !isRTH then cumV[1] else if newSession then volume
    else cumV[1] + volume, volume);
def vwap = if cumV > 0 then cumPV/cumV else close;

def rng = Max(high - low, 0.0001);
def relVol = if Average(volume, slowBars) > 0 then volume / Average(volume, slowBars) else 1;
def upWick = (high - Max(open, close)) / rng;
def dnWick = (Min(open, close) - low) / rng;
def belowVWAP = close < vwap;

# footprint > 0 = distribution/supply (red), < 0 = accumulation/demand (green)
def supply = relVol * (upWick + (if belowVWAP and close < open then 0.5 else 0));
def demand = relVol * (dnWick + (if !belowVWAP and close > open then 0.5 else 0));
plot Footprint = if isRTH then supply - demand else Double.NaN;
Footprint.SetPaintingStrategy(PaintingStrategy.HISTOGRAM);
Footprint.SetLineWeight(3);
Footprint.AssignValueColor(if Footprint > 0 then Color.RED else Color.GREEN);

plot AlertHi = alertLevel; AlertHi.SetDefaultColor(Color.DARK_RED);
plot AlertLo = -alertLevel; AlertLo.SetDefaultColor(Color.DARK_GREEN);
plot Zero = 0; Zero.SetDefaultColor(Color.GRAY);

AddLabel(yes, "FOOTPRINT: red = supply/distribution, green = demand/accumulation", Color.GRAY);
Alert(Footprint >= alertLevel, "FlowForensics: heavy supply footprint (distribution)",
      Alert.BAR, Sound.Ring);
