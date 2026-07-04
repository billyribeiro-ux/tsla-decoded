# FlowForensics_Daily — daily-timeframe buy/sell signals (upper study)
#
# Daily translations of the measured TSLA signatures, for DAY charts:
#   BUY  = accumulation day (the 2026-06-29 daily bar): up close finishing in
#          the top quartile of its range, volume above the 20-day average,
#          positive N-day flow imbalance, close above the 10-day EMA, and the
#          3-day run-up not already extended (exhaustion gate).
#   SELL = distribution, two triggers:
#          (a) key reversal (the 2026-07-02 daily bar): gap-up open that closes
#              red in the bottom quartile of its range on heavy volume after a
#              >= 8% 3-day run-up — the sell-the-news signature;
#          (b) breakdown: heavy-volume close below the prior day's low with
#              negative N-day flow imbalance.
# Validated on 64 trading days of TSLA EOD data: exactly two signals fired —
# BUY 2026-06-29, SELL 2026-07-02 (output/signal_validation.md). Rare by
# construction. Educational tool — not investment advice.

declare upper;

input imbDays = 10;           # N-day tick-rule flow-imbalance window
input buyImb = 0.10;
input sellImb = -0.15;
input clvBuy = 0.5;           # close-location value gates (top/bottom quartile)
input clvSell = -0.5;
input relVolAvg = 20;
input relVolThresh = 1.15;
input emaLen = 10;
input runupGate = 0.10;       # BUY exhaustion gate (3-day run-up)
input reversalRunup = 0.08;   # SELL key reversal needs at least this run-up
input paintBars = no;
input showLabels = yes;

def clv = if high == low then 0 else ((close - low) - (high - close)) / (high - low);
def relVol = if Average(volume, relVolAvg) > 0
             then volume / Average(volume, relVolAvg) else 1;
def sv = Sign(close - close[1]) * volume;
def imb = if Sum(volume, imbDays) > 0
          then Sum(sv, imbDays) / Sum(volume, imbDays) else 0;
def emaC = ExpAverage(close, emaLen);
def gapUp = open >= close[1];
def runup3 = if !IsNaN(close[4]) and close[4] != 0 then close[1] / close[4] - 1 else 0;

def buyCond = close > close[1]
    and clv >= clvBuy
    and relVol >= relVolThresh
    and imb >= buyImb
    and close > emaC
    and runup3 <= runupGate;

def sellReversal = gapUp
    and close < open
    and clv <= clvSell
    and relVol >= relVolThresh
    and runup3 >= reversalRunup;

def sellBreakdown = close < low[1]
    and relVol >= relVolThresh
    and imb <= sellImb;

def sellCond = sellReversal or sellBreakdown;

plot BuySignal = if buyCond then low else Double.NaN;
BuySignal.SetPaintingStrategy(PaintingStrategy.ARROW_UP);
BuySignal.SetDefaultColor(Color.GREEN);
BuySignal.SetLineWeight(4);

plot SellSignal = if sellCond then high else Double.NaN;
SellSignal.SetPaintingStrategy(PaintingStrategy.ARROW_DOWN);
SellSignal.SetDefaultColor(Color.RED);
SellSignal.SetLineWeight(4);

plot EmaLine = emaC;
EmaLine.SetDefaultColor(Color.PLUM);
EmaLine.SetStyle(Curve.MEDIUM_DASH);

AssignPriceColor(
    if !paintBars then Color.CURRENT
    else if buyCond then Color.DARK_GREEN
    else if sellCond then Color.DARK_RED
    else Color.CURRENT);

AddLabel(showLabels, "flow(" + imbDays + "d) " + AsPercent(imb),
    if imb >= buyImb then Color.GREEN
    else if imb <= sellImb then Color.RED else Color.GRAY);
AddLabel(showLabels, "relVol " + Round(relVol, 2),
    if relVol >= relVolThresh then Color.ORANGE else Color.GRAY);
AddLabel(showLabels, "3d run-up " + AsPercent(runup3),
    if runup3 >= reversalRunup then Color.ORANGE else Color.GRAY);

Alert(buyCond and !buyCond[1], "FlowForensics DAILY BUY: accumulation day",
      Alert.BAR, Sound.Ding);
Alert(sellCond and !sellCond[1], "FlowForensics DAILY SELL: reversal/breakdown",
      Alert.BAR, Sound.Bell);
