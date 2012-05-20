from django_nose import FastFixtureTestCase as TestCase

from mock import MagicMock

from nose.tools import ok_, eq_, set_trace

from apps.sganalytics.backends import RedisAnalyticsBackend

import datetime


class RedisAnalyticsBackendTest(TestCase):
    def setUp(self):
        #DB5 is arbratery. May have to change later.
        self._backend = RedisAnalyticsBackend(host="localhost", db=5)

        self._redis_backend = self._backend.get_backend()

        #clear the redis database so we are in a consistent state
        self._redis_backend.flushdb()

    def tearDown(self):
        self._redis_backend.flushdb()

    def test_track_metric(self):
        user_id = 1234
        metric = "badge:25"
        datetime_obj = datetime.datetime(year=2012, month=1, day=1)

        ok_(self._backend.track_metric(user_id, metric, datetime_obj))

        keys = self._redis_backend.keys()
        keys.sort()
        eq_(len(keys), 3)

        daily = self._redis_backend.hgetall(keys[2])
        weekly = self._redis_backend.hgetall(keys[1])
        aggregated = self._redis_backend.get("analy:%s:count:%s" % (user_id, metric, ))

        #each metric should be at 1
        [eq_(int(value), 1) for value in daily.values()]
        [eq_(int(value), 1) for value in weekly.values()]
        eq_(int(aggregated), 1)

        #each hash should only have one key
        eq_(len(daily.keys()), 1)
        eq_(len(weekly.keys()), 2)

        #try incrementing by the non default value
        ok_(self._backend.track_metric(user_id, metric, datetime_obj, inc_amt=3))

        keys = self._redis_backend.keys()
        keys.sort()
        eq_(len(keys), 3)

        daily = self._redis_backend.hgetall(keys[2])
        weekly = self._redis_backend.hgetall(keys[1])
        aggregated = self._redis_backend.get("analy:%s:count:%s" % (user_id, metric, ))

        #each metric should be at 4
        [eq_(int(value), 4) for value in daily.values()]
        [eq_(int(value), 4) for value in weekly.values()]
        eq_(int(aggregated), 4)

    def test_track_count(self):
        user_id = 1234
        metric = "badge:25"

        ok_(self._backend.track_count(user_id, metric))

        keys = self._redis_backend.keys()
        eq_(len(keys), 1)

        aggregated = self._redis_backend.get("analy:%s:count:%s" % (user_id, metric, ))

        #count should be at 1
        eq_(int(aggregated), 1)

        #try incrementing by the non default value
        ok_(self._backend.track_count(user_id, metric, inc_amt=3))

        keys = self._redis_backend.keys()
        eq_(len(keys), 1)

        aggregated = self._redis_backend.get("analy:%s:count:%s" % (user_id, metric, ))

        #count should be at 4
        eq_(int(aggregated), 4)

    def test_get_closest_week(self):
        """
        Gets the closest Monday to the provided date.
        """
        date_april_1 = datetime.date(year=2012, month=4, day=1)
        date_april_2 = datetime.date(year=2012, month=4, day=2)
        date_april_7 = datetime.date(year=2012, month=4, day=7)
        date_april_8 = datetime.date(year=2012, month=4, day=8)
        date_april_9 = datetime.date(year=2012, month=4, day=9)

        monday_march_26 = datetime.date(year=2012, month=3, day=26)
        monday_april_2 = datetime.date(year=2012, month=4, day=2)
        monday_april_9 = datetime.date(year=2012, month=4, day=9)

        eq_(self._backend._get_closest_week(date_april_1), monday_march_26)
        eq_(self._backend._get_closest_week(date_april_2), monday_april_2)
        eq_(self._backend._get_closest_week(date_april_7), monday_april_2)
        eq_(self._backend._get_closest_week(date_april_8), monday_april_2)
        eq_(self._backend._get_closest_week(date_april_9), monday_april_9)

    def test_metric_by_month_over_several_months(self):
        user_id = 1234
        metric = "badge:25"
        from_date = datetime.date(year=2012, month=4, day=2)

        ok_(self._backend.track_metric(user_id, metric, datetime.datetime(year=2012, month=4, day=5), inc_amt=2))
        ok_(self._backend.track_metric(user_id, metric, datetime.datetime(year=2012, month=4, day=7), inc_amt=2))
        ok_(self._backend.track_metric(user_id, metric, datetime.datetime(year=2012, month=4, day=9), inc_amt=2))
        ok_(self._backend.track_metric(user_id, metric, datetime.datetime(year=2012, month=5, day=11), inc_amt=2))
        ok_(self._backend.track_metric(user_id, metric, datetime.datetime(year=2012, month=6, day=18), inc_amt=3))
        ok_(self._backend.track_metric(user_id, metric, datetime.datetime(year=2012, month=4, day=30)))

        series, values = self._backend.get_metric_by_month(user_id, metric, from_date, num_of_months=5)
        eq_(len(series), 5)
        eq_(values["2012-04-01"], 7)
        eq_(values["2012-05-01"], 2)
        eq_(values["2012-06-01"], 3)
        eq_(values["2012-07-01"], 0)
        eq_(values["2012-08-01"], 0)

    def test_metric_by_month_over_several_months_crossing_year_boundry(self):
        user_id = 1234
        metric = "badge:25"
        from_date = datetime.date(year=2011, month=12, day=1)

        ok_(self._backend.track_metric(user_id, metric, datetime.datetime(year=2011, month=12, day=5), inc_amt=2))
        ok_(self._backend.track_metric(user_id, metric, datetime.datetime(year=2011, month=12, day=8), inc_amt=2))
        ok_(self._backend.track_metric(user_id, metric, datetime.datetime(year=2011, month=12, day=30), inc_amt=2))
        ok_(self._backend.track_metric(user_id, metric, datetime.datetime(year=2012, month=1, day=1), inc_amt=2))
        ok_(self._backend.track_metric(user_id, metric, datetime.datetime(year=2012, month=1, day=5), inc_amt=3))
        ok_(self._backend.track_metric(user_id, metric, datetime.datetime(year=2012, month=4, day=7)))

        series, values = self._backend.get_metric_by_month(user_id, metric, from_date, num_of_months=6)
        eq_(len(series), 6)
        eq_(values["2011-12-01"], 6)
        eq_(values["2012-01-01"], 5)
        eq_(values["2012-02-01"], 0)
        eq_(values["2012-03-01"], 0)
        eq_(values["2012-04-01"], 1)
        eq_(values["2012-05-01"], 0)

    def test_metric_by_week_over_several_weeks(self):
        user_id = 1234
        metric = "badge:25"
        from_date = datetime.date(year=2012, month=4, day=2)

        ok_(self._backend.track_metric(user_id, metric, datetime.datetime(year=2012, month=4, day=5), inc_amt=2))
        ok_(self._backend.track_metric(user_id, metric, datetime.datetime(year=2012, month=4, day=7), inc_amt=2))
        ok_(self._backend.track_metric(user_id, metric, datetime.datetime(year=2012, month=4, day=9), inc_amt=2))
        ok_(self._backend.track_metric(user_id, metric, datetime.datetime(year=2012, month=4, day=11), inc_amt=2))
        ok_(self._backend.track_metric(user_id, metric, datetime.datetime(year=2012, month=4, day=18), inc_amt=3))
        ok_(self._backend.track_metric(user_id, metric, datetime.datetime(year=2012, month=4, day=30)))

        series, values = self._backend.get_metric_by_week(user_id, metric, from_date, num_of_weeks=5)
        eq_(len(series), 5)
        eq_(values["2012-04-02"], 4)
        eq_(values["2012-04-09"], 4)
        eq_(values["2012-04-16"], 3)
        eq_(values["2012-04-23"], 0)
        eq_(values["2012-04-30"], 1)

    def test_metric_by_week_over_several_weeks_crossing_year_boundry(self):
        user_id = 1234
        metric = "badge:25"
        from_date = datetime.date(year=2011, month=12, day=1)

        ok_(self._backend.track_metric(user_id, metric, datetime.datetime(year=2011, month=12, day=5), inc_amt=2))
        ok_(self._backend.track_metric(user_id, metric, datetime.datetime(year=2011, month=12, day=8), inc_amt=2))
        ok_(self._backend.track_metric(user_id, metric, datetime.datetime(year=2011, month=12, day=30), inc_amt=2))
        ok_(self._backend.track_metric(user_id, metric, datetime.datetime(year=2012, month=1, day=1), inc_amt=2))
        ok_(self._backend.track_metric(user_id, metric, datetime.datetime(year=2012, month=1, day=5), inc_amt=3))
        ok_(self._backend.track_metric(user_id, metric, datetime.datetime(year=2012, month=4, day=7)))

        series, values = self._backend.get_metric_by_week(user_id, metric, from_date, num_of_weeks=6)
        eq_(len(series), 6)
        eq_(values["2011-11-28"], 0)
        eq_(values["2011-12-05"], 4)
        eq_(values["2011-12-12"], 0)
        eq_(values["2011-12-19"], 0)
        eq_(values["2011-12-26"], 4)
        eq_(values["2012-01-02"], 3)

    def test_get_weekly_date_range(self):
        date = datetime.date(year=2011, month=11, day=1)

        result = self._backend._get_weekly_date_range(date, datetime.timedelta(weeks=12))
        eq_(len(result), 2)
        eq_(result[0], datetime.date(year=2011, month=11, day=1))
        eq_(result[1], datetime.date(year=2012, month=1, day=1))

    def test_get_daily_date_range(self):
        date = datetime.date(year=2011, month=11, day=15)

        result = self._backend._get_daily_date_range(date, datetime.timedelta(days=30))
        eq_(len(result), 2)
        eq_(result[0], datetime.date(year=2011, month=11, day=15))
        eq_(result[1], datetime.date(year=2011, month=12, day=1))

    def test_get_daily_date_range_spans_month_and_year(self):
        date = datetime.date(year=2011, month=11, day=15)

        result = self._backend._get_daily_date_range(date, datetime.timedelta(days=65))
        eq_(len(result), 3)
        eq_(result[0], datetime.date(year=2011, month=11, day=15))
        eq_(result[1], datetime.date(year=2011, month=12, day=1))
        eq_(result[2], datetime.date(year=2012, month=1, day=1))

    def test_metric_by_day(self):
        date = datetime.date(year=2011, month=12, day=1)
        user_id = "user1234"
        metric = "badges:21"

        #track some metrics
        ok_(self._backend.track_metric(user_id, metric, datetime.datetime(year=2011, month=12, day=5), inc_amt=2))
        ok_(self._backend.track_metric(user_id, metric, datetime.datetime(year=2011, month=12, day=8), inc_amt=3))
        ok_(self._backend.track_metric(user_id, metric, datetime.datetime(year=2011, month=12, day=30), inc_amt=5))

        series, values = self._backend.get_metric_by_day(user_id, metric, date, 30)

        eq_(len(series), 30)
        eq_(len(values.keys()), 30)
        eq_(values["2011-12-05"], 2)
        eq_(values["2011-12-08"], 3)
        eq_(values["2011-12-30"], 5)

    def test_metric_by_day_spans_month_year_boundry(self):
        date = datetime.date(year=2011, month=12, day=1)
        user_id = "user1234"
        metric = "badges:21"

        #track some metrics
        ok_(self._backend.track_metric(user_id, metric, datetime.datetime(year=2011, month=12, day=5), inc_amt=2))
        ok_(self._backend.track_metric(user_id, metric, datetime.datetime(year=2011, month=12, day=8), inc_amt=3))
        ok_(self._backend.track_metric(user_id, metric, datetime.datetime(year=2012, month=1, day=1), inc_amt=5))

        series, values = self._backend.get_metric_by_day(user_id, metric, date, 35)

        eq_(len(series), 35)
        eq_(len(values.keys()), 35)
        eq_(values["2011-12-05"], 2)
        eq_(values["2011-12-08"], 3)
        eq_(values["2012-01-01"], 5)
