// NATIVE TEST SCRIPT, NOT AN EA OR PERFORMANCE BACKTEST.
// Includes production functions unchanged, with explicit test adapters for clock,
// bar identity, CSV filename and a last-resort no-send sentinel in Trade.mqh.
// No production event handler, OpenPosition or CloseAll is executed by OnStart.
string g_nativePrefix="";
datetime g_nativeClock=0;
int g_nativeSendAttempts=0,g_nativeDeniedFiles=0;
int AGNativeFileOpen(string name,int flags,short delimiter='\t',uint codepage=CP_ACP){
 if(name=="macro_feed.csv"&&(flags&FILE_READ)!=0&&(flags&FILE_WRITE)==0){name=g_nativePrefix+"_macro.csv";flags&=~FILE_COMMON;}
 if(g_nativePrefix==""||StringFind(name,g_nativePrefix)!=0){g_nativeDeniedFiles++;return INVALID_HANDLE;}
 return FileOpen(name,flags,delimiter,codepage);
}
datetime AGNativeClock(){return g_nativeClock;}
datetime AGNativeBarTime(string symbol,ENUM_TIMEFRAMES timeframe,int shift){
 if(shift<0)return 0;return g_nativeClock-(datetime)((shift+1)*300);
}
bool AGNativeOrderSendBlocked(const MqlTradeRequest &request,MqlTradeResult &result){
 g_nativeSendAttempts++;ZeroMemory(result);result.retcode=TRADE_RETCODE_TRADE_DISABLED;return false;
}
bool AGNativeOrderSendAsyncBlocked(const MqlTradeRequest &request,MqlTradeResult &result){
 return AGNativeOrderSendBlocked(request,result);
}
#define OnInit AGNativeProductionOnInit
#define OnTick AGNativeProductionOnTick
#define OnDeinit AGNativeProductionOnDeinit
#define FileOpen AGNativeFileOpen
#define TimeCurrent AGNativeClock
#define TimeGMT AGNativeClock
#define iTime AGNativeBarTime
#define OrderSend AGNativeOrderSendBlocked
#define OrderSendAsync AGNativeOrderSendAsyncBlocked
// Bind standard-library send sites to the no-send sentinel before its include
// guard is set. Only the subsequent production CTrade variable is substituted.
#include <Trade/Trade.mqh>
uint g_nativeResultCode=0;
int g_nativeRetcodeReads=0,g_nativeOrderReads=0,g_nativeDealReads=0;
class AGNativeTrade:public CTrade {
 public:
  uint ResultRetcode(void) const {g_nativeRetcodeReads++;return g_nativeResultCode;}
  ulong ResultOrder(void) const {g_nativeOrderReads++;return CTrade::ResultOrder();}
  ulong ResultDeal(void) const {g_nativeDealReads++;return CTrade::ResultDeal();}
};
#define CTrade AGNativeTrade
#include "../../Experts/AnticipatoryGold_AI_v1.mq5"
#undef CTrade
#undef OnInit
#undef OnTick
#undef OnDeinit
#undef FileOpen
#undef TimeCurrent
#undef TimeGMT
#undef iTime
#undef OrderSend
#undef OrderSendAsync

int g_nativeOutput=INVALID_HANDLE,g_nativeTotal=0,g_nativePassed=0;
string NativeJSON(string value){
 StringReplace(value,"\\","\\\\");StringReplace(value,"\"","\\\"");
 StringReplace(value,"\r","\\r");StringReplace(value,"\n","\\n");StringReplace(value,"\t","\\t");return "\""+value+"\"";
}
void NativeCase(string id,bool pass,string observed,string basis){
 g_nativeTotal++;if(pass)g_nativePassed++;
 string line="{\"type\":\"case\",\"id\":"+NativeJSON(id)+",\"passed\":"+(pass?"true":"false")+",\"observed\":"+NativeJSON(observed)+",\"basis\":"+NativeJSON(basis)+"}";
 FileWriteString(g_nativeOutput,line+"\r\n");FileFlush(g_nativeOutput);Print(line);
}
bool NativeWrite(string name,string value){
 if(StringFind(name,g_nativePrefix)!=0)return false;
 int file=FileOpen(name,FILE_WRITE|FILE_BIN|FILE_ANSI);if(file==INVALID_HANDLE)return false;
 uint written=FileWriteString(file,value);FileFlush(file);FileClose(file);return written==(uint)StringLen(value);
}
string NativeUTC(datetime value){
 MqlDateTime parts;TimeToStruct(value,parts);
 return StringFormat("%04d-%02d-%02dT%02d:%02d:%02dZ",parts.year,parts.mon,parts.day,parts.hour,parts.min,parts.sec);
}
string NativeMacro(datetime snapshot,datetime numeric,datetime newsUntil,string number="0.1",string flag="0",string digest="0000000000000000000000000000000000000000000000000000000000000000"){
 string header="schema_version,timestamp_utc,dxy_change_pct,us10y_change_bps,real_yield_change_bps,high_impact_news_block,dxy_observed_at_utc,us10y_observed_at_utc,real_yield_observed_at_utc,news_observed_at_utc,news_valid_until_utc,provenance_sha256";
 return header+"\n2,"+NativeUTC(snapshot)+","+number+",2,-1,"+flag+","+NativeUTC(numeric)+","+NativeUTC(numeric)+","+NativeUTC(numeric)+","+NativeUTC(snapshot)+","+NativeUTC(newsUntil)+","+digest+"\n";
}
bool NativeReadMacro(string text){
 if(!NativeWrite(g_nativePrefix+"_macro.csv",text))return false;ReadMacroCSV();return true;
}
void NativeReset(string id){
 if(g_scopeLock!=INVALID_HANDLE){FileClose(g_scopeLock);g_scopeLock=INVALID_HANDLE;}
 g_stateKey="native_"+id;g_statePath=g_nativePrefix+"_"+id+".state";
 g_scopeFresh=true;g_stateHealthy=true;g_journalHealthy=true;g_riskHalt=false;
 g_dayStart=UTCDay(g_nativeClock);g_dayEquity=1000;g_startEquity=1000;
 g_consumedBar=0;g_basketStart=0;g_intentKind="NONE";g_intentSignal="";
 g_intentDirection=0;g_intentVolume=0;g_intentEntry=0;g_intentStop=0;g_intentRisk=0;g_intentTicket=0;
 ArrayResize(g_basketIds,0);ArrayResize(g_basketOrders,0);ArrayResize(g_basketEntryVolumes,0);ArrayResize(g_basketStops,0);ArrayResize(g_basketRiskCeilings,0);
 g_scopeLock=FileOpen(g_statePath+".lock",FILE_READ|FILE_WRITE|FILE_BIN);
}
bool NativeSeedJournal(){return g_scopeLock!=INVALID_HANDLE&&PublishRecord(JournalPath()+".started","AG3_STARTED|"+g_stateKey)&&SaveExecutionJournal();}
bool NativeRetcodeVeto(string kind,uint retcode,bool doneControl=false){
 NativeReset("retcode_"+kind+"_"+IntegerToString((long)retcode));
 g_intentKind=kind;g_intentDirection=kind=="OPEN"?1:-1;
 g_intentVolume=0.01;g_intentEntry=2000;g_intentStop=1990;g_intentRisk=10;g_intentTicket=123;
 bool seeded=NativeSeedJournal();string before,after;
 bool readBefore=ReadOneRecord(JournalPath(),before);g_nativeResultCode=retcode;
 g_nativeRetcodeReads=0;g_nativeOrderReads=0;g_nativeDealReads=0;
 // These are the actual production verifier functions, with only retcode
 // supplied by a test double. No order/deal/fill or broker fault is generated.
 bool accepted=kind=="OPEN"?VerifyOpenFill():VerifyCloseFill();
 bool readAfter=ReadOneRecord(JournalPath(),after);g_nativeResultCode=0;
 // Negative retcodes must reject BEFORE touching order/deal getters. The DONE
 // control must reach the real zero-order getter, proving branch discrimination.
 bool branch=doneControl?(g_nativeRetcodeReads==1&&g_nativeOrderReads==1&&g_nativeDealReads==0):(g_nativeRetcodeReads==1&&g_nativeOrderReads==0&&g_nativeDealReads==0);
 return seeded&&readBefore&&readAfter&&!accepted&&branch&&g_intentKind==kind&&before==after&&!g_riskHalt&&g_nativeSendAttempts==0;
}
void NativeSummary(){
 string line="{\"type\":\"summary\",\"schema_version\":1,\"total\":"+IntegerToString(g_nativeTotal)+",\"passed\":"+IntegerToString(g_nativePassed)+",\"failed\":"+IntegerToString(g_nativeTotal-g_nativePassed)+",\"send_attempts\":"+IntegerToString(g_nativeSendAttempts)+",\"denied_file_opens\":"+IntegerToString(g_nativeDeniedFiles)+",\"broker_fault_tests\":\"NOT_RUN\",\"performance_backtest\":\"NOT_RUN\"}";
 FileWriteString(g_nativeOutput,line+"\r\n");FileFlush(g_nativeOutput);FileClose(g_nativeOutput);g_nativeOutput=INVALID_HANDLE;
 if(g_scopeLock!=INVALID_HANDLE){FileClose(g_scopeLock);g_scopeLock=INVALID_HANDLE;}
 Print(line);Print("AG_NATIVE_RESULT|",g_nativePrefix,".jsonl|",g_nativeTotal,"|",g_nativePassed);
}
void OnStart(){
 // Local wall-clock is used solely for a unique filename. Test time is fixed.
 g_nativePrefix="AG_NATIVE_"+IntegerToString((long)TimeLocal())+"_"+UIntText(GetTickCount64());
 g_nativeClock=D'2026.01.02 12:00:00';
 g_nativeOutput=FileOpen(g_nativePrefix+".jsonl",FILE_WRITE|FILE_TXT|FILE_ANSI);
 if(g_nativeOutput==INVALID_HANDLE){Print("AG_NATIVE_OUTPUT_FAILED");return;}
 bool flat=PositionsTotal()==0&&OrdersTotal()==0;
 NativeCase("ENV_FLAT_NO_ORDERS",flat,"read_only_positions_and_orders","NATIVE-ENVIRONMENT");
 if(!flat){NativeSummary();return;}
 NativeCase("TERMINAL_RESEARCH_GUARD",!ResearchExecutionAllowed(),"production_guard_false_outside_tester","NATIVE-GUARD");
 NativeCase("ENTRY_POLICY_HARD_FALSE",!EntryRiskPolicyApproved(),"production_entry_policy_false","NATIVE-GUARD");
 double number=0;
 NativeCase("NUMBER_SIGNED_DECIMAL",StrictNumber("-.25",number)&&number==-0.25,"signed_decimal","NATIVE-PARSER");
 NativeCase("NUMBER_TRAILING_DOT",StrictNumber("2.",number)&&number==2.0,"trailing_decimal_point","NATIVE-PARSER");
 NativeCase("NUMBER_EXPONENT_REJECT",!StrictNumber("1e2",number),"exponent_rejected","NATIVE-PARSER");
 NativeCase("NUMBER_NAN_REJECT",!StrictNumber("NaN",number),"nan_text_rejected","NATIVE-PARSER");
 NativeCase("NUMBER_SPACE_REJECT",!StrictNumber(" 1",number),"leading_space_rejected","NATIVE-PARSER");
 NativeCase("NUMBER_SIGN_ONLY_REJECT",!StrictNumber("+",number),"sign_only_rejected","NATIVE-PARSER");
 NativeCase("NUMBER_EMPTY_REJECT",!StrictNumber("",number),"empty_rejected","NATIVE-PARSER");
 NativeCase("EMPTY_INDICATOR_REJECT",!ValidValue(EMPTY_VALUE),"empty_indicator_sentinel_rejected","NATIVE-PARSER");
 datetime parsed=0;
 NativeCase("UTC_INVALID_DATE_REJECT",!CanonicalUTC("2026-02-30T00:00:00Z",parsed),"invalid_calendar_date","NATIVE-PARSER");
 NativeCase("UTC_OFFSET_CANONICAL_REJECT",!CanonicalUTC("2026-01-02T12:00:00+00:00",parsed),"v2_requires_seconds_Z","NATIVE-PARSER");

 bool io=NativeReadMacro(NativeMacro(g_nativeClock,g_nativeClock,g_nativeClock+60));
 NativeCase("MACRO_VALID_FILE",io&&g_macroStatus=="OK"&&!MacroBlocked()&&!NewsBlocked(),g_macroStatus,"NATIVE-FILE-FIXED-CLOCK");
 io=NativeReadMacro(NativeMacro(g_nativeClock-900,g_nativeClock-900,g_nativeClock+60));
 NativeCase("MACRO_AGE_900_INCLUSIVE",io&&g_macroStatus=="OK"&&!MacroBlocked(),g_macroStatus,"NATIVE-FILE-FIXED-CLOCK");
 io=NativeReadMacro(NativeMacro(g_nativeClock-901,g_nativeClock-901,g_nativeClock+60));
 NativeCase("MACRO_AGE_901_REJECT",io&&g_macroStatus=="STALE"&&MacroBlocked(),g_macroStatus,"NATIVE-FILE-FIXED-CLOCK");
 io=NativeReadMacro(NativeMacro(g_nativeClock,g_nativeClock-901,g_nativeClock+60));
 NativeCase("MACRO_OLD_SOURCE_REJECT",io&&g_macroStatus=="STALE"&&MacroBlocked(),g_macroStatus,"NATIVE-FILE-FIXED-CLOCK");
 io=NativeReadMacro(NativeMacro(g_nativeClock,g_nativeClock+1,g_nativeClock+60));
 NativeCase("MACRO_FUTURE_SOURCE_REJECT",io&&g_macroStatus=="FUTURE"&&MacroBlocked(),g_macroStatus,"NATIVE-FILE-FIXED-CLOCK");
 io=NativeReadMacro(NativeMacro(g_nativeClock,g_nativeClock,g_nativeClock-1));
 NativeCase("MACRO_NEWS_EXPIRED_REJECT",io&&g_macroStatus=="NEWS_EXPIRED"&&MacroBlocked(),g_macroStatus,"NATIVE-FILE-FIXED-CLOCK");
 io=NativeReadMacro(NativeMacro(g_nativeClock,g_nativeClock,g_nativeClock));
 NativeCase("MACRO_NEWS_EXPIRY_INCLUSIVE",io&&g_macroStatus=="OK"&&!MacroBlocked(),g_macroStatus,"NATIVE-FILE-FIXED-CLOCK");
 g_nativeClock++;
 NativeCase("MACRO_EXPIRY_RECHECK",MacroBlocked(),"advanced_fixture_clock_without_reload","NATIVE-MOCKSTATE");g_nativeClock--;
 io=NativeReadMacro(NativeMacro(g_nativeClock,g_nativeClock,g_nativeClock+60,"0.1","1"));
 NativeCase("MACRO_NEWS_FLAG_BLOCK",io&&g_macroStatus=="OK"&&NewsBlocked(),g_macroStatus,"NATIVE-FILE-FIXED-CLOCK");
 io=NativeReadMacro(NativeMacro(g_nativeClock,g_nativeClock,g_nativeClock+60,"NaN"));
 NativeCase("MACRO_NONFINITE_TEXT_REJECT",io&&g_macroStatus!="OK"&&MacroBlocked(),g_macroStatus,"NATIVE-FILE-FIXED-CLOCK");
 io=NativeReadMacro(NativeMacro(g_nativeClock,g_nativeClock,g_nativeClock+60,"1e2"));
 NativeCase("MACRO_EXPONENT_FILE_REJECT",io&&g_macroStatus!="OK"&&MacroBlocked(),g_macroStatus,"NATIVE-FILE-FIXED-CLOCK");
 io=NativeReadMacro(NativeMacro(g_nativeClock,g_nativeClock,g_nativeClock+60)+"\n");
 NativeCase("MACRO_EXTRA_LINE_REJECT",io&&g_macroStatus!="OK"&&MacroBlocked(),g_macroStatus,"NATIVE-FILE-FIXED-CLOCK");
 io=NativeReadMacro("timestamp_utc,dxy_change_pct,us10y_change_bps,real_yield_change_bps,high_impact_news_block\n2026-01-02T12:00:00Z,0.1,2,-1,0\n");
 NativeCase("MACRO_OLD_SCHEMA_REJECT",io&&g_macroStatus!="OK"&&MacroBlocked(),g_macroStatus,"NATIVE-FILE-FIXED-CLOCK");

 NativeReset("roundtrip");bool seeded=NativeSeedJournal();g_journalHealthy=false;
 NativeCase("JOURNAL_FILE_ROUNDTRIP",seeded&&LoadExecutionJournal()&&g_journalHealthy&&!g_riskHalt,"fresh_synthetic_flat_scope","NATIVE-FILE-MOCKSTATE");
 NativeReset("truncated");seeded=NativeSeedJournal();io=NativeWrite(JournalPath(),"AG3|truncated");
 NativeCase("JOURNAL_TRUNCATION_REJECT",seeded&&io&&!LoadExecutionJournal()&&!g_journalHealthy,"real_truncated_sandbox_file","NATIVE-FILE-MOCKSTATE");
 NativeReset("checksum");seeded=NativeSeedJournal();string record;bool read=ReadOneRecord(JournalPath(),record);io=NativeWrite(JournalPath(),record+"0");
 NativeCase("JOURNAL_CHECKSUM_REJECT",seeded&&read&&io&&!LoadExecutionJournal()&&!g_journalHealthy,"real_checksum_mismatch_file","NATIVE-FILE-MOCKSTATE");
 NativeReset("orphan");seeded=NativeSeedJournal();io=NativeWrite(JournalPath()+".tmp","incomplete");
 NativeCase("JOURNAL_ORPHAN_TMP_REJECT",seeded&&io&&!LoadExecutionJournal()&&!g_journalHealthy,"real_orphan_tmp_file","NATIVE-FILE-MOCKSTATE");
 NativeReset("missing");io=PublishRecord(JournalPath()+".started","AG3_STARTED|"+g_stateKey);
 NativeCase("JOURNAL_MISSING_INITIALIZED_REJECT",io&&!LoadExecutionJournal()&&!g_journalHealthy,"started_marker_without_journal","NATIVE-FILE-MOCKSTATE");
 NativeReset("pending_open");g_intentKind="OPEN";g_intentDirection=1;g_intentVolume=0.01;g_intentEntry=2000;g_intentStop=1990;g_intentRisk=10;seeded=NativeSeedJournal();g_intentKind="NONE";
 NativeCase("JOURNAL_PENDING_OPEN_RESTART_REJECT",seeded&&!LoadExecutionJournal()&&g_riskHalt&&!g_journalHealthy&&g_intentKind=="OPEN"&&FileIsExist(g_statePath+".halt"),"reload_not_process_restart_no_broker_order","NATIVE-FILE-MOCKSTATE");
 NativeReset("pending_close");g_intentKind="CLOSE";g_intentDirection=-1;g_intentVolume=0.01;g_intentTicket=123;seeded=NativeSeedJournal();g_intentKind="NONE";
 NativeCase("JOURNAL_PENDING_CLOSE_RESTART_REJECT",seeded&&!LoadExecutionJournal()&&g_riskHalt&&!g_journalHealthy&&g_intentKind=="CLOSE"&&FileIsExist(g_statePath+".halt"),"reload_not_process_restart_no_broker_order","NATIVE-FILE-MOCKSTATE");
 NativeReset("duplicate");g_consumedBar=AGNativeBarTime(InpSymbol,InpEntryTF,1);seeded=NativeSeedJournal();g_consumedBar=0;bool loaded=LoadExecutionJournal();
 NativeCase("DUPLICATE_CONSUMED_BAR_REJECT",seeded&&loaded&&!PrepareIntent("OPEN",1,0.01,2000,1990,10,0)&&g_intentKind=="NONE","persisted_synthetic_bar_reloaded_no_send","NATIVE-FILE-MOCKSTATE");
 NativeReset("intent_prewrite");seeded=NativeSeedJournal();bool prepared=PrepareIntent("OPEN",1,0.01,2000,1990,10,0);read=ReadOneRecord(JournalPath(),record);
 NativeCase("INTENT_PREWRITE_REAL_FILE",seeded&&prepared&&read&&StringFind(record,"|OPEN|")>=0&&g_nativeSendAttempts==0,"prepare_only_no_send_side_effect","NATIVE-FILE-MOCKSTATE");
 NativeReset("locked_tmp");seeded=NativeSeedJournal();
 int locked=FileOpen(JournalPath()+".tmp",FILE_READ|FILE_WRITE|FILE_BIN);
 ResetLastError();bool published=PublishRecord(JournalPath(),"must_not_publish_while_tmp_is_exclusive");int lockError=GetLastError();
 if(locked!=INVALID_HANDLE)FileClose(locked);
 NativeCase("PUBLISH_EXCLUSIVE_TMP_IO_FAILURE",seeded&&locked!=INVALID_HANDLE&&!published&&lockError!=0,"native_exclusive_file_handle_error="+IntegerToString(lockError),"NATIVE-FILE-IO-FAULT");
 NativeCase("OPEN_PARTIAL_RETCODE_VETO",NativeRetcodeVeto("OPEN",TRADE_RETCODE_DONE_PARTIAL),"mock_retcode_only_pending_unchanged_caller_halt_not_executed","NATIVE-MOCKSTATE");
 NativeCase("CLOSE_PARTIAL_RETCODE_VETO",NativeRetcodeVeto("CLOSE",TRADE_RETCODE_DONE_PARTIAL),"mock_retcode_only_pending_unchanged_caller_halt_not_executed","NATIVE-MOCKSTATE");
 NativeCase("OPEN_TIMEOUT_RETCODE_VETO",NativeRetcodeVeto("OPEN",TRADE_RETCODE_TIMEOUT),"mock_retcode_only_not_broker_or_network_timeout","NATIVE-MOCKSTATE");
 NativeCase("CLOSE_TIMEOUT_RETCODE_VETO",NativeRetcodeVeto("CLOSE",TRADE_RETCODE_TIMEOUT),"mock_retcode_only_not_broker_or_network_timeout","NATIVE-MOCKSTATE");
 NativeCase("OPEN_UNKNOWN_RETCODE_VETO",NativeRetcodeVeto("OPEN",0),"mock_unknown_retcode_no_order_or_deal","NATIVE-MOCKSTATE");
 NativeCase("CLOSE_UNKNOWN_RETCODE_VETO",NativeRetcodeVeto("CLOSE",0),"mock_unknown_retcode_no_order_or_deal","NATIVE-MOCKSTATE");
 NativeCase("OPEN_DONE_ZERO_ORDER_CONTROL",NativeRetcodeVeto("OPEN",TRADE_RETCODE_DONE,true),"done_reaches_real_zero_order_getter_deal_not_read_pending_retained","NATIVE-MOCKSTATE");
 NativeReset("costs");double bound=-1;
 NativeCase("FUTURE_COST_UNKNOWN_VETO",!FutureCostsKnown(bound),"no_verified_approved_costs","NATIVE-GUARD");
 Signal base,out;base.direction=1;base.confidence=0.7;base.regime="TEST";base.setup="TEST";base.reason="synthetic";
 NativeCase("DISABLED_AI_VETO_BUY",!GetAISignal(base,out)&&out.direction==0&&out.confidence==0&&base.direction==1,"no_WebRequest_no_timeout_simulation","NATIVE-GUARD");
 base.direction=-1;
 NativeCase("DISABLED_AI_VETO_SELL",!GetAISignal(base,out)&&out.direction==0&&out.confidence==0&&base.direction==-1,"no_WebRequest_no_parser_claim","NATIVE-GUARD");
 base.direction=1;
 NativeCase("DISABLED_AI_ALIAS_VETO",!GetAISignal(base,base)&&base.direction==0&&base.confidence==0,"same_reference_veto","NATIVE-GUARD");
 base.direction=1;int before=g_nativeSendAttempts;ProcessEntry(base);
 NativeCase("PROCESS_ENTRY_LOCK_NO_SEND",g_nativeSendAttempts==before&&g_intentKind=="NONE","actual_locked_entry_function_last_resort_sender_sentinel","NATIVE-GUARD");
 NativeCase("NO_BROKER_SEND_ATTEMPTS",g_nativeSendAttempts==0,"sentinel_attempt_counter","NATIVE-GUARD");
 NativeCase("NO_OUTSIDE_PREFIX_FILE_OPENS",g_nativeDeniedFiles==0,"production_FileOpen_adapter_prefix_guard","NATIVE-GUARD");
 NativeSummary();
}
