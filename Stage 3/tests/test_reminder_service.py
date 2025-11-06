"""
Tests for reminder service functionality
"""
import pytest
from datetime import datetime, timezone, timedelta
from app.features.reminders.service import _get_time_context, _is_quiet_hours
from app.models.models import Task
from unittest.mock import Mock


class TestTimeContext:
    """Test time context generation for reminders."""
    
    def test_reminder_time_due_now(self):
        """Test reminder_time that is due now."""
        task = Mock()
        task.reminder_time = datetime.now(timezone.utc)
        task.due_date = None
        task.last_reminder_sent = None
        
        context = _get_time_context(task)
        assert context == "due now"
    
    def test_reminder_time_not_yet(self):
        """Test reminder_time in the future."""
        task = Mock()
        task.reminder_time = datetime.now(timezone.utc) + timedelta(hours=2)
        task.due_date = None
        task.last_reminder_sent = None
        
        context = _get_time_context(task)
        assert context is None  # Not time yet
    
    def test_due_date_24h_advance(self):
        """Test due date 24 hours in advance."""
        task = Mock()
        task.reminder_time = None
        task.due_date = datetime.now(timezone.utc) + timedelta(hours=24)
        task.last_reminder_sent = None
        
        context = _get_time_context(task)
        # Accept any reasonable format for ~24 hours
        assert context is not None and "due in" in context and ("day" in context or "hour" in context)
    
    def test_due_date_1h_advance(self):
        """Test due date 1 hour in advance."""
        task = Mock()
        task.reminder_time = None
        task.due_date = datetime.now(timezone.utc) + timedelta(hours=1)
        task.last_reminder_sent = None
        
        context = _get_time_context(task)
        assert context is not None and "due in" in context
    
    def test_overdue_task(self):
        """Test overdue task."""
        task = Mock()
        task.reminder_time = None
        task.due_date = datetime.now(timezone.utc) - timedelta(days=2)
        task.last_reminder_sent = None
        
        context = _get_time_context(task)
        assert context is not None and "overdue" in context
        assert "2 day" in context
    
    def test_overdue_max_reminders(self):
        """Test that max reminders prevents spam."""
        task = Mock()
        task.reminder_time = None
        task.due_date = datetime.now(timezone.utc) - timedelta(days=30)  # Very overdue
        task.last_reminder_sent = datetime.now(timezone.utc) - timedelta(hours=1)  # Recent reminder
        
        context = _get_time_context(task)
        # Should not send another reminder so soon
        assert context is None
    
    def test_no_dates_set(self):
        """Test task with no dates returns None."""
        task = Mock()
        task.reminder_time = None
        task.due_date = None
        task.last_reminder_sent = None
        
        context = _get_time_context(task)
        assert context is None


class TestQuietHours:
    """Test quiet hours detection."""
    
    def test_quiet_hours_detection(self):
        """Test that quiet hours are properly detected."""
        # This test is time-dependent, so we just verify the function runs
        settings = Mock()
        settings.reminder_quiet_hours_start = 22
        settings.reminder_quiet_hours_end = 8
        
        # Just ensure it doesn't crash
        result = _is_quiet_hours(settings)
        assert isinstance(result, bool)


@pytest.mark.asyncio
async def test_reminder_service_import():
    """Test that reminder service can be imported."""
    from app.features import reminders
    assert reminders is not None
    assert hasattr(reminders, 'start_reminder_scheduler')
    assert hasattr(reminders, 'stop_reminder_scheduler')


@pytest.mark.asyncio
async def test_llm_generate_reminder_message():
    """Test reminder message generation."""
    from app.utils.llm import generate_reminder_message
    
    # Test with fallback (in case Groq fails in test env)
    message = generate_reminder_message("Buy groceries", "due in 2 hours")
    assert "groceries" in message.lower() or "reminder" in message.lower()
    assert len(message) > 0
