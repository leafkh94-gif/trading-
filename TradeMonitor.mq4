//+------------------------------------------------------------------+
//| TradeMonitor.mq4                                                 |
//| Sends your open MT4 positions to GoldScalperPro AI Agent        |
//| every few seconds so the agent can monitor and advise on them.  |
//|                                                                  |
//| SETUP:                                                           |
//| 1. In MT4: Tools → Options → Expert Advisors                    |
//|    ✓ Allow WebRequest for listed URL:                            |
//|      http://localhost:5000                                       |
//| 2. Attach this EA to ANY chart (e.g. XAUUSD M1)                 |
//| 3. Keep gold_agent.py running in the background                 |
//+------------------------------------------------------------------+
#property strict
#property version "1.0"

input string AgentURL      = "http://localhost:5000/trades"; // Agent endpoint
input int    SendInterval  = 5;   // Seconds between updates
input bool   AllSymbols    = true; // true = all symbols, false = only current chart

datetime g_lastSend = 0;

int OnInit()
{
   Print("TradeMonitor: connected to ", AgentURL);
   EventSetTimer(SendInterval);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   // Send empty trades list so agent knows no positions are open
   SendTrades("[]");
}

void OnTimer()
{
   SendTrades(BuildJSON());
}

// Also send on every tick for faster P&L updates
void OnTick()
{
   if(TimeCurrent() - g_lastSend < SendInterval) return;
   g_lastSend = TimeCurrent();
   SendTrades(BuildJSON());
}

//+------------------------------------------------------------------+
//| Build the JSON payload of all open positions                     |
//+------------------------------------------------------------------+
string BuildJSON()
{
   string trades = "";
   int    count  = 0;

   for(int i = 0; i < OrdersTotal(); i++)
   {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES)) continue;
      if(OrderType() > OP_SELL)                       continue; // Skip pending orders

      // Filter by symbol if requested
      if(!AllSymbols && OrderSymbol() != Symbol())    continue;

      double currentPrice = (OrderType() == OP_BUY) ? MarketInfo(OrderSymbol(), MODE_BID)
                                                     : MarketInfo(OrderSymbol(), MODE_ASK);
      double pointSize    = MarketInfo(OrderSymbol(), MODE_POINT);
      double pips         = (OrderType() == OP_BUY)
                            ? (currentPrice - OrderOpenPrice()) / pointSize
                            : (OrderOpenPrice() - currentPrice) / pointSize;
      double pnl          = OrderProfit() + OrderSwap() + OrderCommission();
      string direction    = (OrderType() == OP_BUY) ? "BUY" : "SELL";

      // Warn in JSON if stop is dangerously close
      double slDist = 0;
      if(OrderStopLoss() > 0)
         slDist = MathAbs(currentPrice - OrderStopLoss()) / pointSize;
      bool nearSL = (OrderStopLoss() > 0 && slDist < 30);

      if(count > 0) trades += ",";
      trades += StringFormat(
         "{\"ticket\":%d,\"symbol\":\"%s\",\"direction\":\"%s\","
         "\"lots\":%.2f,\"open\":%.3f,\"current\":%.3f,"
         "\"sl\":%.3f,\"tp\":%.3f,\"pnl\":%.2f,\"pips\":%.1f,\"near_sl\":%s}",
         OrderTicket(),
         OrderSymbol(),
         direction,
         OrderLots(),
         OrderOpenPrice(),
         currentPrice,
         OrderStopLoss(),
         OrderTakeProfit(),
         pnl,
         pips,
         nearSL ? "true" : "false"
      );
      count++;
   }

   return "[" + trades + "]";
}

//+------------------------------------------------------------------+
//| POST the trades JSON to the agent                                |
//+------------------------------------------------------------------+
void SendTrades(string tradesJSON)
{
   string body    = "{\"trades\":" + tradesJSON + "}";
   string headers = "Content-Type: application/json\r\n";

   char   postData[];
   char   response[];
   string respHeaders;

   int len = StringLen(body);
   ArrayResize(postData, len);
   StringToCharArray(body, postData, 0, len);

   int result = WebRequest("POST", AgentURL, headers, 3000,
                            postData, response, respHeaders);

   if(result == -1)
   {
      int err = GetLastError();
      if(err == 4060)
         Print("TradeMonitor: WebRequest not allowed. Go to MT4 Tools → Options → Expert Advisors → Add URL: http://localhost:5000");
      else
         Print("TradeMonitor: Send failed. Error: ", err);
   }
}
//+------------------------------------------------------------------+
