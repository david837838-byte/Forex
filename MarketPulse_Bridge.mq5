//+------------------------------------------------------------------+
//|                                           MarketPulse_Bridge.mq5 |
//|                                 Copyright 2026, MARKETPULSE FX   |
//|                          https://marketpulse.fx / 187.77.174.215 |
//+------------------------------------------------------------------+
#property copyright "MARKETPULSE FX"
#property link      "http://187.77.174.215:8080"
#property version   "2.00"
#property description "Institutional Real-Time Bidirectional Execution Bridge connecting MetaTrader 5 with MarketPulse FX Server"

#include <Trade\Trade.mqh>
CTrade trade;

input string ServerURL     = "http://187.77.174.215:2200/api/mt5/sync"; // MarketPulse Sync Webhook URL
input string SecretKey     = "marketpulse_live_bridge_sec_2026";       // Authentication Secret Key
input int    SyncInterval  = 1;                                          // Sync Interval in Seconds (1s)
input ulong  MagicNumber   = 888999;                                     // Magic Number for Bot Orders

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   trade.SetExpertMagicNumber(MagicNumber);
   EventSetTimer(SyncInterval);
   Print("🟢 [MarketPulse Bridge v2.0] Started successfully. Syncing 1-sec stream with: ", ServerURL);
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   Print("🔴 [MarketPulse Bridge v2.0] Stopped.");
}

//+------------------------------------------------------------------+
//| Helper to build JSON string of open positions                     |
//+------------------------------------------------------------------+
string GetOpenPositionsJSON()
{
   string json = "[";
   int total = PositionsTotal();
   int count = 0;
   
   for(int i = 0; i < total; i++)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket > 0)
      {
         string sym   = PositionGetString(POSITION_SYMBOL);
         long type    = PositionGetInteger(POSITION_TYPE);
         double vol   = PositionGetDouble(POSITION_VOLUME);
         double openP = PositionGetDouble(POSITION_PRICE_OPEN);
         double curP  = PositionGetDouble(POSITION_PRICE_CURRENT);
         double sl    = PositionGetDouble(POSITION_SL);
         double tp    = PositionGetDouble(POSITION_TP);
         double pnl   = PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
         
         string posJson = StringFormat("{"ticket":"%I64u","symbol":"%s","type":"%s","lot":%.2f,"entry":%.5f,"current_price":%.5f,"sl":%.5f,"tp1":%.5f,"pnl":%.2f}",
                                       ticket, sym, (type == POSITION_TYPE_BUY ? "BUY" : "SELL"), vol, openP, curP, sl, tp, pnl);
         
         if(count > 0) json += ",";
         json += posJson;
         count++;
      }
   }
   json += "]";
   return json;
}

//+------------------------------------------------------------------+
//| Expert timer function (Syncs balance & executes commands)        |
//+------------------------------------------------------------------+
void OnTimer()
{
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double equity  = AccountInfoDouble(ACCOUNT_EQUITY);
   double margin  = AccountInfoDouble(ACCOUNT_MARGIN);
   double freeMar = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
   long   login   = AccountInfoInteger(ACCOUNT_LOGIN);
   string server  = AccountInfoString(ACCOUNT_SERVER);
   string curr    = AccountInfoString(ACCOUNT_CURRENCY);
   
   string positionsJson = GetOpenPositionsJSON();
   
   // Build full synchronization payload with secret
   string payload = StringFormat("{"secret":"%s","login":%I64d,"server":"%s","currency":"%s","balance":%.2f,"equity":%.2f,"margin":%.2f,"free_margin":%.2f,"positions":%s}",
                                 SecretKey, login, server, curr, balance, equity, margin, freeMar, positionsJson);
   
   char postData[];
   char resultData[];
   string resultHeaders;
   StringToCharArray(payload, postData, 0, WHOLE_ARRAY, CP_UTF8);
   ArrayResize(postData, ArraySize(postData) - 1); // remove null terminator
   
   string headers = StringFormat("Content-Type: application/json
X-MarketPulse-Secret: %s
", SecretKey);
   
   int res = WebRequest("POST", ServerURL, headers, 1500, postData, resultData, resultHeaders);
   
   if(res == 200)
   {
      string responseText = CharArrayToString(resultData, 0, WHOLE_ARRAY, CP_UTF8);
      ProcessServerCommands(responseText);
   }
   else if(res == -1)
   {
      Print("⚠️ [MarketPulse Bridge] WebRequest error: ", GetLastError(), ". Please add 'http://187.77.174.215:2200' to Tools -> Options -> Expert Advisors -> Allow WebRequest.");
   }
}

//+------------------------------------------------------------------+
//| Simple JSON key-value string extractor                           |
//+------------------------------------------------------------------+
string ExtractJSONValue(string json, string key)
{
   string pattern = "\"" + key + "\":";
   int pos = StringFind(json, pattern);
   if(pos < 0) return "";
   
   int start = pos + StringLen(pattern);
   while(start < StringLen(json) && (StringGetCharacter(json, start) == ' ' || StringGetCharacter(json, start) == '"'))
      start++;
      
   int end = start;
   while(end < StringLen(json) && StringGetCharacter(json, end) != '"' && StringGetCharacter(json, end) != ',' && StringGetCharacter(json, end) != '}')
      end++;
      
   return StringSubstr(json, start, end - start);
}

//+------------------------------------------------------------------+
//| Parse and execute server commands (OPEN, CLOSE, MODIFY_SL, etc.) |
//+------------------------------------------------------------------+
void ProcessServerCommands(string response)
{
   if(StringFind(response, ""commands":") < 0) return;
   
   // 1. OPEN ORDER COMMAND
   if(StringFind(response, ""action":"OPEN"") >= 0)
   {
      string sym = ExtractJSONValue(response, "symbol");
      string typ = ExtractJSONValue(response, "type");
      double lot = StringToDouble(ExtractJSONValue(response, "lot"));
      double sl  = StringToDouble(ExtractJSONValue(response, "sl"));
      double tp  = StringToDouble(ExtractJSONValue(response, "tp1"));
      
      if(sym != "" && lot > 0)
      {
         bool ok = false;
         if(typ == "BUY")
         {
            ok = trade.Buy(lot, sym, 0, sl, tp, "MarketPulse AI");
            Print("🚀 [MarketPulse Bridge] BUY Order Sent: ", sym, " Lot: ", lot, " SL: ", sl, " TP: ", tp, " | Result: ", (ok ? "SUCCESS ✅" : "FAILED ❌"));
         }
         else if(typ == "SELL")
         {
            ok = trade.Sell(lot, sym, 0, sl, tp, "MarketPulse AI");
            Print("🚀 [MarketPulse Bridge] SELL Order Sent: ", sym, " Lot: ", lot, " SL: ", sl, " TP: ", tp, " | Result: ", (ok ? "SUCCESS ✅" : "FAILED ❌"));
         }
      }
   }
   
   // 2. CLOSE ORDER COMMAND
   if(StringFind(response, ""action":"CLOSE"") >= 0)
   {
      string ticketStr = ExtractJSONValue(response, "ticket");
      ulong ticket = (ulong)StringToInteger(ticketStr);
      if(ticket > 0)
      {
         bool ok = trade.PositionClose(ticket);
         Print("🔒 [MarketPulse Bridge] Position Close Sent for #", ticket, " | Result: ", (ok ? "SUCCESS ✅" : "FAILED ❌"));
      }
   }
   
   // 3. MODIFY STOP LOSS (AUTO BREAK-EVEN / TRAILING STOP)
   if(StringFind(response, ""action":"MODIFY_SL"") >= 0)
   {
      string ticketStr = ExtractJSONValue(response, "ticket");
      ulong ticket = (ulong)StringToInteger(ticketStr);
      double new_sl = StringToDouble(ExtractJSONValue(response, "new_sl"));
      double new_tp = StringToDouble(ExtractJSONValue(response, "new_tp"));
      
      if(ticket > 0 && new_sl > 0)
      {
         bool ok = trade.PositionModify(ticket, new_sl, new_tp);
         Print("🛡️ [MarketPulse Bridge] Stop Loss Modified for #", ticket, " to: ", new_sl, " | Result: ", (ok ? "SUCCESS ✅" : "FAILED ❌"));
      }
   }
   
   // 4. PARTIAL CLOSE COMMAND (TP1 50% / TP2 30%)
   if(StringFind(response, ""action":"CLOSE_PARTIAL"") >= 0)
   {
      string ticketStr = ExtractJSONValue(response, "ticket");
      ulong ticket = (ulong)StringToInteger(ticketStr);
      double close_lot = StringToDouble(ExtractJSONValue(response, "close_lot"));
      
      if(ticket > 0 && close_lot > 0)
      {
         bool ok = trade.PositionClosePartial(ticket, close_lot);
         Print("🎯 [MarketPulse Bridge] Partial Close (", close_lot, " lot) for #", ticket, " | Result: ", (ok ? "SUCCESS ✅" : "FAILED ❌"));
      }
   }
}
//+------------------------------------------------------------------+
