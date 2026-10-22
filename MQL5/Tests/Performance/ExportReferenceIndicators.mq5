// Offline native-indicator export only. No EA, account login or trading API.
// Input M1 bars must be externally derived from authenticated bid/ask ticks.
#property strict
#property version "1.00"

const string REF_SYMBOL="AG_REF_XAUUSD_NEW";
const string REF_INPUT="AG_REF_M1.csv";
const string REF_M5="AG_REF_M5.csv";
const string REF_H1="AG_REF_H1.csv";
const string REF_RESULT="AG_REF_INDICATORS_RESULT.json";
string g_refHash="";
int g_refM1=0,g_refM5=0,g_refH1=0,g_refInvalidM5=0,g_refInvalidH1=0;
long g_refSourceBegin=0,g_refSourceEnd=0;
int g_refFast=INVALID_HANDLE,g_refSlow=INVALID_HANDLE,g_refADX=INVALID_HANDLE,g_refATR=INVALID_HANDLE,g_refBands=INVALID_HANDLE;
ulong g_refDeadline=0;

bool RefFinite(double value){return MathIsValidNumber(value)&&value!=EMPTY_VALUE;}
bool RefPositive(double value){return RefFinite(value)&&value>0;}
bool RefUnsigned(string text,long &value){
 if(text==""||StringLen(text)>19)return false;value=0;
 for(int i=0;i<StringLen(text);i++){ushort c=StringGetCharacter(text,i);if(c<'0'||c>'9')return false;long digit=(long)(c-'0');if(value>(LONG_MAX-digit)/10)return false;value=value*10+digit;}
 return IntegerToString(value)==text;
}
bool RefPrice(string text,double &value){
 if(text=="")return false;bool dot=false;int digits=0;
 for(int i=0;i<StringLen(text);i++){ushort c=StringGetCharacter(text,i);if(c=='.'&&!dot){dot=true;continue;}if(c<'0'||c>'9')return false;digits++;}
 value=StringToDouble(text);return digits>0&&RefPositive(value)&&NormalizeDouble(value,3)==value;
}
bool RefHashInput(string &hash){
 int file=FileOpen(REF_INPUT,FILE_READ|FILE_BIN);if(file==INVALID_HANDLE)return false;
 ulong size=FileSize(file);if(size==0||size>(ulong)INT_MAX){FileClose(file);return false;}
 uchar data[],key[],digest[];
 if(ArrayResize(data,(int)size)!=(int)size){FileClose(file);return false;}
 uint read=FileReadArray(file,data,0,(int)size);FileClose(file);
 if(read!=(uint)size||CryptEncode(CRYPT_HASH_SHA256,data,key,digest)!=32)return false;
 hash="";for(int i=0;i<32;i++)hash+=StringFormat("%02x",(uint)digest[i]);return StringLen(hash)==64;
}
void RefRelease(){
 if(g_refFast!=INVALID_HANDLE)IndicatorRelease(g_refFast);if(g_refSlow!=INVALID_HANDLE)IndicatorRelease(g_refSlow);
 if(g_refADX!=INVALID_HANDLE)IndicatorRelease(g_refADX);if(g_refATR!=INVALID_HANDLE)IndicatorRelease(g_refATR);if(g_refBands!=INVALID_HANDLE)IndicatorRelease(g_refBands);
}
void RefResult(bool passed,string stage,string detail){
 // Stage/detail are fixed literals, and the only other string value is a hex hash.
 int file=FileOpen(REF_RESULT,FILE_WRITE|FILE_TXT|FILE_ANSI);if(file==INVALID_HANDLE){Print("AG_REF_OUTPUT_FAILED");RefRelease();TerminalClose(1);return;}
 string json="{\"schema_version\":1,\"passed\":"+(passed?"true":"false")+",\"stage\":\""+stage+"\",\"detail\":\""+detail+"\",\"input\":\"AG_REF_M1.csv\",\"input_sha256\":\""+g_refHash+"\",\"source_begin_utc\":"+IntegerToString(g_refSourceBegin)+",\"source_end_utc\":"+IntegerToString(g_refSourceEnd)+",\"m1_bars\":"+IntegerToString(g_refM1)+",\"m5_rows\":"+IntegerToString(g_refM5)+",\"h1_rows\":"+IntegerToString(g_refH1)+",\"m5_invalid\":"+IntegerToString(g_refInvalidM5)+",\"h1_invalid\":"+IntegerToString(g_refInvalidH1)+",\"symbol\":\"AG_REF_XAUUSD_NEW\",\"native_indicators\":true,\"source_authenticity_verified_by_script\":false,\"mt5_strategy_tester_backtest\":\"NOT_RUN\",\"orders_submitted\":0}";
 FileWriteString(file,json+"\r\n");FileFlush(file);FileClose(file);RefRelease();Print("AG_REF_RESULT|",REF_RESULT,"|",passed?"PASSED":"FAILED");TerminalClose(passed?0:1);
}
bool RefReadM1(MqlRates &rates[]){
 int file=FileOpen(REF_INPUT,FILE_READ|FILE_TXT|FILE_ANSI);if(file==INVALID_HANDLE)return false;
 if(FileReadString(file)!="time_utc,open,high,low,close,tick_volume,spread"){FileClose(file);return false;}
 long previous=0;bool valid=true;int count=0;
 while(!FileIsEnding(file)){
  string line=FileReadString(file);if(line==""&&FileIsEnding(file))break;
  string fields[];long time,volume,spread;double open,high,low,close;
  if(count==INT_MAX||StringSplit(line,',',fields)!=7||!RefUnsigned(fields[0],time)||time<=0||time%60!=0||time<=previous||!RefPrice(fields[1],open)||!RefPrice(fields[2],high)||!RefPrice(fields[3],low)||!RefPrice(fields[4],close)||high<MathMax(open,close)||low>MathMin(open,close)||high<low||!RefUnsigned(fields[5],volume)||volume<=0||!RefUnsigned(fields[6],spread)||spread>INT_MAX){valid=false;break;}
  if(ArrayResize(rates,count+1,4096)!=count+1){valid=false;break;}
  ZeroMemory(rates[count]);rates[count].time=(datetime)time;rates[count].open=open;rates[count].high=high;rates[count].low=low;rates[count].close=close;rates[count].tick_volume=volume;rates[count].spread=(int)spread;
  previous=time;count++;
 }
 FileClose(file);g_refM1=count;
 if(!valid||count<1)return false;g_refSourceBegin=(long)rates[0].time;g_refSourceEnd=(long)rates[count-1].time+60;return true;
}
bool RefConfigure(){
 if(!CustomSymbolCreate(REF_SYMBOL,"AnticipatoryGoldReference"))return false;
 if(!CustomSymbolSetInteger(REF_SYMBOL,SYMBOL_DIGITS,3)||!CustomSymbolSetDouble(REF_SYMBOL,SYMBOL_POINT,0.001)||!CustomSymbolSetDouble(REF_SYMBOL,SYMBOL_TRADE_TICK_SIZE,0.001)||!CustomSymbolSetDouble(REF_SYMBOL,SYMBOL_TRADE_CONTRACT_SIZE,100))return false;
 if(!CustomSymbolSetString(REF_SYMBOL,SYMBOL_CURRENCY_BASE,"XAU")||!CustomSymbolSetString(REF_SYMBOL,SYMBOL_CURRENCY_PROFIT,"USD")||!CustomSymbolSetString(REF_SYMBOL,SYMBOL_CURRENCY_MARGIN,"USD")||!CustomSymbolSetInteger(REF_SYMBOL,SYMBOL_TRADE_MODE,SYMBOL_TRADE_MODE_DISABLED))return false;
 return SymbolSelect(REF_SYMBOL,true);
}
bool RefCopyRates(ENUM_TIMEFRAMES timeframe,MqlRates &rates[]){
 ArraySetAsSeries(rates,false);
 do {
  int count=CopyRates(REF_SYMBOL,timeframe,(datetime)(g_refSourceBegin-PeriodSeconds(timeframe)),(datetime)(g_refSourceEnd-1),rates);
  if(count>0&&SeriesInfoInteger(REF_SYMBOL,timeframe,SERIES_SYNCHRONIZED))return true;
  if(IsStopped())return false;Sleep(20);
 }while(GetTickCount64()<g_refDeadline);
 return false;
}
bool RefCopyBuffer(int handle,int buffer,int count,double &values[]){
 ArraySetAsSeries(values,false);
 do {
  if(BarsCalculated(handle)>=count&&CopyBuffer(handle,buffer,0,count,values)==count)return true;
  if(IsStopped())return false;Sleep(20);
 }while(GetTickCount64()<g_refDeadline);
 return false;
}
bool RefNativeTimes(ENUM_TIMEFRAMES timeframe,MqlRates &rates[]){
 datetime times[];ArraySetAsSeries(times,false);int count=ArraySize(rates);
 if(CopyTime(REF_SYMBOL,timeframe,0,count,times)!=count)return false;
 for(int i=0;i<count;i++)if(times[i]!=rates[i].time)return false;return true;
}
bool RefM1Readback(MqlRates &expected[]){
 MqlRates observed[];if(!RefCopyRates(PERIOD_M1,observed)||ArraySize(observed)!=ArraySize(expected))return false;
 for(int i=0;i<ArraySize(expected);i++)if(observed[i].time!=expected[i].time||observed[i].open!=expected[i].open||observed[i].high!=expected[i].high||observed[i].low!=expected[i].low||observed[i].close!=expected[i].close||observed[i].tick_volume!=expected[i].tick_volume||observed[i].spread!=expected[i].spread)return false;
 return true;
}
string RefIndicatorText(double value,bool lookback){return lookback&&RefFinite(value)?DoubleToString(value,16):"EMPTY_VALUE";}
string RefBarPrefix(MqlRates &bar,int seconds){
 return IntegerToString((long)bar.time)+","+IntegerToString((long)bar.time+seconds)+","+DoubleToString(bar.open,16)+","+DoubleToString(bar.high,16)+","+DoubleToString(bar.low,16)+","+DoubleToString(bar.close,16)+","+IntegerToString(bar.tick_volume)+","+IntegerToString(bar.spread)+",";
}
bool RefExportM5(){
 MqlRates bars[];if(!RefCopyRates(PERIOD_M5,bars))return false;int count=ArraySize(bars);
 double atr[],upper[],lower[];
 if(!RefCopyBuffer(g_refATR,0,count,atr)||!RefCopyBuffer(g_refBands,1,count,upper)||!RefCopyBuffer(g_refBands,2,count,lower)||!RefNativeTimes(PERIOD_M5,bars))return false;
 int file=FileOpen(REF_M5,FILE_WRITE|FILE_TXT|FILE_ANSI);if(file==INVALID_HANDLE)return false;
 FileWriteString(file,"time_utc,bar_end_utc,open,high,low,close,tick_volume,spread,atr14,band_upper,band_lower,valid,closed_by_source_end\r\n");
 for(int i=0;i<count;i++){
  bool atrReady=i+1>=14&&RefPositive(atr[i]),bandsReady=i+1>=20&&RefPositive(upper[i])&&RefPositive(lower[i])&&upper[i]>=lower[i];bool valid=atrReady&&bandsReady;
  if(!valid)g_refInvalidM5++;
  string row=RefBarPrefix(bars[i],300)+RefIndicatorText(atr[i],atrReady)+","+RefIndicatorText(upper[i],bandsReady)+","+RefIndicatorText(lower[i],bandsReady)+","+(valid?"1":"0")+","+((long)bars[i].time+300<=g_refSourceEnd?"1":"0")+"\r\n";
  if(FileWriteString(file,row)!=(uint)StringLen(row)){FileClose(file);return false;}
 }
 FileFlush(file);FileClose(file);g_refM5=count;return true;
}
bool RefExportH1(){
 MqlRates bars[];if(!RefCopyRates(PERIOD_H1,bars))return false;int count=ArraySize(bars);
 double fast[],slow[],adx[];
 if(!RefCopyBuffer(g_refFast,0,count,fast)||!RefCopyBuffer(g_refSlow,0,count,slow)||!RefCopyBuffer(g_refADX,0,count,adx)||!RefNativeTimes(PERIOD_H1,bars))return false;
 int file=FileOpen(REF_H1,FILE_WRITE|FILE_TXT|FILE_ANSI);if(file==INVALID_HANDLE)return false;
 FileWriteString(file,"time_utc,bar_end_utc,open,high,low,close,tick_volume,spread,ema20,ema50,adx14,valid,closed_by_source_end\r\n");
 for(int i=0;i<count;i++){
  bool fastReady=i+1>=20&&RefPositive(fast[i]),slowReady=i+1>=50&&RefPositive(slow[i]),adxReady=i+1>=28&&RefFinite(adx[i])&&adx[i]>=0;bool valid=fastReady&&slowReady&&adxReady;
  if(!valid)g_refInvalidH1++;
  string row=RefBarPrefix(bars[i],3600)+RefIndicatorText(fast[i],fastReady)+","+RefIndicatorText(slow[i],slowReady)+","+RefIndicatorText(adx[i],adxReady)+","+(valid?"1":"0")+","+((long)bars[i].time+3600<=g_refSourceEnd?"1":"0")+"\r\n";
  if(FileWriteString(file,row)!=(uint)StringLen(row)){FileClose(file);return false;}
 }
 FileFlush(file);FileClose(file);g_refH1=count;return true;
}
void OnStart(){
 if(FileIsExist(REF_RESULT)||FileIsExist(REF_M5)||FileIsExist(REF_H1)){Print("AG_REF_REFUSES_EXISTING_OUTPUTS");TerminalClose(1);return;}
 g_refDeadline=GetTickCount64()+90000;
 if(PositionsTotal()!=0||OrdersTotal()!=0){RefResult(false,"ENVIRONMENT","requires_flat_no_orders");return;}
 bool custom=false;if(SymbolExist(REF_SYMBOL,custom)){RefResult(false,"ENVIRONMENT","refuses_existing_custom_symbol");return;}
 if(!RefHashInput(g_refHash)){RefResult(false,"INPUT","raw_file_sha256_failed");return;}
 MqlRates source[];if(!RefReadM1(source)){RefResult(false,"INPUT","invalid_M1_header_values_or_time_order");return;}
 string after;if(!RefHashInput(after)||after!=g_refHash){RefResult(false,"INPUT","input_changed_during_read");return;}
 if(!RefConfigure()){RefResult(false,"CUSTOM_SYMBOL","configuration_failed_symbol_retained");return;}
 if(CustomRatesReplace(REF_SYMBOL,source[0].time,source[ArraySize(source)-1].time,source)!=ArraySize(source)||!RefM1Readback(source)){RefResult(false,"READBACK","M1_replace_or_full_readback_failed");return;}
 g_refFast=iMA(REF_SYMBOL,PERIOD_H1,20,0,MODE_EMA,PRICE_CLOSE);g_refSlow=iMA(REF_SYMBOL,PERIOD_H1,50,0,MODE_EMA,PRICE_CLOSE);g_refADX=iADX(REF_SYMBOL,PERIOD_H1,14);g_refATR=iATR(REF_SYMBOL,PERIOD_M5,14);g_refBands=iBands(REF_SYMBOL,PERIOD_M5,20,0,2.0,PRICE_CLOSE);
 if(g_refFast==INVALID_HANDLE||g_refSlow==INVALID_HANDLE||g_refADX==INVALID_HANDLE||g_refATR==INVALID_HANDLE||g_refBands==INVALID_HANDLE){RefResult(false,"INDICATORS","native_handle_creation_failed");return;}
 if(!RefExportM5()||!RefExportH1()){RefResult(false,"EXPORT","native_series_or_buffers_not_ready_or_write_failed");return;}
 if(!RefHashInput(after)||after!=g_refHash){RefResult(false,"INPUT","input_changed_during_export");return;}
 RefResult(true,"EXPORTED","native_indicators_only_not_MT5_strategy_tester");
}
