// Research source only. No runtime/MetaEditor evidence; all execution vetoes remain.
// The journal is scoped by the already-held AG2 exclusive file handle.
datetime g_consumedBar=0,g_basketStart=0;
string g_intentKind="NONE",g_intentSignal="";
int g_intentDirection=0;
double g_intentVolume=0,g_intentEntry=0,g_intentStop=0,g_intentRisk=0;
ulong g_intentTicket=0;
ulong g_basketIds[],g_basketOrders[];
double g_basketEntryVolumes[],g_basketStops[],g_basketRiskCeilings[];
bool g_journalHealthy=false;

bool ValidValue(double value){return MathIsValidNumber(value)&&value!=EMPTY_VALUE;}
bool PositiveValue(double value){return ValidValue(value)&&value>0;}
bool ClosedRates(ENUM_TIMEFRAMES timeframe,int count,MqlRates &rates[]){
 if(count<2||!SeriesInfoInteger(InpSymbol,timeframe,SERIES_SYNCHRONIZED))return false;
 datetime current=iTime(InpSymbol,timeframe,0),now=TimeCurrent();int seconds=PeriodSeconds(timeframe);
 if(current<=0||current>now||seconds<=0)return false;
 ArraySetAsSeries(rates,true);
 if(CopyRates(InpSymbol,timeframe,1,count,rates)!=count||ArraySize(rates)!=count)return false;
 if(iTime(InpSymbol,timeframe,0)!=current||rates[0].time!=iTime(InpSymbol,timeframe,1))return false;
 for(int i=0;i<count;i++){
  if(rates[i].time<=0||rates[i].time>=current||rates[i].time>now-seconds)return false;
  if(i>0&&(rates[i].time>=rates[i-1].time||rates[i-1].time-rates[i].time<seconds))return false;
  if(!PositiveValue(rates[i].open)||!PositiveValue(rates[i].high)||!PositiveValue(rates[i].low)||!PositiveValue(rates[i].close))return false;
  if(rates[i].high<rates[i].low||rates[i].high<MathMax(rates[i].open,rates[i].close)||rates[i].low>MathMin(rates[i].open,rates[i].close))return false;
 }
 return rates[0].time<=current-seconds;
}
string JournalPath(){return g_statePath+".execution";}
bool ReadOneRecord(string path,string &record){
 int file=FileOpen(path,FILE_READ|FILE_TXT|FILE_ANSI);if(file==INVALID_HANDLE)return false;
 record=FileReadString(file);bool extra=false;while(!FileIsEnding(file)){if(FileReadString(file)!="")extra=true;}FileClose(file);
 return !extra&&record!="";
}
bool PublishRecord(string path,string record){
 string temporary=path+".tmp";int file=FileOpen(temporary,FILE_WRITE|FILE_TXT|FILE_ANSI);if(file==INVALID_HANDLE)return false;
 uint bytes=FileWriteString(file,record);FileFlush(file);FileClose(file);
 string check;if(bytes!=(uint)StringLen(record)||!ReadOneRecord(temporary,check)||check!=record)return false;
 if(!FileMove(temporary,0,path,FILE_REWRITE)||!ReadOneRecord(path,check)||check!=record)return false;
 return true;
}
string UIntText(ulong value){return StringFormat("%I64u",value);}
bool ParseUInt(string raw,ulong &value){
 if(raw=="")return false;value=0;
 for(int i=0;i<StringLen(raw);i++){
  ushort c=StringGetCharacter(raw,i);if(c<'0'||c>'9')return false;
  ulong digit=(ulong)(c-'0');if(value>(ULONG_MAX-digit)/10)return false;value=value*10+digit;
 }
 return UIntText(value)==raw;
}
bool SaveExecutionJournal(){
 if(g_statePath=="")return false;
 string positions="";
 for(int i=0;i<ArraySize(g_basketIds);i++){
  if(i>0)positions+=";";
  positions+=UIntText(g_basketIds[i])+","+UIntText(g_basketOrders[i])+","+DoubleToString(g_basketEntryVolumes[i],16)+","+DoubleToString(g_basketStops[i],16)+","+DoubleToString(g_basketRiskCeilings[i],16);
 }
 string payload="AG3|"+g_stateKey+"|"+IntegerToString((long)g_consumedBar)+"|"+IntegerToString((long)g_basketStart)+"|"+g_intentKind+"|"+g_intentSignal+"|"+IntegerToString(g_intentDirection)+"|"+DoubleToString(g_intentVolume,16)+"|"+DoubleToString(g_intentEntry,16)+"|"+DoubleToString(g_intentStop,16)+"|"+DoubleToString(g_intentRisk,16)+"|"+UIntText(g_intentTicket)+"|"+positions;
 return PublishRecord(JournalPath(),payload+"|"+StateDigest(payload));
}
bool ScopedPendingOrders(){
 for(int i=OrdersTotal()-1;i>=0;i--){
  ulong ticket=OrderGetTicket(i);if(ticket==0)return true;
  string symbol;long magic;if(!OrderGetString(ORDER_SYMBOL,symbol)||!OrderGetInteger(ORDER_MAGIC,magic))return true;
  if(symbol==InpSymbol&&magic==InpMagic)return true;
 }
 return false;
}
bool LoadExecutionJournal(){
 g_journalHealthy=false;string path=JournalPath(),record;
 // Missing journal in an already-initialized AG2 scope is not a migration/reset.
 if(FileIsExist(path+".tmp")||FileIsExist(path+".started.tmp"))return false;
 bool started=FileIsExist(path+".started");
 if(!FileIsExist(path)){
  if(started||!g_scopeFresh||PositionsTotal()>0||OrdersTotal()>0)return false;
  if(!PublishRecord(path+".started","AG3_STARTED|"+g_stateKey)||!SaveExecutionJournal())return false;
 }else{
  string marker;if(!started||!ReadOneRecord(path+".started",marker)||marker!="AG3_STARTED|"+g_stateKey||!ReadOneRecord(path,record))return false;
  string fields[];if(StringSplit(record,'|',fields)!=14||fields[0]!="AG3"||fields[1]!=g_stateKey)return false;
  string payload="";for(int i=0;i<13;i++){if(i>0)payload+="|";payload+=fields[i];}if(fields[13]!=StateDigest(payload))return false;
  ulong consumed,start,ticket;if(!ParseUInt(fields[2],consumed)||!ParseUInt(fields[3],start)||!ParseUInt(fields[11],ticket)||consumed>(ulong)TimeCurrent()||start>(ulong)TimeCurrent())return false;
  if(fields[4]!="NONE"&&fields[4]!="OPEN"&&fields[4]!="CLOSE")return false;
  double direction,volume,entry,stop,risk;
  if(!StrictNumber(fields[6],direction)||!StrictNumber(fields[7],volume)||!StrictNumber(fields[8],entry)||!StrictNumber(fields[9],stop)||!StrictNumber(fields[10],risk))return false;
  if(direction!=(int)direction||volume<0||entry<0||stop<0||risk<0)return false;
  g_consumedBar=(datetime)consumed;g_basketStart=(datetime)start;g_intentKind=fields[4];g_intentSignal=fields[5];g_intentDirection=(int)direction;g_intentVolume=volume;g_intentEntry=entry;g_intentStop=stop;g_intentRisk=risk;g_intentTicket=ticket;
  ArrayResize(g_basketIds,0);ArrayResize(g_basketOrders,0);ArrayResize(g_basketEntryVolumes,0);ArrayResize(g_basketStops,0);ArrayResize(g_basketRiskCeilings,0);
  if(fields[12]!=""){
   string tuples[];int count=StringSplit(fields[12],';',tuples);if(count<1)return false;
   if(ArrayResize(g_basketIds,count)!=count||ArrayResize(g_basketOrders,count)!=count||ArrayResize(g_basketEntryVolumes,count)!=count||ArrayResize(g_basketStops,count)!=count||ArrayResize(g_basketRiskCeilings,count)!=count)return false;
   for(int i=0;i<count;i++){
    string item[];ulong id,order;double expected,stop,risk;
    if(StringSplit(tuples[i],',',item)!=5||!ParseUInt(item[0],id)||!ParseUInt(item[1],order)||id==0||order==0||!StrictNumber(item[2],expected)||expected<=0||!StrictNumber(item[3],stop)||stop<=0||!StrictNumber(item[4],risk)||risk<=0)return false;
    for(int j=0;j<i;j++)if(g_basketIds[j]==id||g_basketOrders[j]==order)return false;
    g_basketIds[i]=id;g_basketOrders[i]=order;g_basketEntryVolumes[i]=expected;g_basketStops[i]=stop;g_basketRiskCeilings[i]=risk;
   }
  }
  if((g_basketStart==0)!=(ArraySize(g_basketIds)==0)&&g_intentKind=="NONE")return false;
 }
 if(g_intentKind!="NONE"||ScopedPendingOrders()){
  LatchRiskHalt("Unresolved persisted order intent/pending order; never resend on restart");return false;
 }
 g_journalHealthy=true;double cash,openValue;
 if(!BasketLedger(cash,openValue)){g_journalHealthy=false;return false;}
 return true;
}
int BasketIdIndex(ulong id){for(int i=0;i<ArraySize(g_basketIds);i++)if(g_basketIds[i]==id)return i;return -1;}
bool DealNumber(ulong ticket,ENUM_DEAL_PROPERTY_DOUBLE property,double &value){return HistoryDealGetDouble(ticket,property,value)&&ValidValue(value);}
bool DealInteger(ulong ticket,ENUM_DEAL_PROPERTY_INTEGER property,long &value){return HistoryDealGetInteger(ticket,property,value);}
bool SelectedPositionIdentity(string &symbol,long &magic,long &type,ulong &identifier){
 long id;
 if(!PositionGetString(POSITION_SYMBOL,symbol)||!PositionGetInteger(POSITION_MAGIC,magic)||!PositionGetInteger(POSITION_TYPE,type)||!PositionGetInteger(POSITION_IDENTIFIER,id)||id<=0||(type!=POSITION_TYPE_BUY&&type!=POSITION_TYPE_SELL))return false;
 identifier=(ulong)id;return true;
}
bool ScopedExposure(int &count,double &lots,int direction=0){
 count=0;lots=0;
 for(int i=PositionsTotal()-1;i>=0;i--){
  ulong ticket=PositionGetTicket(i);if(ticket==0||!PositionSelectByTicket(ticket))return false;
  string symbol;long magic,type;ulong identifier;
  if(!SelectedPositionIdentity(symbol,magic,type,identifier))return false;
  if(symbol!=InpSymbol||magic!=InpMagic)continue;
  double volume;if(!PositionGetDouble(POSITION_VOLUME,volume)||!PositiveValue(volume))return false;
  if(direction!=0&&(type==POSITION_TYPE_BUY?1:-1)!=direction)continue;
  count++;lots+=volume;if(!ValidValue(lots))return false;
 }
 return true;
}
bool VolumeUnits(double volume,long &units){
 double step;if(!SymbolInfoDouble(InpSymbol,SYMBOL_VOLUME_STEP,step)||!PositiveValue(step)||!ValidValue(volume)||volume<0)return false;
 double scaled=volume/step;if(!ValidValue(scaled)||scaled>9007199254740991.0)return false;
 double rounded=MathRound(scaled);
 // Convert broker decimal volumes individually, then add/subtract integer units.
 // Require exact round-trip at MT5's supported 8 volume decimal places; never
 // accept a non-grid volume or introduce an exposure/risk tolerance.
 if(NormalizeDouble(rounded*step,8)!=volume)return false;
 units=(long)rounded;return units>=0;
}
// Signed closed cash flows are included exactly once. Current POSITION_PROFIT/
// POSITION_SWAP value only the remaining open volume; entry fees are NOT added again.
bool BasketLedger(double &realized,double &openValue,double &recordedLosses){
 realized=0;openValue=0;recordedLosses=0;int count=ArraySize(g_basketIds);
 if(!g_journalHealthy||g_intentKind!="NONE"||ScopedPendingOrders())return false;
 if(count==0){int live;double lots;return g_basketStart==0&&ScopedExposure(live,lots)&&live==0;}
 if(g_basketStart<=0||g_basketStart>TimeCurrent())return false;
 // Unallocated account cash/charges cannot be assigned to a basket safely.
 if(!HistorySelect(g_basketStart,TimeCurrent()))return false;
 for(int n=0;n<HistoryDealsTotal();n++){
  ulong ticket=HistoryDealGetTicket(n);long type,id;if(ticket==0||!DealInteger(ticket,DEAL_TYPE,type)||!DealInteger(ticket,DEAL_POSITION_ID,id))return false;
  if(type!=DEAL_TYPE_BUY&&type!=DEAL_TYPE_SELL)return false;
  string symbol;if(!HistoryDealGetString(ticket,DEAL_SYMBOL,symbol))return false;
  long magic;if(!DealInteger(ticket,DEAL_MAGIC,magic))return false;
  if(symbol==InpSymbol&&magic==InpMagic&&BasketIdIndex((ulong)id)<0)return false;
 }
 for(int i=0;i<count;i++){
  if(!HistorySelectByPosition(g_basketIds[i])||HistoryDealsTotal()<1)return false;
  long entered=0,exited=0,expectedUnits;if(!VolumeUnits(g_basketEntryVolumes[i],expectedUnits)||expectedUnits<=0)return false;
  int direction=0;ulong seen[];int total=HistoryDealsTotal();
  for(int n=0;n<total;n++){
   ulong deal=HistoryDealGetTicket(n);if(deal==0)return false;
   for(int j=0;j<ArraySize(seen);j++)if(seen[j]==deal)return false;
   if(ArrayResize(seen,n+1)!=n+1)return false;seen[n]=deal;
   long id,type,entry,order,magic,time;double volume,profit,commission,fee,swap;string symbol;
   if(!DealInteger(deal,DEAL_POSITION_ID,id)||!DealInteger(deal,DEAL_TYPE,type)||!DealInteger(deal,DEAL_ENTRY,entry)||!DealInteger(deal,DEAL_ORDER,order)||!DealInteger(deal,DEAL_MAGIC,magic)||!DealInteger(deal,DEAL_TIME,time)||!HistoryDealGetString(deal,DEAL_SYMBOL,symbol))return false;
   if((ulong)id!=g_basketIds[i]||symbol!=InpSymbol||time<(long)g_basketStart||time>(long)TimeCurrent()||(type!=DEAL_TYPE_BUY&&type!=DEAL_TYPE_SELL))return false;
   if(!DealNumber(deal,DEAL_VOLUME,volume)||volume<=0||!DealNumber(deal,DEAL_PROFIT,profit)||!DealNumber(deal,DEAL_COMMISSION,commission)||!DealNumber(deal,DEAL_FEE,fee)||!DealNumber(deal,DEAL_SWAP,swap))return false;
   long units;if(!VolumeUnits(volume,units)||units<=0)return false;
   int dealDirection=type==DEAL_TYPE_BUY?1:-1;
   if(entry==DEAL_ENTRY_IN){
    if((ulong)order!=g_basketOrders[i]||magic!=InpMagic||exited>0||(direction!=0&&direction!=dealDirection))return false;
    if(entered>LONG_MAX-units)return false;direction=dealDirection;entered+=units;
   }else if(entry==DEAL_ENTRY_OUT){
    if(direction==0||dealDirection==direction||exited>LONG_MAX-units)return false;exited+=units;
   }else return false;
   realized+=profit+commission+fee+swap;
   recordedLosses+=MathMax(0,-profit)+MathMax(0,-commission)+MathMax(0,-fee)+MathMax(0,-swap);
   if(!ValidValue(realized)||!ValidValue(recordedLosses)||exited>entered)return false;
  }
  // Expected entry volume is persisted after verified fill; a truncated history
  // cannot silently turn a missing entry/partial exit into zero risk.
  if(entered!=expectedUnits)return false;
  double liveVolume=0;int matches=0;
  for(int n=PositionsTotal()-1;n>=0;n--){
   ulong ticket=PositionGetTicket(n);if(ticket==0||!PositionSelectByTicket(ticket))return false;
   string symbol;long magic,type;ulong identifier;if(!SelectedPositionIdentity(symbol,magic,type,identifier))return false;
   if(identifier!=g_basketIds[i])continue;
   if(symbol!=InpSymbol||magic!=InpMagic||++matches>1)return false;
   if((type==POSITION_TYPE_BUY?1:-1)!=direction)return false;
   double value,swap,stop,price,loss;if(!PositionGetDouble(POSITION_VOLUME,liveVolume)||!PositionGetDouble(POSITION_PROFIT,value)||!PositionGetDouble(POSITION_SWAP,swap)||!PositionGetDouble(POSITION_SL,stop)||!PositionGetDouble(POSITION_PRICE_OPEN,price)||!PositiveValue(liveVolume)||!ValidValue(value)||!ValidValue(swap)||!PositiveValue(stop)||!PositiveValue(price)||stop!=g_basketStops[i]||(direction>0?stop>=price:stop<=price)||!ModeledStopLoss(direction,liveVolume,price,stop,loss)||loss>g_basketRiskCeilings[i])return false;
   openValue+=value+swap;if(!ValidValue(openValue))return false;
  }
  long liveUnits;if(!VolumeUnits(liveVolume,liveUnits)||entered-exited!=liveUnits)return false;
 }
 for(int n=PositionsTotal()-1;n>=0;n--){
  ulong ticket=PositionGetTicket(n);if(ticket==0||!PositionSelectByTicket(ticket))return false;
  string symbol;long magic,type;ulong identifier;if(!SelectedPositionIdentity(symbol,magic,type,identifier))return false;
  if(symbol==InpSymbol&&magic==InpMagic&&BasketIdIndex(identifier)<0)return false;
 }
 return ValidValue(realized+openValue)&&CountPositions()<=InpMaxGridLayers&&LotsTotal()<=InpMaxLotsPerBasket&&LotsTotal()<=InpMaxTotalLots;
}
bool BasketLedger(double &realized,double &openValue){double recordedLosses;return BasketLedger(realized,openValue,recordedLosses);}
bool FinalizeFlatBasket(){
 if(!g_journalHealthy||g_riskHalt||g_intentKind!="NONE")return false;
 if(ArraySize(g_basketIds)==0||CountPositions()!=0)return true;
 double realized,openValue,losses;if(!BasketLedger(realized,openValue,losses)||openValue!=0)return false;
 string positions="";
 for(int i=0;i<ArraySize(g_basketIds);i++){
  if(i>0)positions+=";";
  positions+=UIntText(g_basketIds[i])+","+UIntText(g_basketOrders[i])+","+DoubleToString(g_basketEntryVolumes[i],16)+","+DoubleToString(g_basketStops[i],16)+","+DoubleToString(g_basketRiskCeilings[i],16);
 }
 string path=JournalPath()+".basket_"+IntegerToString((long)g_basketStart)+".closed";
 string payload="AG3_CLOSED|"+g_stateKey+"|"+IntegerToString((long)g_basketStart)+"|"+positions+"|"+DoubleToString(realized,16)+"|"+DoubleToString(losses,16);
 string record=payload+"|"+StateDigest(payload),existing;
 if(FileIsExist(path+".tmp"))return false;
 if(FileIsExist(path)){if(!ReadOneRecord(path,existing)||existing!=record)return false;}
 else if(!PublishRecord(path,record))return false;
 // The verified final archive exists before the active basket is retired.
 // Repeated finalization may reuse only that exact record; never overwrite it.
 ArrayResize(g_basketIds,0);ArrayResize(g_basketOrders,0);ArrayResize(g_basketEntryVolumes,0);ArrayResize(g_basketStops,0);ArrayResize(g_basketRiskCeilings,0);g_basketStart=0;
 if(!SaveExecutionJournal()){g_journalHealthy=false;LatchRiskHalt("Flat-basket retirement persistence failed");return false;}
 return true;
}
bool PrepareIntent(string kind,int direction,double volume,double entry,double stop,double risk,ulong ticket){
 if(!g_journalHealthy||g_intentKind!="NONE"||ScopedPendingOrders())return false;
 double cash,openValue;
 if((kind!="OPEN"&&kind!="CLOSE")||!BasketLedger(cash,openValue)){
  g_journalHealthy=false;LatchRiskHalt("Pre-send lifecycle ledger unknown/ambiguous");return false;
 }
 if(kind=="CLOSE"){
  if((direction!=1&&direction!=-1)||!PositiveValue(volume)||BasketIdIndex(ticket)<0)return false;
  bool found=false;
  for(int i=PositionsTotal()-1;i>=0;i--){
   ulong selected=PositionGetTicket(i);if(selected==0||!PositionSelectByTicket(selected))return false;
   string symbol;long magic,type;ulong identifier;if(!SelectedPositionIdentity(symbol,magic,type,identifier))return false;
   if(identifier!=ticket)continue;
   double currentVolume;if(found||!PositionGetDouble(POSITION_VOLUME,currentVolume))return false;
   if(symbol!=InpSymbol||magic!=InpMagic||(type!=POSITION_TYPE_BUY&&type!=POSITION_TYPE_SELL)||(type==POSITION_TYPE_BUY?-1:1)!=direction||currentVolume!=volume)return false;
   found=true;
  }
  if(!found)return false;
 }
 if(kind=="OPEN"){
  datetime bar=iTime(InpSymbol,InpEntryTF,1);if(bar<=0||bar<=g_consumedBar)return false;
  if(CountPositions()==0){if(ArraySize(g_basketIds)!=0||g_basketStart!=0)return false;g_basketStart=TimeCurrent();}
  g_consumedBar=bar;g_intentSignal=g_stateKey+"_"+IntegerToString((int)InpEntryTF)+"_"+IntegerToString((long)bar);
 }
 g_intentKind=kind;g_intentDirection=direction;g_intentVolume=volume;g_intentEntry=entry;g_intentStop=stop;g_intentRisk=risk;g_intentTicket=ticket;
 if(!SaveExecutionJournal()){g_journalHealthy=false;LatchRiskHalt("Pre-send intent persistence failed");return false;}
 return true;
}
bool FinishIntent(){
 // Verify complete history/live state BEFORE clearing the persisted pending bit.
 string pending=g_intentKind;g_intentKind="NONE";
 double cash,openValue;if(!BasketLedger(cash,openValue)){g_intentKind=pending;return false;}
 g_intentDirection=0;g_intentVolume=0;g_intentEntry=0;g_intentStop=0;g_intentRisk=0;g_intentTicket=0;
 if(!SaveExecutionJournal()){g_intentKind=pending;g_journalHealthy=false;LatchRiskHalt("Post-fill journal persistence failed");return false;}return true;
}
bool VerifiedOrder(ulong order,int direction,double expectedVolume,ulong &positionId){
 long state,magic,type,id;double initial,current;string symbol;
 if(!HistoryOrderSelect(order)||!HistoryOrderGetInteger(order,ORDER_STATE,state)||!HistoryOrderGetInteger(order,ORDER_MAGIC,magic)||!HistoryOrderGetInteger(order,ORDER_TYPE,type)||!HistoryOrderGetInteger(order,ORDER_POSITION_ID,id)||!HistoryOrderGetDouble(order,ORDER_VOLUME_INITIAL,initial)||!HistoryOrderGetDouble(order,ORDER_VOLUME_CURRENT,current)||!HistoryOrderGetString(order,ORDER_SYMBOL,symbol))return false;
 if(state!=ORDER_STATE_FILLED||magic!=InpMagic||symbol!=InpSymbol||type!=(direction>0?ORDER_TYPE_BUY:ORDER_TYPE_SELL)||id<=0||!PositiveValue(initial)||!ValidValue(current)||initial!=expectedVolume||current!=0)return false;
 positionId=(ulong)id;return true;
}
bool VerifyOpenFill(){
 if(g_intentKind!="OPEN"||trade.ResultRetcode()!=TRADE_RETCODE_DONE||trade.ResultOrder()==0||trade.ResultDeal()==0)return false;
 ulong order=trade.ResultOrder(),deal=trade.ResultDeal(),orderPosition;
 if(!VerifiedOrder(order,g_intentDirection,g_intentVolume,orderPosition)||!HistoryDealSelect(deal))return false;
 long id,entry,type,dealOrder;if(!DealInteger(deal,DEAL_POSITION_ID,id)||!DealInteger(deal,DEAL_ENTRY,entry)||!DealInteger(deal,DEAL_TYPE,type)||!DealInteger(deal,DEAL_ORDER,dealOrder)||(ulong)dealOrder!=order||id<=0||(ulong)id!=orderPosition||entry!=DEAL_ENTRY_IN||type!=(g_intentDirection>0?DEAL_TYPE_BUY:DEAL_TYPE_SELL)||BasketIdIndex((ulong)id)>=0)return false;
 bool found=false;double actualRisk=0;
 for(int i=PositionsTotal()-1;i>=0;i--){
  ulong ticket=PositionGetTicket(i);if(ticket==0||!PositionSelectByTicket(ticket))return false;
  string symbol;long magic,positionType;ulong identifier;if(!SelectedPositionIdentity(symbol,magic,positionType,identifier))return false;
  if(identifier!=(ulong)id)continue;if(found)return false;found=true;
  double volume,price,stop;if(!PositionGetDouble(POSITION_VOLUME,volume)||!PositionGetDouble(POSITION_PRICE_OPEN,price)||!PositionGetDouble(POSITION_SL,stop))return false;
  if(symbol!=InpSymbol||magic!=InpMagic||(positionType==POSITION_TYPE_BUY?1:-1)!=g_intentDirection||volume!=g_intentVolume||stop!=g_intentStop||!PositiveValue(price)||!PositiveValue(stop))return false;
  if(g_intentDirection>0?stop>=price:stop<=price)return false;
  if(!ModeledStopLoss(g_intentDirection,volume,price,stop,actualRisk)||actualRisk>g_intentRisk||actualRisk>AccountInfoDouble(ACCOUNT_EQUITY)*InpRiskPctPerInitialTrade/100.0)return false;
 }
 if(!found)return false;
 int count=ArraySize(g_basketIds);if(ArrayResize(g_basketIds,count+1)!=count+1||ArrayResize(g_basketOrders,count+1)!=count+1||ArrayResize(g_basketEntryVolumes,count+1)!=count+1||ArrayResize(g_basketStops,count+1)!=count+1||ArrayResize(g_basketRiskCeilings,count+1)!=count+1)return false;
 g_basketIds[count]=(ulong)id;g_basketOrders[count]=order;g_basketEntryVolumes[count]=g_intentVolume;g_basketStops[count]=g_intentStop;g_basketRiskCeilings[count]=g_intentRisk;
 return FinishIntent();
}
bool VerifyCloseFill(){
 if(g_intentKind!="CLOSE"||trade.ResultRetcode()!=TRADE_RETCODE_DONE||trade.ResultOrder()==0||trade.ResultDeal()==0)return false;
 ulong order=trade.ResultOrder(),deal=trade.ResultDeal(),orderPosition;
 if(!VerifiedOrder(order,g_intentDirection,g_intentVolume,orderPosition)||orderPosition!=g_intentTicket||!HistoryDealSelect(deal))return false;
 long id,entry,dealOrder,magic,type;double volume;string symbol;
 if(!DealInteger(deal,DEAL_POSITION_ID,id)||!DealInteger(deal,DEAL_ENTRY,entry)||!DealInteger(deal,DEAL_ORDER,dealOrder)||!DealInteger(deal,DEAL_MAGIC,magic)||!DealInteger(deal,DEAL_TYPE,type)||!HistoryDealGetString(deal,DEAL_SYMBOL,symbol)||!DealNumber(deal,DEAL_VOLUME,volume)||(ulong)id!=g_intentTicket||(ulong)dealOrder!=order||magic!=InpMagic||symbol!=InpSymbol||type!=(g_intentDirection>0?DEAL_TYPE_BUY:DEAL_TYPE_SELL)||entry!=DEAL_ENTRY_OUT||volume!=g_intentVolume)return false;
 for(int i=PositionsTotal()-1;i>=0;i--){
  ulong ticket=PositionGetTicket(i);if(ticket==0||!PositionSelectByTicket(ticket))return false;
  string positionSymbol;long positionMagic,positionType;ulong identifier;
  if(!SelectedPositionIdentity(positionSymbol,positionMagic,positionType,identifier)||identifier==g_intentTicket)return false;
 }
 return FinishIntent();
}
// There is deliberately no setter/loading path: no prospective fee assumption
// has been approved or verified. A missing cost bound must never mean zero.
struct FutureCostBudget { bool authorized; bool verified; bool known; double commission; double fee; double swap; string currency; string provenance; string reason; datetime validUntil; };
bool FutureCostsKnown(double &bound){
 FutureCostBudget costs;ZeroMemory(costs);costs.reason="No verified, approved prospective broker-cost source";bound=0;
 if(!costs.authorized||!costs.verified||!costs.known)return false;
 if(costs.currency!=AccountInfoString(ACCOUNT_CURRENCY)||costs.provenance==""||costs.validUntil<TimeCurrent())return false;
 if(!ValidValue(costs.commission)||!ValidValue(costs.fee)||!ValidValue(costs.swap)||costs.commission<0||costs.fee<0||costs.swap<0)return false;
 bound=costs.commission+costs.fee+costs.swap;return ValidValue(bound);
}
