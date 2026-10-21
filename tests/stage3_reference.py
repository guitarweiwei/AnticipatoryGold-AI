"""Independent stage-3 policy examples, NOT MQL5 execution evidence.

The journal is an abstract durable transaction service with injected faults.
It makes no filesystem/crash durability claim. Prices use a supplied linear
account-currency loss fixture, not OrderCalcProfit or a broker fill simulator.
No policy here authorizes an order or supplies an unknown future-cost bound.
"""
from dataclasses import dataclass
from decimal import Decimal


class Reject(ValueError):
    pass


def amount(value, *, positive=False, signed=False):
    try:
        number = Decimal(str(value))
    except Exception as exc:
        raise Reject('invalid numeric evidence') from exc
    if not number.is_finite() or (not signed and number < 0) or (positive and number <= 0):
        raise Reject('invalid numeric evidence')
    return number


@dataclass(frozen=True)
class Signal:
    scope: str
    symbol: str
    closed_bar: int
    timeframe: str = 'M5'

    def validate(self):
        if (not self.scope or not self.symbol or self.timeframe not in ('M1', 'M5', 'M15', 'M30', 'H1')
                or type(self.closed_bar) is not int or self.closed_bar <= 0):
            raise Reject('invalid signal identity')
        return self


@dataclass(frozen=True)
class Intent:
    signal: Signal
    direction: str
    lots: Decimal
    stop: Decimal
    approved_price_loss: Decimal

    def validate(self):
        self.signal.validate()
        if self.direction not in ('BUY', 'SELL'):
            raise Reject('invalid direction')
        for value in (self.lots, self.stop, self.approved_price_loss):
            amount(value, positive=True)
        return self


class Journal:
    """Abstract transaction contract; retained barrier represents uncertainty."""
    def __init__(self):
        self.intents = {}
        self.resolved = set()
        self.barrier = False
        self.fault = None

    def reserve(self, intent):
        intent.validate()
        if self.barrier or intent.signal in self.intents:
            raise Reject('uncertain or consumed signal')
        if self.fault == 'before':
            raise OSError('no durable prewrite receipt')
        self.barrier = True
        if self.fault == 'partial':
            raise OSError('uncertain partial prewrite')
        self.intents[intent.signal] = intent
        if self.fault == 'after':
            raise OSError('commit acknowledgement unavailable')
        self.barrier = False


class Coordinator:
    """A callback is a side-effect spy only; no terminal order is executed."""
    def __init__(self, journal):
        self.journal = journal
        self.halted = journal.barrier or bool(set(journal.intents) - journal.resolved)

    def attempt(self, intent, side_effect):
        if self.halted:
            raise Reject('unresolved restart or local failure')
        try:
            self.journal.reserve(intent)
        except (Reject, OSError):
            self.halted = True
            raise
        # From here the key stays consumed even if acknowledgement is lost.
        self.halted = True
        return side_effect()

    def resolve(self, signal, *, conclusive):
        if not conclusive or signal not in self.journal.intents or self.journal.barrier:
            raise Reject('reconciliation incomplete')
        self.journal.resolved.add(signal)
        self.halted = bool(set(self.journal.intents) - self.journal.resolved)


@dataclass(frozen=True)
class Fill:
    deal_id: int
    position_id: int
    direction: str
    lots: Decimal
    price: Decimal


def audit_fills(intent, fills, live_stops, loss_per_price_unit_lot):
    """Evaluate known price exposure only, not whether an order may proceed.

    Correlation to the expected order and position must be established upstream.
    A partial fill returns its known exposure; the project may conservatively halt
    on every partial fill and must never automatically top it up.
    """
    intent.validate()
    slope = amount(loss_per_price_unit_lot, positive=True)
    if not fills:
        raise Reject('no conclusive fill evidence')
    tickets = set()
    volume = Decimal(0)
    loss = Decimal(0)
    for fill in fills:
        if (type(fill.deal_id) is not int or fill.deal_id <= 0 or fill.deal_id in tickets
                or type(fill.position_id) is not int or fill.position_id <= 0
                or fill.direction != intent.direction):
            raise Reject('duplicate or uncorrelated fill')
        tickets.add(fill.deal_id)
        lots, price = amount(fill.lots, positive=True), amount(fill.price, positive=True)
        stop = amount(live_stops.get(fill.position_id), positive=True)
        # A different stop, including a seemingly safer one, is not the reviewed order.
        if stop != amount(intent.stop, positive=True):
            raise Reject('actual SL differs from intended protection')
        distance = price - stop if fill.direction == 'BUY' else stop - price
        if distance <= 0:
            raise Reject('fill beyond stop or invalid SL side')
        volume += lots
        loss += lots * distance * slope
    if volume > amount(intent.lots, positive=True):
        raise Reject('overfill exceeds intent')
    if loss > amount(intent.approved_price_loss, positive=True):
        raise Reject('actual fill risk exceeds approved loss')
    return volume, loss


@dataclass(frozen=True)
class Deal:
    ticket: int
    position_id: int
    entry: str
    volume: Decimal
    profit: Decimal = Decimal(0)
    commission: Decimal = Decimal(0)
    fee: Decimal = Decimal(0)
    swap: Decimal = Decimal(0)


def reconstruct(deals, live_volume, *, complete_history):
    """Exact cash ledger plus exposure consistency; deals must be scoped upstream.

    Return signed economic cash and conservative recorded-cost totals separately.
    Neither is a prospective all-cost basket bound; rebates/profits cannot be
    silently used to authorize another entry. Broker history completeness is a
    required external assertion, not inferred from a nonempty list.
    """
    if complete_history is not True:
        raise Reject('complete broker history unavailable')
    seen = {}
    exposure = {}
    cash = Decimal(0)
    recorded_cost = Decimal(0)
    realized_losses = Decimal(0)
    for deal in deals:
        if type(deal.ticket) is not int or deal.ticket <= 0 or type(deal.position_id) is not int or deal.position_id <= 0:
            raise Reject('invalid deal identity')
        if deal.ticket in seen:
            if seen[deal.ticket] != deal:
                raise Reject('conflicting duplicate ticket')
            continue
        seen[deal.ticket] = deal
        if deal.entry not in ('IN', 'OUT'):
            raise Reject('unmodeled lifecycle, including reversal/OUT_BY')
        lots = amount(deal.volume, positive=True)
        current = exposure.get(deal.position_id, Decimal(0))
        current += lots if deal.entry == 'IN' else -lots
        if current < 0:
            raise Reject('missing entry or invalid deal ordering')
        exposure[deal.position_id] = current
        profit, commission, fee, swap = [amount(v, signed=True) for v in
                                         (deal.profit, deal.commission, deal.fee, deal.swap)]
        if deal.entry == 'IN' and (profit != 0 or swap != 0):
            raise Reject('unsupported nonzero entry profit/swap')
        cash += profit + commission + fee + swap
        recorded_cost += sum(max(-v, Decimal(0)) for v in (commission, fee, swap))
        if deal.entry == 'OUT':
            realized_losses += max(-profit, Decimal(0))
    actual = {key: amount(value, positive=True) for key, value in live_volume.items()}
    expected = {key: value for key, value in exposure.items() if value != 0}
    if actual != expected:
        raise Reject('history/live-position volume mismatch')
    return cash, recorded_cost, realized_losses


def prospective_budget(existing_price_loss, candidate_price_loss, recorded_losses_and_costs,
                       future_cost_bound, budget):
    # In the actual project this bound remains UNKNOWN and all candidates veto.
    if future_cost_bound is None:
        raise Reject('verified future commission/fee/swap bound absent')
    terms = [amount(v) for v in (existing_price_loss, candidate_price_loss,
                                 recorded_losses_and_costs, future_cost_bound)]
    return sum(terms, Decimal(0)) <= amount(budget, positive=True)
