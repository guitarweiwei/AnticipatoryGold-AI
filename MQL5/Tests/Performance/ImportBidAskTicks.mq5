// Offline data importer only: no EA events, CTrade, OrderSend or account login.
// All configured contract/session properties are a fixed synthetic specification.
// Successful import/readback does not authenticate historical broker contracts.
#property strict
#property version "1.00"
input string InpDatasetFile="AG_PERF_ticks.csv";
input string InpCustomSymbol="AG_PERF_XAUUSD";
input long InpExpectedTicks=0;
input string InpDatasetSHA256="UNVERIFIED";
input string InpRunId="UNCONFIGURED";
input int InpPriceDigits=2;
input double InpContractSize=100.0;
input double InpTickSize=0.01;
input double InpVolumeMin=0.01;
input double InpVolumeMax=100.0;
input double InpVolumeStep=0.01;
input string InpSessionScenario="UNKNOWN";

string g_importOutput="";
string ImportJSON(string value){
 StringReplace(value,"\\","\\\\");StringReplace(value,"\"","\\\"");StringReplace(value,"\r","\\r");StringReplace(value,"\n","\\n");StringReplace(value,"\t","\\t");return "\""+value+"\"";
}
bool ImportPositive(double value){return MathIsValidNumber(value)&&value!=EMPTY_VALUE&&value>0;}
bool ImportIdentifier(string value){
 if(StringLen(value)<1||StringLen(value)>64)return false;
 for(int i=0;i<StringLen(value);i++){ushort c=StringGetCharacter(value,i);if(!((c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9')||c=='_'||c=='-'))return false;}
 return true;
}
bool ImportHash(string value){
 if(StringLen(value)!=64)return false;
 for(int i=0;i<64;i++){ushort c=StringGetCharacter(value,i);if(!((c>='0'&&c<='9')||(c>='a'&&c<='f')))return false;}return true;
}
bool ImportUnsigned(string value,long &number){
 if(value==""||StringLen(value)>19)return false;number=0;
 for(int i=0;i<StringLen(value);i++){ushort c=StringGetCharacter(value,i);if(c<'0'||c>'9')return false;long digit=(long)(c-'0');if(number>(LONG_MAX-digit)/10)return false;number=number*10+digit;}
 return IntegerToString(number)==value;
}
bool ImportPrice(string value,double &number){
 if(value=="")return false;bool dot=false;int digits=0;
 for(int i=0;i<StringLen(value);i++){ushort c=StringGetCharacter(value,i);if(c=='.'&&!dot){dot=true;continue;}if(c<'0'||c>'9')return false;digits++;}
 number=StringToDouble(value);return digits>0&&ImportPositive(number)&&NormalizeDouble(number,InpPriceDigits)==number&&NormalizeDouble(MathRound(number/InpTickSize)*InpTickSize,InpPriceDigits)==number;
}
bool ImportResult(bool passed,string stage,string detail,long rows,long bars,long first,long last){
 int out=FileOpen(g_importOutput,FILE_WRITE|FILE_TXT|FILE_ANSI);if(out==INVALID_HANDLE){Print("AG_PERF_IMPORT_OUTPUT_FAILED");return false;}
 string json="{\"schema_version\":1,\"passed\":"+(passed?"true":"false")+",\"stage\":"+ImportJSON(stage)+",\"detail\":"+ImportJSON(detail)+",\"run_id\":"+ImportJSON(InpRunId)+",\"symbol\":"+ImportJSON(InpCustomSymbol)+",\"dataset_sha256_external_binding\":"+ImportJSON(InpDatasetSHA256)+",\"ticks\":"+IntegerToString(rows)+",\"m1_bars\":"+IntegerToString(bars)+",\"first_utc_msc\":"+IntegerToString(first)+",\"last_utc_msc\":"+IntegerToString(last)+",\"source_authenticity_verified_by_importer\":false,\"contract\":\"FIXED_SYNTHETIC_SPEC\",\"historical_performance\":\"NOT_RUN\"}";
 FileWriteString(out,json+"\r\n");FileFlush(out);FileClose(out);Print("AG_PERF_IMPORT_RESULT|",g_importOutput,"|",passed?"PASSED":"FAILED");return passed;
}
bool ImportConfigure(string symbol){
 double point=MathPow(10.0,-InpPriceDigits);
 if(!CustomSymbolCreate(symbol,"AnticipatoryGoldResearch"))return false;
 if(!CustomSymbolSetString(symbol,SYMBOL_DESCRIPTION,"Offline bid/ask dataset; fixed synthetic contract; no broker equivalence")||!CustomSymbolSetString(symbol,SYMBOL_CURRENCY_BASE,"XAU")||!CustomSymbolSetString(symbol,SYMBOL_CURRENCY_PROFIT,"USD")||!CustomSymbolSetString(symbol,SYMBOL_CURRENCY_MARGIN,"USD"))return false;
 if(!CustomSymbolSetInteger(symbol,SYMBOL_DIGITS,InpPriceDigits)||!CustomSymbolSetDouble(symbol,SYMBOL_POINT,point)||!CustomSymbolSetDouble(symbol,SYMBOL_TRADE_TICK_SIZE,InpTickSize)||!CustomSymbolSetDouble(symbol,SYMBOL_TRADE_CONTRACT_SIZE,InpContractSize))return false;
 if(!CustomSymbolSetDouble(symbol,SYMBOL_VOLUME_MIN,InpVolumeMin)||!CustomSymbolSetDouble(symbol,SYMBOL_VOLUME_MAX,InpVolumeMax)||!CustomSymbolSetDouble(symbol,SYMBOL_VOLUME_STEP,InpVolumeStep))return false;
 // Trading remains disabled after import. A reviewed tester scenario must
 // configure actual commission/swap/margin/session policies before execution.
 if(!CustomSymbolSetInteger(symbol,SYMBOL_TRADE_MODE,SYMBOL_TRADE_MODE_DISABLED)||!CustomSymbolSetInteger(symbol,SYMBOL_TRADE_CALC_MODE,SYMBOL_CALC_MODE_CFDLEVERAGE)||!CustomSymbolSetInteger(symbol,SYMBOL_ORDER_MODE,SYMBOL_ORDER_MARKET|SYMBOL_ORDER_SL)||!CustomSymbolSetInteger(symbol,SYMBOL_FILLING_MODE,SYMBOL_FILLING_FOK|SYMBOL_FILLING_IOC))return false;
 // This explicit import-only continuous UTC session is not IC Markets' trading
 // calendar. It preserves all source ticks pending a separately reviewed model.
 for(int day=0;day<7;day++){
  if(!CustomSymbolSetSessionQuote(symbol,(ENUM_DAY_OF_WEEK)day,0,0,86399)||!CustomSymbolSetSessionTrade(symbol,(ENUM_DAY_OF_WEEK)day,0,0,86399))return false;
 }
 return SymbolSelect(symbol,true);
}
void OnStart(){
 string unique=IntegerToString((long)TimeLocal())+"_"+StringFormat("%I64u",GetTickCount64());g_importOutput="AG_PERF_IMPORT_"+unique+".json";
 if(InpRunId=="UNCONFIGURED"||!ImportIdentifier(InpRunId)||!ImportIdentifier(InpCustomSymbol)||StringFind(InpCustomSymbol,"AG_PERF_")!=0||StringFind(InpDatasetFile,"AG_PERF_")!=0||StringFind(InpDatasetFile,"..")>=0||StringFind(InpDatasetFile,"\\")>=0||StringFind(InpDatasetFile,"/")>=0||!ImportHash(InpDatasetSHA256)||InpExpectedTicks<=0||InpExpectedTicks>INT_MAX||InpSessionScenario!="CONTINUOUS_UTC_IMPORT_ONLY"){
  ImportResult(false,"CONFIG","explicit_dataset_run_and_import_scenario_required",0,0,0,0);return;
 }
 if(InpPriceDigits<0||InpPriceDigits>8||!ImportPositive(InpContractSize)||!ImportPositive(InpTickSize)||!ImportPositive(InpVolumeMin)||!ImportPositive(InpVolumeMax)||!ImportPositive(InpVolumeStep)||InpVolumeMax<InpVolumeMin||NormalizeDouble(InpTickSize,InpPriceDigits)!=InpTickSize){ImportResult(false,"CONFIG","invalid_contract_precision_or_volume",0,0,0,0);return;}
 bool custom=false;if(SymbolExist(InpCustomSymbol,custom)){ImportResult(false,"CONFIG","refuses_existing_symbol_no_overwrite_or_reset",0,0,0,0);return;}
 int sourceFile=FileOpen(InpDatasetFile,FILE_READ|FILE_TXT|FILE_ANSI);if(sourceFile==INVALID_HANDLE){ImportResult(false,"INPUT","dataset_unavailable",0,0,0,0);return;}
 if(FileReadString(sourceFile)!="time_utc_msc,bid,ask"){FileClose(sourceFile);ImportResult(false,"INPUT","wrong_three_column_header",0,0,0,0);return;}
 MqlTick ticks[];int expected=(int)InpExpectedTicks;
 if(ArrayResize(ticks,expected)!=expected){FileClose(sourceFile);ImportResult(false,"MEMORY","tick_allocation_failed",0,0,0,0);return;}
 long rows=0,previous=0;bool valid=true;
 while(!FileIsEnding(sourceFile)){
  string line=FileReadString(sourceFile);if(line==""&&FileIsEnding(sourceFile))break;
  string fields[];long time;double bid,ask;
  if(rows>=InpExpectedTicks||StringSplit(line,',',fields)!=3||!ImportUnsigned(fields[0],time)||time<=0||time<previous||!ImportPrice(fields[1],bid)||!ImportPrice(fields[2],ask)||ask<bid){valid=false;break;}
  int i=(int)rows;ZeroMemory(ticks[i]);ticks[i].time=(datetime)(time/1000);ticks[i].time_msc=time;ticks[i].bid=bid;ticks[i].ask=ask;ticks[i].flags=TICK_FLAG_BID|TICK_FLAG_ASK;
  previous=time;rows++;
 }
 FileClose(sourceFile);
 if(!valid||rows!=InpExpectedTicks){ImportResult(false,"INPUT","invalid_rows_order_precision_or_count",rows,0,0,0);return;}
 long first=ticks[0].time_msc,last=ticks[expected-1].time_msc;
 MqlRates rates[];int rateCount=0;datetime minute=0;double point=MathPow(10.0,-InpPriceDigits);
 for(int i=0;i<expected;i++){
  datetime current=(datetime)((long)ticks[i].time/60*60);
  if(current!=minute){
   if(ArrayResize(rates,rateCount+1,4096)!=rateCount+1){ImportResult(false,"MEMORY","bar_allocation_failed",rows,rateCount,first,last);return;}
   ZeroMemory(rates[rateCount]);rates[rateCount].time=current;rates[rateCount].open=ticks[i].bid;rates[rateCount].high=ticks[i].bid;rates[rateCount].low=ticks[i].bid;rateCount++;minute=current;
  }
  int n=rateCount-1;rates[n].high=MathMax(rates[n].high,ticks[i].bid);rates[n].low=MathMin(rates[n].low,ticks[i].bid);rates[n].close=ticks[i].bid;rates[n].tick_volume++;
  double spread=(ticks[i].ask-ticks[i].bid)/point;if(!MathIsValidNumber(spread)||spread>INT_MAX){ImportResult(false,"INPUT","invalid_spread",rows,rateCount,first,last);return;}rates[n].spread=(int)MathRound(spread);
 }
 if(!ImportConfigure(InpCustomSymbol)){ImportResult(false,"SYMBOL","property_or_session_configuration_failed_symbol_retained",rows,rateCount,first,last);return;}
 int written=CustomTicksReplace(InpCustomSymbol,first,last,ticks);
 if(written!=expected){ImportResult(false,"TICKS","replace_count_mismatch_partial_import_retained",written,rateCount,first,last);return;}
 int barsWritten=CustomRatesReplace(InpCustomSymbol,rates[0].time,rates[rateCount-1].time,rates);
 if(barsWritten!=rateCount){ImportResult(false,"BARS","bar_replace_count_mismatch",rows,barsWritten,first,last);return;}
 // Minute-sized readback keeps same-millisecond ties in one batch; no tick is
 // deduplicated, sorted anew, interpolated or read back from a shifted boundary.
 int cursor=0;
 while(cursor<expected){
  long start=ticks[cursor].time_msc,end=(start/60000+1)*60000-1;int until=cursor;
  while(until<expected&&ticks[until].time_msc<=end)until++;
  MqlTick observed[];int copied=CopyTicksRange(InpCustomSymbol,observed,COPY_TICKS_ALL,(ulong)start,(ulong)MathMin(end,last));
  if(copied!=until-cursor){ImportResult(false,"READBACK","tick_count_or_tie_order_mismatch",rows,rateCount,first,last);return;}
  for(int j=0;j<copied;j++)if(observed[j].time_msc!=ticks[cursor+j].time_msc||observed[j].bid!=ticks[cursor+j].bid||observed[j].ask!=ticks[cursor+j].ask){ImportResult(false,"READBACK","tick_quote_or_order_mismatch",rows,rateCount,first,last);return;}
  cursor=until;
 }
 MqlRates observedRates[];ArraySetAsSeries(observedRates,false);
 int copiedRates=CopyRates(InpCustomSymbol,PERIOD_M1,rates[0].time,rates[rateCount-1].time,observedRates);
 if(copiedRates!=rateCount){ImportResult(false,"READBACK","m1_count_mismatch",rows,rateCount,first,last);return;}
 for(int i=0;i<rateCount;i++)if(observedRates[i].time!=rates[i].time||observedRates[i].open!=rates[i].open||observedRates[i].high!=rates[i].high||observedRates[i].low!=rates[i].low||observedRates[i].close!=rates[i].close||observedRates[i].tick_volume!=rates[i].tick_volume){ImportResult(false,"READBACK","m1_time_ohlc_or_volume_mismatch",rows,rateCount,first,last);return;}
 ImportResult(true,"READBACK","exact_bid_ask_tick_and_m1_parity_trading_still_disabled",rows,rateCount,first,last);
}
