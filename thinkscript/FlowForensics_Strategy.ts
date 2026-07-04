# FlowForensics_Strategy — backtestable strategy version (thinkorswim Strategies tab)
#
# Same signal logic as FlowForensics_Signals, wired to AddOrder so thinkorswim's
# built-in strategy report (right-click chart -> Show Report) can evaluate it on
# any symbol/period. Long entries on the accumulation signature, optional short
# entries on the distribution/rejection signature, everything flattened by 15:55.
# Tuned on one measured week + 2-week baseline — backtest on longer history
# before any live use. Educational tool — not investment advice.

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
input allowShort = yes;
input tradeSize = 100;
input marketOpen = 0930;
input marketClose = 1600;
input flattenTime = 1555;

def isRTH = SecondsFromTime(marketOpen) >= 0 and SecondsTillTime(marketClose) > 0;
def newSession = isRTH and (!isRTH[1] or GetYYYYMMDD() != GetYYYYMMDD()[1]);
def minOfDay = if isRTH then Floor(SecondsFromTime(marketOpen) / 60) else 0;

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

def buyCond = isRTH and minOfDay >= imbWindow and aboveVWAP and imb >= buyThresh
    and relVol >= relVolThresh and clvS > 0 and dayCumSV >= cumSVHigh;
def sellCond = (isRTH and minOfDay >= 5 and minOfDay <= openWindowMin
        and hodMin <= openHighMin and gapUp and !aboveVWAP
        and dayImb <= sellThresh and relVol >= relVolThresh)
    or (isRTH and belowStreak >= belowVwapBars and imb <= sellThresh
        and failedReclaim and clvS < 0);

def buyEdge = buyCond and !buyCond[1];
def sellEdge = sellCond and !sellCond[1];
def sinceBuy = CompoundValue(1,
    if buyEdge and sinceBuy[1] >= cooldownBars then 0 else sinceBuy[1] + 1, cooldownBars);
def sinceSell = CompoundValue(1,
    if sellEdge and sinceSell[1] >= cooldownBars then 0 else sinceSell[1] + 1, cooldownBars);
def buyFire = buyEdge and sinceBuy == 0;
def sellFire = sellEdge and sinceSell == 0;
def flatten = SecondsTillTime(flattenTime) <= 0;

AddOrder(OrderType.BUY_TO_OPEN, buyFire and !flatten, open[-1], tradeSize,
         Color.GREEN, Color.GREEN, "FF Long");
AddOrder(OrderType.SELL_TO_CLOSE, sellFire or flatten, open[-1], tradeSize,
         Color.RED, Color.RED, "FF Long Exit");
AddOrder(OrderType.SELL_TO_OPEN, allowShort and sellFire and !flatten, open[-1], tradeSize,
         Color.DARK_RED, Color.DARK_RED, "FF Short");
AddOrder(OrderType.BUY_TO_CLOSE, allowShort and (buyFire or flatten), open[-1], tradeSize,
         Color.DARK_GREEN, Color.DARK_GREEN, "FF Short Exit");
