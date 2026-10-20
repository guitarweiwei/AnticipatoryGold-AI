//+------------------------------------------------------------------+
//| AnticipatoryGold AI v1 - research prototype, not investment advice|
//| Strategy tester mode is deterministic and does not call online AI|
//+------------------------------------------------------------------+
#property strict
#property version   "1.00"
#property description "Trend + squeeze/level trigger + optional AI filter + capped grid"
#include <Trade/Trade.mqh>
CTrade trade;

input string InpSymbol="XAUUSD";
input ENUM_TIMEFRAMES InpTrendTF=PERIOD_H1;
input ENUM_TIMEFRAMES InpEntryTF=PERIOD_M5;
input int InpFastEMA=20;
input int InpSlowEMA=50;
input int InpATRPeriod=14;
input int InpADXPeriod=14;
input double InpMinADX=18.0;
input int InpLevelLookback=12;
input double InpSqueezeATRRatio=0.75;
input double InpGridATRStep=1.2;
input int InpMaxGridLayers=3;                 // hard cap including first position
input double InpBaseLots=0.01;
input double InpLotMultiplier=1.0;             // do not use martingale by default
input double InpMaxLotsPerBasket=0.03;
input double InpMaxTotalLots=0.05;
input double InpBasketStopMoney=35.0;          // account currency; hard basket loss
input double InpDailyLossLimitMoney=75.0;      // EA stops opening new positions after this loss
input double InpMaxEquityDrawdownPct=5.0;      // stop new entries; emergency close optional
input bool InpCloseOnRiskBreach=true;
input double InpBasketTakeProfitMoney=8.0;
input double InpRiskPctPerInitialTrade=0.25;   // used as additional sizing ceiling
input int InpMaxSpreadPoints=80;
input int InpMaxHoldMinutes=180;
input int InpMagic=26101401;
input bool InpUseOnlineAI=false;               // turn on only after live API connectivity tests
input string InpAIEndpoint="http://192.168.1.20:8000/decision";
input string InpAIBearerToken="CHANGE_ME_SHARED_TOKEN";
input double InpAIMinConfidence=0.58;
input bool InpUseMacroCSV=true;
input string InpMacroCSV="macro_feed.csv";     // MQL5/Files; see config/macro_feed.csv
input double InpMaxDXYChangePct=0.35;           // absolute 1-day change; block if beyond threshold
input double InpMaxUS10YChangeBps=12.0;         // absolute 1-day change
input bool InpBlockOnHighImpactNews=true;
input bool InpEmergencyCloseOnDD=false;        // false by default: avoid uncontrolled close during spread spikes

int hStopATR=INVALID_HANDLE;
string g_statePath="",g_stateKey="";bool g_stateHealthy=false;int g_scopeLock=INVALID_HANDLE;
int hFastTrend=INVALID_HANDLE,hSlowTrend=INVALID_HANDLE,hATR=INVALID_HANDLE,hADX=INVALID_HANDLE,hBands=INVALID_HANDLE;
datetime g_lastBar=0,g_dayStart=0; double g_dayEquity=0,g_startEquity=0; bool g_riskHalt=false;
string g_macroStatus="UNKNOWN"; double g_dxyChange=0,g_us10yChange=0,g_realYieldChange=0; bool g_newsBlock=true;
datetime g_macroTime=0;

struct Signal { int direction; double confidence; string regime; string setup; string reason; };

// Hard research boundary: there is deliberately no input that enables terminal trading.
bool ResearchExecutionAllowed(){return (bool)MQLInfoInteger(MQL_TESTER);}
// D1/D2 policy code is implemented, but compile/runtime and cost evidence are absent.
// Until independently verified, even tester runs must submit zero new orders.
bool EntryRiskPolicyApproved(){return false;}
int OnInit(){
 if(!ResearchExecutionAllowed()){Print("RESEARCH ONLY: attach/run in Strategy Tester; terminal execution is disabled.");return INIT_FAILED;}
 // Position count is a layer count only for hedging accounts. Netting needs a deal ledger.
 if(AccountInfoInteger(ACCOUNT_MARGIN_MODE)!=ACCOUNT_MARGIN_MODE_RETAIL_HEDGING){Print("Netting/exchange accounting is unsupported: layer cap cannot be reconciled safely.");return INIT_FAILED;}
 if(InpBaseLots<=0||InpLotMultiplier<=0||InpMaxGridLayers<1||InpMaxLotsPerBasket<=0||InpMaxTotalLots<=0||InpBasketStopMoney<=0||InpDailyLossLimitMoney<=0||InpMaxEquityDrawdownPct<=0||InpRiskPctPerInitialTrade<=0||InpAIMinConfidence<0||InpAIMinConfidence>1||InpMaxSpreadPoints<0||InpLevelLookback<1){Print("Invalid research inputs");return INIT_PARAMETERS_INCORRECT;}
 if(!SymbolSelect(InpSymbol,true)){Print("Symbol unavailable: ",InpSymbol);return INIT_FAILED;}
 hFastTrend=iMA(InpSymbol,InpTrendTF,InpFastEMA,0,MODE_EMA,PRICE_CLOSE);
 hSlowTrend=iMA(InpSymbol,InpTrendTF,InpSlowEMA,0,MODE_EMA,PRICE_CLOSE);
 hStopATR=iATR(InpSymbol,PERIOD_M5,InpATRPeriod);
 hATR=iATR(InpSymbol,InpEntryTF,InpATRPeriod); hADX=iADX(InpSymbol,InpTrendTF,InpADXPeriod);
 hBands=iBands(InpSymbol,InpEntryTF,20,0,2.0,PRICE_CLOSE);
 if(hStopATR==INVALID_HANDLE||hFastTrend==INVALID_HANDLE||hSlowTrend==INVALID_HANDLE||hATR==INVALID_HANDLE||hADX==INVALID_HANDLE||hBands==INVALID_HANDLE){Print("Indicator init failed");return INIT_FAILED;}
 trade.SetExpertMagicNumber(InpMagic); trade.SetDeviationInPoints(30);
 if(!InitRiskState())return INIT_FAILED;
 Print("RESEARCH ONLY: new orders locked pending compile/runtime, cost and reconciliation evidence. Tester mode skips online AI."); return INIT_SUCCEEDED;
}
void OnDeinit(const int reason){ if(g_scopeLock!=INVALID_HANDLE)FileClose(g_scopeLock); if(hStopATR!=INVALID_HANDLE)IndicatorRelease(hStopATR); if(hFastTrend!=INVALID_HANDLE)IndicatorRelease(hFastTrend);if(hSlowTrend!=INVALID_HANDLE)IndicatorRelease(hSlowTrend);if(hATR!=INVALID_HANDLE)IndicatorRelease(hATR);if(hADX!=INVALID_HANDLE)IndicatorRelease(hADX);if(hBands!=INVALID_HANDLE)IndicatorRelease(hBands); }
void OnTick(){
 if(!ResearchExecutionAllowed())return;
 if(_Symbol!=InpSymbol && !SymbolSelect(InpSymbol,true)) return;
 UpdateDay(); ReadMacroCSV(); CheckRiskLimits(); ManageBaskets();
 if(g_riskHalt) return;
 datetime bt=iTime(InpSymbol,InpEntryTF,0); if(bt==0||bt==g_lastBar)return; g_lastBar=bt;
 if(!SpreadOK()||NewsBlocked()||MacroBlocked())return;
 Signal s=BuildSignal();
 if(s.direction==0)return;
 if(InpUseOnlineAI && !MQLInfoInteger(MQL_TESTER)) { Signal ai=s; if(!GetAISignal(s,ai))return; s=ai; }
 if(s.direction==0||s.confidence<InpAIMinConfidence)return;
 if(!DirectionAllowedByTrend(s.direction))return;
 ProcessEntry(s);
}
// Tester TimeGMT equals simulated server time. Require explicitly UTC test data.
datetime UTCDay(datetime now){return (datetime)((long)now/86400*86400);}
string StateDigest(string data){
 uint hash=2166136261;for(int i=0;i<StringLen(data);i++){hash^=(uint)StringGetCharacter(data,i);hash*=16777619;}
 return IntegerToString((long)hash);
}
bool SaveRiskState(){
 if(g_statePath=="")return false;
 string payload="AG2|"+g_stateKey+"|"+IntegerToString((long)g_dayStart)+"|"+DoubleToString(g_dayEquity,16)+"|"+DoubleToString(g_startEquity,16)+"|"+(g_riskHalt?"1":"0");
 string record=payload+"|"+StateDigest(payload),temporary=g_statePath+".tmp";
 int file=FileOpen(temporary,FILE_WRITE|FILE_TXT|FILE_ANSI);if(file==INVALID_HANDLE)return false;
 uint written=FileWriteString(file,record);FileFlush(file);FileClose(file);
 if(written!=(uint)StringLen(record))return false;
 // Read-after-write detects truncated or altered serialization before publication.
 file=FileOpen(temporary,FILE_READ|FILE_TXT|FILE_ANSI);if(file==INVALID_HANDLE)return false;
 string verify=FileReadString(file);FileClose(file);if(verify!=record)return false;
 if(!FileMove(temporary,0,g_statePath,FILE_REWRITE))return false;
 file=FileOpen(g_statePath,FILE_READ|FILE_TXT|FILE_ANSI);if(file==INVALID_HANDLE)return false;
 verify=FileReadString(file);FileClose(file);return verify==record;
}
bool WriteHaltBarrier(){
 string path=g_statePath+".halt",record="HALTED|"+g_stateKey;
 int file=FileOpen(path,FILE_WRITE|FILE_TXT|FILE_ANSI);if(file==INVALID_HANDLE)return false;
 uint bytes=FileWriteString(file,record);FileFlush(file);FileClose(file);if(bytes!=(uint)StringLen(record))return false;
 file=FileOpen(path,FILE_READ|FILE_TXT|FILE_ANSI);if(file==INVALID_HANDLE)return false;
 string check=FileReadString(file);FileClose(file);return check==record;
}
void LatchRiskHalt(string why){
 g_riskHalt=true;
 bool barrier=WriteHaltBarrier();
 // Durable halt must be attempted before any risk-triggered close or order action.
 bool saved=SaveRiskState();
 if(!barrier||!saved){g_stateHealthy=false;Print("RISK STATE WRITE FAILED; review required. ",why);}
 Print("RISK HALT: ",why);
}
bool InitRiskState(){
 g_stateHealthy=false;
 if(MQLInfoInteger(MQL_OPTIMIZATION)){Print("Optimization unsupported: each independent pass needs an isolated state scope.");return false;}
 int scope=FileOpen("anticipatory_test_scope.txt",FILE_READ|FILE_TXT|FILE_ANSI);
 if(scope==INVALID_HANDLE){Print("Missing local tester scope file (unique run ID then UTC on second line)");return false;}
 string run=FileReadString(scope),clock=FileReadString(scope);bool extra=false;while(!FileIsEnding(scope)){if(FileReadString(scope)!="")extra=true;}FileClose(scope);
 if(StringLen(run)<1||StringLen(run)>64||clock!="UTC"||extra)return false;
 for(int i=0;i<StringLen(run);i++){ushort c=StringGetCharacter(run,i);if(!((c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9')||c=='_'||c=='-'))return false;}
 string identity=IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN))+"/"+AccountInfoString(ACCOUNT_SERVER)+"/"+InpSymbol+"/"+IntegerToString(InpMagic)+"/"+run;
 g_stateKey=StateDigest(identity);g_statePath="AG2_"+g_stateKey+".state";
 // No sharing flags: retain exclusive per-scope lock for this EA lifecycle.
 g_scopeLock=FileOpen(g_statePath+".lock",FILE_READ|FILE_WRITE|FILE_BIN);
 if(g_scopeLock==INVALID_HANDLE){Print("Risk scope already held or inaccessible");return false;}
 string marker=g_statePath+".started";bool initialized=FileIsExist(marker);
 if(FileIsExist(g_statePath+".tmp")||(!initialized&&FileIsExist(g_statePath+".halt")))return false;
 if(initialized){
  int mark=FileOpen(marker,FILE_READ|FILE_TXT|FILE_ANSI);if(mark==INVALID_HANDLE)return false;
  string identityRead=FileReadString(mark);FileClose(mark);if(identityRead!=identity)return false;
 }
 datetime now=TimeGMT();double equity=AccountInfoDouble(ACCOUNT_EQUITY);
 if(now<=0||!MathIsValidNumber(equity)||equity<=0)return false;
 if(FileIsExist(g_statePath)){
  if(!initialized)return false;
  int file=FileOpen(g_statePath,FILE_READ|FILE_TXT|FILE_ANSI);if(file==INVALID_HANDLE)return false;
  string record=FileReadString(file);bool tail=false;while(!FileIsEnding(file)){if(FileReadString(file)!="")tail=true;}FileClose(file);
  string fields[];if(tail||StringSplit(record,'|',fields)!=7||fields[0]!="AG2"||fields[1]!=g_stateKey)return false;
  string payload="";for(int i=0;i<6;i++){if(i>0)payload+="|";payload+=fields[i];}
  double day,baseline,initial;
  if(StateDigest(payload)!=fields[6]||!StrictNumber(fields[2],day)||!StrictNumber(fields[3],baseline)||!StrictNumber(fields[4],initial)||(fields[5]!="0"&&fields[5]!="1"))return false;
  g_dayStart=(datetime)day;g_dayEquity=baseline;g_startEquity=initial;g_riskHalt=fields[5]=="1";
  if(day!=(double)g_dayStart||g_dayStart!=UTCDay(g_dayStart)||g_dayStart>UTCDay(now)||baseline<=0||initial<=0)return false;
 }else{
  // A previously initialized scope never gets a new baseline, even when flat.
  if(initialized){g_riskHalt=true;Print("Missing state for initialized scope; no automatic reset");return false;}
  // Account-wide loss scope: any position OR pending order makes missing state unsafe.
  if(PositionsTotal()>0||OrdersTotal()>0){g_riskHalt=true;Print("Missing risk state with exposure: operator review required");return false;}
  int mark=FileOpen(marker,FILE_WRITE|FILE_TXT|FILE_ANSI);if(mark==INVALID_HANDLE)return false;
  uint bytes=FileWriteString(mark,identity);FileFlush(mark);FileClose(mark);if(bytes!=(uint)StringLen(identity))return false;
  mark=FileOpen(marker,FILE_READ|FILE_TXT|FILE_ANSI);if(mark==INVALID_HANDLE)return false;
  string identityRead=FileReadString(mark);FileClose(mark);if(identityRead!=identity)return false;
  g_dayStart=UTCDay(now);g_dayEquity=equity;g_startEquity=equity;g_riskHalt=false;
  if(!SaveRiskState()){g_riskHalt=true;return false;}
 }
 // An interrupted publication or independent halt barrier can never clear a latch.
 if(FileIsExist(g_statePath+".tmp"))return false;
 if(FileIsExist(g_statePath+".halt")){
  int barrier=FileOpen(g_statePath+".halt",FILE_READ|FILE_TXT|FILE_ANSI);if(barrier==INVALID_HANDLE)return false;
  string content=FileReadString(barrier);FileClose(barrier);if(content!="HALTED|"+g_stateKey)return false;
  g_riskHalt=true;if(!SaveRiskState())return false;
 }
 g_stateHealthy=true;return true;
}
void UpdateDay(){
 datetime day=UTCDay(TimeGMT());
 if(day<g_dayStart){LatchRiskHalt("UTC clock moved backwards");return;}
 if(day>g_dayStart&&!g_riskHalt){
  // Check losses against the old baseline BEFORE rollover can hide a breach.
  CheckRiskLimits();if(g_riskHalt)return;
  double eq=AccountInfoDouble(ACCOUNT_EQUITY);if(!MathIsValidNumber(eq)||eq<=0){LatchRiskHalt("Invalid equity at UTC rollover");return;}
  g_dayStart=day;g_dayEquity=eq;if(!SaveRiskState())LatchRiskHalt("UTC rollover persistence failed");
 }
}
bool NewBar(){return true;}
bool CopyVal(int handle,int buffer,int shift,double &v){double a[];ArraySetAsSeries(a,true);if(CopyBuffer(handle,buffer,shift,1,a)!=1)return false;v=a[0];return true;}
bool SpreadOK(){ double ask=SymbolInfoDouble(InpSymbol,SYMBOL_ASK),bid=SymbolInfoDouble(InpSymbol,SYMBOL_BID),pt=SymbolInfoDouble(InpSymbol,SYMBOL_POINT);if(pt<=0)return false;return ((ask-bid)/pt<=InpMaxSpreadPoints); }
bool DirectionAllowedByTrend(int dir){double f,s;if(!CopyVal(hFastTrend,0,1,f)||!CopyVal(hSlowTrend,0,1,s))return false;return dir>0?f>s:f<s;}
Signal BuildSignal(){
 Signal x; x.direction=0;x.confidence=0;x.regime="NEUTRAL";x.setup="NONE";x.reason="No valid setup";
 double fast,slow,adx,atr,upper,lower; if(!CopyVal(hFastTrend,0,1,fast)||!CopyVal(hSlowTrend,0,1,slow)||!CopyVal(hADX,0,1,adx)||!CopyVal(hATR,0,1,atr)||!CopyVal(hBands,1,1,upper)||!CopyVal(hBands,2,1,lower)||atr<=0)return x;
 double close1=iClose(InpSymbol,InpEntryTF,1),close2=iClose(InpSymbol,InpEntryTF,2); if(close1<=0||close2<=0)return x;
 double hh=-DBL_MAX,ll=DBL_MAX; for(int i=2;i<2+InpLevelLookback;i++){hh=MathMax(hh,iHigh(InpSymbol,InpEntryTF,i));ll=MathMin(ll,iLow(InpSymbol,InpEntryTF,i));}
 double bandWidth=upper-lower; bool squeeze=(bandWidth/atr)<InpSqueezeATRRatio; bool up=fast>slow,down=fast<slow;
 // Trend continuation: lower high / bearish close near recent low; symmetric long logic.
 bool bearish=(close1<close2 && close1< iOpen(InpSymbol,InpEntryTF,1));
 bool bullish=(close1>close2 && close1> iOpen(InpSymbol,InpEntryTF,1));
 if(adx<InpMinADX && !squeeze)return x;
 if(down && bearish && (close1<=ll+0.35*atr || squeeze)){x.direction=-1;x.regime="STRONG_DOWNTREND";x.setup=squeeze?"SQZ+LVL_BREAKDOWN":"TREND_CONTINUATION";x.confidence=0.60+MathMin(0.18,MathMax(0,adx-InpMinADX)*0.006);x.reason="H1 bearish alignment; M5 bearish close near recent low";}
 else if(up && bullish && (close1>=hh-0.35*atr || squeeze)){x.direction=1;x.regime="STRONG_UPTREND";x.setup=squeeze?"SQZ+LVL_BREAKOUT":"TREND_CONTINUATION";x.confidence=0.60+MathMin(0.18,MathMax(0,adx-InpMinADX)*0.006);x.reason="H1 bullish alignment; M5 bullish close near recent high";}
 if(MacroBlocked()){x.direction=0;x.reason="Macro filter blocked";} return x;
}
int CountPositions(int dir=0){int n=0;for(int i=PositionsTotal()-1;i>=0;i--){ulong t=PositionGetTicket(i);if(t==0||!PositionSelectByTicket(t))continue;if(PositionGetString(POSITION_SYMBOL)!=InpSymbol||PositionGetInteger(POSITION_MAGIC)!=InpMagic)continue;long typ=PositionGetInteger(POSITION_TYPE);int d=typ==POSITION_TYPE_BUY?1:-1;if(dir==0||d==dir)n++;}return n;}
double BasketProfit(int dir=0){double p=0;for(int i=PositionsTotal()-1;i>=0;i--){ulong t=PositionGetTicket(i);if(t==0||!PositionSelectByTicket(t))continue;if(PositionGetString(POSITION_SYMBOL)!=InpSymbol||PositionGetInteger(POSITION_MAGIC)!=InpMagic)continue;int d=PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY?1:-1;if(dir==0||d==dir)p+=PositionGetDouble(POSITION_PROFIT)+PositionGetDouble(POSITION_SWAP)+PositionEntryCosts((ulong)PositionGetInteger(POSITION_IDENTIFIER));}return p;}
double LotsTotal(){double v=0;for(int i=PositionsTotal()-1;i>=0;i--){ulong t=PositionGetTicket(i);if(t==0||!PositionSelectByTicket(t))continue;if(PositionGetString(POSITION_SYMBOL)==InpSymbol&&PositionGetInteger(POSITION_MAGIC)==InpMagic)v+=PositionGetDouble(POSITION_VOLUME);}return v;}
// MT5 position properties do not contain POSITION_COMMISSION. Entry costs are deals.
// Exits/partial exits require a full basket ledger before any release use.
double PositionEntryCosts(ulong identifier){
 if(!HistorySelectByPosition(identifier)){LatchRiskHalt("Cannot reconcile entry costs");return 0;}
 double costs=0;
 for(int i=0;i<HistoryDealsTotal();i++){
  ulong deal=HistoryDealGetTicket(i);if(deal==0)continue;
  if(HistoryDealGetInteger(deal,DEAL_ENTRY)==DEAL_ENTRY_IN)
   costs+=HistoryDealGetDouble(deal,DEAL_COMMISSION)+HistoryDealGetDouble(deal,DEAL_FEE);
 }
 return costs;
}
double NormalizeLots(double lots){
 double minimum,maximum,step;
 if(!SymbolInfoDouble(InpSymbol,SYMBOL_VOLUME_MIN,minimum)||!SymbolInfoDouble(InpSymbol,SYMBOL_VOLUME_MAX,maximum)||!SymbolInfoDouble(InpSymbol,SYMBOL_VOLUME_STEP,step))return 0;
 if(!MathIsValidNumber(lots)||!MathIsValidNumber(minimum)||!MathIsValidNumber(maximum)||!MathIsValidNumber(step)||minimum<=0||maximum<minimum||step<=0||lots<minimum)return 0;
 double normalized=NormalizeDouble(MathFloor(MathMin(lots,maximum)/step)*step,8);
 // Never round requested exposure upward, including for sub-minimum risk budgets.
 if(normalized<minimum||normalized>lots||normalized>maximum)return 0;
 return normalized;
}
void ProcessEntry(Signal &s){
 if(!EntryRiskPolicyApproved())return;
 int n=CountPositions(); if(n==0){double lot=InpBaseLots;if(lot>0)OpenPosition(s.direction,lot,s.reason);return;}
 // One directional basket only. Never hedge opposing directions within this prototype.
 int d=CountPositions(1)>0?1:-1;if(s.direction!=d)return;if(n>=InpMaxGridLayers)return;
 double atr;if(!CopyVal(hATR,0,1,atr)||atr<=0)return;
 double last=0;datetime latest=0;for(int i=PositionsTotal()-1;i>=0;i--){ulong t=PositionGetTicket(i);if(t==0||!PositionSelectByTicket(t))continue;if(PositionGetString(POSITION_SYMBOL)!=InpSymbol||PositionGetInteger(POSITION_MAGIC)!=InpMagic)continue;datetime tm=(datetime)PositionGetInteger(POSITION_TIME);if(tm>latest){latest=tm;last=PositionGetDouble(POSITION_PRICE_OPEN);}}
 double px=d>0?SymbolInfoDouble(InpSymbol,SYMBOL_ASK):SymbolInfoDouble(InpSymbol,SYMBOL_BID);bool adverse=d>0?(px<=last-InpGridATRStep*atr):(px>=last+InpGridATRStep*atr);if(!adverse)return;
 double lot=NormalizeLots(MathMin(InpBaseLots,InpBaseLots*MathPow(InpLotMultiplier,n)));if(LotsTotal()+lot>InpMaxTotalLots||BasketLots()+lot>InpMaxLotsPerBasket)return;
 if(BasketProfit()< -InpBasketStopMoney*0.50)return; // don't average into a basket already under material stress
 OpenPosition(d,lot,"GRID_ADD: "+s.reason);
}
double BasketLots(){return LotsTotal();}
bool ModeledStopLoss(int dir,double volume,double entry,double stop,double &loss){
 if((dir!=1&&dir!=-1)||!MathIsValidNumber(volume)||volume<=0||!MathIsValidNumber(entry)||!MathIsValidNumber(stop)||entry<=0||stop<=0)return false;
 double profit=0;if(!OrderCalcProfit(dir>0?ORDER_TYPE_BUY:ORDER_TYPE_SELL,InpSymbol,volume,entry,stop,profit)||!MathIsValidNumber(profit))return false;
 loss=MathMax(0,-profit);return true;
}
bool BuildProtectiveStop(int dir,double &entry,double &stop){
 MqlTick quote;if(!SymbolInfoTick(InpSymbol,quote)||!MathIsValidNumber(quote.ask)||!MathIsValidNumber(quote.bid)||quote.ask<=0||quote.bid<=0||quote.ask<quote.bid)return false;
 double atr,tick,point;long orderMode,stopLevel,freezeLevel,digits;
 if(!SymbolInfoDouble(InpSymbol,SYMBOL_TRADE_TICK_SIZE,tick)||!SymbolInfoDouble(InpSymbol,SYMBOL_POINT,point)||!SymbolInfoInteger(InpSymbol,SYMBOL_ORDER_MODE,orderMode)||!SymbolInfoInteger(InpSymbol,SYMBOL_TRADE_STOPS_LEVEL,stopLevel)||!SymbolInfoInteger(InpSymbol,SYMBOL_TRADE_FREEZE_LEVEL,freezeLevel)||!SymbolInfoInteger(InpSymbol,SYMBOL_DIGITS,digits))return false;
 if(stopLevel<0||freezeLevel<0||digits<0||digits>8)return false;
 if(!CopyVal(hStopATR,0,1,atr)||!MathIsValidNumber(atr)||atr<=0||!MathIsValidNumber(tick)||tick<=0||!MathIsValidNumber(point)||point<=0||(dir!=1&&dir!=-1))return false;
 if((orderMode&SYMBOL_ORDER_SL)==0)return false;
 entry=dir>0?quote.ask:quote.bid;double raw=entry-dir*2.0*atr;
 stop=dir>0?MathFloor(raw/tick)*tick:MathCeil(raw/tick)*tick;
 stop=NormalizeDouble(stop,(int)digits);
 if(!MathIsValidNumber(stop)||stop<=0||(dir>0?stop>=entry||stop>raw:stop<=entry||stop<raw))return false;
 // Broker stop validation uses the closing quote, not the executable opening quote.
 double minimum=(double)MathMax(stopLevel,freezeLevel)*point;
 if(!MathIsValidNumber(minimum))return false;
 if(dir>0?quote.bid-stop<minimum:stop-quote.ask<minimum)return false;
 return true;
}
double RiskSizedLots(int dir,double entry,double stop,double requested){
 double equity=AccountInfoDouble(ACCOUNT_EQUITY),minimum,loss;
 if(!MathIsValidNumber(requested)||requested<=0||!MathIsValidNumber(entry)||!MathIsValidNumber(stop)||(dir!=1&&dir!=-1)||(dir>0?stop>=entry:stop<=entry)||!SymbolInfoDouble(InpSymbol,SYMBOL_VOLUME_MIN,minimum))return 0;
 if(!MathIsValidNumber(equity)||equity<=0||!ModeledStopLoss(dir,minimum,entry,stop,loss)||loss<=0)return 0;
 double ceiling=MathMin(requested,InpBaseLots);
 ceiling=MathMin(ceiling,equity*InpRiskPctPerInitialTrade/100.0/loss*minimum);
 ceiling=MathMin(ceiling,InpMaxLotsPerBasket-BasketLots());ceiling=MathMin(ceiling,InpMaxTotalLots-LotsTotal());
 double lots=NormalizeLots(ceiling),actual;
 if(lots<=0||!ModeledStopLoss(dir,lots,entry,stop,actual)||actual>equity*InpRiskPctPerInitialTrade/100.0)return 0;
 return lots;
}
bool BasketStopBudget(int candidateDir,double candidateLots,double candidateEntry,double candidateStop){
 double total;if(!ModeledStopLoss(candidateDir,candidateLots,candidateEntry,candidateStop,total))return false;
 for(int i=PositionsTotal()-1;i>=0;i--){
  ulong ticket=PositionGetTicket(i);if(ticket==0||!PositionSelectByTicket(ticket))return false;
  if(PositionGetString(POSITION_SYMBOL)!=InpSymbol||PositionGetInteger(POSITION_MAGIC)!=InpMagic)continue;
  int dir=PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY?1:-1;
  double stop=PositionGetDouble(POSITION_SL),entry=PositionGetDouble(POSITION_PRICE_OPEN),volume=PositionGetDouble(POSITION_VOLUME),loss;
  MqlTick quote;if(!SymbolInfoTick(InpSymbol,quote)||!MathIsValidNumber(quote.bid)||!MathIsValidNumber(quote.ask)||quote.bid<=0||quote.ask<=0||quote.ask<quote.bid)return false;
  if(stop<=0||(dir>0?quote.bid<=stop:quote.ask>=stop)||!ModeledStopLoss(dir,volume,entry,stop,loss))return false;
  double costs=PositionEntryCosts((ulong)PositionGetInteger(POSITION_IDENTIFIER)),swap=PositionGetDouble(POSITION_SWAP);
  if(g_riskHalt||!MathIsValidNumber(costs)||!MathIsValidNumber(swap))return false;
  total+=loss+MathMax(0,-costs)+MathMax(0,-swap);
 }
 if(total>InpBasketStopMoney)return false;
 // OrderCalcProfit excludes prospective commission/fees and future swaps. No
 // configured verified cost model exists, so no candidate can pass this gate.
 // Do not infer zero costs from missing metadata or fabricate a fee allowance.
 Print("Entry blocked: prospective broker costs unverified; modeled price-only basket loss=",total);
 return false;
}
void OpenPosition(int dir,double requested,string comment){
 if(!ResearchExecutionAllowed()||!EntryRiskPolicyApproved()||!g_stateHealthy||g_riskHalt)return;
 CheckRiskLimits();if(g_riskHalt||CountPositions()>=InpMaxGridLayers)return;
 double entry,stop;if(!BuildProtectiveStop(dir,entry,stop))return;
 double lots=RiskSizedLots(dir,entry,stop,requested);if(lots<=0||!BasketStopBudget(dir,lots,entry,stop))return;
 if(LotsTotal()+lots>InpMaxTotalLots||BasketLots()+lots>InpMaxLotsPerBasket)return;
 // Before eventual enablement: persist consumed bar/pending-order intent and
 // reconcile fills; the unconditional entry lock remains until that is verified.
 bool sent=dir>0?trade.Buy(lots,InpSymbol,entry,stop,0,comment):trade.Sell(lots,InpSymbol,entry,stop,0,comment);
 if(!sent||trade.ResultRetcode()!=TRADE_RETCODE_DONE)LatchRiskHalt("Order incomplete/failed; reconciliation required");
}
void ManageBaskets(){int n=CountPositions();if(n==0)return;double p=BasketProfit();if(p>=InpBasketTakeProfitMoney){CloseAll("Basket TP");return;}if(p<=-InpBasketStopMoney){CloseAll("Basket SL");return;}datetime oldest=TimeCurrent();for(int i=PositionsTotal()-1;i>=0;i--){ulong t=PositionGetTicket(i);if(t==0||!PositionSelectByTicket(t))continue;if(PositionGetString(POSITION_SYMBOL)==InpSymbol&&PositionGetInteger(POSITION_MAGIC)==InpMagic)oldest=MathMin(oldest,(datetime)PositionGetInteger(POSITION_TIME));}if(TimeCurrent()-oldest>InpMaxHoldMinutes*60 && p>0)CloseAll("Time exit");}
void CloseAll(string why){
 if(!ResearchExecutionAllowed()||!g_stateHealthy)return;
 if(!SaveRiskState()){LatchRiskHalt("Pre-close persistence failed");return;}
 Print("Closing basket: ",why);
 for(int i=PositionsTotal()-1;i>=0;i--){
  ulong ticket=PositionGetTicket(i);if(ticket==0||!PositionSelectByTicket(ticket))continue;
  if(PositionGetString(POSITION_SYMBOL)!=InpSymbol||PositionGetInteger(POSITION_MAGIC)!=InpMagic)continue;
  if(!trade.PositionClose(ticket)||trade.ResultRetcode()!=TRADE_RETCODE_DONE){
   Print("Close incomplete/failed ticket=",ticket," retcode=",trade.ResultRetcode()," ",trade.ResultRetcodeDescription());
   LatchRiskHalt("Close requires reconciliation");return;
  }
 }
}
void CheckRiskLimits(){
 double eq=AccountInfoDouble(ACCOUNT_EQUITY);
 if(!g_stateHealthy||!MathIsValidNumber(eq)||eq<=0||g_dayEquity<=0||g_startEquity<=0){LatchRiskHalt("Invalid risk state/equity");return;}
 double dailyLoss=g_dayEquity-eq,dd=(g_startEquity-eq)/g_startEquity*100,basket=BasketProfit();
 bool breach=dailyLoss>=InpDailyLossLimitMoney||dd>=InpMaxEquityDrawdownPct||basket<=-InpBasketStopMoney;
 if(breach){
  LatchRiskHalt("Account daily/drawdown or EA basket limit breached");
  // No close side effect until the halt has been published successfully.
  if(!g_stateHealthy)return;
  if(InpCloseOnRiskBreach)CloseAll("Risk limit breach");
  if(InpEmergencyCloseOnDD&&dd>=InpMaxEquityDrawdownPct)CloseAll("Equity drawdown breach");
 }
}
bool NewsBlocked(){return InpBlockOnHighImpactNews&&g_newsBlock;}
bool MacroBlocked(){
 if(!InpUseMacroCSV)return false;
 if(g_macroStatus!="OK")return true;
 // In Strategy Tester, TimeGMT follows simulated server time. Historical feeds
 // therefore require an explicitly UTC-configured test dataset/server offset.
 datetime now=TimeGMT();if(g_macroTime>now||now-g_macroTime>15*60)return true;
 return MathAbs(g_dxyChange)>InpMaxDXYChangePct||MathAbs(g_us10yChange)>InpMaxUS10YChangeBps;
}
bool StrictNumber(string raw,double &value){
 int len=StringLen(raw),i=0,digits=0;if(len==0)return false;
 if(StringGetCharacter(raw,0)=='-'||StringGetCharacter(raw,0)=='+')i++;
 bool dot=false;
 for(;i<len;i++){ushort ch=StringGetCharacter(raw,i);if(ch=='.'&&!dot){dot=true;continue;}if(ch<'0'||ch>'9')return false;digits++;}
 if(digits==0)return false;value=StringToDouble(raw);return MathIsValidNumber(value);
}
bool DigitsAt(string raw,int start,int count){
 for(int i=start;i<start+count;i++){ushort ch=StringGetCharacter(raw,i);if(ch<'0'||ch>'9')return false;}return true;
}
bool ParseUTC(string raw,datetime &value){
 // Exact seconds with Z or +/-HH:MM; reject normalized invalid calendar dates.
 int len=StringLen(raw);if(len!=20&&len!=25)return false;
 if(StringSubstr(raw,4,1)!="-"||StringSubstr(raw,7,1)!="-"||StringSubstr(raw,10,1)!="T"||StringSubstr(raw,13,1)!=":"||StringSubstr(raw,16,1)!=":")return false;
 if(!DigitsAt(raw,0,4)||!DigitsAt(raw,5,2)||!DigitsAt(raw,8,2)||!DigitsAt(raw,11,2)||!DigitsAt(raw,14,2)||!DigitsAt(raw,17,2))return false;
 MqlDateTime dt;ZeroMemory(dt);
 dt.year=(int)StringToInteger(StringSubstr(raw,0,4));dt.mon=(int)StringToInteger(StringSubstr(raw,5,2));dt.day=(int)StringToInteger(StringSubstr(raw,8,2));
 dt.hour=(int)StringToInteger(StringSubstr(raw,11,2));dt.min=(int)StringToInteger(StringSubstr(raw,14,2));dt.sec=(int)StringToInteger(StringSubstr(raw,17,2));
 if(dt.year<1970||dt.mon<1||dt.mon>12||dt.day<1||dt.day>31||dt.hour>23||dt.min>59||dt.sec>59)return false;
 datetime local=StructToTime(dt);MqlDateTime check;TimeToStruct(local,check);
 if(check.year!=dt.year||check.mon!=dt.mon||check.day!=dt.day)return false;
 int offset=0;
 if(len==20){if(StringSubstr(raw,19,1)!="Z")return false;}
 else {
  string sign=StringSubstr(raw,19,1);
  if((sign!="+"&&sign!="-")||StringSubstr(raw,22,1)!=":"||!DigitsAt(raw,20,2)||!DigitsAt(raw,23,2))return false;
  int hours=(int)StringToInteger(StringSubstr(raw,20,2)),minutes=(int)StringToInteger(StringSubstr(raw,23,2));
  if(hours>23||minutes>59)return false;offset=(hours*60+minutes)*60;if(sign=="-")offset=-offset;
 }
 value=local-offset;return value>0;
}
void ReadMacroCSV(){
 g_newsBlock=true;g_macroTime=0;g_dxyChange=0;g_us10yChange=0;g_realYieldChange=0;
 if(!InpUseMacroCSV){g_macroStatus="DISABLED";g_newsBlock=false;return;}
 g_macroStatus="INVALID";
 int file=FileOpen(InpMacroCSV,FILE_READ|FILE_TXT|FILE_ANSI|FILE_COMMON);
 if(file==INVALID_HANDLE){g_macroStatus="MISSING";return;}
 string header=FileReadString(file),row="";if(!FileIsEnding(file))row=FileReadString(file);
 bool extra=false;while(!FileIsEnding(file)){if(FileReadString(file)!="")extra=true;}FileClose(file);
 if(extra||header!="timestamp_utc,dxy_change_pct,us10y_change_bps,real_yield_change_bps,high_impact_news_block")return;
 string fields[];if(StringSplit(row,',',fields)!=5)return;
 double dxy,yield,real;datetime observed;
 if(!ParseUTC(fields[0],observed)||!StrictNumber(fields[1],dxy)||!StrictNumber(fields[2],yield)||!StrictNumber(fields[3],real)||(fields[4]!="0"&&fields[4]!="1"))return;
 datetime now=TimeGMT();if(observed>now){g_macroStatus="FUTURE";return;}if(now-observed>15*60){g_macroStatus="STALE";return;}
 g_macroTime=observed;g_dxyChange=dxy;g_us10yChange=yield;g_realYieldChange=real;g_newsBlock=fields[4]=="1";g_macroStatus="OK";
}
// Online advisory integration is intentionally disabled in this research build.
// Strategy Tester never calls WebRequest; non-tester initialization is forbidden.
// Re-enable only after strict JSON/schema/request-ID/UTC-age validation is tested.
bool GetAISignal(Signal &base,Signal &out){
 out=base;out.direction=0;out.confidence=0;out.reason="Online AI unavailable in research-only build";return false;
}
