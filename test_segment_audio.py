#!/usr/bin/env python3
"""Self-check for segment planning — run: python3 test_segment_audio.py"""
from segment_audio import plan_cuts


def test_short_clip_is_one_segment():
    assert plan_cuts(20.0, [(5, 6)]) == ([(0.0, 20.0)], 0)


def test_cuts_in_the_latest_pause_that_fits():
    ranges, forced = plan_cuts(60.0, [(10, 11), (25, 26), (45, 46)])
    assert ranges == [(0.0, 25.5), (25.5, 45.5), (45.5, 60.0)] and forced == 0


def test_no_pause_forces_a_cut():
    ranges, forced = plan_cuts(70.0, [])
    assert ranges == [(0.0, 28.0), (28.0, 56.0), (56.0, 70.0)] and forced == 2


def test_ranges_cover_the_whole_clip_within_the_limit():
    ranges, _ = plan_cuts(627.12, [(i * 13.0, i * 13.0 + 0.4) for i in range(1, 48)])
    assert ranges[0][0] == 0 and ranges[-1][1] == 627.12
    assert all(a[1] == b[0] for a, b in zip(ranges, ranges[1:]))
    assert all(b - a <= 28.0 for a, b in ranges)


if __name__ == "__main__":
    for t in (test_short_clip_is_one_segment, test_cuts_in_the_latest_pause_that_fits,
              test_no_pause_forces_a_cut, test_ranges_cover_the_whole_clip_within_the_limit):
        t()
    print("ok")
