from datetime import datetime, timedelta, timezone

from ac10next.utils import elapsed_seconds


def testelapsed_seconds_handles_aware_datetime():
    now=datetime(2026,9,30,15,30,tzinfo=timezone.utc)
    previous=now-timedelta(minutes=15)
    assert elapsed_seconds(now,previous)==900


def testelapsed_seconds_handles_naive_as_utc():
    now=datetime(2026,9,30,15,30,tzinfo=timezone.utc)
    previous=datetime(2026,9,30,15,20)
    assert elapsed_seconds(now,previous)==600


def testelapsed_seconds_none_means_first_run():
    now=datetime(2026,9,30,15,30,tzinfo=timezone.utc)
    assert elapsed_seconds(now,None) is None


def testelapsed_seconds_never_negative():
    now=datetime(2026,9,30,15,30,tzinfo=timezone.utc)
    assert elapsed_seconds(now,now+timedelta(seconds=30))==0
