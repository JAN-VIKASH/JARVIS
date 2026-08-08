import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from app.services.cognitive.recurring_schedule_engine import RecurringScheduleEngine

class TestRecurrenceEngine(unittest.TestCase):
    def test_rule_validation(self):
        self.assertTrue(RecurringScheduleEngine.validate_rule("daily"))
        self.assertTrue(RecurringScheduleEngine.validate_rule("WEEKLY"))
        self.assertTrue(RecurringScheduleEngine.validate_rule(" weekday "))
        self.assertTrue(RecurringScheduleEngine.validate_rule("monthly"))
        self.assertFalse(RecurringScheduleEngine.validate_rule("yearly"))
        self.assertFalse(RecurringScheduleEngine.validate_rule(None))

    def test_daily_recurrence(self):
        start = datetime(2026, 8, 8, 10, 0, 0)
        # Calculate 5 daily occurrences
        occs = RecurringScheduleEngine.calculate_occurrences(
            start_time=start,
            rule="daily",
            count=5
        )
        self.assertEqual(len(occs), 5)
        self.assertEqual(occs[0], start)
        self.assertEqual(occs[1], start + timedelta(days=1))
        self.assertEqual(occs[4], start + timedelta(days=4))

    def test_weekly_recurrence(self):
        start = datetime(2026, 8, 8, 10, 0, 0)  # Saturday
        occs = RecurringScheduleEngine.calculate_occurrences(
            start_time=start,
            rule="weekly",
            count=3
        )
        self.assertEqual(len(occs), 3)
        self.assertEqual(occs[0], start)
        self.assertEqual(occs[1], start + timedelta(days=7))
        self.assertEqual(occs[2], start + timedelta(days=14))

    def test_weekday_recurrence(self):
        # August 7, 2026 is Friday
        start = datetime(2026, 8, 7, 10, 0, 0)
        occs = RecurringScheduleEngine.calculate_occurrences(
            start_time=start,
            rule="weekday",
            count=5
        )
        self.assertEqual(len(occs), 5)
        # Fri, Mon, Tue, Wed, Thu
        self.assertEqual(occs[0].strftime("%A"), "Friday")
        self.assertEqual(occs[1].strftime("%A"), "Monday")
        self.assertEqual(occs[2].strftime("%A"), "Tuesday")
        self.assertEqual(occs[3].strftime("%A"), "Wednesday")
        self.assertEqual(occs[4].strftime("%A"), "Thursday")

    def test_monthly_recurrence_and_rollover(self):
        # Test rollover from Jan 31 to Feb
        start = datetime(2026, 1, 31, 10, 0, 0)
        occs = RecurringScheduleEngine.calculate_occurrences(
            start_time=start,
            rule="monthly",
            count=3
        )
        self.assertEqual(len(occs), 3)
        self.assertEqual(occs[0], start)
        # Feb 28 in 2026 (non-leap year)
        self.assertEqual(occs[1], datetime(2026, 2, 28, 10, 0, 0))
        # March 31
        self.assertEqual(occs[2], datetime(2026, 3, 31, 10, 0, 0))

    def test_until_date_boundaries(self):
        start = datetime(2026, 8, 8, 10, 0, 0)
        until = datetime(2026, 8, 10, 12, 0, 0)
        # Daily should only yield 3 occurrences (Aug 8, Aug 9, Aug 10)
        occs = RecurringScheduleEngine.calculate_occurrences(
            start_time=start,
            rule="daily",
            until=until,
            count=100
        )
        self.assertEqual(len(occs), 3)
        self.assertEqual(occs[0], datetime(2026, 8, 8, 10, 0, 0))
        self.assertEqual(occs[1], datetime(2026, 8, 9, 10, 0, 0))
        self.assertEqual(occs[2], datetime(2026, 8, 10, 10, 0, 0))

    def test_timezone_localization(self):
        start = datetime(2026, 8, 8, 10, 0, 0)
        # Attempt to resolve zone info, falling back to a fixed offset on Windows if tzdata is missing
        tz_name = "America/New_York"
        try:
            ny_tz = ZoneInfo(tz_name)
        except Exception:
            from datetime import timezone, timedelta
            ny_tz = timezone(timedelta(hours=-5))
            tz_name = None  # force calculate_occurrences to fall back or use custom zone info
            
        # If tzdata is missing on Windows, passing America/New_York to calculate_occurrences will trigger a warning.
        # So we pass the resolved tz_name or pass a dummy one if we are testing fallback
        occs = RecurringScheduleEngine.calculate_occurrences(
            start_time=start,
            rule="daily",
            timezone_str="America/New_York" if tz_name else None,
            count=3
        )
        self.assertEqual(len(occs), 3)
        if tz_name:
            self.assertEqual(occs[0].tzinfo, ny_tz)
        else:
            # If fallback triggered, our engine will have generated naive UTC times since it fell back to naive.
            # Assert they are naive datetimes
            self.assertIsNone(occs[0].tzinfo)

    def test_get_next_occurrence(self):
        start = datetime(2026, 8, 8, 10, 0, 0)  # Saturday
        ref = datetime(2026, 8, 9, 12, 0, 0)    # Sunday Noon
        
        # Next weekly occurrence after Sunday Noon should be next Saturday (Aug 15)
        next_occ = RecurringScheduleEngine.get_next_occurrence(
            start_time=start,
            rule="weekly",
            reference_time=ref
        )
        self.assertEqual(next_occ, datetime(2026, 8, 15, 10, 0, 0))
