//+------------------------------------------------------------------+
//|                                           MarketPulse_Bridge.mq5 |
//|                                 Copyright 2026, MARKETPULSE FX   |
//|                          https://marketpulse.fx / 187.77.174.215 |
//+------------------------------------------------------------------+
#property copyright "MARKETPULSE FX"
#property link      "http://187.77.174.215:8080"
#property version   "2.50"
#property description "Institutional Real-Time Bidirectional Execution Bridge & Reconciliation Engine for MarketPulse FX"

#include <Trade\Trade.mqh>
CTrade trade;

input string ServerURL     = "http://187.77.174.215:2200";             // MarketPulse REST API Base URL
input string SecretKey     = "marketpulse_live_bridge_sec_2026";       // Authentication Secret Key
input int    SyncInterval  = 1;                                          // Sync Interval in Seconds (1s)
input ulong  MagicNumber   = 888999;                                     // Magic Number for Bot Orders

int prev_positions_total = -1;
int prev_history_total   = -1;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   trade.SetExpertMagicNumber(MagicNumber);
   trade.SetDeviationInPoints(20);
   EventSetTimer(SyncInterval);
   Print("🟢 [MarketPulse Bridge v2.5] Started. 1-sec Real-Time Stream & Reconciliation active with: ", ServerURL);
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   Print("🔴 [MarketPulse Bridge v2.5] Stopped.");
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
         double swap  = PositionGetDouble(POSITION_SWAP);
         
         string posJson = StringFormat("{\"ticket\":\"%I64u\",\"symbol\":\"%s\",\"type\":\"%s\",\"lot\":%.2f,\"entry\":%.5f,\"current_price\":%.5f,\"sl\":%.5f,\"tp1\":%.5f,\"pnl\":%.2f,\"swap\":%.2f}",
                                       ticket, sym, (type == POSITION_TYPE_BUY ? "BUY" : "SELL"), vol, openP, curP, sl, tp, pnl, swap);
         
         if(count > 0) json += ",";
         json += posJson;
         count++;
      }
   }
   json += "]";
   return json;
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
   while(end < StringLen(json) && StringGetCharacter(json, end) != '"' && StringGetCharacter(json, end) != ',' && StringGetCharacter(json, end) != '}' && StringGetCharacter(json, end) != ']')
      end++;
      
   return StringSubstr(json, start, end - start);
}

//+------------------------------------------------------------------+
//| Report execution result back to backend State Machine            |
//+------------------------------------------------------------------+
void ReportCommandResult(string cmdId, ulong ticket, int retcode, string errMsg)
{
   string url = ServerURL + "/api/mt5/command-result";
   string payload = StringFormat("{\"secret\":\"%s\",\"command_id\":\"%s\",\"ticket\":\"%I64u\",\"retcode\":%d,\"error_message\":\"%s\"}",
                                 SecretKey, cmdId, ticket, retcode, errMsg);
   char postData[];
   char resultData[];
   string resultHeaders;
   StringToCharArray(payload, postData, 0, WHOLE_ARRAY, CP_UTF8);
   ArrayResize(postData, ArraySize(postData) - 1);
   string headers = StringFormat("Content-Type: application/json\r\nX-MarketPulse-Secret: %s\r\n", SecretKey);
   WebRequest("POST", url, headers, 1000, postData, resultData, resultHeaders);
}

//+------------------------------------------------------------------+
//| Parse and execute server commands from queue                     |
//+------------------------------------------------------------------+
void ProcessServerCommands(string response)
{
   if(StringFind(response, "\"commands\":") < 0) return;
   
   // 1. OPEN ORDER
   if(StringFind(response, "\"action\":\"OPEN\"") >= 0 || StringFind(response, "\"type\":\"BUY\"") >= 0 || StringFind(response, "\"type\":\"SELL\"") >= 0)
   {
      string cmdId = ExtractJSONValue(response, "command_id");
      string sym   = ExtractJSONValue(response, "symbol");
      string typ   = ExtractJSONValue(response, "type");
      double lot   = StringToDouble(ExtractJSONValue(response, "lot"));
      double sl    = StringToDouble(ExtractJSONValue(response, "sl"));
      double tp    = StringToDouble(ExtractJSONValue(response, "tp1"));
      
      if(sym != "" && lot > 0)
      {
         bool ok = false;
         if(typ == "BUY" || typ == "OPEN_BUY")
            ok = trade.Buy(lot, sym, 0, sl, tp, "MarketPulse AI");
         else if(typ == "SELL" || typ == "OPEN_SELL")
            ok = trade.Sell(lot, sym, 0, sl, tp, "MarketPulse AI");
            
         ulong ticket = trade.ResultOrder();
         if(ticket == 0) ticket = trade.ResultDeal();
         int retcode = (int)trade.ResultRetcode();
         string errStr = trade.ResultRetcodeDescription();
         
         ReportCommandResult(cmdId, ticket, retcode, errStr);
         PrintFormat("🚀 [MarketPulse Bridge] Order: %s %s %.2f Lot | Result: %d (%s) | Ticket: %I64u", typ, sym, lot, retcode, errStr, ticket);
      }
   }
   
   // 2. CLOSE ORDER
   if(StringFind(response, "\"action\":\"CLOSE\"") >= 0)
   {
      string cmdId = ExtractJSONValue(response, "command_id");
      string ticketStr = ExtractJSONValue(response, "ticket");
      ulong ticket = (ulong)StringToInteger(ticketStr);
      if(ticket > 0)
      {
         bool ok = trade.PositionClose(ticket);
         int retcode = (int)trade.ResultRetcode();
         ReportCommandResult(cmdId, ticket, retcode, trade.ResultRetcodeDescription());
         PrintFormat("🔒 [MarketPulse Bridge] Position Close Ticket: %I64u | Result: %d", ticket, retcode);
      }
   }
   
   // 3. MODIFY SL / TP (Auto Break-Even)
   if(StringFind(response, "\"action\":\"MODIFY_SL\"") >= 0)
   {
      string cmdId = ExtractJSONValue(response, "command_id");
      ulong ticket = (ulong)StringToInteger(ExtractJSONValue(response, "ticket"));
      double new_sl = StringToDouble(ExtractJSONValue(response, "sl"));
      double new_tp = StringToDouble(ExtractJSONValue(response, "tp1"));
      if(ticket > 0 && new_sl > 0)
      {
         bool ok = trade.PositionModify(ticket, new_sl, new_tp);
         int retcode = (int)trade.ResultRetcode();
         ReportCommandResult(cmdId, ticket, retcode, trade.ResultRetcodeDescription());
         PrintFormat("🛡️ [MarketPulse Bridge] PositionModify Ticket: %I64u to SL: %.5f | Result: %d", ticket, new_sl, retcode);
      }
   }
}

//+------------------------------------------------------------------+
//| Expert timer function (1-sec bidirectional synchronization)      |
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
   long   leverage= AccountInfoInteger(ACCOUNT_LEVERAGE);
   long   accMode = AccountInfoInteger(ACCOUNT_TRADE_MODE);
   
   string modeStr = "REAL";
   if(accMode == ACCOUNT_TRADE_MODE_DEMO) modeStr = "DEMO";
   else if(accMode == ACCOUNT_TRADE_MODE_CONTEST) modeStr = "CONTEST";
   
   string positionsJson = GetOpenPositionsJSON();
   
   string payload = StringFormat("{\"secret\":\"%s\",\"login\":%I64d,\"server\":\"%s\",\"currency\":\"%s\",\"account_type\":\"%s\",\"leverage\":%I64d,\"balance\":%.2f,\"equity\":%.2f,\"margin\":%.2f,\"free_margin\":%.2f,\"positions\":%s}",
                                 SecretKey, login, server, curr, modeStr, leverage, balance, equity, margin, freeMar, positionsJson);
   
   char postData[];
   char resultData[];
   string resultHeaders;
   StringToCharArray(payload, postData, 0, WHOLE_ARRAY, CP_UTF8);
   ArrayResize(postData, ArraySize(postData) - 1);
   
   string headers = StringFormat("Content-Type: application/json\r\nX-MarketPulse-Secret: %s\r\n", SecretKey);
   string syncUrl = ServerURL + "/api/mt5/sync";
   
   int res = WebRequest("POST", syncUrl, headers, 1500, postData, resultData, resultHeaders);
   
   if(res == 200)
   {
      string responseText = CharArrayToString(resultData, 0, WHOLE_ARRAY, CP_UTF8);
      ProcessServerCommands(responseText);
   }
   else if(res == -1)
   {
      Print("⚠️ [MarketPulse Bridge] WebRequest error: ", GetLastError(), ". Please ensure '", ServerURL, "' is added to Tools -> Options -> Expert Advisors -> Allow WebRequest.");
   }
}
