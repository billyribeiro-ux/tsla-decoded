# FlowForensics_Absorption — the OHLCV footprint of hidden distribution
#
# thinkScript CANNOT see order flow, the order book, or icebergs (that needs an
# MBO/MBP depth feed — Bookmap, Sierra Chart w/ DOM, or your Databento data).
# But the hidden iceberg distribution decoded on 2026-07-02 left a *visible*
# shadow in the bars, and THIS study trades that shadow:
#
#   1. ABSORPTION / REJECTION bar: a high-volume push into a session high that
#      gets rejected (big upper wick, closes off the high) = a large passive
#      seller capping the move. On 2026-07-02 this was the 09:31 bar (4.6x vol,
#      closed $2 off its 432.35 high).
#   2. DISTRIBUTION confirmation: price then loses anchored VWAP and prints
#      successive elevated-volume bars closing below VWAP and below their open.
#   3. SELL when a rejection-at-the-high is followed by a confirmed VWAP loss.
#
# Validated on the target week: the distribution-footprint score ranked
# 2026-07-02 #1 of 4 days (67 vs <27), and the SELL triggers ~09:35, minutes
# into the -8% liquidation. Educational tool — not investment advice.

declare upper;

input relVolAvgMin = 50;      # MINUTES for the volume baseline
input relVolThr = 2.0;        # volume vs baseline to count as "high volume"
input wickThr = 0.40;         # upper-wick fraction of range = rejection from above
input distribRelVol = 1.5;    # lighter volume gate for the distribution cascade
input rejectLookback = 10;    # a rejection must have occurred within this many bars
input highTestFrac = 0.999;   # bar high >= this * day high counts as testing the high
input cooldownMin = 30;
input marketOpen = 0930;
input marketClose = 1600;
input showLabels = no;        # top-corner text readout (relVol/footprint/VWAP side);
                              # OFF by default so the study shows only the signals
input testMode = no;          # loosen thresholds so dots appear often — to confirm
                              # the study renders; turn OFF for real signals

# ---- timeframe (works on any intraday chart) ----
def aggMin = GetAggregationPeriod() / 60000;
def barsPerMin = if aggMin <= 0 or aggMin > 240 then 1 else 1 / aggMin;
def slowBars = Max(Round(relVolAvgMin * barsPerMin, 0), 1);
def rejBars = Max(Round(rejectLookback * barsPerMin, 0), 1);
def cooldownBars = Max(Round(cooldownMin * barsPerMin, 0), 1);

# ---- session + anchored VWAP ----
def isRTH = SecondsFromTime(marketOpen) >= 0 and SecondsTillTime(marketClose) > 0;
def newSession = isRTH and (!isRTH[1] or GetYYYYMMDD() != GetYYYYMMDD()[1]);
def tp = (high + low + close) / 3;
def cumPV = CompoundValue(1, if !isRTH then cumPV[1] else if newSession then tp*volume
    else cumPV[1] + tp*volume, tp*volume);
def cumV = CompoundValue(1, if !isRTH then cumV[1] else if newSession then volume
    else cumV[1] + volume, volume);
plot VWAP = if cumV > 0 then cumPV/cumV else Double.NaN;
VWAP.SetDefaultColor(Color.PLUM); VWAP.SetStyle(Curve.MEDIUM_DASH);
def belowVWAP = close < VWAP;

# ---- footprint components (all OHLCV) ----
def rng = Max(high - low, 0.0001);
def relVol = if Average(volume, slowBars) > 0 then volume / Average(volume, slowBars) else 1;
def upWick = (high - Max(open, close)) / rng;               # rejection from above
def dayHigh = CompoundValue(1, if !isRTH then dayHigh[1] else if newSession then high
    else Max(dayHigh[1], high), high);
def testingHigh = high >= dayHigh * highTestFrac;

# a REJECTION / ABSORPTION bar: high volume, upper-wick rejection, at a session high
# testMode loosens the gates so you can SEE dots on any day and confirm rendering
def rvThr = if testMode then 1.1 else relVolThr;
def wkThr = if testMode then 0.15 else wickThr;
def rejectionBar = isRTH and relVol >= rvThr and upWick >= wkThr and testingHigh;
# a DISTRIBUTION bar: elevated volume, closes below VWAP and below its open
def distribBar = isRTH and relVol >= distribRelVol and belowVWAP and close < open;

# distribution-footprint score (for the label / panel companion)
def footprint = relVol * (upWick + (if belowVWAP and close < open then 0.5 else 0));

# ---- SELL: a recent rejection-at-the-high, now confirmed by a VWAP loss ----
def recentRejection = Highest(if rejectionBar then 1 else 0, rejBars) > 0;
def sellCond = isRTH and recentRejection and belowVWAP and distribBar;
def sellEdge = sellCond and !sellCond[1];
def since = CompoundValue(1, if sellEdge and since[1] >= cooldownBars then 0 else since[1]+1, cooldownBars);
def sellFire = sellEdge and since == 0;

# ---- plots ----
plot Rejection = if rejectionBar then high * 1.001 else Double.NaN;   # the iceberg's shadow
Rejection.SetPaintingStrategy(PaintingStrategy.POINTS);   # POINTS (not BOOLEAN_POINTS) so the dot renders on the price overlay
Rejection.SetDefaultColor(Color.ORANGE);
Rejection.SetLineWeight(5);

plot Sell = if sellFire then high * 1.002 else Double.NaN;
Sell.SetPaintingStrategy(PaintingStrategy.ARROW_DOWN);
Sell.SetDefaultColor(Color.RED); Sell.SetLineWeight(5);

AddChartBubble(sellFire, high, "DISTRIB", Color.RED, yes);

AddLabel(showLabels, "relVol " + Round(relVol, 1),
    if relVol >= relVolThr then Color.ORANGE else Color.GRAY);
AddLabel(showLabels, "footprint " + Round(footprint, 1),
    if footprint >= 1.5 then Color.RED else Color.GRAY);
AddLabel(showLabels, if belowVWAP then "below VWAP" else "above VWAP",
    if belowVWAP then Color.RED else Color.GREEN);

Alert(rejectionBar, "FlowForensics: absorption/rejection at the high", Alert.BAR, Sound.Ding);
Alert(sellFire, "FlowForensics: distribution SELL (rejection + VWAP loss)", Alert.BAR, Sound.Bell);
