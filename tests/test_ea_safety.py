"""Source regression checks; these are not a compiler or a runtime safety proof."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


def uncomment(text):
    # Keep string literals intact, so comment-like endpoint text cannot hide code.
    return re.sub(r'"(?:\\.|[^"\\])*"|//[^\n]*|/\*[\s\S]*?\*/',
                  lambda m: m.group(0) if m.group(0).startswith('"') else "", text)


def function_body(source, name):
    match = re.search(r'\b' + re.escape(name) + r'\s*\([^;{}]*\)\s*\{', source)
    if not match:
        raise AssertionError(f"Missing function {name}")
    depth = 1
    start = match.end()
    for index in range(start, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if not depth:
                return source[start:index]
    raise AssertionError(f"Unterminated function {name}")


class EASourceSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = uncomment((ROOT / "MQL5/Experts/AnticipatoryGold_AI_v1.mq5").read_text())

    def test_execution_guard_is_tester_only_with_no_input_override(self):
        guard = re.sub(r'\s+', '', function_body(self.source, "ResearchExecutionAllowed"))
        self.assertEqual(guard, 'return(bool)MQLInfoInteger(MQL_TESTER);')
        init = re.sub(r'\s+', '', function_body(self.source, "OnInit"))
        self.assertRegex(init, r'if\(!ResearchExecutionAllowed\(\)\)\{[^}]*returnINIT_FAILED;')
        for name in ("OnTick", "OpenPosition", "CloseAll"):
            body = re.sub(r'\s+', '', function_body(self.source, name))
            self.assertRegex(body, r'^if\(!ResearchExecutionAllowed\(\)(?:\|\|[^;{}]+)?\)return;', name)

    def test_new_orders_remain_locked_pending_execution_validation(self):
        self.assertEqual(re.sub(r'\s+', '', function_body(self.source, "EntryRiskPolicyApproved")), 'returnfalse;')
        for name in ("ProcessEntry", "OpenPosition"):
            self.assertIn('!EntryRiskPolicyApproved()', re.sub(r'\s+', '', function_body(self.source, name)))

    def test_volume_cannot_be_rounded_up_to_minimum(self):
        body = re.sub(r'\s+', '', function_body(self.source, "NormalizeLots"))
        self.assertIn('lots<minimum', body)
        self.assertIn('MathFloor(', body)
        self.assertIn('normalized>lots', body)
        self.assertNotRegex(body, r'MathMax\((?:minimum|min),')
        self.assertNotRegex(body, r'Math(?:Round|Ceil)\(')

    def test_invalid_position_commission_property_removed(self):
        self.assertNotRegex(self.source, r'\bPOSITION_COMMISSION\b')

    def test_no_online_requests_in_research_ea(self):
        self.assertNotRegex(self.source, r'\bWebRequest\s*\(')

    def test_stop_calculation_is_wired_to_closed_m5_atr_and_order_stop(self):
        init = re.sub(r'\s+', '', function_body(self.source, "OnInit"))
        self.assertIn('hStopATR=iATR(InpSymbol,PERIOD_M5,InpATRPeriod);', init)
        stop = re.sub(r'\s+', '', function_body(self.source, "BuildProtectiveStop"))
        self.assertIn('CopyVal(hStopATR,0,1,atr)', stop)
        self.assertIn('SYMBOL_TRADE_TICK_SIZE', stop)
        self.assertIn('MathFloor(', stop)
        self.assertIn('MathCeil(', stop)
        execution = re.sub(r'\s+', '', function_body(self.source, "OpenPosition"))
        self.assertIn('trade.Buy(lots,InpSymbol,entry,stop,0,comment)', execution)
        self.assertIn('trade.Sell(lots,InpSymbol,entry,stop,0,comment)', execution)

    def test_broker_stop_risk_and_basket_gate_precede_order(self):
        self.assertIn('OrderCalcProfit(', function_body(self.source, "ModeledStopLoss"))
        execution = function_body(self.source, "OpenPosition")
        order_offset = execution.index('trade.Buy(')
        for gate in ('BuildProtectiveStop(', 'RiskSizedLots(', 'BasketStopBudget('):
            self.assertLess(execution.index(gate), order_offset)
        budget = function_body(self.source, "BasketStopBudget")
        self.assertIn('POSITION_PRICE_OPEN', budget)
        self.assertIn('POSITION_SL', budget)
        self.assertIn('InpBasketStopMoney', budget)

    def test_old_day_limit_check_precedes_rollover_baseline_update(self):
        update = re.sub(r'\s+', '', function_body(self.source, "UpdateDay"))
        self.assertLess(update.index('CheckRiskLimits();'), update.index('g_dayEquity=eq;'))
        self.assertIn('!g_riskHalt', update)
        self.assertNotIn('g_riskHalt=false', update)

    def test_persistence_barriers_and_bootstrap_exposure_checks_are_wired(self):
        init = re.sub(r'\s+', '', function_body(self.source, "InitRiskState"))
        self.assertIn('PositionsTotal()>0||OrdersTotal()>0', init)
        self.assertIn('if(initialized){g_riskHalt=true;', init)
        self.assertIn('g_statePath+".tmp"', init)
        self.assertIn('g_statePath+".halt"', init)
        latch = function_body(self.source, "LatchRiskHalt")
        self.assertLess(latch.index('WriteHaltBarrier('), latch.index('SaveRiskState('))
        save = function_body(self.source, "SaveRiskState")
        self.assertLess(save.index('FileFlush('), save.index('FileMove('))

    def test_source_checker_preserves_urls_and_drops_comments(self):
        self.assertEqual(uncomment('"https://host" // note\n/* block */x'), '"https://host" \nx')


if __name__ == '__main__':
    unittest.main()
