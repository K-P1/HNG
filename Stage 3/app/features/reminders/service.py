"""
Reminder Service: Background scheduler for autonomous task deadline reminders
"""
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import get_settings
from app import crud
from app.utils.llm import generate_reminder_message
from app.utils.telex_push import send_telex_followup

logger = logging.getLogger("reminder_service")

# Global scheduler instance
_scheduler: Optional[AsyncIOScheduler] = None


def _is_quiet_hours(settings) -> bool:
    """Check if current time is within quiet hours."""
    now = datetime.now(timezone.utc)
    current_hour = now.hour
    
    start = settings.reminder_quiet_hours_start
    end = settings.reminder_quiet_hours_end
    
    # Handle quiet hours that wrap around midnight
    if start < end:
        return start <= current_hour < end
    else:
        return current_hour >= start or current_hour < end


def _get_time_context(task) -> Optional[str]:
    """
    Generate time context string for a task.
    Returns None if no reminder should be sent yet.
    """
    now = datetime.now(timezone.utc)
    settings = get_settings()
    
    # Parse advance hours from config
    advance_hours = [int(h.strip()) for h in settings.reminder_advance_hours.split(",") if h.strip().isdigit()]
    
    # Check reminder_time first (explicit "remind me in X" scenarios)
    if task.reminder_time:
        if task.reminder_time <= now:
            delta = now - task.reminder_time
            if delta.total_seconds() < 300:  # Within 5 minutes
                return "due now"
            else:
                return None  # Already passed, don't send late reminders
        else:
            return None  # Not yet time
    
    # Check due_date
    if task.due_date:
        time_until = task.due_date - now
        hours_until = time_until.total_seconds() / 3600
        
        # Check if overdue
        if hours_until < 0:
            days_overdue = abs(int(hours_until / 24))
            hours_overdue = abs(int(hours_until % 24))
            
            # Check if we should send overdue reminder
            if task.last_reminder_sent:
                hours_since_last = (now - task.last_reminder_sent).total_seconds() / 3600
                if hours_since_last < settings.reminder_overdue_interval_hours:
                    return None
                
                # Count how many reminders sent
                days_since_due = abs(hours_until) / 24
                estimated_reminders = int(days_since_due / (settings.reminder_overdue_interval_hours / 24))
                if estimated_reminders >= settings.reminder_max_overdue_reminders:
                    return None
            
            if days_overdue > 0:
                return f"overdue by {days_overdue} day{'s' if days_overdue != 1 else ''}"
            elif hours_overdue > 0:
                return f"overdue by {hours_overdue} hour{'s' if hours_overdue != 1 else ''}"
            else:
                return "overdue"
        
        # Check advance reminders
        for advance_h in sorted(advance_hours, reverse=True):
            if advance_h - 0.5 <= hours_until <= advance_h + 0.5:  # Within 30min window
                # Check if already reminded for this window
                if task.last_reminder_sent:
                    hours_since_last = (now - task.last_reminder_sent).total_seconds() / 3600
                    if hours_since_last < 0.5:  # Don't spam within 30min
                        return None
                
                if hours_until >= 24:
                    days = int(hours_until / 24)
                    return f"due in {days} day{'s' if days != 1 else ''}"
                elif hours_until >= 2:
                    hours = int(hours_until)
                    return f"due in {hours} hours"
                elif hours_until >= 1:
                    return "due in 1 hour"
                else:
                    mins = int(hours_until * 60)
                    return f"due in {mins} minutes"
        
        # At deadline (within 5 min)
        if -0.08 <= hours_until <= 0.08:  # ~5 minutes window
            return "due now"
    
    return None


async def check_and_send_reminders():
    """Check all tasks and send reminders where needed."""
    settings = get_settings()
    
    # Skip during quiet hours
    if _is_quiet_hours(settings):
        return
    
    try:
        # Get all tasks that might need reminders
        tasks = await crud.get_tasks_needing_reminders()
        
        if not tasks:
            return
        
        reminders_sent = 0
        
        for task in tasks:
            try:
                # Determine if reminder should be sent
                time_context = _get_time_context(task)
                
                if not time_context:
                    continue
                
                # Get user's push configuration
                user = await crud.get_user(task.user_id)
                if not user or not user.push_url:
                    logger.warning("No push_url configured for user %s, skipping reminder", task.user_id)
                    continue
                
                # Generate reminder message
                reminder_msg = generate_reminder_message(task.description, time_context)
                
                # Prepare push config for authentication
                push_config = {}
                if user.push_token:
                    push_config = {"authentication": {"credentials": user.push_token}}
                
                # Prepare task data as artifact
                task_data = [{
                    "kind": "data",
                    "data": {
                        "task": {
                            "id": task.id,
                            "description": task.description,
                            "status": task.status,
                            "due_date": task.due_date.isoformat() if task.due_date else None,
                            "reminder_time": task.reminder_time.isoformat() if task.reminder_time else None,
                        }
                    }
                }]
                
                # Send reminder with unique IDs
                import uuid
                reminder_request_id = str(uuid.uuid4())
                reminder_context_id = str(uuid.uuid4())
                
                await send_telex_followup(
                    push_url=user.push_url,
                    message=reminder_msg,
                    push_config=push_config,
                    request_id=reminder_request_id,
                    context_id=reminder_context_id,
                    additional_parts=task_data
                )
                
                # Mark reminder as sent
                await crud.mark_reminder_sent(task.id)
                
                reminders_sent += 1
                logger.info("Sent reminder for task %d: %s", task.id, time_context)
                
            except Exception as e:
                logger.error("Failed to send reminder for task %d: %s", task.id, e)
                continue
        
        if reminders_sent > 0:
            logger.info("Sent %d reminder(s) this cycle", reminders_sent)
        
    except Exception as e:
        logger.error("Error in reminder check cycle: %s", e)


async def start_reminder_scheduler():
    """Start the background reminder scheduler."""
    global _scheduler
    
    if _scheduler is not None:
        logger.warning("Scheduler already running")
        return
    
    settings = get_settings()
    
    _scheduler = AsyncIOScheduler()
    
    # Schedule reminder checks
    _scheduler.add_job(
        check_and_send_reminders,
        trigger=IntervalTrigger(minutes=settings.reminder_check_interval_minutes),
        id="reminder_checker",
        name="Check and send task reminders",
        replace_existing=True,
        max_instances=1,  # Prevent overlapping runs
    )
    
    _scheduler.start()
    logger.info("Reminder scheduler started (checking every %d minutes)", settings.reminder_check_interval_minutes)


async def stop_reminder_scheduler():
    """Stop the background reminder scheduler."""
    global _scheduler
    
    if _scheduler is None:
        logger.warning("Scheduler not running")
        return
    
    _scheduler.shutdown(wait=False)
    _scheduler = None
    logger.info("Reminder scheduler stopped")


def is_scheduler_running() -> bool:
    """Check if scheduler is running."""
    return _scheduler is not None and _scheduler.running
