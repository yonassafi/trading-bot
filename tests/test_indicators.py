#!/usr/bin/env python3
"""
Tests for scripts/lib/indicators.py.

Every position size, stop, and exit decision in this system flows through
that module's window math. An off-by-one in any of it silently reprices
the whole strategy — and unlike a rule violation, nothing in the routine
prompts would ever notice. These tests exist to make boundary errors
loud.

Run: python3 -m unittest discover -s tests -v
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "lib"))
import indicators as ind  # noqa: E402


def bar(o, h, l, c, v=1000, t="2026-01-01T05:00:00Z"):
    return {"t": t, "o": o, "h": h, "l": l, "c": c, "v": v}


def flat_bars(closes_seq):
    """Bars whose high/low straddle each close by exactly 1."""
    return [bar(c, c + 1, c - 1, c) for c in closes_seq]


class TestSMA(unittest.TestCase):
    def test_exact_window_no_off_by_one(self):
        # 5 values, period 5 -> uses ALL of them, not 4 or 6.
        self.assertEqual(ind.sma([1, 2, 3, 4, 5], 5), 3.0)

    def test_returns_none_when_one_short(self):
        # The single most likely off-by-one: period == len+1.
        self.assertIsNone(ind.sma([1, 2, 3, 4], 5))

    def test_indexed_window_is_trailing_not_centred(self):
        vals = [10, 20, 30, 40, 50]
        # ending at index 2, period 3 -> (10+20+30)/3
        self.assertEqual(ind.sma(vals, 3, index=2), 20.0)

    def test_index_too_early_is_none(self):
        self.assertIsNone(ind.sma([10, 20, 30], 3, index=1))

    def test_empty(self):
        self.assertIsNone(ind.sma([], 3))

    def test_sma_series_alignment(self):
        s = ind.sma_series([1, 2, 3, 4], 2)
        # first entry undefined, then trailing pairs
        self.assertEqual(s, [None, 1.5, 2.5, 3.5])


class TestADR20(unittest.TestCase):
    def test_needs_exactly_20_sessions(self):
        self.assertIsNone(ind.adr20(flat_bars(range(100, 119))))  # 19 bars
        self.assertIsNotNone(ind.adr20(flat_bars(range(100, 120))))  # 20 bars

    def test_known_value(self):
        # h/l = 110/100 -> 10% every session
        bars = [bar(100, 110, 100, 105) for _ in range(20)]
        self.assertAlmostEqual(ind.adr20(bars), 10.0, places=6)

    def test_uses_only_the_last_20(self):
        # 20 quiet sessions then 20 wide ones: must report the wide ones.
        quiet = [bar(100, 101, 100, 100) for _ in range(20)]
        wide = [bar(100, 120, 100, 110) for _ in range(20)]
        self.assertAlmostEqual(ind.adr20(quiet + wide), 20.0, places=6)

    def test_zero_low_does_not_divide_by_zero(self):
        bars = [bar(1, 2, 0, 1) for _ in range(20)]
        self.assertIsNone(ind.adr20(bars))  # <20 usable ratios


class TestDollarVolume(unittest.TestCase):
    def test_uses_close_times_volume_over_period(self):
        bars = [bar(10, 10, 10, 10, v=1_000_000) for _ in range(50)]
        self.assertEqual(ind.dollar_volume_avg(bars, period=50), 10_000_000)

    def test_insufficient_history(self):
        self.assertIsNone(ind.dollar_volume_avg(flat_bars(range(49)), period=50))


class TestPctReturn(unittest.TestCase):
    def test_lookback_is_period_bars_back(self):
        bars = flat_bars([100, 110, 120, 130])
        # index 3 vs index 1 -> 130/110 - 1
        self.assertAlmostEqual(ind.pct_return(bars, 2), 130 / 110 - 1)

    def test_boundary_exact(self):
        bars = flat_bars([100, 200])
        self.assertAlmostEqual(ind.pct_return(bars, 1), 1.0)
        self.assertIsNone(ind.pct_return(bars, 2))  # would need index -1

    def test_zero_denominator(self):
        bars = flat_bars([0, 100])
        self.assertIsNone(ind.pct_return(bars, 1))


class TestPercentileRank(unittest.TestCase):
    def test_max_is_100(self):
        self.assertEqual(ind.percentile_rank(5, [1, 2, 3, 4, 5]), 100.0)

    def test_min_is_not_zero_because_le_is_inclusive(self):
        # Section 5 gates on >= 90; the <= semantics matter.
        self.assertEqual(ind.percentile_rank(1, [1, 2, 3, 4, 5]), 20.0)

    def test_ninety_threshold_boundary(self):
        pop = list(range(1, 11))  # 1..10
        self.assertEqual(ind.percentile_rank(9, pop), 90.0)   # passes >= 90
        self.assertEqual(ind.percentile_rank(8, pop), 80.0)   # fails

    def test_empty_population(self):
        self.assertIsNone(ind.percentile_rank(1, []))


class TestRangePct(unittest.TestCase):
    def test_known_value(self):
        bars = [bar(100, 110, 90, 100) for _ in range(5)]
        self.assertAlmostEqual(ind.range_pct(bars, 5), (110 - 90) / 90)

    def test_contraction_ordering_is_detectable(self):
        # 6.5 needs R(5) < R(10) < R(20): wide early, tight late.
        wide = [bar(100, 150, 50, 100) for _ in range(10)]
        mid = [bar(100, 120, 80, 100) for _ in range(5)]
        tight = [bar(100, 105, 95, 100) for _ in range(5)]
        bars = wide + mid + tight
        r5, r10, r20 = ind.range_pct(bars, 5), ind.range_pct(bars, 10), ind.range_pct(bars, 20)
        self.assertLess(r5, r10)
        self.assertLess(r10, r20)

    def test_insufficient(self):
        self.assertIsNone(ind.range_pct(flat_bars(range(3)), 5))


class TestFindPriorImpulse(unittest.TestCase):
    def _series(self):
        # low 100 at idx 5, high 140 at idx 15 (+40%), then drift.
        bars = [bar(100, 101, 99, 100) for _ in range(5)]
        bars.append(bar(100, 101, 100, 100))                  # idx 5, L=100
        bars += [bar(110, 111, 109, 110) for _ in range(9)]
        bars.append(bar(139, 140, 138, 139))                  # idx 15, H=140
        bars += [bar(135, 136, 134, 135) for _ in range(15)]  # consolidation
        return bars

    def test_finds_an_impulse(self):
        got = ind.find_prior_impulse(self._series())
        self.assertIsNotNone(got)

    def test_H_is_the_most_recent_qualifying_bar_NOT_the_impulse_peak(self):
        """CHARACTERISATION TEST — documents a live defect, not intent.

        The series peaks at 140 (idx 15) then drifts sideways at ~135.
        The returned H is NOT that peak: it is the most recent bar that
        happens to sit >=30% above some low within the preceding 25
        sessions, which is always index-10 while price stays elevated.

        This is not cosmetic. Every Section 6 shape test measures over
        [h_idx, today], so a drifting H truncates the consolidation to
        ~11 sessions and 6.7 compares against the wrong reference price.
        See test_consolidation_window_degenerates below.

        If Section 6.1's tie-break is amended to "H = highest high in the
        lookback", this test SHOULD fail — that is the signal the fix
        landed, and it should then be rewritten to assert the peak.
        """
        bars = self._series()
        got = ind.find_prior_impulse(bars)
        _l_idx, h_idx, _l_price, h_price = got
        true_peak_idx = max(range(len(bars)), key=lambda i: bars[i]["h"])
        self.assertEqual(true_peak_idx, 15)
        self.assertEqual(bars[true_peak_idx]["h"], 140)
        self.assertNotEqual(h_idx, true_peak_idx)
        self.assertLess(h_price, 140)

    def test_consolidation_window_degenerates(self):
        """Section 6.2 requires a 10-40 session consolidation. Because H
        drifts forward, the MEASURED length is pinned near 11 regardless
        of the true base length — so 6.2 is effectively inert and 6.3-6.5
        analyse a truncated slice."""
        base = [bar(100, 101, 99, 100) for _ in range(10)]
        base.append(bar(120, 140, 119, 138))  # the real peak
        measured = []
        for base_len in (10, 15, 20, 30):
            b = base + [bar(132, 134, 130, 132) for _ in range(base_len)]
            _l, h_idx, _lp, _hp = ind.find_prior_impulse(b)
            measured.append((len(b) - 1) - h_idx + 1)
        self.assertEqual(measured, [11, 11, 11, 11])

    def test_respects_min_h_age(self):
        # H must be >= min_h_age sessions old; demand more age than exists.
        self.assertIsNone(ind.find_prior_impulse(self._series(), min_h_age=100))

    def test_respects_min_gain(self):
        self.assertIsNone(ind.find_prior_impulse(self._series(), min_gain=0.99))

    def test_respects_max_lh_span(self):
        # L at 5, H at 15 -> span 10. Allowing only 3 must reject.
        self.assertIsNone(ind.find_prior_impulse(self._series(), max_lh_span=3))

    def test_tiebreak_takes_the_latest_eligible_index(self):
        # Documented tie-break: scan back from index-min_h_age and take
        # the FIRST hit. With price held near 140, the first hit is the
        # boundary bar itself (index-10), not either "real" high.
        bars = [bar(100, 100, 100, 100) for _ in range(3)]
        bars.append(bar(100, 140, 100, 140))                  # idx 3
        bars += [bar(100, 100, 100, 100) for _ in range(3)]
        bars.append(bar(100, 145, 100, 145))                  # idx 7
        bars += [bar(140, 141, 139, 140) for _ in range(12)]
        got = ind.find_prior_impulse(bars)
        self.assertEqual(got[1], len(bars) - 1 - 10)


class TestSegmentMinLows(unittest.TestCase):
    def test_remainder_folds_into_final_segment(self):
        # length 10, seg_len 3 -> [0:3], [3:6], [6:10] (4 bars in seg3)
        lows = [9, 9, 9, 5, 5, 5, 1, 1, 1, 1]
        bars = [bar(10, 11, lo, 10) for lo in lows]
        self.assertEqual(ind.segment_min_lows(bars, 0, 9), (9, 5, 1))

    def test_exact_thirds(self):
        lows = [3, 3, 2, 2, 1, 1]
        bars = [bar(10, 11, lo, 10) for lo in lows]
        self.assertEqual(ind.segment_min_lows(bars, 0, 5), (3, 2, 1))

    def test_too_short_to_split(self):
        self.assertIsNone(ind.segment_min_lows(flat_bars([1, 2]), 0, 1))

    def test_higher_lows_ordering_detected(self):
        lows = [1, 1, 2, 2, 3, 3]
        bars = [bar(10, 11, lo, 10) for lo in lows]
        s1, s2, s3 = ind.segment_min_lows(bars, 0, 5)
        self.assertTrue(s3 > s2 > s1)


class TestSelectReferenceSMA(unittest.TestCase):
    def test_prefers_shortest_qualifying_period(self):
        # Steadily rising closes: 10 SMA sits below price throughout.
        bars = flat_bars([100 + i for i in range(80)])
        self.assertEqual(ind.select_reference_sma(bars, 60, 79), 10)

    def test_returns_none_when_price_below_all_smas(self):
        # Steadily falling: every SMA sits ABOVE price.
        bars = flat_bars([200 - i for i in range(80)])
        self.assertIsNone(ind.select_reference_sma(bars, 60, 79))

    def test_threshold_is_a_fraction_of_valid_points(self):
        bars = flat_bars([100 + i for i in range(80)])
        # An impossible threshold must reject even a clean uptrend.
        self.assertIsNone(
            ind.select_reference_sma(bars, 60, 79, threshold=1.01)
        )


class TestRegressionGuards(unittest.TestCase):
    """Properties the strategy depends on that no single function owns."""

    def test_sma_period_divisor_matches_window_length(self):
        # sma() divides by `period`, not len(window). If the start-guard
        # ever regresses, this catches the silent wrong-average.
        vals = list(range(1, 21))
        for p in (5, 10, 20):
            got = ind.sma(vals, p)
            manual = sum(vals[-p:]) / p
            self.assertAlmostEqual(got, manual, places=9)

    def test_adr20_is_percent_not_fraction(self):
        # Section 8.3 compares est_risk_share against (ADR_20 x price).
        # If this ever returned a fraction, every stop-width test breaks.
        bars = [bar(100, 110, 100, 105) for _ in range(20)]
        self.assertGreater(ind.adr20(bars), 1.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
