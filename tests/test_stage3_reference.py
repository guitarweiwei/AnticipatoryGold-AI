"""Adversarial policy fixtures only; do not execute or prove any MQL5 code."""
from dataclasses import replace
from decimal import Decimal as D
import unittest

from stage3_reference import (Reject, Signal, Intent, Journal, Coordinator, Fill,
                              Deal, audit_fills, reconstruct, prospective_budget)


def proposal(**changes):
    values = dict(signal=Signal('isolated-run', 'XAUUSD', 1800000000), direction='BUY',
                  lots=D('.02'), stop=D('1990'), approved_price_loss=D('20'))
    values.update(changes)
    return Intent(**values)


class IntentFaultFixtures(unittest.TestCase):
    def test_prewrite_receipt_precedes_side_effect(self):
        store = Journal(); engine = Coordinator(store); intent = proposal()
        observed = []
        engine.attempt(intent, lambda: observed.append(store.intents[intent.signal]))
        self.assertEqual(observed, [intent])

    def test_every_prewrite_fault_prevents_side_effect(self):
        for fault in ('before', 'partial', 'after'):
            with self.subTest(fault=fault):
                store = Journal(); store.fault = fault; engine = Coordinator(store); sent = []
                with self.assertRaises(OSError):
                    engine.attempt(proposal(), lambda: sent.append('sent'))
                self.assertEqual(sent, [])
                with self.assertRaises(Reject):
                    engine.attempt(proposal(), lambda: sent.append('sent'))

    def test_partial_and_lost_commit_ack_block_restart(self):
        for fault in ('partial', 'after'):
            store = Journal(); store.fault = fault
            with self.assertRaises(OSError): Coordinator(store).attempt(proposal(), lambda: None)
            store.fault = None
            with self.assertRaises(Reject): Coordinator(store).attempt(proposal(), lambda: None)

    def test_lost_broker_ack_never_retransmits_on_restart(self):
        store = Journal(); sent = []
        def sent_then_timeout():
            sent.append('broker-may-have-filled')
            raise TimeoutError('ack lost')
        with self.assertRaises(TimeoutError): Coordinator(store).attempt(proposal(), sent_then_timeout)
        with self.assertRaises(Reject): Coordinator(store).attempt(proposal(), sent_then_timeout)
        self.assertEqual(len(sent), 1)

    def test_consumed_bar_blocks_opposite_direction_after_reconciliation(self):
        store = Journal(); engine = Coordinator(store); intent = proposal()
        engine.attempt(intent, lambda: None)
        engine.resolve(intent.signal, conclusive=True)
        with self.assertRaises(Reject):
            engine.attempt(replace(intent, direction='SELL', stop=D('2010')), lambda: None)

    def test_conclusive_zero_fill_still_consumes_signal(self):
        store = Journal(); engine = Coordinator(store); intent = proposal()
        engine.attempt(intent, lambda: 'definitive broker rejection')
        engine.resolve(intent.signal, conclusive=True)
        with self.assertRaises(Reject): Coordinator(store).attempt(intent, lambda: None)

    def test_pending_scope_blocks_even_next_bar_until_reconciled(self):
        store = Journal(); intent = proposal(); engine = Coordinator(store)
        engine.attempt(intent, lambda: None)
        next_bar = replace(intent, signal=replace(intent.signal, closed_bar=1800000300))
        with self.assertRaises(Reject): Coordinator(store).attempt(next_bar, lambda: None)
        with self.assertRaises(Reject): engine.resolve(intent.signal, conclusive=False)
        engine.resolve(intent.signal, conclusive=True)
        self.assertEqual(engine.attempt(next_bar, lambda: 'only next bar'), 'only next bar')

    def test_invalid_signal_identity_never_sent(self):
        for signal in (Signal('', 'XAUUSD', 1), Signal('run', '', 1), Signal('run', 'XAUUSD', True), Signal('run', 'XAUUSD', 0)):
            with self.assertRaises(Reject): Coordinator(Journal()).attempt(proposal(signal=signal), lambda: self.fail('sent'))


class ActualFillFixtures(unittest.TestCase):
    def fill(self, **changes):
        values = dict(deal_id=1, position_id=51, direction='BUY', lots=D('.01'), price=D('2000'))
        values.update(changes)
        return Fill(**values)

    def test_partial_fill_is_known_exposure_not_permission_to_top_up(self):
        self.assertEqual(audit_fills(proposal(), [self.fill()], {51: D('1990')}, 100), (D('.01'), D('10')))
        # Intent coordinator remains pending until explicit reconciliation.
        store = Journal(); engine = Coordinator(store); engine.attempt(proposal(), lambda: None)
        with self.assertRaises(Reject): Coordinator(store).attempt(proposal(), lambda: None)

    def test_multiple_deals_account_for_total_actual_risk(self):
        fills = [self.fill(), self.fill(deal_id=2, price=D('1999'))]
        self.assertEqual(audit_fills(proposal(), fills, {51: D('1990')}, 100), (D('.02'), D('19')))

    def test_adverse_fill_over_budget_rejected(self):
        with self.assertRaises(Reject):
            audit_fills(proposal(), [self.fill(lots=D('.02'), price=D('2000.01'))], {51: D('1990')}, 100)

    def test_exact_reviewed_stop_and_direction_required(self):
        for stop in (None, 0, 'NaN', 1989, 1991):
            with self.assertRaises(Reject): audit_fills(proposal(), [self.fill()], {51: stop}, 100)
        with self.assertRaises(Reject): audit_fills(proposal(), [self.fill(direction='SELL')], {51: 1990}, 100)

    def test_sell_fill_and_crossed_stop(self):
        intent = proposal(direction='SELL', stop=D('2010'))
        self.assertEqual(audit_fills(intent, [self.fill(direction='SELL')], {51: 2010}, 100)[1], D(10))
        with self.assertRaises(Reject):
            audit_fills(intent, [self.fill(direction='SELL', price=D('2011'))], {51: 2010}, 100)

    def test_duplicate_overfill_and_missing_fill_rejected(self):
        for fills in ([], [self.fill(), self.fill()], [self.fill(lots=D('.021'))]):
            with self.assertRaises(Reject): audit_fills(proposal(), fills, {51: 1990}, 100)

    def test_nonfinite_fill_evidence_rejected(self):
        for field in ('lots', 'price'):
            for value in ('NaN', 'Infinity', 0, -1):
                with self.assertRaises(Reject): audit_fills(proposal(), [self.fill(**{field: value})], {51: 1990}, 100)


class LedgerFixtures(unittest.TestCase):
    def history(self):
        return [Deal(1, 51, 'IN', D('.02'), commission=D('-.20'), fee=D('-.02')),
                Deal(2, 51, 'OUT', D('.005'), profit=D('-3'), commission=D('-.05'), fee=D('-.01'), swap=D('-.04'))]

    def test_partial_close_rebuild_preserves_all_entry_and_exit_costs(self):
        # Entry .20+.02 plus partial exit .05+.01+.04 = .32.
        self.assertEqual(reconstruct(self.history(), {51: '.015'}, complete_history=True), (D('-3.32'), D('.32'), D('3')))

    def test_repeated_history_poll_does_not_double_count_deals(self):
        original = reconstruct(self.history(), {51: '.015'}, complete_history=True)
        repeated = reconstruct(self.history() * 3, {51: '.015'}, complete_history=True)
        self.assertEqual(repeated, original)

    def test_conflicting_duplicate_fee_rejected(self):
        history = self.history(); history.append(replace(history[0], commission=D('-.21')))
        with self.assertRaises(Reject): reconstruct(history, {51: '.015'}, complete_history=True)

    def test_fully_closed_positions_remain_in_cash_ledger(self):
        history = self.history() + [Deal(3, 51, 'OUT', D('.015'), profit=D('5'), commission=D('-.15'))]
        self.assertEqual(reconstruct(history, {}, complete_history=True), (D('1.53'), D('.47'), D('3')))

    def test_rebates_and_positive_swap_do_not_erase_recorded_debits(self):
        history = self.history() + [Deal(3, 51, 'OUT', D('.015'), profit=D('5'), commission=D('.10'), swap=D('.50'))]
        cash, cost, realized_losses = reconstruct(history, {}, complete_history=True)
        self.assertEqual((cash, cost, realized_losses), (D('2.28'), D('.32'), D('3')))

    def test_missing_history_or_position_mismatch_rejected(self):
        for complete, live in ((False, {51: '.015'}), (True, {51: '.02'}), (True, {}), (True, {52: '.015'})):
            with self.assertRaises(Reject): reconstruct(self.history(), live, complete_history=complete)
        with self.assertRaises(Reject): reconstruct(self.history()[1:], {51: '.015'}, complete_history=True)

    def test_unsupported_reversal_and_invalid_cash_rejected(self):
        for entry in ('INOUT', 'OUT_BY', 'BALANCE'):
            with self.assertRaises(Reject): reconstruct([Deal(1, 51, entry, D('.01'))], {}, complete_history=True)
        for field in ('profit', 'commission', 'fee', 'swap'):
            history = self.history(); history[1] = replace(history[1], **{field: D('NaN')})
            with self.assertRaises(Reject): reconstruct(history, {51: '.015'}, complete_history=True)

    def test_future_cost_missing_invalid_or_above_budget_never_zero_assumed(self):
        for bound in (None, 'NaN', 'Infinity', -1):
            with self.assertRaises(Reject): prospective_budget(20, 10, 2, bound, 35)
        self.assertTrue(prospective_budget(20, 10, 2, 3, 35))
        self.assertFalse(prospective_budget(20, 10, 2, '3.01', 35))


if __name__ == '__main__':
    unittest.main()
