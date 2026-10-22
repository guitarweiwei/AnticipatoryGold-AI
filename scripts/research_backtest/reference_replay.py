#!/usr/bin/env python3
"""Native-indicator / Python-quote-execution research REFERENCE, NOT MT5 tester.

No production EA, journal, broker-cost gate or live account is executed here.
Quotes remain private; exported performance artifacts contain no quote prices.
All strategy/risk/cost scenarios are frozen, not optimization CLI parameters.
"""
import argparse
from collections import Counter, deque
import csv
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import re
import time

UTC = timezone.utc
POINT = .001
CONTRACT = 100.0
INITIAL = 5000.0
LEVERAGE = 30.0
SCORE_START = 1704067200000  # 2024-01-01T00:00:00Z
SCORE_END = 1735689600000    # 2025-01-01T00:00:00Z, exclusive
ARCHIVE_START = '2023-11-01T00:00:00Z'
WARMUP = 500
MAX_SPREAD_POINTS = 80
M1_HEADER = ['time_utc','open','high','low','close','tick_volume','spread']
BAR_PREFIX = ['time_utc','bar_end_utc','open','high','low','close','tick_volume','spread']
M5_HEADER = BAR_PREFIX + ['atr14','band_upper','band_lower','valid','closed_by_source_end']
H1_HEADER = BAR_PREFIX + ['ema20','ema50','adx14','valid','closed_by_source_end']


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''): h.update(block)
    return h.hexdigest()


def write_json(path,value):
    Path(path).write_text(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n',encoding='utf-8')


def price_units(text):
    if not re.fullmatch(r'[0-9]+(?:\.[0-9]{1,3})?',text):
        raise ValueError('Quote must have finite nonnegative fixed decimal precision <=3')
    whole,_,fraction=text.partition('.')
    result=int(whole)*1000+int(fraction.ljust(3,'0') or '0')
    if result<=0: raise ValueError('Nonpositive quote')
    return result


def tick_rows(path):
    previous=0
    with Path(path).open(newline='',encoding='utf-8-sig') as stream:
        reader=csv.reader(stream)
        if next(reader,None)!=['time_utc_msc','bid','ask']: raise ValueError('Exact CSV3 quote header required')
        for row in reader:
            if len(row)!=3 or not row[0].isdigit(): raise ValueError('Malformed quote row')
            clock=int(row[0]);bid=price_units(row[1]);ask=price_units(row[2])
            if clock<=0 or clock<previous or ask<bid: raise ValueError('Invalid quote clock/order/sides')
            previous=clock
            yield clock,bid,ask


def prepare_m1(args):
    if args.output.exists() or args.metadata.exists(): raise ValueError('Use fresh output and metadata paths')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.metadata.parent.mkdir(parents=True,exist_ok=True)
    partial=args.output.with_suffix(args.output.suffix+'.part')
    if partial.exists(): raise ValueError('Prior partial exists; preserve it')
    current=None;minute=None;count=bars=0;first=last=None
    with partial.open('w',newline='',encoding='ascii') as stream:
        writer=csv.writer(stream,lineterminator='\n');writer.writerow(M1_HEADER)
        def emit(value):
            writer.writerow([value[0]]+[format(Decimal(v)/1000,'f') for v in value[1:5]]+value[5:])
        for clock,bid,ask in tick_rows(args.ticks):
            count+=1;first=clock if first is None else first;last=clock
            slot=clock//60000*60
            if slot!=minute:
                if current is not None: emit(current);bars+=1
                minute=slot;current=[slot,bid,bid,bid,bid,1,ask-bid]
            else:
                current[2]=max(current[2],bid);current[3]=min(current[3],bid)
                current[4]=bid;current[5]+=1;current[6]=ask-bid
        if current is not None: emit(current);bars+=1
    if not count: raise ValueError('No ticks; no M1 bars fabricated')
    partial.replace(args.output)
    metadata={'schema':'agai.native-indicator-input/1','status':'BID_M1_DERIVED_NOT_MT5_READBACK',
              'source_ticks_sha256':sha(args.ticks),'m1_sha256':sha(args.output),
              'tick_count':count,'m1_count':bars,'first_tick_utc_msc':first,'last_tick_utc_msc':last,
              'price_point':POINT,'spread_field':'last actual ask-bid in .001 points per minute',
              'missing_minutes_fabricated':False,'original_equal_ms_order_preserved':True,
              'indicator_implementation':'NONE - native MT5 export required',
              'warning':'Last M1 may be incomplete; native exporter must mark source-end closure correctly'}
    write_json(args.metadata,metadata)
    print(json.dumps(metadata,indent=2))
    return 0


@dataclass(frozen=True)
class NativeBar:
    time:int
    end:int
    open:float
    high:float
    low:float
    close:float
    values:dict
    valid:bool
    closed:bool


def read_native(path,timeframe):
    header=M5_HEADER if timeframe==300 else H1_HEADER
    rows=[];previous=-1
    with Path(path).open(newline='',encoding='utf-8-sig') as stream:
        reader=csv.DictReader(stream)
        if reader.fieldnames!=header: raise ValueError(f'Unexpected native {timeframe}s schema')
        for row in reader:
            opening=int(row['time_utc']);end=int(row['bar_end_utc'])
            if opening<=previous or opening%timeframe or end!=opening+timeframe:
                raise ValueError('Native rows must be strict ordered UTC timeframe boundaries')
            previous=opening
            if row['valid'] not in ('0','1') or row['closed_by_source_end'] not in ('0','1'):
                raise ValueError('Native validity fields must be 0/1')
            valid=row['valid']=='1';closed=row['closed_by_source_end']=='1'
            values={}
            for field in header[2:-2]:
                try: number=float(row[field])
                except ValueError: number=None
                if number is not None and not math.isfinite(number): number=None
                if valid and number is None: raise ValueError('Native valid row has nonfinite/missing value')
                values[field]=number
            prices=[values[name] for name in ('open','high','low','close')]
            if any(v is None or v<=0 for v in prices) or not values['low']<=min(values['open'],values['close'])<=max(values['open'],values['close'])<=values['high']:
                raise ValueError('Invalid native OHLC')
            if valid:
                fields=('atr14','band_upper','band_lower') if timeframe==300 else ('ema20','ema50','adx14')
                if any(values[f]<0 for f in fields) or any(values[f]<=0 for f in fields if f!='adx14'):
                    raise ValueError('Invalid ready native indicator domain')
                if timeframe==300 and values['band_upper']<values['band_lower']: raise ValueError('Native bands inverted')
            rows.append(NativeBar(opening,end,*prices,values,valid,closed))
    return rows


class AsOf:
    def __init__(self,rows): self.rows=rows;self.index=0
    def advance(self,clock):
        while self.index<len(self.rows) and self.rows[self.index].end*1000<=clock:
            self.index+=1
    def latest(self): return self.rows[self.index-1] if self.index else None


def build_signal(m5,h1):
    """Source BuildSignal formulas; supplied native indicators only."""
    if len(m5)<13 or h1 is None or not h1.valid or not h1.closed:
        return 0,'NATIVE_HISTORY_NOT_READY'
    selected=m5[-13:]
    if any(not bar.valid or not bar.closed for bar in selected): return 0,'NATIVE_HISTORY_NOT_READY'
    last,previous=selected[-1],selected[-2]
    v=last.values;trend=h1.values;atr=v['atr14']
    if atr<=0 or v['band_upper']<v['band_lower']: return 0,'NATIVE_INDICATOR_INVALID'
    squeeze=(v['band_upper']-v['band_lower'])/atr<.75
    adx=trend['adx14']
    if adx<18 and not squeeze: return 0,'ADX_VETO'
    highs=max(bar.high for bar in selected[:-1]);lows=min(bar.low for bar in selected[:-1])
    bearish=last.close<previous.close and last.close<last.open
    bullish=last.close>previous.close and last.close>last.open
    if trend['ema20']<trend['ema50'] and bearish and (last.close<=lows+.35*atr or squeeze): direction=-1
    elif trend['ema20']>trend['ema50'] and bullish and (last.close>=highs-.35*atr or squeeze): direction=1
    else: return 0,'NO_SETUP'
    confidence=.60+min(.18,max(0,adx-18)*.006)
    if confidence<.58: return 0,'SCORE_VETO'
    return direction,'SQUEEZE' if squeeze else 'TREND_CONTINUATION'


@dataclass(frozen=True)
class Scenario:
    name:str
    commission_per_lot_side:float
    swap_debit_per_lot_utc_day:float
    slippage_points:int
    fee_per_lot_side:float=0.0


SCENARIOS=(Scenario('BASE_FIXED',20.0,150.0,30),Scenario('STRESS_DOUBLE',40.0,300.0,60))


@dataclass
class Position:
    opened:int
    direction:int
    lots:float
    entry_units:int
    stop_units:int
    entry_cost:float
    approved_price_risk:float
    swap:float=0.0


class Engine:
    def __init__(self,scenario):
        self.scenario=scenario;self.balance=INITIAL;self.position=None;self.halted=False
        self.halt_reason=None;self.halt_time=None;self.day=None;self.day_equity=INITIAL
        self.last_clock=None;self.last_bid=self.last_ask=None;self.trades=[];self.veto=Counter()
        self.equity_high=self.balance_high=INITIAL;self.max_equity_dd=self.max_balance_dd=0.0
        self.max_equity_dd_pct=0.0;self.max_floating_loss=0.0;self.peak_margin=0.0
        self.fees=0.0;self.swaps=0.0;self.exposed_ms=0;self.first_clock=None
        self.samples=[];self.sample_min=self.sample_max=INITIAL;self.max_fixed_initial_loss=0.0
        self.last_closed_net=None;self.warmup_seen_at_start=None

    def gross(self,bid,ask):
        p=self.position
        return 0.0 if p is None else p.direction*((bid if p.direction>0 else ask)-p.entry_units)*POINT*CONTRACT*p.lots

    def equity(self,bid,ask):
        return self.balance+self.gross(bid,ask)+(self.position.swap if self.position else 0)

    def basket(self,bid,ask):
        p=self.position
        return 0.0 if p is None else self.gross(bid,ask)+p.swap-p.entry_cost

    def mark(self,clock,bid,ask):
        eq=self.equity(bid,ask)
        if not math.isfinite(eq): raise ValueError('Invalid modeled equity')
        self.equity_high=max(self.equity_high,eq);self.balance_high=max(self.balance_high,self.balance)
        dd=self.equity_high-eq
        self.max_equity_dd=max(self.max_equity_dd,dd)
        self.max_equity_dd_pct=max(self.max_equity_dd_pct,100*dd/self.equity_high)
        self.max_balance_dd=max(self.max_balance_dd,self.balance_high-self.balance)
        self.max_fixed_initial_loss=max(self.max_fixed_initial_loss,INITIAL-eq)
        self.sample_min=min(self.sample_min,eq);self.sample_max=max(self.sample_max,eq)
        if self.position:
            self.max_floating_loss=max(self.max_floating_loss,-self.basket(bid,ask))
            self.peak_margin=max(self.peak_margin,self.position.lots*CONTRACT*self.position.entry_units*POINT/LEVERAGE)

    def close(self,clock,bid,ask,reason):
        p=self.position
        if p is None: return
        self.max_floating_loss=max(self.max_floating_loss,-self.basket(bid,ask))
        executable=(bid if p.direction>0 else ask)-p.direction*self.scenario.slippage_points
        if executable<=0: raise ValueError('Slippage produced nonpositive execution price')
        gross=p.direction*(executable-p.entry_units)*POINT*CONTRACT*p.lots
        exit_cost=p.lots*(self.scenario.commission_per_lot_side+self.scenario.fee_per_lot_side)
        net=gross+p.swap-p.entry_cost-exit_cost
        self.balance+=gross+p.swap-exit_cost;self.fees+=exit_cost
        self.trades.append({'opened_utc_msc':p.opened,'closed_utc_msc':clock,'direction':'BUY' if p.direction>0 else 'SELL',
                            'lots':p.lots,'gross_pnl_usd':gross,'commission_and_fees_usd':p.entry_cost+exit_cost,
                            'swap_pnl_usd':p.swap,'net_pnl_usd':net,'holding_seconds':(clock-p.opened)/1000,
                            'exit_reason':reason,'approved_entry_price_sl_risk_usd':p.approved_price_risk})
        self.last_closed_net=net;self.position=None

    def risk(self,clock,bid,ask):
        equity=self.equity(bid,ask)
        basket=self.basket(bid,ask) if self.position else self.last_closed_net
        why=None
        if equity<=4750.0: why='FIXED_INITIAL_EQUITY_4750'
        elif self.day_equity-equity>=75.0: why='DAILY_LOSS_75'
        elif basket is not None and basket<=-35.0: why='BASKET_LOSS_35'
        if why and not self.halted:
            self.halted=True;self.halt_reason=why;self.halt_time=clock
        if self.halted and self.position: self.close(clock,bid,ask,'HALT_'+self.halt_reason)

    def daily_roll(self,clock,bid,ask):
        new_day=clock//86400000
        if self.day is None:
            self.day=new_day;self.day_equity=self.equity(bid,ask);return
        if new_day<self.day: raise ValueError('UTC day moved backward')
        if new_day==self.day: return
        for day in range(self.day+1,new_day+1):
            # Synthetic scenario charge at each UTC midnight crossed while held.
            if self.position:
                weekday=datetime.fromtimestamp(day*86400,UTC).weekday()
                factor=0 if weekday>=5 else (3 if weekday==2 else 1)
                charge=self.position.lots*self.scenario.swap_debit_per_lot_utc_day*factor
                self.position.swap-=charge;self.swaps-=charge
        # All elapsed fees are owed until the first available quote. Do not
        # retrospectively close on an earlier day using this later quote.
        self.risk(clock,bid,ask)
        if not self.halted: self.day_equity=self.equity(bid,ask)
        self.day=new_day

    def attempt_open(self,clock,bid,ask,direction,atr):
        if self.position: self.veto['ONE_LAYER_ALREADY_OPEN']+=1;return
        if self.halted: self.veto['STICKY_HALT']+=1;return
        intended=ask if direction>0 else bid
        raw=intended-direction*2.0*atr/POINT
        stop=math.floor(raw) if direction>0 else math.ceil(raw)
        if stop<=0 or (bid-stop if direction>0 else stop-ask)<0:
            self.veto['STOP_SIDE_OR_SPREAD']+=1;return
        price_loss_one_lot=abs(intended-stop)*POINT*CONTRACT
        equity=self.equity(bid,ask);risk_limit=equity*.0025
        ceiling=min(.01,risk_limit/price_loss_one_lot,.03,.05)
        # Frozen minimum/step .01 lot; never round a sub-minimum request upward.
        lots=math.floor((ceiling+1e-12)/.01)*.01
        if lots<.01 or lots>ceiling+1e-12: self.veto['LOT_MIN_OR_PRICE_RISK']+=1;return
        actual=intended+direction*self.scenario.slippage_points
        actual_risk=abs(actual-stop)*POINT*CONTRACT*lots
        if actual<=0 or actual_risk>risk_limit+1e-9:
            self.veto['POST_SLIPPAGE_PRICE_SL_RISK']+=1;return
        entry_cost=lots*(self.scenario.commission_per_lot_side+self.scenario.fee_per_lot_side)
        # Scenario round-trip known transaction costs only; future overnight/gap
        # costs are NOT a production prospective-cost bound.
        if actual_risk+2*entry_cost>35.0:
            self.veto['MODELED_STOP_PLUS_FIXED_COMMISSION_BUDGET']+=1;return
        margin=actual*POINT*CONTRACT*lots/LEVERAGE
        if margin>equity-entry_cost: self.veto['MARGIN']+=1;return
        self.balance-=entry_cost;self.fees+=entry_cost
        self.position=Position(clock,direction,lots,actual,stop,entry_cost,actual_risk)
        self.last_closed_net=None;self.veto['OPENED']+=1

    def tick(self,clock,bid,ask,new_bar,m5,h1,m5_count,h1_count):
        if self.first_clock is None:
            self.first_clock=clock;self.warmup_seen_at_start={'m5':m5_count,'h1':h1_count}
        if self.last_clock is not None and self.position: self.exposed_ms+=clock-self.last_clock
        self.daily_roll(clock,bid,ask)
        p=self.position
        # Server-like stop detection precedes OnTick decisions; gaps fill at the
        # actual first crossed closing-side quote, plus fixed adverse slippage.
        if p and (bid<=p.stop_units if p.direction>0 else ask>=p.stop_units): self.close(clock,bid,ask,'PRICE_SL')
        self.mark(clock,bid,ask);self.risk(clock,bid,ask)
        if self.position and not self.halted:
            value=self.basket(bid,ask)
            if value>=8.0: self.close(clock,bid,ask,'BASKET_TP_8')
            elif value<=-35.0: self.close(clock,bid,ask,'BASKET_STOP_35')
            elif clock-self.position.opened>180*60000 and value>0: self.close(clock,bid,ask,'PROFITABLE_ONLY_180MIN')
        self.risk(clock,bid,ask);self.last_closed_net=None
        if new_bar:
            if self.halted: self.veto['STICKY_HALT_BAR']+=1
            elif ask-bid>MAX_SPREAD_POINTS: self.veto['SPREAD_GT_80_POINTS']+=1
            elif m5_count<WARMUP or h1_count<WARMUP: self.veto['WARMUP_LT_500_CLOSED_BARS']+=1
            else:
                direction,why=build_signal(m5,h1)
                if direction: self.attempt_open(clock,bid,ask,direction,m5[-1].values['atr14'])
                else: self.veto[why]+=1
        self.risk(clock,bid,ask);self.mark(clock,bid,ask)
        if new_bar: self.sample(clock,bid,ask)
        self.last_clock=clock;self.last_bid=bid;self.last_ask=ask

    def sample(self,clock,bid,ask):
        self.samples.append({'time_utc_msc':clock,'balance_usd':self.balance,'equity_usd':self.equity(bid,ask),
                             'interval_min_equity_usd':self.sample_min,'interval_max_equity_usd':self.sample_max,
                             'exposure_lots':self.position.lots if self.position else 0.0,'halted':self.halted})
        self.sample_min=self.sample_max=self.equity(bid,ask)

    def summary(self):
        nets=[trade['net_pnl_usd'] for trade in self.trades];wins=[v for v in nets if v>0];losses=[v for v in nets if v<0]
        end_eq=self.equity(self.last_bid,self.last_ask) if self.last_clock is not None else INITIAL
        elapsed=(self.last_clock-self.first_clock) if self.last_clock is not None else 0
        return {'scenario':asdict(self.scenario),'trade_count':len(nets),'closed_basket_count':len(nets),
                'ending_balance_usd':self.balance,'ending_mark_to_market_equity_usd':end_eq,
                'net_mark_to_market_pnl_usd':end_eq-INITIAL,'closed_trade_net_pnl_usd':sum(nets),
                'expectancy_closed_trade_usd':sum(nets)/len(nets) if nets else None,
                'profit_factor_closed_trades':sum(wins)/abs(sum(losses)) if losses else None,
                'average_win_usd':sum(wins)/len(wins) if wins else None,'average_loss_usd':sum(losses)/len(losses) if losses else None,
                'worst_closed_basket_usd':min(nets) if nets else None,'max_equity_drawdown_highwater_usd_exact_ticks':self.max_equity_dd,
                'max_equity_drawdown_highwater_pct_exact_ticks':self.max_equity_dd_pct,'max_balance_drawdown_highwater_usd':self.max_balance_dd,
                'max_loss_below_fixed_initial_equity_usd':self.max_fixed_initial_loss,'max_floating_basket_loss_usd':self.max_floating_loss,
                'commissions_and_fees_charged_usd':self.fees,'swap_pnl_charged_usd':self.swaps,
                'peak_modeled_initial_margin_usd':self.peak_margin,'time_exposed_pct_of_observed_clock':100*self.exposed_ms/elapsed if elapsed else None,
                'sticky_halted':self.halted,'halt_reason':self.halt_reason,'halt_time_utc_msc':self.halt_time,
                'open_position_at_end':self.position is not None,'end_window_forced_liquidation':False,
                'warmup_counts_at_first_scored_tick':self.warmup_seen_at_start,'veto_and_action_counts':dict(self.veto)}


def export_csv(path,rows,fields):
    with Path(path).open('w',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields,lineterminator='\n');writer.writeheader();writer.writerows(rows)


TRADE_FIELDS=['opened_utc_msc','closed_utc_msc','direction','lots','gross_pnl_usd','commission_and_fees_usd','swap_pnl_usd',
              'net_pnl_usd','holding_seconds','exit_reason','approved_entry_price_sl_risk_usd']
EQUITY_FIELDS=['time_utc_msc','balance_usd','equity_usd','interval_min_equity_usd','interval_max_equity_usd','exposure_lots','halted']


def replay(args):
    args.output.mkdir(parents=True,exist_ok=False)
    started=time.monotonic()
    try:
        quality=json.loads(args.quality.read_text(encoding='utf-8'))
        tick_hash=sha(args.ticks)
        if quality.get('status')!='STRUCTURAL_CHECKS_PASSED' or quality.get('normalized_sha256')!=tick_hash:
            raise ValueError('Quote structural quality or normalized hash does not match')
        if quality.get('unclassified_failed_hours') or quality.get('expected_hours')!=10248:
            raise ValueError('Frozen archive interval requires 10248 enumerated nonfailed hours')
        bars5=read_native(args.m5,300);bars1=read_native(args.h1,3600)
        m5=AsOf(bars5);h1=AsOf(bars1);engines=[Engine(scenario) for scenario in SCENARIOS]
        previous_bucket=None;total=scored=0;first=last=None
        for clock,bid,ask in tick_rows(args.ticks):
            total+=1;first=clock if first is None else first;last=clock
            if clock>=SCORE_END: break
            m5.advance(clock);h1.advance(clock)
            bucket=clock//300000
            new_bar=bucket!=previous_bucket;previous_bucket=bucket
            if clock<SCORE_START: continue
            scored+=1
            selected=bars5[max(0,m5.index-13):m5.index]
            for engine in engines:
                engine.tick(clock,bid,ask,new_bar,selected,h1.latest(),m5.index,h1.index)
            if total%1000000==0:
                print(json.dumps({'reference_ticks_processed':total,'scored_ticks':scored,'elapsed_seconds':round(time.monotonic()-started,3)}),flush=True)
        if not scored: raise ValueError('No actual quotes in frozen 2024 performance interval')
        for engine in engines:
            engine.sample(engine.last_clock,engine.last_bid,engine.last_ask)
            folder=args.output/engine.scenario.name;folder.mkdir()
            export_csv(folder/'trades.csv',engine.trades,TRADE_FIELDS)
            export_csv(folder/'equity.csv',engine.samples,EQUITY_FIELDS)
        warmup_ok=all(engine.warmup_seen_at_start and min(engine.warmup_seen_at_start.values())>=WARMUP for engine in engines)
        report={'schema':'agai.native-indicator-python-execution-reference/1',
                'status':'REFERENCE_REPLAY_COMPLETED' if warmup_ok else 'BLOCKED_INSUFFICIENT_WARMUP_AT_START',
                'result_type':'NATIVE_INDICATORS_PLUS_PYTHON_QUOTE_EXECUTION_REFERENCE_PROXY_NOT_MT5_STRATEGY_TESTER',
                'mt5_strategy_tester_run':False,'production_ea_or_ledger_executed':False,'production_cost_gate_verified':False,
                'costs_are_frozen_hypothetical_scenarios_not_broker_history':True,
                'fixed_configuration':{'initial_usd':INITIAL,'leverage':LEVERAGE,'contract_oz_per_lot':CONTRACT,'point':POINT,
                                       'max_spread_points':MAX_SPREAD_POINTS,'max_layers':1,'base_lots_cap':.01,'minimum_lot_step':.01,
                                       'initial_price_sl_risk_pct':.25,'stop_closed_m5_atr_multiple':2,'basket_tp_usd':8,'basket_stop_usd':35,
                                       'daily_loss_usd':75,'fixed_initial_halt_equity_usd':4750,'online_ai':False,'macro':False,
                                       'minimum_closed_warmup_each_timeframe':WARMUP},
                'frozen_interval':{'warmup_from_utc':ARCHIVE_START,'performance_from_utc':'2024-01-01T00:00:00Z','performance_to_utc_exclusive':'2025-01-01T00:00:00Z'},
                'input_hashes':{'ticks':tick_hash,'native_m5':sha(args.m5),'native_h1':sha(args.h1),'quote_quality':sha(args.quality),'engine':sha(Path(__file__))},
                'archive_tick_count_read':total,'scored_tick_count':scored,'first_input_tick_utc_msc':first,'last_input_tick_utc_msc':last,
                'elapsed_seconds':round(time.monotonic()-started,3),'scenarios':[engine.summary() for engine in engines],
                'limitations':['This is not an MT5 Strategy Tester report or production EA/journal/fill verification',
                               'Native indicator tables must be bound to the same M1/tick data by the Windows runner metadata',
                               'Source authenticity, licensing and independent scale/timebase checks remain separate reviews',
                               'Frozen cost scenarios are not authenticated Dukascopy historical commissions/swaps/slippage',
                               'Midnight UTC swap debit is synthetic: Wednesday 3x, Saturday/Sunday 0, others 1x for either direction',
                               'No broker order rejection, fill latency, partial execution, account persistence or storage faults are simulated',
                               'Immediate adverse entry/exit slippage uses recorded quote plus fixed points; gaps can exceed risk limits',
                               'Entry price-to-SL risk cap excludes future holding costs; no verified finite future-swap bound exists',
                               'Stops/freeze levels and margin are fixed research assumptions, not effective-dated broker conditions',
                               'No forced liquidation at window end: open losses stay in mark-to-market equity and are explicitly reported',
                               'No profitability or guaranteed realized-loss limit follows from these scenario results']}
        write_json(args.output/'summary.json',report)
        print(json.dumps(report,indent=2))
        return 0 if warmup_ok else 2
    except Exception as exc:
        write_json(args.output/'failure.json',{'status':'REFERENCE_REPLAY_FAILED','error_type':type(exc).__name__,
                                            'reason':str(exc),'mt5_strategy_tester_run':False,'performance_metrics_valid':False})
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    prepare=sub.add_parser('prepare-m1');prepare.add_argument('--ticks',type=Path,required=True)
    prepare.add_argument('--output',type=Path,required=True);prepare.add_argument('--metadata',type=Path,required=True)
    run=sub.add_parser('replay');run.add_argument('--ticks',type=Path,required=True)
    run.add_argument('--m5',type=Path,required=True);run.add_argument('--h1',type=Path,required=True)
    run.add_argument('--quality',type=Path,required=True);run.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    return prepare_m1(args) if args.command=='prepare-m1' else replay(args)


if __name__=='__main__': raise SystemExit(main())
