"""Approved policy fixtures only. No MQL5/MT5 execution or performance evidence."""
from datetime import datetime, timezone, timedelta
from decimal import Decimal as D
import unittest

from risk_reference import (Reject, RiskState, MemoryStore, stop_price, floor_volume,
                            initial_volume, basket_budget, evaluate_state, recover, utc_day, fixture_stop_loss)

NOW = datetime(2026, 10, 21, 12, tzinfo=timezone.utc)
SCOPE = 'dedicated-test-account/server/XAUUSD/magic/test-run'


class StopSizingFixtures(unittest.TestCase):
    def test_two_closed_atr_outward_alignment_both_directions(self):
        self.assertEqual(stop_price('BUY', '2000.03', '2.01', '.05'), D('1996.00'))
        self.assertEqual(stop_price('SELL', '2000.03', '2.01', '.05'), D('2004.05'))

    def test_broker_minimum_rejects_without_silent_widening(self):
        with self.assertRaises(Reject):
            stop_price('BUY', 2000, 2, '.01', minimum_distance=5)
        self.assertEqual(stop_price('BUY', 2000, 2, '.01', minimum_distance=4), D('1996'))

    def test_broker_minimum_uses_closing_quote_after_spread(self):
        with self.assertRaises(Reject):
            stop_price('BUY', 2000, 2, '.01', 4, liquidation_quote='1999.9')
        with self.assertRaises(Reject):
            stop_price('SELL', 2000, 2, '.01', 4, liquidation_quote='2000.1')

    def test_invalid_quotes_atr_ticks_and_negative_stop(self):
        for field in range(3):
            for bad in (0, -1, 'NaN', 'Infinity'):
                args = [2000, 2, '.01']; args[field] = bad
                with self.subTest(field=field, bad=bad), self.assertRaises(Reject):
                    stop_price('BUY', *args)
        with self.assertRaises(Reject):
            stop_price('BUY', 1, 2, '.01')
        with self.assertRaises(Reject):
            stop_price('HOLD', 2000, 2, '.01')

    def test_point_zero_zero_one_volume_step_is_not_two_decimals(self):
        self.assertEqual(floor_volume('.0099', '.001', 10, '.001'), D('.009'))
        self.assertEqual(initial_volume(1000, 300, '.001', 10, '.001'), D('.008'))
        self.assertLessEqual(D('.008') * 300, D('2.50'))

    def test_minimum_never_rounds_risk_up(self):
        with self.assertRaises(Reject):
            initial_volume(1000, 300, '.01', 10, '.01')
        with self.assertRaises(Reject):
            floor_volume('.0099', '.01', 10, '.01')

    def test_all_existing_caps_and_exact_boundary(self):
        self.assertEqual(initial_volume(10000, 100, '.001', 10, '.001'), D('.01'))
        self.assertEqual(initial_volume(10000, 100, '.001', 10, '.001', '.026', '.046'), D('.004'))
        for basket, total in (('.03', 0), (0, '.05'), ('.04', 0)):
            with self.subTest(basket=basket, total=total), self.assertRaises(Reject):
                initial_volume(10000, 100, '.001', 10, '.001', basket, total)

    def test_nonfinite_or_zero_loss_cannot_size(self):
        for bad in (0, -1, 'NaN', 'Infinity'):
            with self.subTest(bad=bad), self.assertRaises(Reject):
                initial_volume(1000, bad, '.001', 10, '.001')

    def test_full_original_entry_to_stop_losses_are_summed(self):
        existing = fixture_stop_loss('BUY', '.01', 2000, 1980, 100)
        candidate = fixture_stop_loss('SELL', '.01', 2010, 2025, 100)
        self.assertEqual((existing, candidate), (D(20), D(15)))
        self.assertTrue(basket_budget([existing], candidate, 0))
        self.assertFalse(basket_budget([existing], candidate, '.01'))
        # Current floating gain is deliberately not an input to this budget.
        for direction, entry, stop in (('BUY', 2000, 2010), ('SELL', 2000, 1990), ('HOLD', 2000, 1990)):
            with self.assertRaises(Reject):
                fixture_stop_loss(direction, '.01', entry, stop, 100)

    def test_invalid_volume_contract_values(self):
        for field in range(4):
            for bad in (0, -1, 'NaN', 'Infinity'):
                args = ['.01', '.001', 10, '.001']; args[field] = bad
                with self.subTest(field=field, bad=bad), self.assertRaises(Reject):
                    floor_volume(*args)
        with self.assertRaises(Reject):
            floor_volume('.01', '.02', '.01', '.001')

    def test_basket_existing_risk_cost_and_gap_cases(self):
        self.assertTrue(basket_budget([20, 10], 4, 1))
        self.assertFalse(basket_budget([20, 10], 4, '1.001'))
        self.assertFalse(basket_budget([36], '.01', 0))
        with self.assertRaises(Reject):
            basket_budget([10], 1, 0, crossed_stop=True)
        for existing, candidate, costs in (([-10], 1, 0), ([10], 0, 0), ([10], 1, None), ([10], 1, 'NaN')):
            with self.subTest(existing=existing, candidate=candidate, costs=costs), self.assertRaises(Reject):
                basket_budget(existing, candidate, costs)


class PersistentRiskFixtures(unittest.TestCase):
    def state(self, **changes):
        values = dict(scope=SCOPE, day='2026-10-21', initial_equity=D(1000), day_equity=D(1000), halted=False)
        values.update(changes)
        return RiskState(**values)

    def test_initial_fixed_drawdown_not_highwater(self):
        state = evaluate_state(self.state(day_equity=D(1100)), SCOPE, NOW, 1040)
        self.assertFalse(state.halted)  # 60 daily loss; above fixed initial equity.
        self.assertTrue(evaluate_state(self.state(), SCOPE, NOW, 950).halted)

    def test_daily_loss_exact_boundary_is_account_wide(self):
        state = self.state(initial_equity=D(2000), day_equity=D(2100))
        self.assertFalse(evaluate_state(state, SCOPE, NOW, '2025.01').halted)
        self.assertTrue(evaluate_state(state, SCOPE, NOW, 2025).halted)

    def test_midnight_cannot_erase_old_baseline_breach(self):
        yesterday = self.state(day='2026-10-20', initial_equity=D(2000), day_equity=D(2100))
        self.assertTrue(evaluate_state(yesterday, SCOPE, NOW, 2025).halted)
        rolled = evaluate_state(yesterday, SCOPE, NOW, 2050)
        self.assertEqual((rolled.day, rolled.day_equity, rolled.initial_equity), ('2026-10-21', D(2050), D(2000)))

    def test_halt_survives_restart_recovery_and_rollover(self):
        store = MemoryStore(self.state())
        self.assertTrue(recover(store, SCOPE, NOW, 940, exposure=True).halted)
        self.assertTrue(recover(store, SCOPE, NOW + timedelta(days=1), 2000, exposure=False).halted)
        self.assertEqual(store.record.day, '2026-10-21')

    def test_utc_boundary_uses_instant_not_local_calendar(self):
        local = datetime(2026, 10, 22, 0, 30, tzinfo=timezone(timedelta(hours=2)))
        self.assertEqual(utc_day(local), '2026-10-21')
        with self.assertRaises(Reject):
            utc_day(datetime(2026, 10, 21))

    def test_missing_exposed_and_corrupt_states_never_reinitialize(self):
        for record, exposed in ((None, True), ({}, False), (self.state(scope='other'), True),
                                (self.state(day='2026-10-22'), True), (self.state(day='2026-02-30'), True),
                                (self.state(initial_equity=D('NaN')), True)):
            with self.subTest(record=record), self.assertRaises(Reject):
                recover(MemoryStore(record), SCOPE, NOW, 1000, exposure=exposed)
        fresh = recover(MemoryStore(), SCOPE, NOW, 1000, exposure=False)
        self.assertEqual(fresh.initial_equity, D(1000))

    def test_reused_scope_missing_state_is_not_a_clean_bootstrap(self):
        for exposure in (False, True):
            with self.subTest(exposure=exposure), self.assertRaises(Reject):
                recover(MemoryStore(marker=SCOPE), SCOPE, NOW, 1000, exposure=exposure)
        with self.assertRaises(Reject):
            recover(MemoryStore(self.state(), marker='wrong-marker'), SCOPE, NOW, 1000, exposure=False)
        orphaned = MemoryStore(self.state()); orphaned.marker = None
        with self.assertRaises(Reject):
            recover(orphaned, SCOPE, NOW, 1000, exposure=False)

    def test_partial_marker_write_never_authorizes_initialization(self):
        store = MemoryStore(); store.fail_marker = True
        with self.assertRaises(Reject):
            recover(store, SCOPE, NOW, 1000, exposure=False)
        self.assertIsNone(store.record)
        store.fail_marker = False
        with self.assertRaises(Reject):
            recover(store, SCOPE, NOW, 1000, exposure=False)

    def test_partial_first_bootstrap_never_resets_on_retry(self):
        store = MemoryStore(); store.fail_commit = True
        with self.assertRaises(Reject):
            recover(store, SCOPE, NOW, 1000, exposure=False)
        self.assertEqual(store.marker, SCOPE)
        self.assertIsNone(store.record)
        store.fail_commit = False
        with self.assertRaises(Reject):
            recover(store, SCOPE, NOW, 2000, exposure=False)
        store.barrier = False  # Even removing transaction barrier does not erase scope history.
        with self.assertRaises(Reject):
            recover(store, SCOPE, NOW, 2000, exposure=False)

    def test_failed_commit_retains_barrier_across_restart(self):
        store = MemoryStore(self.state()); store.fail_commit = True
        with self.assertRaises(Reject):
            recover(store, SCOPE, NOW, 940, exposure=True)
        self.assertTrue(store.barrier)
        store.fail_commit = False
        with self.assertRaises(Reject):
            recover(store, SCOPE, NOW, 2000, exposure=False)

    def test_barrier_write_failure_denies_current_action(self):
        store = MemoryStore(self.state()); store.fail_barrier = True
        with self.assertRaises(Reject):
            recover(store, SCOPE, NOW, 1000, exposure=False)
        # This cannot prove restart durability after TOTAL storage failure.
        # Terminal design must separately retain fail-closed evidence or refuse recovery.
        self.assertEqual(store.record, self.state())


if __name__ == '__main__':
    unittest.main()
