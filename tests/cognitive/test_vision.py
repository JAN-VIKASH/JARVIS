import os
import time
import json
import unittest
from unittest.mock import MagicMock, patch

from app.services.vision_service import VisionService
from app.services.factory import ServiceFactory
from app.services.chat_service import ChatService
from app.agent.executor import ExecutionEngine
from app.agent.models import AgentPlan, AgentStep
from app.database.migrations import init_db

class TestVisionService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await init_db()
        self.vision_service = VisionService(testing=True)
        
    async def test_screenshot_lifecycle_success(self):
        # 1. Capture screen creates mock file
        filepath = await self.vision_service.capture_screen("test_sess")
        self.assertTrue(os.path.exists(filepath))
        
        # Debounce/caching checks
        cached_filepath = await self.vision_service.capture_screen("test_sess")
        self.assertEqual(filepath, cached_filepath)
        
        # 2. Clean screenshot purges file
        self.vision_service.clean_screenshot(filepath)
        self.assertFalse(os.path.exists(filepath))

    async def test_screenshot_lifecycle_failure_logging(self):
        # Trigger cleanup on non-existent path
        with self.assertLogs("jarvis", level="ERROR") as cm:
            # Pass a path that triggers exception or delete error
            # We can patch os.remove to raise OSError and mock os.path.exists to return True
            with patch("os.path.exists", return_value=True), patch("os.remove", side_effect=OSError("Perm denied")):
                self.vision_service.clean_screenshot("some_temp_file.png")
            
            # Verify only metadata / path is logged, never bytes
            log_output = "\n".join(cm.output)
            self.assertIn("Failed to delete screenshot metadata", log_output)
            self.assertNotIn("bytes", log_output)

    async def test_ocr_tesseract_available(self):
        # Mock tesseract binary as available
        with patch.object(self.vision_service, "_is_tesseract_available", return_value=True):
            filepath = await self.vision_service.capture_screen("test_sess")
            
            # Mock pytesseract image_to_data
            mock_data = {
                'level': [1, 2],
                'text': ['Login', 'Submit'],
                'left': [100, 300],
                'top': [200, 200],
                'width': [100, 100],
                'height': [50, 50]
            }
            
            with patch("pytesseract.image_to_data", return_value=mock_data):
                res = await self.vision_service.perform_ocr(filepath)
                self.assertEqual(len(res), 2)
                self.assertEqual(res[0]["text"], "Login")
                self.assertEqual(res[0]["center"], [150, 225])
            
            self.vision_service.clean_screenshot(filepath)

    async def test_ocr_tesseract_unavailable_fallback(self):
        # Mock tesseract binary as unavailable
        with patch.object(self.vision_service, "_is_tesseract_available", return_value=False):
            filepath = await self.vision_service.capture_screen("test_sess")
            
            # Verify fallback to MockOCREngine
            res = await self.vision_service.perform_ocr(filepath, query_text="Submit")
            self.assertEqual(len(res), 1)
            self.assertEqual(res[0]["text"], "Submit")
            self.assertEqual(res[0]["center"], [350, 225])
            
            self.vision_service.clean_screenshot(filepath)

    async def test_find_element_coordinates(self):
        # Find element coordinates purges screenshot automatically
        res = await self.vision_service.find_element_coordinates("test_sess", "Login")
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["target"], "Login")
        self.assertTrue(len(res["matches"]) > 0)
        self.assertEqual(res["matches"][0]["text"], "Login")

    async def test_model_unavailable_behavior(self):
        # Test non-testing mode where model is absent
        absent_service = VisionService(testing=False, model_path="models/vision/absent_model_weights.onnx")
        res = await absent_service.describe_screen("test_sess", "Describe screen contents")
        self.assertEqual(res["status"], "MODEL_UNAVAILABLE")
        self.assertIn("VLM model weights are missing", res["message"])

    async def test_vlm_inference_success_and_release(self):
        res = await self.vision_service.describe_screen("test_sess", "what is on my screen?")
        self.assertEqual(res["status"], "SUCCESS")
        self.assertIn("blue screen containing button elements", res["description"])
        
        # Test release resources does not crash
        self.vision_service.release_vlm_resources()
        self.assertFalse(self.vision_service._vlm_model_loaded)

    async def test_executor_vision_routing(self):
        # Mock DesktopAutomationService
        mock_desktop = MagicMock()
        mock_desktop._classify_safety_tier.return_value = "SAFE"
        
        # Create execution engine with mock desktop and our testing vision_service
        executor = ExecutionEngine(desktop_service=mock_desktop, vision_service=self.vision_service)
        
        # Formulate steps calling vision tools
        plan = AgentPlan(
            plan_id="plan_vis_1",
            goal="Take screenshot and describe",
            created_at=time.time(),
            updated_at=time.time(),
            steps=[
                AgentStep(
                    step_id=1,
                    description="Take a screenshot",
                    selected_tool="take_screenshot",
                    parameters={}
                ),
                AgentStep(
                    step_id=2,
                    description="Describe screen visual content",
                    selected_tool="describe_screen",
                    parameters={"prompt": "Describe my screen"},
                    prerequisites=[1]
                )
            ]
        )
        
        res = await executor.execute_plan(plan, "session_vis")
        self.assertEqual(plan.status, "SUCCESS")
        self.assertIn("completed successfully", res.lower() or "completed" in res.lower() or "success" in res.lower())
        
        # Verify both steps succeeded
        self.assertEqual(plan.steps[0].status, "COMPLETED")
        self.assertTrue("screenshot_" in plan.steps[0].result)
        self.assertEqual(plan.steps[1].status, "COMPLETED")
        
        parsed_result = json.loads(plan.steps[1].result)
        self.assertEqual(parsed_result["status"], "SUCCESS")
        self.assertIn("blue screen", parsed_result["description"])
