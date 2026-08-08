import asyncio
import unittest
from datetime import datetime, timedelta
from app.database.migrations import init_db
from app.database.session import get_async_session
from app.database.models import TaskModel
from memory.memory_factory import MemoryFactory
from app.services.task_service import TaskService
from sqlalchemy import text

class TestTaskOperations(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Initialize database and tables
        await init_db()
        
        # Clean tasks table before each test
        async with get_async_session() as session:
            await session.execute(text("DELETE FROM tasks"))
            await session.commit()
            
        self.sqlite_repo = MemoryFactory.get_sqlite_repo()
        self.task_service = TaskService(self.sqlite_repo)

    async def test_create_and_retrieve_task(self):
        session_id = "test_sess_1"
        due = datetime.utcnow() + timedelta(days=2)
        
        # 1. Create task
        task = await self.task_service.create_task(
            session_id=session_id,
            title="Finish Homework",
            description="Math and Physics",
            status="pending",
            importance=80,
            due_date=due
        )
        self.assertIsNotNone(task["id"])
        self.assertEqual(task["title"], "Finish Homework")
        self.assertEqual(task["status"], "pending")
        self.assertEqual(task["importance"], 80)
        self.assertEqual(task["due_date"], due)
        self.assertFalse(task["is_overdue"])
        self.assertTrue(task["is_upcoming"])

        # 2. Retrieve task
        retrieved = await self.task_service.retrieve_task(session_id, task["id"])
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["title"], "Finish Homework")
        self.assertEqual(retrieved["version"], 1)

    async def test_session_isolation(self):
        # Create task in session 1
        task_s1 = await self.task_service.create_task(
            session_id="session_A",
            title="Wash Dishes",
            importance=30
        )
        # Create task in session 2
        task_s2 = await self.task_service.create_task(
            session_id="session_B",
            title="Wash Dishes",  # Same title, but different session
            importance=50
        )
        self.assertNotEqual(task_s1["id"], task_s2["id"])
        
        # Assert list is isolated
        tasks_a = await self.task_service.list_tasks("session_A")
        tasks_b = await self.task_service.list_tasks("session_B")
        
        self.assertEqual(len(tasks_a), 1)
        self.assertEqual(tasks_a[0]["id"], task_s1["id"])
        self.assertEqual(len(tasks_b), 1)
        self.assertEqual(tasks_b[0]["id"], task_s2["id"])

    async def test_lifecycle_transitions(self):
        session_id = "test_lifecycle"
        task = await self.task_service.create_task(
            session_id=session_id,
            title="Read Book"
        )
        task_id = task["id"]
        self.assertEqual(task["status"], "pending")

        # pending -> in_progress (valid)
        task = await self.task_service.update_status(session_id, task_id, "in_progress")
        self.assertEqual(task["status"], "in_progress")
        self.assertEqual(task["version"], 2)

        # in_progress -> completed (valid)
        task = await self.task_service.complete_task(session_id, task_id)
        self.assertEqual(task["status"], "completed")

        # completed -> pending (valid)
        task = await self.task_service.reopen_task(session_id, task_id)
        self.assertEqual(task["status"], "pending")

        # pending -> cancelled (valid)
        task = await self.task_service.cancel_task(session_id, task_id)
        self.assertEqual(task["status"], "cancelled")

        # cancelled -> pending (valid)
        task = await self.task_service.reopen_task(session_id, task_id)
        self.assertEqual(task["status"], "pending")

        # Test invalid transition: completed -> in_progress (should raise ValueError)
        task = await self.task_service.complete_task(session_id, task_id)
        with self.assertRaises(ValueError):
            await self.task_service.update_status(session_id, task_id, "in_progress")

        # Test invalid transition: cancelled -> completed (should raise ValueError)
        task = await self.task_service.reopen_task(session_id, task_id)
        task = await self.task_service.cancel_task(session_id, task_id)
        with self.assertRaises(ValueError):
            await self.task_service.update_status(session_id, task_id, "completed")

    async def test_soft_deletion_and_archiving(self):
        session_id = "test_cleanup"
        task = await self.task_service.create_task(
            session_id=session_id,
            title="Unwanted Task"
        )
        task_id = task["id"]

        # standard list returns it
        active_list = await self.task_service.list_tasks(session_id)
        self.assertEqual(len(active_list), 1)

        # Archive task
        archived = await self.task_service.archive_task(session_id, task_id)
        self.assertTrue(archived)

        # archived should be hidden in standard list
        active_list = await self.task_service.list_tasks(session_id)
        self.assertEqual(len(active_list), 0)

        # Soft delete task
        deleted = await self.task_service.soft_delete_task(session_id, task_id)
        self.assertTrue(deleted)

        # Verify not returned in get/retrieve
        retrieved = await self.task_service.retrieve_task(session_id, task_id)
        self.assertIsNone(retrieved)

    async def test_due_date_and_overdue(self):
        session_id = "test_dates"
        past_due = datetime.utcnow() - timedelta(hours=2)
        
        # 1. Create overdue task
        task = await self.task_service.create_task(
            session_id=session_id,
            title="Late Report",
            due_date=past_due
        )
        self.assertTrue(task["is_overdue"])
        self.assertFalse(task["is_upcoming"])

        # 2. Complete overdue task (should no longer be overdue)
        completed = await self.task_service.complete_task(session_id, task["id"])
        self.assertFalse(completed["is_overdue"])
        self.assertFalse(completed["is_upcoming"])
