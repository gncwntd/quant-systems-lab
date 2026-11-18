// SPDX-License-Identifier: Apache-2.0
// One-shot read-only daily-history export. Run on a separate chart from the quote bridge.
#property strict
#property version "1.00"
#property description "QSLab read-only EURUSD closed D1 history export"

string Escaped(string value)
{
   StringReplace(value,"\\","\\\\");
   StringReplace(value,"\"","\\\"");
   StringReplace(value,"\r"," ");
   StringReplace(value,"\n"," ");
   StringReplace(value,"\t"," ");
   return value;
}

bool DemoConnected()
{
   return AccountInfoInteger(ACCOUNT_TRADE_MODE)==ACCOUNT_TRADE_MODE_DEMO
          && (bool)TerminalInfoInteger(TERMINAL_CONNECTED);
}

void OnStart()
{
   const string symbol="EURUSD";
   if(!DemoConnected() || !SymbolSelect(symbol,true))
   {
      Print("QSLab history: connected demo EURUSD source required");
      return;
   }
   string server=AccountInfoString(ACCOUNT_SERVER);
   MqlRates rates[];
   ArraySetAsSeries(rates,false);
   // Position zero is forming; shift one excludes it. CopyRates may download missing history.
   int copied=CopyRates(symbol,PERIOD_D1,1,1500,rates);
   long current=(long)iTime(symbol,PERIOD_D1,0);
   if(copied<30 || current<=0 || (long)rates[copied-1].time>=current)
   {
      Print("QSLab history: fewer than 30 closed bars ready; retry after synchronization");
      return;
   }
   FolderCreate("QSLab",FILE_COMMON);
   const string temporary="QSLab\\history.tmp";
   const string destination="QSLab\\history.json";
   int file=FileOpen(temporary,FILE_WRITE|FILE_TXT|FILE_ANSI|FILE_COMMON,0,CP_UTF8);
   if(file==INVALID_HANDLE)
   {
      Print("QSLab history: export file unavailable; error ",GetLastError());
      return;
   }
   string header=StringFormat("{\"schema\":1,\"symbol\":\"EURUSD\",\"timeframe\":\"D1\",\"demo\":true,\"server\":\"%s\",\"captured_utc\":%I64d,\"current_bar_server_time\":%I64d,\"requested_bars\":1500,\"count\":%d,\"digits\":%d,\"point\":%s,\"bars\":[",
      Escaped(server),(long)TimeGMT(),current,copied,(int)SymbolInfoInteger(symbol,SYMBOL_DIGITS),
      DoubleToString(SymbolInfoDouble(symbol,SYMBOL_POINT),10));
   bool written=FileWriteString(file,header)>0;
   for(int i=0;i<copied && written;i++)
   {
      string row=StringFormat("%s{\"server_time\":%I64d,\"open\":%s,\"high\":%s,\"low\":%s,\"close\":%s,\"tick_volume\":%I64d,\"spread_points\":%d,\"real_volume\":%I64d}",
         i>0?",":"",(long)rates[i].time,DoubleToString(rates[i].open,8),DoubleToString(rates[i].high,8),
         DoubleToString(rates[i].low,8),DoubleToString(rates[i].close,8),rates[i].tick_volume,rates[i].spread,rates[i].real_volume);
      written=FileWriteString(file,row)>0;
   }
   written=written && FileWriteString(file,"]}")>0;
   FileClose(file);
   if(!written || !DemoConnected() || AccountInfoString(ACCOUNT_SERVER)!=server)
   {
      Print("QSLab history: incomplete export or changed source; snapshot not published");
      return;
   }
   if(!FileMove(temporary,FILE_COMMON,destination,FILE_COMMON|FILE_REWRITE))
   {
      Print("QSLab history: snapshot publication failed; error ",GetLastError());
      return;
   }
   Print("QSLab history: exported ",copied," closed EURUSD D1 bars; no trading operation");
}
