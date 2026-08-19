//+------------------------------------------------------------------+
//|                                           MarketPulse_Bridge.mq5 |
//|                                 Copyright 2026, MARKETPULSE FX   |
//|                          https://marketpulse.fx / 187.77.174.215 |
//+------------------------------------------------------------------+
#property copyright "MARKETPULSE FX"
#property link      "http://187.77.174.215:8080"
#property version   "1.00"
#property description "Dual-Channel Real-Time Bridge connecting MetaTrader 5 with MarketPulse FX Server"

#include <Trade\Trade.mqh>
CTrade trade;

input string ServerURL     = "http://187.77.174.215:2200/api/mt5/sync"; // MarketPulse Webhook URL
input int    SyncInterval  = 1;                                          // Sync Interval in Seconds
input ulong  MagicNumber   = 888999;                                     // Magic Number for Bot Orders

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   trade.SetExpertMagicNumber(MagicNumber);
   EventSetTimer(SyncInterval);
   Print("🟢 [MarketPulse Bridge] Started successfully. Syncing with: ", ServerURL);
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   Print("🔴 [MarketPulse Bridge] Stopped.");
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
         double pnl   = PositionGetDouble(POSITION_PROFIT);
         
         string posJson = StringFormat("{\"ticket\":\"%d\",\"symbol\":\"%s\",\"type\":\"%s\",\"lot\":%.2f,\"entry\":%.5f,\"current_price\":%.5f,\"sl\":%.5f,\"tp1\":%.5f,\"pnl\":%.2f}",
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
   double margin  = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
   long   login   = AccountInfoInteger(ACCOUNT_LOGIN);
   string server  = AccountInfoString(ACCOUNT_SERVER);
   string curr    = AccountInfoString(ACCOUNT_CURRENCY);
   
   string positionsJson = GetOpenPositionsJSON();
   
   // Build full synchronization payload
   string payload = StringFormat("{\"login\":%d,\"server\":\"%s\",\"currency\":\"%s\",\"balance\":%.2f,\"equity\":%.2f,\"free_margin\":%.2f,\"positions\":%s}",
                                 login, server, curr, balance, equity, margin, positionsJson);
   
   char postData[];
   char resultData[];
   string resultHeaders;
   StringToCharArray(payload, postData, 0, WHOLE_ARRAY, CP_UTF8);
   ArrayResize(postData, ArraySize(postData) - 1); // remove null terminator
   
   string headers = "Content-Type: application/json\r\n";
   
   int res = WebRequest("POST", ServerURL, headers, 2000, postData, resultData, resultHeaders);
   
   if(res == 200)
   {
      string responseText = CharArrayToString(resultData, 0, WHOLE_ARRAY, CP_UTF8);
      // Process incoming commands if any
      ProcessServerCommands(responseText);
   }
   else if(res == -1)
   {
      Print("⚠️ [MarketPulse Bridge] WebRequest error: ", GetLastError(), ". Please add 'http://187.77.174.215:2200' to Tools -> Options -> Expert Advisors -> Allow WebRequest.");
   }
}

//+------------------------------------------------------------------+
//| Parse and execute server commands (e.g. OPEN, CLOSE)             |
//+------------------------------------------------------------------+
void ProcessServerCommands(string response)
{
   if(StringFind(response, "\"commands\":") < 0) return;
   
   // Check for OPEN_TRADE command
   if(StringFind(response, "\"action\":\"OPEN\"") >= 0)
   {
      string sym = ExtractJSONValue(response, "symbol");
      string typ = ExtractJSONValue(response, "type");
      double lot = StringToDouble(ExtractJSONValue(response, "lot"));
      double sl  = StringToDouble(ExtractJSONValue(response, "sl"));
      double tp  = StringToDouble(ExtractJSONValue(response, "tp1"));
      
      if(sym != "" && lot > 0)
      {
         if(typ == "BUY")
         {
            trade.Buy(lot, sym, 0, sl, tp, "MarketPulse AI Signal");
            Print("🚀 [MarketPulse Bridge] Executed BUY: ", sym, " Lot: ", lot, " SL: ", sl, " TP: ", tp);
         }
         else if(typ == "SELL")
         {
            trade.Sell(lot, sym, 0, sl, tp, "MarketPulse AI Signal");
            Print("🚀 [MarketPulse Bridge] Executed SELL: ", sym, " Lot: ", lot, " SL: ", sl, " TP: ", tp);
         }
      }
   }
   
   // Check for CLOSE_TRADE command
   if(StringFind(response, "\"action\":\"CLOSE\"") >= 0)
   {
      ulong ticket = (ulong)StringToInteger(ExtractJSONValue(response, "ticket"));
      if(ticket > 0)
      {
         trade.PositionClose(ticket);
         Print("🔒 [MarketPulse Bridge] Closed Position: #", ticket);
      }
   }
}

//+------------------------------------------------------------------+
//| Simple JSON string extractor helper                              |
//+------------------------------------------------------------------+
string ExtractJSONValue(string json, string key)
{
   string searchKey = "\"" + key + "\":";
   int pos = StringFind(json, searchKey);
   if(pos < 0) return "";
   
   pos += StringLen(searchKey);
   // Skip whitespace or quotes
   while(pos < StringLen(json) && (StringGetCharacter(json, pos) == ' ' || StringGetCharacter(json, pos) == '\"')) pos++;
   
   int endPos = pos;
   while(endPos < StringLen(json) && StringGetCharacter(json, endPos) != '\"' && StringGetCharacter(json, endPos) != ',' && StringGetCharacter(json, endPos) != '}') endPos++;
   
   return StringSubstr(json, pos, endPos - pos);
}
