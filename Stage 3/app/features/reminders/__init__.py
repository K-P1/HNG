"""
Reminder feature module: Autonomous task deadline reminders via push notifications
"""
from .service import start_reminder_scheduler, stop_reminder_scheduler, is_scheduler_running

__all__ = ["start_reminder_scheduler", "stop_reminder_scheduler", "is_scheduler_running"]
