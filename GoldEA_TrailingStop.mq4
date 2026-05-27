//+------------------------------------------------------------------+
//| GoldEA_TrailingStop.mq4                                          |
//| Expert Advisor for XAU/USD (Gold) — 1-Minute Scalping           |
//| Strategy : EMA(8/21) crossover + RSI(14) overbought/oversold    |
//| Trailing  : Step-based activation with configurable threshold    |
//+------------------------------------------------------------------+
#property copyright "GoldEA"
#property link      ""
#property version   "1.00"
#property strict
#include <stdlib.mqh>

//+------------------------------------------------------------------+
//| INPUT PARAMETERS                                                 |
//+------------------------------------------------------------------+

// --- Indicator settings ---
input int    EMA_Fast_Period  = 8;      // Fast EMA period
input int    EMA_Slow_Period  = 21;     // Slow EMA period
input int    RSI_Period       = 14;     // RSI period
input double RSI_Overbought   = 70.0;  // Block longs above this RSI level
input double RSI_Oversold     = 30.0;  // Block shorts below this RSI level

// --- Risk management ---
input double LotSize           = 0.01;  // Trade volume (lots)
input double StopLoss_Points   = 200.0; // Stop loss distance in points (200 pts = 20 pips on 5-digit broker)
input double TakeProfit_Points = 400.0; // Take profit distance in points (2:1 R/R)
input double MaxSpreadPoints   = 50.0;  // Maximum allowed spread in points before rejecting entry
input int    MagicNumber       = 20241; // Unique ID — change if running multiple EA instances
input string TradeComment      = "GoldEA_v1";

// --- Trailing stop settings ---
input bool   UseTrailingStop       = true;   // Enable trailing stop
input double TrailActivation_Pts   = 150.0;  // Minimum profit (points) before trailing activates
input double TrailDistance_Pts     = 100.0;  // Points to keep SL behind current price
input double TrailStep_Pts         = 25.0;   // Minimum SL movement per update (prevents spamming OrderModify)

//+------------------------------------------------------------------+
//| GLOBAL STATE                                                     |
//+------------------------------------------------------------------+

datetime g_lastBarTime       = 0;     // Tracks last processed bar open time
bool     g_tradingAllowed    = true;  // Halted after 5 consecutive order errors
int      g_consecutiveErrors = 0;     // Count of consecutive OrderSend failures

//+------------------------------------------------------------------+
//| INITIALIZATION                                                   |
//+------------------------------------------------------------------+

int OnInit()
{
   // Symbol check — warn but don't fail (broker naming varies: XAUUSD, GOLD, XAU/USD)
   string sym = Symbol();
   if(StringFind(sym, "XAU") < 0 && StringFind(sym, "GOLD") < 0)
      Print("WARNING: EA designed for XAUUSD/GOLD. Active symbol: ", sym);

   // Timeframe check
   if(Period() != PERIOD_M1)
      Print("WARNING: EA optimized for M1. Current period: ", Period());

   // Input sanity checks
   if(EMA_Fast_Period >= EMA_Slow_Period)
   {
      Alert("GoldEA: Fast EMA period must be less than Slow EMA period.");
      return INIT_PARAMETERS_INCORRECT;
   }
   if(StopLoss_Points <= 0 || TakeProfit_Points <= 0)
   {
      Alert("GoldEA: Stop Loss and Take Profit must be positive.");
      return INIT_PARAMETERS_INCORRECT;
   }
   if(TrailDistance_Pts >= StopLoss_Points)
   {
      Alert("GoldEA: Trail distance must be less than initial stop loss.");
      return INIT_PARAMETERS_INCORRECT;
   }
   if(TrailActivation_Pts < TrailDistance_Pts)
   {
      Alert("GoldEA: Trail activation must be >= trail distance.");
      return INIT_PARAMETERS_INCORRECT;
   }

   // Log broker precision info (useful for debugging point/pip confusion)
   Print("GoldEA initialized | Symbol: ", sym,
         " | Point: ", DoubleToStr(Point, 6),
         " | Digits: ", Digits,
         " | Spread: ", MarketInfo(sym, MODE_SPREAD), " pts");

   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| DEINITIALIZATION                                                 |
//+------------------------------------------------------------------+

void OnDeinit(const int reason)
{
   Print("GoldEA removed. Reason code: ", reason,
         ". Open positions remain on the server.");
}

//+------------------------------------------------------------------+
//| MAIN TICK HANDLER                                                |
//+------------------------------------------------------------------+

void OnTick()
{
   // Hard stop: halt after repeated order failures
   if(!g_tradingAllowed) return;

   // --- Trailing stop runs on EVERY tick (price-sensitive) ---
   if(UseTrailingStop && GetOpenOrderCount() > 0)
      ManageTrailingStop();

   // --- Entry logic runs only once per new bar ---
   if(!IsNewBar()) return;

   // Only one trade at a time
   if(GetOpenOrderCount() > 0) return;

   // Reject entry if spread is too wide (news event guard)
   if(!ValidateSpread())
   {
      Print("GoldEA: Spread too wide (", MarketInfo(Symbol(), MODE_SPREAD),
            " pts). Skipping bar at ", TimeToStr(Time[0]));
      return;
   }

   // Evaluate signals and open if triggered
   if(CheckBuySignal())
      OpenBuyOrder();
   else if(CheckSellSignal())
      OpenSellOrder();
}

//+------------------------------------------------------------------+
//| BAR & ORDER HELPERS                                              |
//+------------------------------------------------------------------+

// Returns true exactly once per new M1 bar (on bar open)
bool IsNewBar()
{
   datetime currentBar = Time[0];
   if(currentBar != g_lastBarTime)
   {
      g_lastBarTime = currentBar;
      return true;
   }
   return false;
}

// Count EA's own open orders on this symbol (filtered by magic number)
int GetOpenOrderCount()
{
   int count = 0;
   for(int i = 0; i < OrdersTotal(); i++)
   {
      if(OrderSelect(i, SELECT_BY_POS, MODE_TRADES))
         if(OrderSymbol() == Symbol() && OrderMagicNumber() == MagicNumber)
            count++;
   }
   return count;
}

// Returns false if current spread exceeds MaxSpreadPoints
bool ValidateSpread()
{
   return (MarketInfo(Symbol(), MODE_SPREAD) <= MaxSpreadPoints);
}

//+------------------------------------------------------------------+
//| INDICATOR WRAPPERS                                               |
//+------------------------------------------------------------------+

// EMA value at the given bar shift on M1
double CalculateEMA(int period, int shift)
{
   return iMA(Symbol(), PERIOD_M1, period, 0, MODE_EMA, PRICE_CLOSE, shift);
}

// RSI value at the given bar shift on M1
double CalculateRSI(int shift)
{
   return iRSI(Symbol(), PERIOD_M1, RSI_Period, PRICE_CLOSE, shift);
}

//+------------------------------------------------------------------+
//| SIGNAL LOGIC                                                     |
//+------------------------------------------------------------------+
// Both functions use shift=1 and shift=2 (last two CLOSED bars).
// This avoids look-ahead bias from the still-forming bar[0].

bool CheckBuySignal()
{
   double fast1 = CalculateEMA(EMA_Fast_Period, 1);
   double slow1 = CalculateEMA(EMA_Slow_Period, 1);
   double fast2 = CalculateEMA(EMA_Fast_Period, 2);
   double slow2 = CalculateEMA(EMA_Slow_Period, 2);
   double rsi1  = CalculateRSI(1);

   // Fast EMA crossed above slow EMA between bar[2] and bar[1]
   bool crossUp = (fast2 <= slow2) && (fast1 > slow1);

   // RSI filter: avoid buying into overbought conditions
   bool rsiOk   = (rsi1 < RSI_Overbought);

   return crossUp && rsiOk;
}

bool CheckSellSignal()
{
   double fast1 = CalculateEMA(EMA_Fast_Period, 1);
   double slow1 = CalculateEMA(EMA_Slow_Period, 1);
   double fast2 = CalculateEMA(EMA_Fast_Period, 2);
   double slow2 = CalculateEMA(EMA_Slow_Period, 2);
   double rsi1  = CalculateRSI(1);

   // Fast EMA crossed below slow EMA between bar[2] and bar[1]
   bool crossDown = (fast2 >= slow2) && (fast1 < slow1);

   // RSI filter: avoid selling into oversold conditions
   bool rsiOk     = (rsi1 > RSI_Oversold);

   return crossDown && rsiOk;
}

//+------------------------------------------------------------------+
//| ORDER EXECUTION                                                  |
//+------------------------------------------------------------------+

void OpenBuyOrder()
{
   double ask  = NormalizePrice(Ask);
   double sl   = NormalizePrice(ask - StopLoss_Points   * Point);
   double tp   = NormalizePrice(ask + TakeProfit_Points * Point);

   // Respect broker minimum stop distance
   double minDist = MarketInfo(Symbol(), MODE_STOPLEVEL) * Point;
   if((ask - sl) < minDist)
      sl = NormalizePrice(ask - minDist - Point);

   int ticket = OrderSend(Symbol(), OP_BUY, LotSize, ask,
                          3, sl, tp, TradeComment, MagicNumber, 0, clrGreen);
   if(ticket < 0)
   {
      LogError("OpenBuyOrder", GetLastError());
      g_consecutiveErrors++;
      if(g_consecutiveErrors >= 5)
      {
         g_tradingAllowed = false;
         Alert("GoldEA: 5 consecutive order errors. Trading halted. Check Experts log.");
      }
   }
   else
   {
      g_consecutiveErrors = 0;
      Print("BUY opened | Ticket: ", ticket,
            " | SL: ", DoubleToStr(sl, Digits),
            " | TP: ", DoubleToStr(tp, Digits));
   }
}

void OpenSellOrder()
{
   double bid  = NormalizePrice(Bid);
   double sl   = NormalizePrice(bid + StopLoss_Points   * Point);
   double tp   = NormalizePrice(bid - TakeProfit_Points * Point);

   double minDist = MarketInfo(Symbol(), MODE_STOPLEVEL) * Point;
   if((sl - bid) < minDist)
      sl = NormalizePrice(bid + minDist + Point);

   int ticket = OrderSend(Symbol(), OP_SELL, LotSize, bid,
                          3, sl, tp, TradeComment, MagicNumber, 0, clrRed);
   if(ticket < 0)
   {
      LogError("OpenSellOrder", GetLastError());
      g_consecutiveErrors++;
      if(g_consecutiveErrors >= 5)
      {
         g_tradingAllowed = false;
         Alert("GoldEA: 5 consecutive order errors. Trading halted. Check Experts log.");
      }
   }
   else
   {
      g_consecutiveErrors = 0;
      Print("SELL opened | Ticket: ", ticket,
            " | SL: ", DoubleToStr(sl, Digits),
            " | TP: ", DoubleToStr(tp, Digits));
   }
}

//+------------------------------------------------------------------+
//| TRAILING STOP MANAGEMENT                                         |
//+------------------------------------------------------------------+
// Runs on every tick. Uses a step-based approach:
//   - Only activates once profit exceeds TrailActivation_Pts
//   - Only calls OrderModify when SL would move by at least TrailStep_Pts
//   - Never moves SL against the position (only tightens)
// This prevents "trade context busy" (error 146) from excessive modify calls.

void ManageTrailingStop()
{
   double minStopDist = MarketInfo(Symbol(), MODE_STOPLEVEL) * Point;

   for(int i = 0; i < OrdersTotal(); i++)
   {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES)) continue;
      if(OrderSymbol()      != Symbol())      continue;
      if(OrderMagicNumber() != MagicNumber)   continue;

      double openPrice = OrderOpenPrice();
      double currentSL = OrderStopLoss();
      double currentTP = OrderTakeProfit();

      // ---- BUY order trailing ----
      if(OrderType() == OP_BUY)
      {
         double profitPts = (Bid - openPrice) / Point;
         if(profitPts < TrailActivation_Pts) continue;

         double idealSL = NormalizePrice(Bid - TrailDistance_Pts * Point);

         // Move SL only if: it goes higher, moves by at least TrailStep, and satisfies broker minimum
         bool shouldMove = (idealSL > currentSL + TrailStep_Pts * Point) &&
                           ((Bid - idealSL) >= minStopDist);

         if(shouldMove)
         {
            if(!OrderModify(OrderTicket(), openPrice, idealSL, currentTP, 0, clrDodgerBlue))
               LogError("Trail_BUY_Modify", GetLastError());
         }
      }

      // ---- SELL order trailing ----
      else if(OrderType() == OP_SELL)
      {
         double profitPts = (openPrice - Ask) / Point;
         if(profitPts < TrailActivation_Pts) continue;

         double idealSL = NormalizePrice(Ask + TrailDistance_Pts * Point);

         // Move SL only if: it goes lower (or no SL set), moves by at least TrailStep, and satisfies broker minimum
         bool noSL       = (currentSL == 0);
         bool shouldMove = (noSL || idealSL < currentSL - TrailStep_Pts * Point) &&
                           ((idealSL - Ask) >= minStopDist);

         if(shouldMove)
         {
            if(!OrderModify(OrderTicket(), openPrice, idealSL, currentTP, 0, clrOrange))
               LogError("Trail_SELL_Modify", GetLastError());
         }
      }
   }
}

//+------------------------------------------------------------------+
//| UTILITY FUNCTIONS                                                |
//+------------------------------------------------------------------+

double NormalizePrice(double price)
{
   return NormalizeDouble(price, Digits);
}

void LogError(string context, int errorCode)
{
   string msg = StringFormat("[GoldEA ERROR] %s | Code: %d | %s | %s",
                             context, errorCode,
                             ErrorDescription(errorCode),
                             TimeToStr(TimeCurrent(), TIME_DATE | TIME_SECONDS));
   Print(msg);
   // Alert for server-side errors (>4000) which need trader attention
   if(errorCode > 4000)
      Alert(msg);
}
//+------------------------------------------------------------------+
