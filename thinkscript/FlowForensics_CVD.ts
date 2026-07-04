# FlowForensics_CVD — Cumulative Volume Delta with distribution divergence
#
# The community-standard thinkScript "order flow" proxy, done session-anchored and
# tuned to the hidden-distribution finding. IMPORTANT: this is an OHLC APPROXIMATION
# of delta (close-location volume), NOT true bid/ask order flow. thinkScript cannot
# read Level 2 / the order book / real aggressor volume — it can only estimate
# buying vs selling from where each bar closes in its range. Same class of proxy as
# every "CVD" indicator on the platform; it cannot see the iceberg. For the real
# book you need a DOM feed (Bookmap / Sierra Chart / your Databento data).
#
# What it DOES do well: flag DISTRIBUTION DIVERGENCE — price makes a new session
# high while cumulative delta does NOT confirm (buyers exhausted, supply hidden).
# Validated on the target week: no divergence on Mon's accumulation high; bearish
# divergence at Wed's 11:27 top; and July 2's CVD went negative by 09:32 while price
# was still ~427 — minutes before the -8%. Educational tool — not investment advice.

declare lower;

input marketOpen = 0930;
input marketClose = 1600;
input divergenceLookbackMin = 30;   # window to compare price high vs CVD high
input showDivergence = yes;

def isRTH = SecondsFromTime(marketOpen) >= 0 and SecondsTillTime(marketClose) > 0;
def newSession = isRTH and (!isRTH[1] or GetYYYYMMDD() != GetYYYYMMDD()[1]);
def aggMin = GetAggregationPeriod() / 60000;
def barsPerMin = if aggMin <= 0 or aggMin > 240 then 1 else 1 / aggMin;
def divBars = Max(Round(divergenceLookbackMin * barsPerMin, 0), 1);

# CLV delta (the OHLC approximation): volume split by close location in the bar
def rng = Max(high - low, 0.0001);
def buying = volume * (close - low) / rng;
def selling = volume * (high - close) / rng;
def delta = buying - selling;

# session-anchored cumulative delta
def cvd = CompoundValue(1, if !isRTH then cvd[1] else if newSession then delta
    else cvd[1] + delta, delta);

plot CVD = if isRTH then cvd else Double.NaN;
CVD.SetPaintingStrategy(PaintingStrategy.LINE);
CVD.AssignValueColor(if cvd >= 0 then Color.GREEN else Color.RED);
CVD.SetLineWeight(2);
plot Zero = if isRTH then 0 else Double.NaN;
Zero.SetDefaultColor(Color.GRAY);

# distribution divergence: price at a new session high, CVD NOT at its window high
def priceNewHigh = high >= Highest(high, divBars);
def cvdNewHigh = cvd >= Highest(cvd, divBars);
def bearDiv = isRTH and priceNewHigh and !cvdNewHigh;
# accumulation divergence: price at a new low, CVD holding (buyers absorbing)
def priceNewLow = low <= Lowest(low, divBars);
def cvdNewLow = cvd <= Lowest(cvd, divBars);
def bullDiv = isRTH and priceNewLow and !cvdNewLow;

plot BearDiv = if showDivergence and bearDiv then cvd else Double.NaN;
BearDiv.SetPaintingStrategy(PaintingStrategy.POINTS);
BearDiv.SetDefaultColor(Color.RED); BearDiv.SetLineWeight(4);
plot BullDiv = if showDivergence and bullDiv then cvd else Double.NaN;
BullDiv.SetPaintingStrategy(PaintingStrategy.POINTS);
BullDiv.SetDefaultColor(Color.GREEN); BullDiv.SetLineWeight(4);

AddLabel(yes, "CVD " + Round(cvd / 1000, 0) + "k",
    if cvd >= 0 then Color.GREEN else Color.RED);
AddLabel(yes, "OHLC-approx delta (NOT true order flow / L2)", Color.GRAY);

Alert(bearDiv, "FlowForensics CVD: bearish divergence (price high, delta not = distribution)",
      Alert.BAR, Sound.Bell);
