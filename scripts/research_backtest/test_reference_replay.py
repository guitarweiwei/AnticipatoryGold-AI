import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace
import reference_replay as r

class ReferenceChecks(unittest.TestCase):
 def bar(self,t,tf=300):
  return r.NativeBar(t,t+tf,2000.,2001.,1999.,2000.,{},True,True)
 def test_asof_never_exposes_unclosed_native_bar(self):
  a=r.AsOf([self.bar(300),self.bar(600)]);a.advance(599999);self.assertIsNone(a.latest());a.advance(600000);self.assertEqual(a.latest().time,300)
 def test_bid_m1_preserves_tied_last_quote_and_missing_minute(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);p=d/'ticks.csv';p.write_text('time_utc_msc,bid,ask\n60000,2000.100,2000.130\n60000,2000.090,2000.140\n180000,2001.000,2001.020\n')
   r.prepare_m1(SimpleNamespace(ticks=p,output=d/'m1.csv',metadata=d/'meta.json'))
   rows=(d/'m1.csv').read_text().splitlines();self.assertEqual(len(rows),3);self.assertEqual(rows[1],'60,2000.1,2000.1,2000.09,2000.09,2,50');self.assertTrue(rows[2].startswith('180,'))
 def test_spread_gate_uses_original_eighty_points(self):
  e=r.Engine(r.SCENARIOS[0]);e.tick(r.SCORE_START,2000000,2000081,True,[],None,500,500);self.assertEqual(e.veto['SPREAD_GT_80_POINTS'],1);self.assertIsNone(e.position)
 def test_subminimum_risk_is_refused(self):
  e=r.Engine(r.SCENARIOS[0]);e.attempt_open(r.SCORE_START,2000000,2000020,1,10);self.assertIsNone(e.position);self.assertEqual(e.veto['LOT_MIN_OR_PRICE_RISK'],1)
 def test_actual_slippage_risk_is_rechecked(self):
  e=r.Engine(r.SCENARIOS[0]);e.attempt_open(r.SCORE_START,2000000,2000020,1,6.25);self.assertIsNone(e.position);self.assertEqual(e.veto['POST_SLIPPAGE_PRICE_SL_RISK'],1)
 def test_open_close_costs_and_bidask_are_charged_once(self):
  e=r.Engine(r.SCENARIOS[0]);e.attempt_open(r.SCORE_START,2000000,2000020,1,1);self.assertIsNotNone(e.position);self.assertAlmostEqual(e.balance,4999.8)
  e.close(r.SCORE_START+1,2001000,2001020,'TEST');self.assertAlmostEqual(e.trades[0]['gross_pnl_usd'],.92);self.assertAlmostEqual(e.trades[0]['net_pnl_usd'],.52);self.assertAlmostEqual(e.balance,5000.52)
 def test_gap_stop_uses_first_actual_quote_not_stop_price(self):
  e=r.Engine(r.SCENARIOS[0]);e.attempt_open(r.SCORE_START,2000000,2000020,1,1);e.day=r.SCORE_START//86400000
  e.tick(r.SCORE_START+1,1990000,1990020,False,[],None,500,500);self.assertIsNone(e.position);self.assertLess(e.trades[0]['gross_pnl_usd'],-10);self.assertEqual(e.trades[0]['exit_reason'],'PRICE_SL')
 def test_daily_halt_is_sticky_after_next_day(self):
  e=r.Engine(r.SCENARIOS[0]);e.day=100;e.day_equity=5000;e.balance=4924;e.daily_roll(101*86400000,2000000,2000020);self.assertTrue(e.halted);e.balance=5100;e.daily_roll(102*86400000,2000000,2000020);self.assertTrue(e.halted)
 def test_crossed_rollovers_all_charged_before_gap_close(self):
  e=r.Engine(r.SCENARIOS[0]);start=1704067200000;e.attempt_open(start,2000000,2000020,1,1);e.day=start//86400000
  e.daily_roll(start+3*86400000,2000000,2000020)
  # Tue1 + Wed3 + Thu1; no retrospective close at an earlier midnight.
  self.assertAlmostEqual(e.position.swap,-7.5)
 def test_zero_trade_undefined_metrics_remain_null(self):
  s=r.Engine(r.SCENARIOS[0]).summary();self.assertEqual(s['trade_count'],0);self.assertIsNone(s['profit_factor_closed_trades']);self.assertIsNone(s['expectancy_closed_trade_usd']);self.assertEqual(s['net_mark_to_market_pnl_usd'],0)
 def test_window_end_does_not_hide_open_position_loss(self):
  e=r.Engine(r.SCENARIOS[0]);e.attempt_open(r.SCORE_START,2000000,2000020,1,1);e.last_clock=r.SCORE_START;e.first_clock=r.SCORE_START;e.last_bid=1999500;e.last_ask=1999520
  s=e.summary();self.assertTrue(s['open_position_at_end']);self.assertFalse(s['end_window_forced_liquidation']);self.assertLess(s['net_mark_to_market_pnl_usd'],0)
if __name__=='__main__':unittest.main()
