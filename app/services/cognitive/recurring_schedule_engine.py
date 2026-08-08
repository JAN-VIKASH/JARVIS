from datetime import datetime, timedelta
from typing import List, Optional
from zoneinfo import ZoneInfo
import logging

logger = logging.getLogger("jarvis.cognitive")

class RecurringScheduleEngine:
    """
    Computes occurrences and next occurrences of recurring events.
    Supports daily, weekly, monthly, and weekday patterns.
    """
    @staticmethod
    def validate_rule(rule: str) -> bool:
        if not rule:
            return False
        return rule.strip().lower() in {"daily", "weekly", "weekday", "monthly"}

    @staticmethod
    def calculate_occurrences(
        start_time: datetime,
        rule: str,
        until: Optional[datetime] = None,
        timezone_str: Optional[str] = None,
        count: int = 100
    ) -> List[datetime]:
        rule_norm = rule.strip().lower()
        if rule_norm not in {"daily", "weekly", "weekday", "monthly"}:
            raise ValueError(f"Invalid recurrence rule: {rule}")

        # Resolve timezone info if provided
        tz = None
        if timezone_str:
            try:
                tz = ZoneInfo(timezone_str)
            except Exception as e:
                logger.warning(f"Invalid timezone string '{timezone_str}', falling back to naive: {e}")

        # Localize start_time if timezone info was resolved
        curr = start_time
        if tz:
            if curr.tzinfo is None:
                curr = curr.replace(tzinfo=tz)
            else:
                curr = curr.astimezone(tz)

        # Localize until limit if timezone info was resolved
        until_dt = until
        if until_dt and tz:
            if until_dt.tzinfo is None:
                until_dt = until_dt.replace(tzinfo=tz)
            else:
                until_dt = until_dt.astimezone(tz)

        occurrences = []

        def add_months(dt: datetime, num_months: int) -> datetime:
            total_months = dt.month - 1 + num_months
            year = dt.year + (total_months // 12)
            month = (total_months % 12) + 1
            day = dt.day
            while True:
                try:
                    return dt.replace(year=year, month=month, day=day)
                except ValueError:
                    day -= 1

        curr_occurrence = curr
        for idx in range(count):
            if until_dt and curr_occurrence > until_dt:
                break
            occurrences.append(curr_occurrence)

            if rule_norm == "daily":
                curr_occurrence = curr_occurrence + timedelta(days=1)
            elif rule_norm == "weekly":
                curr_occurrence = curr_occurrence + timedelta(days=7)
            elif rule_norm == "weekday":
                curr_occurrence = curr_occurrence + timedelta(days=1)
                while curr_occurrence.weekday() >= 5:  # Saturday=5, Sunday=6
                    curr_occurrence = curr_occurrence + timedelta(days=1)
            elif rule_norm == "monthly":
                curr_occurrence = add_months(curr, idx + 1)

        # Convert back to naive datetimes if input start_time was naive (matching SQLite naive UTC standard)
        if start_time.tzinfo is None:
            return [o.replace(tzinfo=None) for o in occurrences]
        return occurrences

    @staticmethod
    def get_next_occurrence(
        start_time: datetime,
        rule: str,
        reference_time: datetime,
        timezone_str: Optional[str] = None,
        until: Optional[datetime] = None
    ) -> Optional[datetime]:
        # Generate enough occurrences to find the next one
        occs = RecurringScheduleEngine.calculate_occurrences(
            start_time=start_time,
            rule=rule,
            until=until,
            timezone_str=timezone_str,
            count=366  # limit calculations to 1 year of daily lookups
        )
        for o in occs:
            # Match timezone naive/aware comparison states
            o_cmp = o
            ref_cmp = reference_time
            if o_cmp.tzinfo is not None and ref_cmp.tzinfo is None:
                ref_cmp = ref_cmp.replace(tzinfo=o_cmp.tzinfo)
            elif o_cmp.tzinfo is None and ref_cmp.tzinfo is not None:
                ref_cmp = ref_cmp.replace(tzinfo=None)

            if o_cmp > ref_cmp:
                return o
        return None
