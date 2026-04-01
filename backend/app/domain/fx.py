"""Currency conversion rules.

An exchange rate here always means **one unit of the base currency buys
`rate` units of the quote currency**. Conversions are done with `Decimal` and
rounded exactly once, at the end, to the target currency's minor unit. Floats
never enter the calculation (plan Section 9).

Rounding is `ROUND_HALF_EVEN` -- the accounting default -- and the rate used is
always returned alongside the result by the service layer, so a converted
figure can be audited rather than taken on trust.
"""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation, localcontext

from app.domain.money import Currency

#: Working precision for intermediate conversion arithmetic. Comfortably wider
#: than any amount/rate combination this app can produce, so the only rounding
#: that happens is the explicit final quantize.
_CONVERSION_PRECISION = 50


class FxError(Exception):
    """Base class for exchange-rate errors."""


class InvalidRateError(FxError):
    """The rate is not a finite, strictly positive number."""


class MissingRateError(FxError):
    """No applicable rate exists for the pair at the requested time."""


@dataclass(frozen=True, slots=True)
class ResolvedRate:
    """A rate that applies at a point in time, with its provenance."""

    base_currency: str
    quote_currency: str
    rate: Decimal
    as_of: datetime
    source: str
    is_inverse: bool = False


@dataclass(frozen=True, slots=True)
class RateObservation:
    """One stored rate, decoupled from the ORM for pure-domain testing.

    `is_inverse` is only set on observations derived by `RateBook` when the
    stored row was for the opposite direction; stored rows are always False.
    """

    base_currency: str
    quote_currency: str
    rate: Decimal
    as_of: datetime
    source: str
    is_inverse: bool = False


def validate_rate(rate: Decimal) -> Decimal:
    """Return `rate` unchanged if usable; raise otherwise.

    Rates are quoted as a positive price, never a direction sign -- direction
    lives in the currency pair. Zero or negative rates are data errors.
    """
    if not rate.is_finite() or rate <= 0:
        raise InvalidRateError(f"Exchange rate must be a finite positive number, got {rate!r}")
    return rate


def invert_rate(rate: Decimal) -> Decimal:
    """Return `1 / rate` at working precision.

    The result is intentionally not rounded to a fixed scale: it is an
    intermediate value, and rounding it early would compound error.
    """
    validated = validate_rate(rate)
    with localcontext() as ctx:
        ctx.prec = _CONVERSION_PRECISION
        return Decimal(1) / validated


def convert_minor_units(
    amount_minor: int,
    *,
    from_currency: str,
    to_currency: str,
    rate: Decimal,
) -> int:
    """Convert an integer minor-unit amount using `rate` (base -> quote).

    The amount is first expressed in major units of the source currency, then
    multiplied by the rate, then rounded once to the target currency's exponent
    with banker's rounding.
    """
    source = Currency(from_currency)
    target = Currency(to_currency)

    if source.code == target.code:
        return amount_minor

    validated = validate_rate(rate)

    with localcontext() as ctx:
        ctx.prec = _CONVERSION_PRECISION
        try:
            major = Decimal(amount_minor).scaleb(-source.exponent)
            converted = major * validated
            quantum = Decimal(1).scaleb(-target.exponent)
            rounded = converted.quantize(quantum, rounding=ROUND_HALF_EVEN)
        except (InvalidOperation, ValueError) as exc:  # pragma: no cover - defensive
            raise InvalidRateError(
                f"Could not convert {amount_minor} {source} -> {target}"
            ) from exc
        return int(rounded.scaleb(target.exponent))


_Index = dict[tuple[str, str], tuple[list[datetime], list[RateObservation]]]


def _build_index(observations: Iterable[RateObservation]) -> _Index:
    """Index observations by directed pair, sorted by effective time.

    Both directions are indexed: if only `GBP -> USD` was recorded, converting
    USD to GBP uses its inverse. The original is never mutated.
    """
    index: _Index = {}

    for observation in observations:
        pairs = (
            (observation, observation.base_currency, observation.quote_currency, False),
            (observation, observation.quote_currency, observation.base_currency, True),
        )
        for obs, base, quote, inverse in pairs:
            entry = RateObservation(
                base_currency=base,
                quote_currency=quote,
                rate=invert_rate(obs.rate) if inverse else obs.rate,
                as_of=obs.as_of,
                source=obs.source,
                is_inverse=inverse,
            )
            times, entries = index.setdefault((base, quote), ([], []))
            times.append(obs.as_of)
            entries.append(entry)

    # Stable sort: observations arriving in fetched order keep that order for
    # equal timestamps, so the most recently fetched observation wins.
    for times, entries in index.values():
        order = sorted(range(len(times)), key=times.__getitem__)
        times[:] = [times[i] for i in order]
        entries[:] = [entries[i] for i in order]

    return index


class RateBook:
    """A resolved set of rates, resident in memory for one report/tick.

    User-entered rates take precedence over shared provider rates; within each
    scope the newest observation at or before the requested instant wins.
    """

    def __init__(
        self,
        *,
        user_observations: Iterable[RateObservation] = (),
        global_observations: Iterable[RateObservation] = (),
    ) -> None:
        self._user = _build_index(user_observations)
        self._global = _build_index(global_observations)

    def resolve(self, from_currency: str, to_currency: str, as_of: datetime) -> ResolvedRate:
        """Return the rate applying at `as_of`, or raise `MissingRateError`."""
        source_currency = Currency(from_currency)
        target_currency = Currency(to_currency)

        if source_currency.code == target_currency.code:
            return ResolvedRate(
                base_currency=source_currency.code,
                quote_currency=target_currency.code,
                rate=Decimal(1),
                as_of=as_of,
                source="identity",
            )

        for index in (self._user, self._global):
            observation = _latest(index, source_currency.code, target_currency.code, as_of)
            if observation is not None:
                return ResolvedRate(
                    base_currency=source_currency.code,
                    quote_currency=target_currency.code,
                    rate=observation.rate,
                    as_of=observation.as_of,
                    source=observation.source,
                    is_inverse=observation.is_inverse,
                )

        raise MissingRateError(
            f"No exchange rate from {source_currency.code} to {target_currency.code} "
            f"on or before {as_of.isoformat()}"
        )


def _latest(index: _Index, base: str, quote: str, as_of: datetime) -> RateObservation | None:
    """Return the newest observation at or before `as_of` for a directed pair."""
    times, entries = index.get((base, quote), ([], []))
    position = bisect_right(times, as_of) - 1
    if position < 0:
        return None
    return entries[position]
