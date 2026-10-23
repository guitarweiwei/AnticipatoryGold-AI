"""Independent D1/D2 arithmetic/state specification for deterministic fixtures.

This does not execute MQL5, emulate OrderCalcProfit, simulate fills or prove
terminal durability. Decimal loss slopes are supplied account-currency fixtures.
The store is an abstract two-phase durable interface, not a filesystem emulator.
"""
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR


class Reject(ValueError):
    pass


def number(value, *, positive=False):
    try:
        result = Decimal(str(value))
    except Exception as exc:
        raise Reject('invalid number') from exc
    if not result.is_finite() or result < 0 or (positive and result == 0):
        raise Reject('invalid numeric domain')
    return result


def stop_price(direction, entry, closed_atr, tick_size, minimum_distance=0, liquidation_quote=None):
    entry, atr, tick = [number(x, positive=True) for x in (entry, closed_atr, tick_size)]
    minimum = number(minimum_distance)
    if direction not in ('BUY', 'SELL'):
        raise Reject('invalid direction')
    raw = entry - 2 * atr if direction == 'BUY' else entry + 2 * atr
    mode = ROUND_FLOOR if direction == 'BUY' else ROUND_CEILING
    stop = (raw / tick).to_integral_value(rounding=mode) * tick
    closing = entry if liquidation_quote is None else number(liquidation_quote, positive=True)
    distance = closing - stop if direction == 'BUY' else stop - closing
    if stop <= 0 or distance < minimum:
        raise Reject('unacceptable stop; never widen to broker minimum')
    return stop


def floor_volume(requested, minimum, maximum, step):
    requested, minimum, maximum, step = [number(x, positive=True) for x in (requested, minimum, maximum, step)]
    if minimum > maximum or requested < minimum:
        raise Reject('volume outside symbol domain')
    result = (min(requested, maximum) / step).to_integral_value(rounding=ROUND_FLOOR) * step
    if result < minimum or result > requested:
        raise Reject('minimum lot would exceed requested ceiling')
    return result


def initial_volume(equity, loss_per_lot, minimum, maximum, step, basket_lots=0, total_lots=0):
    equity, slope = number(equity, positive=True), number(loss_per_lot, positive=True)
    basket, total = number(basket_lots), number(total_lots)
    ceiling = min(equity * Decimal('.0025') / slope, Decimal('.01'), Decimal('.03') - basket, Decimal('.05') - total)
    if ceiling <= 0:
        raise Reject('no capacity')
    return floor_volume(ceiling, minimum, maximum, step)


def fixture_stop_loss(direction, volume, original_entry, protective_stop, account_loss_per_price_unit_lot):
    """Linear broker-loss fixture only; MQL must obtain actual OrderCalcProfit."""
    volume, entry, stop, slope = [number(x, positive=True) for x in
                                 (volume, original_entry, protective_stop, account_loss_per_price_unit_lot)]
    if direction not in ('BUY', 'SELL') or (direction == 'BUY' and stop >= entry) or (direction == 'SELL' and stop <= entry):
        raise Reject('invalid protective stop direction')
    return volume * abs(entry - stop) * slope


def basket_budget(existing_losses, candidate_loss, cost_reserve, *, crossed_stop=False):
    # Fixtures give ORIGINAL ENTRY-to-stop losses in account currency. Profit
    # cannot subsidize a losing leg; crossed stops make prospective risk uncertain.
    if crossed_stop:
        raise Reject('stop already crossed')
    losses = [number(value) for value in existing_losses]
    loss, reserve = number(candidate_loss, positive=True), number(cost_reserve)
    return sum(losses, loss + reserve) <= Decimal('35')


def utc_day(now):
    if now.tzinfo is None or now.utcoffset() is None:
        raise Reject('timezone-aware time required')
    return now.astimezone(timezone.utc).date().isoformat()


@dataclass(frozen=True)
class RiskState:
    scope: str
    day: str
    initial_equity: Decimal
    day_equity: Decimal
    halted: bool = False


def validate_state(state, scope, now):
    if not isinstance(state, RiskState) or state.scope != scope or not isinstance(state.halted, bool):
        raise Reject('missing/corrupt/wrong-scope state')
    number(state.initial_equity, positive=True)
    number(state.day_equity, positive=True)
    try:
        parsed = datetime.strptime(state.day, '%Y-%m-%d').date().isoformat()
    except (TypeError, ValueError) as exc:
        raise Reject('invalid day') from exc
    if parsed != state.day or state.day > utc_day(now):
        raise Reject('future/invalid day')
    return state


def evaluate_state(state, scope, now, equity):
    state = validate_state(state, scope, now)
    equity = number(equity, positive=True)
    # Assess the old day's loss before rollover: restarting after midnight must
    # not erase a breached baseline. Once latched, rollover never clears it.
    breached = state.day_equity - equity >= 75 or (state.initial_equity - equity) / state.initial_equity >= Decimal('.05')
    if state.halted or breached:
        return replace(state, halted=True)
    if state.day != utc_day(now):
        return replace(state, day=utc_day(now), day_equity=equity)
    return state


class MemoryStore:
    """Fault-injectable abstract durable store with separately retained barrier."""
    def __init__(self, record=None, marker=None):
        self.record = record
        self.marker = record.scope if isinstance(record, RiskState) and marker is None else marker
        self.barrier = False
        self.fail_marker = False
        self.fail_barrier = False
        self.fail_commit = False

    def bootstrap_marker(self, scope):
        if self.fail_marker:
            self.marker = '<partial marker>'
            raise OSError('partial bootstrap marker')
        self.marker = scope

    def save(self, state):
        if self.fail_barrier:
            raise OSError('barrier unavailable: no state-changing action authorized')
        self.barrier = True
        if self.fail_commit:
            raise OSError('commit unavailable; durable barrier remains')
        self.record = state
        self.barrier = False


def recover(store, scope, now, equity, *, exposure):
    # Reinitialize only explicitly absent, clean state with no positions. Corrupt
    # state must be reviewed even when flat rather than silently wiped.
    if store.barrier:
        raise Reject('incomplete persistence transaction')
    if store.record is None:
        if store.marker is not None:
            raise Reject('previously bootstrapped scope lost its state')
        if exposure:
            raise Reject('missing state with exposure')
        value = number(equity, positive=True)
        # Create-once scope marker precedes the first state commit.
        try:
            store.bootstrap_marker(scope)
        except OSError as exc:
            raise Reject('bootstrap marker failed') from exc
        state = RiskState(scope, utc_day(now), value, value)
    else:
        if store.marker != scope:
            raise Reject('state without matching bootstrap marker')
        state = evaluate_state(store.record, scope, now, equity)
    try:
        store.save(state)
    except OSError as exc:
        raise Reject('storage failed; local execution must remain blocked') from exc
    return state
