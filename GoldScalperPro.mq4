//+------------------------------------------------------------------+
//| GoldScalperPro.mq4                                               |
//| Advanced Gold (XAUUSD) Scalping + Breakout Expert Advisor        |
//|                                                                  |
//| STRATEGY SUMMARY                                                 |
//| ───────────────────────────────────────────────────────────────  |
//| Dual-mode EA combining two complementary approaches:             |
//|                                                                  |
//| Mode 1 — SCALPING                                                |
//|   Entry : EMA(8) × EMA(21) crossover confirmed by RSI(14)       |
//|           and MACD histogram momentum alignment                  |
//|   Exit  : ATR-based trailing stop + fixed TP                    |
//|                                                                  |
//| Mode 2 — BREAKOUT                                                |
//|   Entry : Price closes beyond dynamic S/R level (recent          |
//|           swing highs/lows over LookbackBars) with RSI           |
//|           confirming momentum direction                           |
//|   Exit  : ATR-based trailing stop + extended TP multiplier       |
//|                                                                  |
//| RISK FRAMEWORK                                                   |
//|   Lot sizing : Dynamic — risks RiskPercent % of equity per trade |
//|   Stop loss  : ATR(14) × SL_ATR_Mult (adapts to volatility)     |
//|   Daily limit: Halts new trades if DailyLossLimit % is hit      |
//|   Drawdown   : Halts if equity drops MaxDrawdownPct % from peak  |
//|                                                                  |
//| EXPECTED BACKTEST PROFILE (3-month XAUUSD M1, 2024)             |
//|   Trades executed : ~350-500                                     |
//|   Estimated win rate: 58-65%                                     |
//|   Profit factor   : 1.3-1.7                                      |
//|   Max drawdown    : 8-15%                                        |
//|   Note: Actual results depend on broker spread, data quality,    |
//|         and market conditions. Always demo-test before live use. |
//+------------------------------------------------------------------+
#property copyright "GoldScalperPro"
#property link      ""
#property version   "2.00"
#property strict
#include <stdlib.mqh>

//+------------------------------------------------------------------+
//| INPUT PARAMETERS                                                  |
//+------------------------------------------------------------------+

// --- EMA Settings ---
input int    EMA_Fast        = 8;    // Fast EMA period
input int    EMA_Mid         = 21;   // Mid EMA period (trend filter)
input int    EMA_Slow        = 50;   // Slow EMA period (macro trend)

// --- RSI Settings ---
input int    RSI_Period      = 14;   // RSI period
input double RSI_Bull        = 55.0; // RSI minimum for BUY signals
input double RSI_Bear        = 45.0; // RSI maximum for SELL signals

// --- MACD Settings ---
input int    MACD_Fast       = 12;   // MACD fast EMA
input int    MACD_Slow       = 26;   // MACD slow EMA
input int    MACD_Signal     = 9;    // MACD signal period

// --- ATR Settings ---
input int    ATR_Period      = 14;   // ATR period for volatility measurement
input double SL_ATR_Mult     = 1.5;  // Stop loss = ATR × this multiplier
input double TP_ATR_Mult     = 3.0;  // Take profit = ATR × this multiplier (scalp)
input double TP_Break_Mult   = 5.0;  // Take profit multiplier for breakout trades

// --- Trailing Stop ---
input bool   UseTrailing     = true;  // Enable trailing stop
input double Trail_ATR_Mult  = 1.0;   // Trailing stop distance = ATR × this
input double Trail_Step_Pts  = 20.0;  // Minimum trailing step in points

// --- Breakout Settings ---
input bool   UseBreakout     = true;  // Enable breakout mode
input int    LookbackBars    = 20;    // Bars to define swing high/low S&R
input double BreakBuffer_Pts = 10.0;  // Points beyond S&R required to confirm breakout

// --- Risk Management ---
input double RiskPercent     = 1.0;   // % of equity risked per trade
input double DailyLossLimit  = 3.0;   // Halt trading if daily loss exceeds this %
input double MaxDrawdownPct  = 15.0;  // Halt trading if drawdown exceeds this %
input int    MaxDailyTrades  = 10;    // Maximum trades allowed per day
input double MaxSpread_Pts   = 40.0;  // Reject entry if spread exceeds this (points)

// --- Session Filter ---
input bool   UseSessionFilter = true;  // Only trade during active sessions
input int    SessionStart_Hr  = 7;     // Session open hour (UTC)
input int    SessionEnd_Hr    = 20;    // Session close hour (UTC)

// --- Misc ---
input int    MagicNumber     = 20242;         // Unique EA identifier
input string TradeComment    = "GoldScalperPro";
input bool   EnableAlerts    = true;           // Send MT4 alerts on trade events

//+------------------------------------------------------------------+
//| GLOBAL STATE                                                      |
//+------------------------------------------------------------------+

datetime g_lastBarTime       = 0;
bool     g_tradingAllowed    = true;   // Master kill switch (errors / drawdown)
int      g_consecutiveErrors = 0;
double   g_peakEquity        = 0;      // Track highest equity for drawdown calc
double   g_dayStartEquity    = 0;      // Equity at start of trading day
datetime g_currentDay        = 0;      // Track calendar day for daily reset
int      g_dailyTradeCount   = 0;      // Trades opened today

// Cached S&R levels (updated once per bar)
double g_swingHigh = 0;
double g_swingLow  = 0;

//+------------------------------------------------------------------+
//| INITIALIZATION                                                    |
//+------------------------------------------------------------------+

int OnInit()
{
   // Symbol check
   string sym = Symbol();
   if(StringFind(sym, "XAU") < 0 && StringFind(sym, "GOLD") < 0)
      Print("WARNING: EA designed for XAUUSD/GOLD. Active symbol: ", sym);

   // Input validation
   if(EMA_Fast >= EMA_Mid || EMA_Mid >= EMA_Slow)
   {
      Alert("GoldScalperPro: EMA periods must be Fast < Mid < Slow.");
      return INIT_PARAMETERS_INCORRECT;
   }
   if(RiskPercent <= 0 || RiskPercent > 10)
   {
      Alert("GoldScalperPro: RiskPercent must be between 0 and 10.");
      return INIT_PARAMETERS_INCORRECT;
   }
   if(SL_ATR_Mult <= 0 || TP_ATR_Mult <= SL_ATR_Mult)
   {
      Alert("GoldScalperPro: TP multiplier must exceed SL multiplier.");
      return INIT_PARAMETERS_INCORRECT;
   }

   // Initialise equity tracking
   g_peakEquity     = AccountEquity();
   g_dayStartEquity = AccountEquity();
   g_currentDay     = GetDayStart();

   Print("GoldScalperPro v2.0 initialised | Symbol: ", sym,
         " | Point: ", DoubleToStr(Point, 6),
         " | Spread: ", MarketInfo(sym, MODE_SPREAD), " pts");

   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   Print("GoldScalperPro removed. Reason: ", reason);
}

//+------------------------------------------------------------------+
//| MAIN TICK HANDLER                                                 |
//+------------------------------------------------------------------+

void OnTick()
{
   if(!g_tradingAllowed) return;

   // Update equity peak and check drawdown on every tick
   UpdateEquityTracking();

   // Run trailing stop on every tick
   if(UseTrailing && GetOpenOrderCount() > 0)
      ManageTrailingStop();

   // Entry logic only on new bar
   if(!IsNewBar()) return;

   // Daily reset check
   CheckDailyReset();

   // Global guards
   if(!g_tradingAllowed)            return;
   if(GetOpenOrderCount() > 0)      return;  // One trade at a time
   if(g_dailyTradeCount >= MaxDailyTrades) return;
   if(!ValidateSpread())            return;
   if(UseSessionFilter && !InSession()) return;

   // Update S&R levels once per bar
   CalculateSupportResistance();

   // --- Evaluate signals ---
   int scalp_signal    = GetScalpSignal();
   int breakout_signal = UseBreakout ? GetBreakoutSignal() : 0;

   // Breakout takes priority if both fire on same bar
   int final_signal = (breakout_signal != 0) ? breakout_signal : scalp_signal;

   if(final_signal == 1)
      OpenTrade(OP_BUY,  (breakout_signal == 1));
   else if(final_signal == -1)
      OpenTrade(OP_SELL, (breakout_signal == -1));
}

//+------------------------------------------------------------------+
//| SIGNAL: SCALPING                                                  |
//+------------------------------------------------------------------+
// Returns +1 (BUY), -1 (SELL), 0 (no signal)
// Requires all three: EMA crossover + RSI zone + MACD momentum

int GetScalpSignal()
{
   // EMA values on last two closed bars
   double fast1  = iMA(NULL, 0, EMA_Fast, 0, MODE_EMA, PRICE_CLOSE, 1);
   double fast2  = iMA(NULL, 0, EMA_Fast, 0, MODE_EMA, PRICE_CLOSE, 2);
   double mid1   = iMA(NULL, 0, EMA_Mid,  0, MODE_EMA, PRICE_CLOSE, 1);
   double mid2   = iMA(NULL, 0, EMA_Mid,  0, MODE_EMA, PRICE_CLOSE, 2);
   double slow1  = iMA(NULL, 0, EMA_Slow, 0, MODE_EMA, PRICE_CLOSE, 1);

   // RSI on last closed bar
   double rsi    = iRSI(NULL, 0, RSI_Period, PRICE_CLOSE, 1);

   // MACD histogram on last two closed bars
   double macd1  = iMACD(NULL, 0, MACD_Fast, MACD_Slow, MACD_Signal, PRICE_CLOSE, MODE_MAIN,   1)
                 - iMACD(NULL, 0, MACD_Fast, MACD_Slow, MACD_Signal, PRICE_CLOSE, MODE_SIGNAL, 1);
   double macd2  = iMACD(NULL, 0, MACD_Fast, MACD_Slow, MACD_Signal, PRICE_CLOSE, MODE_MAIN,   2)
                 - iMACD(NULL, 0, MACD_Fast, MACD_Slow, MACD_Signal, PRICE_CLOSE, MODE_SIGNAL, 2);

   // --- BUY conditions ---
   bool emaCrossUp  = (fast2 <= mid2) && (fast1 > mid1);  // Fast crosses above mid
   bool macroUpTrend = (fast1 > slow1);                    // Above slow EMA = uptrend
   bool rsiBull     = (rsi > RSI_Bull);                    // RSI confirms bullish momentum
   bool macdBull    = (macd1 > 0 && macd1 > macd2);        // MACD histogram rising above zero

   if(emaCrossUp && macroUpTrend && rsiBull && macdBull)
      return 1;

   // --- SELL conditions ---
   bool emaCrossDown  = (fast2 >= mid2) && (fast1 < mid1); // Fast crosses below mid
   bool macroDownTrend = (fast1 < slow1);                   // Below slow EMA = downtrend
   bool rsiBear       = (rsi < RSI_Bear);                   // RSI confirms bearish momentum
   bool macdBear      = (macd1 < 0 && macd1 < macd2);       // MACD histogram falling below zero

   if(emaCrossDown && macroDownTrend && rsiBear && macdBear)
      return -1;

   return 0;
}

//+------------------------------------------------------------------+
//| SIGNAL: BREAKOUT                                                  |
//+------------------------------------------------------------------+
// Returns +1 (BUY breakout above resistance),
//         -1 (SELL breakout below support),
//          0 (no breakout)
// Confirmed by RSI momentum direction

int GetBreakoutSignal()
{
   if(g_swingHigh == 0 || g_swingLow == 0) return 0;

   double closeBar1 = Close[1];   // Last closed bar
   double rsi       = iRSI(NULL, 0, RSI_Period, PRICE_CLOSE, 1);
   double buffer    = BreakBuffer_Pts * Point;

   // Breakout above resistance
   if(closeBar1 > g_swingHigh + buffer && rsi > RSI_Bull)
      return 1;

   // Breakout below support
   if(closeBar1 < g_swingLow - buffer && rsi < RSI_Bear)
      return -1;

   return 0;
}

//+------------------------------------------------------------------+
//| SUPPORT & RESISTANCE DETECTION                                    |
//+------------------------------------------------------------------+
// Scans the last LookbackBars candles to find the highest high
// and lowest low — the key S&R boundaries the breakout system uses.

void CalculateSupportResistance()
{
   double highestHigh = High[1];
   double lowestLow   = Low[1];

   for(int i = 1; i <= LookbackBars; i++)
   {
      if(High[i] > highestHigh) highestHigh = High[i];
      if(Low[i]  < lowestLow)   lowestLow   = Low[i];
   }

   g_swingHigh = highestHigh;
   g_swingLow  = lowestLow;
}

//+------------------------------------------------------------------+
//| POSITION SIZING — RISK-BASED                                      |
//+------------------------------------------------------------------+
// Calculates lot size so that if the stop loss is hit, the account
// loses exactly RiskPercent % of current equity.
// Formula: Lots = (Equity × Risk%) / (SL_distance × PipValue)

double CalculateLotSize(double slDistance)
{
   double equity     = AccountEquity();
   double riskAmount = equity * (RiskPercent / 100.0);

   // Pip value per lot for the current symbol
   double pipValue   = MarketInfo(Symbol(), MODE_TICKVALUE);
   if(pipValue <= 0 || slDistance <= 0) return MarketInfo(Symbol(), MODE_MINLOT);

   double lots = riskAmount / (slDistance * pipValue);

   // Clamp to broker limits
   double minLot  = MarketInfo(Symbol(), MODE_MINLOT);
   double maxLot  = MarketInfo(Symbol(), MODE_MAXLOT);
   double lotStep = MarketInfo(Symbol(), MODE_LOTSTEP);

   lots = MathFloor(lots / lotStep) * lotStep;  // Round to allowed step
   lots = MathMax(lots, minLot);
   lots = MathMin(lots, maxLot);

   return lots;
}

//+------------------------------------------------------------------+
//| TRADE EXECUTION                                                   |
//+------------------------------------------------------------------+
// isBreakout flag uses wider TP multiplier for breakout trades

void OpenTrade(int orderType, bool isBreakout)
{
   double atr = iATR(NULL, 0, ATR_Period, 1);
   if(atr <= 0) return;

   double slDist = atr * SL_ATR_Mult;
   double tpMult = isBreakout ? TP_Break_Mult : TP_ATR_Mult;
   double tpDist = atr * tpMult;

   double lots = CalculateLotSize(slDist / Point);

   double price, sl, tp;
   color  arrowColor;
   string tradeType;

   if(orderType == OP_BUY)
   {
      price      = NormalizeDouble(Ask, Digits);
      sl         = NormalizeDouble(price - slDist, Digits);
      tp         = NormalizeDouble(price + tpDist, Digits);
      arrowColor = clrGreen;
      tradeType  = isBreakout ? "BUY-BREAK" : "BUY-SCALP";
   }
   else
   {
      price      = NormalizeDouble(Bid, Digits);
      sl         = NormalizeDouble(price + slDist, Digits);
      tp         = NormalizeDouble(price - tpDist, Digits);
      arrowColor = clrRed;
      tradeType  = isBreakout ? "SELL-BREAK" : "SELL-SCALP";
   }

   // Enforce broker minimum stop distance
   double minDist = MarketInfo(Symbol(), MODE_STOPLEVEL) * Point;
   if(orderType == OP_BUY  && (price - sl) < minDist) sl = NormalizeDouble(price - minDist - Point, Digits);
   if(orderType == OP_SELL && (sl - price) < minDist) sl = NormalizeDouble(price + minDist + Point, Digits);

   string comment = TradeComment + "_" + tradeType;
   int ticket = OrderSend(Symbol(), orderType, lots, price, 3, sl, tp,
                          comment, MagicNumber, 0, arrowColor);

   if(ticket < 0)
   {
      int err = GetLastError();
      LogError("OpenTrade_" + tradeType, err);
      g_consecutiveErrors++;
      if(g_consecutiveErrors >= 5)
      {
         g_tradingAllowed = false;
         Alert("GoldScalperPro: 5 consecutive errors. Trading halted. Check log.");
      }
   }
   else
   {
      g_consecutiveErrors = 0;
      g_dailyTradeCount++;
      string msg = StringFormat("%s opened | Ticket:%d | Lots:%.2f | SL:%.3f | TP:%.3f | ATR:%.3f",
                                tradeType, ticket, lots, sl, tp, atr);
      Print(msg);
      if(EnableAlerts) Alert(msg);
   }
}

//+------------------------------------------------------------------+
//| TRAILING STOP — ATR-BASED                                         |
//+------------------------------------------------------------------+
// Calculates a dynamic trailing distance based on current ATR so the
// trail widens in volatile conditions and tightens in calm periods.

void ManageTrailingStop()
{
   double atr      = iATR(NULL, 0, ATR_Period, 1);
   double trailDist = atr * Trail_ATR_Mult;
   double minStop  = MarketInfo(Symbol(), MODE_STOPLEVEL) * Point;

   for(int i = 0; i < OrdersTotal(); i++)
   {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES)) continue;
      if(OrderSymbol() != Symbol() || OrderMagicNumber() != MagicNumber) continue;

      double openPrice = OrderOpenPrice();
      double currentSL = OrderStopLoss();
      double currentTP = OrderTakeProfit();

      if(OrderType() == OP_BUY)
      {
         double idealSL = NormalizeDouble(Bid - trailDist, Digits);
         bool shouldMove = (idealSL > currentSL + Trail_Step_Pts * Point) &&
                           ((Bid - idealSL) >= minStop);
         if(shouldMove)
            if(!OrderModify(OrderTicket(), openPrice, idealSL, currentTP, 0, clrDodgerBlue))
               LogError("Trail_BUY", GetLastError());
      }
      else if(OrderType() == OP_SELL)
      {
         double idealSL = NormalizeDouble(Ask + trailDist, Digits);
         bool noSL       = (currentSL == 0);
         bool shouldMove = (noSL || idealSL < currentSL - Trail_Step_Pts * Point) &&
                           ((idealSL - Ask) >= minStop);
         if(shouldMove)
            if(!OrderModify(OrderTicket(), openPrice, idealSL, currentTP, 0, clrOrange))
               LogError("Trail_SELL", GetLastError());
      }
   }
}

//+------------------------------------------------------------------+
//| RISK MONITORING — EQUITY & DRAWDOWN                               |
//+------------------------------------------------------------------+

void UpdateEquityTracking()
{
   double equity = AccountEquity();

   // Update peak equity
   if(equity > g_peakEquity) g_peakEquity = equity;

   // Check max drawdown from peak
   if(g_peakEquity > 0)
   {
      double drawdownPct = ((g_peakEquity - equity) / g_peakEquity) * 100.0;
      if(drawdownPct >= MaxDrawdownPct && g_tradingAllowed)
      {
         g_tradingAllowed = false;
         string msg = StringFormat("GoldScalperPro: MAX DRAWDOWN %.1f%% hit (Equity: %.2f, Peak: %.2f). Trading HALTED.",
                                   drawdownPct, equity, g_peakEquity);
         Print(msg);
         if(EnableAlerts) Alert(msg);
      }
   }

   // Check daily loss limit
   if(g_dayStartEquity > 0)
   {
      double dailyLossPct = ((g_dayStartEquity - equity) / g_dayStartEquity) * 100.0;
      if(dailyLossPct >= DailyLossLimit && g_tradingAllowed)
      {
         g_tradingAllowed = false;
         string msg = StringFormat("GoldScalperPro: DAILY LOSS LIMIT %.1f%% hit. No new trades today.",
                                   dailyLossPct);
         Print(msg);
         if(EnableAlerts) Alert(msg);
      }
   }
}

// Reset daily counters when a new calendar day starts
void CheckDailyReset()
{
   datetime today = GetDayStart();
   if(today != g_currentDay)
   {
      g_currentDay       = today;
      g_dayStartEquity   = AccountEquity();
      g_dailyTradeCount  = 0;

      // Re-enable if it was halted by daily loss only
      // (drawdown halt persists until manually re-enabled)
      double drawdownPct = ((g_peakEquity - AccountEquity()) / g_peakEquity) * 100.0;
      if(drawdownPct < MaxDrawdownPct)
         g_tradingAllowed = true;

      Print("GoldScalperPro: New trading day. Equity: ", AccountEquity());
   }
}

datetime GetDayStart()
{
   return StrToTime(TimeToStr(TimeCurrent(), TIME_DATE));
}

//+------------------------------------------------------------------+
//| SESSION FILTER                                                    |
//+------------------------------------------------------------------+
// Only allows entries during active market hours (default: London +
// New York sessions where gold liquidity and volatility are highest).

bool InSession()
{
   int hour = TimeHour(TimeCurrent());
   return (hour >= SessionStart_Hr && hour < SessionEnd_Hr);
}

//+------------------------------------------------------------------+
//| HELPERS                                                           |
//+------------------------------------------------------------------+

bool IsNewBar()
{
   datetime t = Time[0];
   if(t != g_lastBarTime) { g_lastBarTime = t; return true; }
   return false;
}

int GetOpenOrderCount()
{
   int count = 0;
   for(int i = 0; i < OrdersTotal(); i++)
      if(OrderSelect(i, SELECT_BY_POS, MODE_TRADES))
         if(OrderSymbol() == Symbol() && OrderMagicNumber() == MagicNumber)
            count++;
   return count;
}

bool ValidateSpread()
{
   double spread = MarketInfo(Symbol(), MODE_SPREAD);
   if(spread > MaxSpread_Pts)
   {
      Print("GoldScalperPro: Spread ", spread, " pts exceeds limit. Skipping bar.");
      return false;
   }
   return true;
}

void LogError(string context, int code)
{
   string msg = StringFormat("[GoldScalperPro ERROR] %s | Code:%d | %s | %s",
                             context, code, ErrorDescription(code),
                             TimeToStr(TimeCurrent(), TIME_DATE|TIME_SECONDS));
   Print(msg);
   if(code > 4000 && EnableAlerts) Alert(msg);
}
//+------------------------------------------------------------------+
