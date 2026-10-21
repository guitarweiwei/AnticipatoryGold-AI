"""Selected source safety invariants; NOT a compiler or MQL5 execution proof."""
from pathlib import Path
import re
import unittest

from test_ea_safety import function_body as scan_body, uncomment

ROOT = Path(__file__).resolve().parents[1]


def function_body(source, name):
    # Anchor on a function definition, never an if-body after a same-named call.
    match = re.search(r'^(?:bool|double|void|int|string|Signal)\s+' + re.escape(name)
                      + r'\s*\(', source, flags=re.MULTILINE)
    if not match:
        raise AssertionError(f'Missing definition: {name}')
    return scan_body(source[match.start():], name)


class Stage3SourceChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ea = uncomment((ROOT / 'MQL5/Experts/AnticipatoryGold_AI_v1.mq5').read_text())
        cls.lifecycle = uncomment((ROOT / 'MQL5/Experts/Include/ResearchLifecycle.mqh').read_text())

    def test_order_and_close_intents_precede_every_send(self):
        opening = function_body(self.ea, 'OpenPosition')
        self.assertLess(opening.index('PrepareIntent("OPEN"'), opening.index('trade.Buy('))
        self.assertLess(opening.index('PrepareIntent("OPEN"'), opening.index('trade.Sell('))
        closing = function_body(self.ea, 'CloseAll')
        self.assertLess(closing.index('PrepareIntent("CLOSE"'), closing.index('trade.PositionClose('))
        prepare = function_body(self.lifecycle, 'PrepareIntent')
        self.assertIn('SaveExecutionJournal()', prepare)
        self.assertIn('g_consumedBar=bar', prepare)
        self.assertIn('bar<=g_consumedBar', prepare)
        self.assertLess(prepare.index('BasketLedger('), prepare.index('g_intentKind=kind'))

    def test_pending_restart_and_missing_old_scope_never_bootstrap(self):
        load = function_body(self.lifecycle, 'LoadExecutionJournal')
        self.assertIn('!g_scopeFresh', load)
        self.assertIn('PositionsTotal()>0||OrdersTotal()>0', re.sub(r'\s+', '', load))
        self.assertIn('g_intentKind!="NONE"||ScopedPendingOrders()', re.sub(r'\s+', '', load))
        self.assertIn('LatchRiskHalt(', load)
        self.assertNotRegex(load, r'trade\.(?:Buy|Sell|PositionClose)\(')

    def test_verified_fills_require_done_and_actual_protection(self):
        opened = function_body(self.lifecycle, 'VerifyOpenFill')
        closed = function_body(self.lifecycle, 'VerifyCloseFill')
        for body in (opened, closed):
            self.assertIn('trade.ResultRetcode()!=TRADE_RETCODE_DONE', body)
            self.assertIn('VerifiedOrder(', body)
            self.assertNotIn('TRADE_RETCODE_DONE_PARTIAL', body)
        self.assertIn('stop!=g_intentStop', opened)
        self.assertIn('actualRisk>g_intentRisk', opened)
        self.assertIn('ORDER_POSITION_ID', function_body(self.lifecycle, 'VerifiedOrder'))

    def test_ledger_retains_realized_cash_and_conservative_debits(self):
        ledger = re.sub(r'\s+', '', function_body(self.lifecycle, 'BasketLedger'))
        for field in ('DEAL_PROFIT', 'DEAL_COMMISSION', 'DEAL_FEE', 'DEAL_SWAP',
                      'POSITION_PROFIT', 'POSITION_SWAP'):
            self.assertIn(field, ledger)
        self.assertIn('recordedLosses+=MathMax(0,-profit)+MathMax(0,-commission)+MathMax(0,-fee)+MathMax(0,-swap)', ledger)
        self.assertIn('entered!=expectedUnits', ledger)
        self.assertIn('entered-exited!=liveUnits', ledger)
        budget = function_body(self.ea, 'BasketStopBudget')
        self.assertIn('total+=recordedLosses', budget)
        self.assertNotIn('MathMax(0,-realized)', budget)
        self.assertNotRegex(self.ea + self.lifecycle, r'\bPositionGet(?:Integer|Double|String)\(\s*\w+\s*\)')
        self.assertIn('SelectedPositionIdentity(', ledger)

    def test_archive_is_verified_before_active_basket_is_retired(self):
        finalize = function_body(self.lifecycle, 'FinalizeFlatBasket')
        self.assertLess(finalize.index('PublishRecord(path,record)'), finalize.index('ArrayResize(g_basketIds,0)'))
        self.assertIn('existing!=record', finalize)
        self.assertIn('SaveExecutionJournal()', finalize)
        self.assertNotIn('g_consumedBar=0', finalize)
        tick = function_body(self.ea, 'OnTick')
        self.assertLess(tick.index('CheckRiskLimits();', tick.index('ManageBaskets();')),
                        tick.index('FinalizeFlatBasket('))
        self.assertIn('g_journalHealthy=false', function_body(self.ea, 'BasketProfit'))

    def test_unknown_future_costs_and_new_entries_stay_disabled(self):
        self.assertEqual(re.sub(r'\s+', '', function_body(self.ea, 'EntryRiskPolicyApproved')), 'returnfalse;')
        costs = function_body(self.lifecycle, 'FutureCostsKnown')
        self.assertIn('ZeroMemory(costs)', costs)
        self.assertIn('!costs.authorized||!costs.verified||!costs.known', costs)
        budget = function_body(self.ea, 'BasketStopBudget').strip()
        self.assertIn('!FutureCostsKnown(future)', budget)
        self.assertTrue(budget.endswith('return false;'))

    def test_closed_rates_and_finite_indicator_guards_are_used(self):
        rates = re.sub(r'\s+', '', function_body(self.lifecycle, 'ClosedRates'))
        self.assertIn('CopyRates(InpSymbol,timeframe,1,count,rates)', rates)
        self.assertIn('SERIES_SYNCHRONIZED', rates)
        self.assertIn('rates[i].time>=current', rates)
        self.assertIn('rates[i].low>MathMin(rates[i].open,rates[i].close)', rates)
        self.assertIn('value!=EMPTY_VALUE', function_body(self.lifecycle, 'ValidValue'))
        self.assertIn('!ValidValue(values[0])', function_body(self.ea, 'CopyVal'))
        signal = function_body(self.ea, 'BuildSignal')
        self.assertIn('ClosedRates(InpEntryTF,InpLevelLookback+1,entryBars)', signal)
        self.assertIn('entryBars[1].close', signal)
        self.assertNotRegex(signal, r'\bi(?:Open|High|Low|Close)\(')

    def test_macro_consumer_checks_original_source_age_and_news_expiry(self):
        macro = function_body(self.ea, 'ReadMacroCSV')
        self.assertIn('StringSplit(row,\',\',fields)!=12', macro)
        self.assertIn('fields[0]!="2"', macro)
        self.assertIn('now-oldest>15*60', macro)
        self.assertIn('newsUntil<now', macro)
        self.assertIn('dxyTime>snapshot', macro)
        self.assertIn('g_macroOldest', function_body(self.ea, 'MacroBlocked'))


if __name__ == '__main__':
    unittest.main()
