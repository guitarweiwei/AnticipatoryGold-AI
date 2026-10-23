#!/usr/bin/env python3
"""Plot only completed, genuinely produced reference-replay artifacts."""
import argparse,csv,json,hashlib,calendar,math
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates


def finite(value):
 number=float(value)
 if not math.isfinite(number):raise ValueError('Nonfinite artifact value')
 return number


def reconcile(actual,expected,label):
 if not math.isclose(finite(actual),finite(expected),rel_tol=1e-10,abs_tol=1e-6):
  raise ValueError(label+' do not reconcile')


def verify_source(report):
 review=report.get('source_data_review')
 if (report.get('source_provider')!='HISTDATA.COM'
     or report.get('reference_scope')!='CONDITIONAL_OBSERVED_TICKS_RESEARCH'
     or report.get('full_2024_coverage_verified') is not False or not isinstance(review,dict)):
  raise ValueError('This study requires explicitly conditional HISTDATA.COM source metadata')
 rule=review.get('timebase_rule')
 if (review.get('timebase_status')!='EMPIRICALLY_CALIBRATED_RESEARCH_TIMEBASE_NOT_FULLY_CERTIFIED'
     or review.get('coverage_status')!='UNVERIFIED_SOURCE_GAPS'
     or type(review.get('unobserved_hour_count')) is not int or review['unobserved_hour_count']!=3358
     or review.get('source_gap_review_status')!='NOT_VALIDATED_NO_AUTHENTICATED_SESSION_CALENDAR'
     or not isinstance(rule,dict) or rule.get('source_local_dates_plus4_inclusive')!=['20240331','20241026']
     or rule.get('other_2023_2024_source_local_dates_plus5') is not True):
  raise ValueError('Missing or inconsistent empirical +4/+5 clock and unknown source-gap limitations')
 notes=report.get('limitations',[])
 if not isinstance(notes,list) or not any(isinstance(n,str) and all(term in n.lower() for term in ['histdata','clock','gap','not certified','conditional']) for n in notes):
  raise ValueError('Explicit HistData clock/coverage uncertified conditional source note is required')


def verify_trades(folder,name,item,last_exposure):
 with (folder/name/'trades.csv').open(newline='',encoding='utf-8-sig') as f:
  reader=csv.DictReader(f)
  if not reader.fieldnames or not {'opened_utc_msc','closed_utc_msc','net_pnl_usd'}.issubset(reader.fieldnames):
   raise ValueError('Missing actual closed-trade columns')
  fields=set(reader.fieldnames);trades=list(reader)
 for key in ['trade_count','closed_basket_count']:
  if type(item.get(key)) is not int or item[key]!=len(trades):raise ValueError('Closed-trade count and summary disagree')
 previous_close=None
 numeric=['lots','gross_pnl_usd','commission_and_fees_usd','swap_pnl_usd','net_pnl_usd','holding_seconds','approved_entry_price_sl_risk_usd']
 for trade in trades:
  opened=int(trade['opened_utc_msc']);closed=int(trade['closed_utc_msc'])
  if opened<=0 or closed<opened or (previous_close is not None and opened<previous_close):
   raise ValueError('Closed trades have invalid order or overlapping single-layer positions')
  previous_close=closed
  for key in numeric:
   if key in fields:finite(trade[key])
  if 'lots' in fields and finite(trade['lots'])<=0:raise ValueError('Invalid trade lot size')
  if 'commission_and_fees_usd' in fields and finite(trade['commission_and_fees_usd'])<0:raise ValueError('Negative debit cost')
  if {'gross_pnl_usd','swap_pnl_usd','commission_and_fees_usd'}.issubset(fields):
   reconcile(finite(trade['gross_pnl_usd'])+finite(trade['swap_pnl_usd'])-finite(trade['commission_and_fees_usd']),trade['net_pnl_usd'],'Trade net and gross/cost components')
  if 'holding_seconds' in fields:reconcile((closed-opened)/1000,trade['holding_seconds'],'Trade holding duration')
 reconcile(math.fsum(finite(t['net_pnl_usd']) for t in trades),item['closed_trade_net_pnl_usd'],'Closed-trade net sum and summary')
 if type(item.get('open_position_at_end')) is not bool:raise ValueError('Explicit end exposure status required')
 open_end=item['open_position_at_end']
 if (last_exposure>0)!=open_end or last_exposure<0:raise ValueError('End exposure and summary disagree')
 if 'commission_and_fees_usd' in fields and 'commissions_and_fees_charged_usd' in item:
  remaining_entry_cost=0.
  if open_end:
   scenario=item['scenario']
   remaining_entry_cost=last_exposure*(finite(scenario['commission_per_lot_side'])+finite(scenario['fee_per_lot_side']))
  reconcile(math.fsum(finite(t['commission_and_fees_usd']) for t in trades)+remaining_entry_cost,item['commissions_and_fees_charged_usd'],'Closed plus open-entry costs and summary')
 if 'swap_pnl_usd' in fields and 'swap_pnl_charged_usd' in item:
  closed_swap=math.fsum(finite(t['swap_pnl_usd']) for t in trades)
  total_swap=finite(item['swap_pnl_charged_usd'])
  if open_end:
   # Accrued swap on an unclosed position is not a closed-trade CSV row.
   if total_swap>closed_swap+1e-6:raise ValueError('Total swap excludes closed debits or implies unsupported swap credit')
  else:reconcile(closed_swap,total_swap,'Closed swap costs and summary')


def load(folder):
 report=json.loads((folder/'summary.json').read_text())
 if report.get('status')!='REFERENCE_REPLAY_COMPLETED' or report.get('mt5_strategy_tester_run') is not False:
  raise ValueError('A completed, explicitly reference-only result is required')
 verify_source(report)
 series=[]
 for item in report['scenarios']:
  name=item['scenario']['name']
  with (folder/name/'equity.csv').open(newline='') as f:rows=list(csv.DictReader(f))
  if not rows:raise ValueError('Missing actual equity observations')
  times=np.array([int(x['time_utc_msc']) for x in rows],dtype=np.int64)
  if np.any(np.diff(times)<0):raise ValueError('Equity observations out of order')
  equity=np.array([float(x['equity_usd']) for x in rows]);balance=np.array([float(x['balance_usd']) for x in rows])
  if not np.isfinite(equity).all() or not np.isfinite(balance).all():raise ValueError('Nonfinite equity or balance observations')
  reconcile(equity[-1],item['ending_mark_to_market_equity_usd'],'Equity and summary')
  reconcile(balance[-1],item['ending_balance_usd'],'Balance and summary')
  verify_trades(folder,name,item,finite(rows[-1]['exposure_lots']))
  series.append((name,item,times,equity,balance))
 return report,series


def main():
 p=argparse.ArgumentParser();p.add_argument('--results',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 report,series=load(a.results);a.output.mkdir(parents=True,exist_ok=False)
 plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'axes.grid':True,'grid.alpha':.18,'figure.facecolor':'#f7f9fc','axes.facecolor':'white'})
 fig=plt.figure(figsize=(15,10),layout='constrained');gs=fig.add_gridspec(3,2,height_ratios=[1.25,1,.9])
 ax=fig.add_subplot(gs[0,:]);ddax=fig.add_subplot(gs[1,0]);monthlyax=fig.add_subplot(gs[1,1]);statsax=fig.add_subplot(gs[2,:]);statsax.axis('off')
 colors=['#096b9f','#df7830'];monthly=[];rows=[]
 for k,(name,item,times,eq,bal) in enumerate(series):
  dates=[datetime.fromtimestamp(int(t)/1000,timezone.utc) for t in times]
  ax.plot(dates,eq,lw=1.3,label=name.replace('_',' '),color=colors[k]);ax.plot(dates,bal,lw=.6,ls='--',alpha=.45,color=colors[k])
  high=np.maximum.accumulate(np.r_[5000.,eq])[1:];draw=(eq/high-1)*100
  ddax.plot(dates,draw,color=colors[k],label=name.replace('_',' '));ddax.fill_between(dates,draw,0,color=colors[k],alpha=.12)
  mr=[];previous=5000.
  for month in range(1,13):
   indexes=[i for i,d in enumerate(dates) if d.year==2024 and d.month==month]
   if not indexes:mr.append(float('nan'));continue
   end=eq[indexes[-1]];mr.append((end/previous-1)*100);previous=end
  monthly.append(mr)
  pf=item['profit_factor_closed_trades'];rows.append([name.replace('_',' '),f"${item['net_mark_to_market_pnl_usd']:,.2f}",f"{100*(item['ending_mark_to_market_equity_usd']/5000-1):.2f}%",str(item['trade_count']),f"{item['max_equity_drawdown_highwater_pct_exact_ticks']:.3f}%",'undefined' if pf is None else f'{pf:.2f}',str(item['open_position_at_end'])])
 
 if all(item['trade_count']==0 for _,item,*_ in series):
  ax.text(.5,.5,'No completed trades — no evidence of entry profitability',transform=ax.transAxes,ha='center',color='#6e4a32',bbox={'facecolor':'white','alpha':.9,'edgecolor':'#ddd'})
 ax.axhline(5000,color='#627588',lw=.8,ls=':');ax.set_title('Account equity and balance • starting capital USD 5,000 • leverage 1:30',loc='left',fontweight='bold');ax.set_ylabel('USD');ax.legend(loc='best',ncol=2);ax.xaxis.set_major_formatter(mdates.DateFormatter('%b'));ax.xaxis.set_major_locator(mdates.MonthLocator())
 ddax.set_title('Drawdown from prior equity high',loc='left',fontweight='bold');ddax.set_ylabel('% (5-minute chart samples)');ddax.xaxis.set_major_formatter(mdates.DateFormatter('%b'));ddax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
 values=np.array(monthly);finite=values[np.isfinite(values)];lim=max(.01,float(np.max(np.abs(finite)))) if finite.size else 1
 im=monthlyax.imshow(np.ma.masked_invalid(values),cmap='RdYlGn',vmin=-lim,vmax=lim,aspect='auto');monthlyax.grid(False);monthlyax.set_title('Monthly mark-to-market equity returns (%)',loc='left',fontweight='bold');monthlyax.set_xticks(range(12),[calendar.month_abbr[x] for x in range(1,13)],rotation=45);monthlyax.set_yticks(range(len(series)),['Base','Stress'])
 for i in range(values.shape[0]):
  for j in range(12):monthlyax.text(j,i,'NA' if not np.isfinite(values[i,j]) else f'{values[i,j]:.2f}',ha='center',va='center',fontsize=8)
 table=statsax.table(cellText=rows,colLabels=['Fixed cost scenario','MTM P/L','Return','Closed trades','Max equity DD¹','Profit factor','Open at end'],loc='upper center',cellLoc='center');table.auto_set_font_size(False);table.set_fontsize(10);table.scale(1,1.8)
 for (i,j),cell in table.get_celld().items():
  cell.set_edgecolor('#dce3ec')
  if i==0:cell.set_facecolor('#18364e');cell.set_text_props(color='white',weight='bold')
 note=('¹ Maximum drawdown statistics use every processed tick; the plotted path is sampled at M5 boundaries.\n'
       'Native MT5 indicators + Python quote execution reference. NOT an MT5 Strategy Tester performance report.\n'
       'Actual bid/ask spread retained; commission, rollover and slippage are fixed research assumptions, not historical broker charges.\n'
       'Production order journal, intent-risk checks and prospective-cost gate are not validated. No final forced liquidation; residual positions use MTM.\n'
       'Source: HISTDATA.COM. Conditional observed-ticks research; 3,358 unobserved hours remain UNKNOWN source gaps.\n'
       'Research UTC: source dates Mar31–Oct26 +4h, otherwise +5h. Clock and full-window coverage are NOT certified.')
 statsax.text(0,.18,note,ha='left',va='top',fontsize=9,color='#425466',transform=statsax.transAxes)
 fig.suptitle('AnticipatoryGold AI v1 • conditional 2024 reference study',fontsize=20,fontweight='bold',color='#18364e')
 out=a.output/'AnticipatoryGold_2024_Reference_Charts.png';fig.savefig(out,dpi=180);fig.savefig(a.output/'AnticipatoryGold_2024_Reference_Charts.pdf');plt.close(fig)
 with (a.output/'monthly_returns.csv').open('w',newline='') as f:
  w=csv.writer(f);w.writerow(['scenario']+[f'2024-{m:02}' for m in range(1,13)])
  for (name,*_),values in zip(series,monthly):w.writerow([name]+[None if not np.isfinite(v) else v for v in values])
 (a.output/'source_summary_sha256.txt').write_text(hashlib.sha256((a.results/'summary.json').read_bytes()).hexdigest()+'\n')
 print(out)
if __name__=='__main__':main()
