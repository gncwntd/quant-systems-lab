// SPDX-License-Identifier: Apache-2.0
// Read-only, one-second snapshots. No trading, DLL, credential or network API.
#property strict
#property version "1.00"
#property description "QSLab read-only EURUSD demo quote bridge"

string JsonText(string value)
{
   StringReplace(value,"\\","\\\\");
   StringReplace(value,"\"","\\\"");
   StringReplace(value,"\r"," ");
   StringReplace(value,"\n"," ");
   StringReplace(value,"\t"," ");
   return value;
}

void OnStart()
{
   const string symbol="EURUSD";
   const string temporary="QSLab\\quote.tmp";
   const string destination="QSLab\\quote.json";
   if(!FolderCreate("QSLab",FILE_COMMON) && GetLastError()!=0)
      Print("QSLab: using existing common export directory");
   Print("QSLab: read-only demo quote bridge started");
   while(!IsStopped())
   {
      // Fail closed if the user switches to a real or contest account.
      bool demo=(AccountInfoInteger(ACCOUNT_TRADE_MODE)==ACCOUNT_TRADE_MODE_DEMO);
      bool connected=(bool)TerminalInfoInteger(TERMINAL_CONNECTED);
      MqlTick tick={};
      bool valid=demo && connected && SymbolSelect(symbol,true) && SymbolInfoTick(symbol,tick);
      valid=valid && tick.bid>0 && tick.ask>=tick.bid && tick.time_msc>0;
      long now=(long)TimeGMT();
      long age=valid ? (long)TimeTradeServer()*1000-tick.time_msc : 0;
      string json=StringFormat("{\"schema\":1,\"symbol\":\"EURUSD\",\"server\":\"%s\",\"demo\":%s,\"connected\":%s,\"valid\":%s,\"heartbeat_utc\":%I64d,\"tick_time_msc\":%I64d,\"tick_age_ms\":%I64d,\"digits\":%d,\"bid\":%s,\"ask\":%s}",
         JsonText(AccountInfoString(ACCOUNT_SERVER)),demo?"true":"false",connected?"true":"false",valid?"true":"false",now,
         tick.time_msc,age,(int)SymbolInfoInteger(symbol,SYMBOL_DIGITS),
         DoubleToString(tick.bid,8),DoubleToString(tick.ask,8));
      int file=FileOpen(temporary,FILE_WRITE|FILE_TXT|FILE_ANSI|FILE_COMMON,0,CP_UTF8);
      if(file!=INVALID_HANDLE)
      {
         uint written=FileWriteString(file,json);
         FileClose(file);
         if(written>0 && !FileMove(temporary,FILE_COMMON,destination,FILE_COMMON|FILE_REWRITE))
            Print("QSLab: quote publication failed; error ",GetLastError());
      }
      else Print("QSLab: quote file unavailable; error ",GetLastError());
      Sleep(1000);
   }
   Print("QSLab: read-only bridge stopped");
}
