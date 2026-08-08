import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from app.database.repositories.user_profile_repository import UserProfileRepository
from app.services.llm.base import BaseLLM

logger = logging.getLogger("jarvis.cognitive.profile")

class UserProfileEngine:
    """
    Manages structured user profile keys (e.g. skills, career, preferences, IDEs).
    Supports intelligent appends, conflict resolutions, and audit tracking.
    """
    def __init__(self, profile_repo: UserProfileRepository, llm: Optional[BaseLLM] = None):
        self.profile_repo = profile_repo
        self.llm = llm
        self._status = "healthy"
        self._profile_updates_count = 0

    def get_status(self) -> str:
        return self._status

    def get_telemetry(self) -> Dict[str, Any]:
        return {
            "profile_updates_count": self._profile_updates_count
        }

    async def get_profile_context(self, session_id: str) -> Dict[str, Any]:
        """
        Returns a simplified profile key-value dictionary for prompt building.
        """
        profiles = await self.profile_repo.list_profiles(session_id)
        res = {}
        for p in profiles:
            key = p["profile_key"]
            val_dict = p["profile_value"]
            # Expose only the active values to keep contexts concise
            res[key] = val_dict.get("values", val_dict.get("value", ""))
        return res

    async def update_profile_key(
        self,
        session_id: str,
        key: str,
        operation: str,  # "add", "remove", "set"
        value: Any,
        confidence: float = 1.0,
        source: str = "llm",
        source_memory_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes a profile update operation applying confidence and timeline conflict weights.
        """
        self._profile_updates_count += 1
        key_norm = key.strip().lower()
        existing = await self.profile_repo.get_profile(session_id, key_norm)
        
        now_str = datetime.utcnow().isoformat()
        
        if existing:
            val_dict = existing["profile_value"]
            current_values = val_dict.get("values", [])
            history = val_dict.get("history", [])
        else:
            val_dict = {}
            current_values = []
            history = []

        # Conflict resolution check: If an existing history entry with higher confidence and source='user'
        # overrides the new LLM extraction, we drop the new extraction.
        is_user_override = source == "user"
        
        # Check operation
        if operation == "add":
            if isinstance(value, list):
                to_add = value
            else:
                to_add = [value]
                
            for item in to_add:
                if item not in current_values:
                    current_values.append(item)
                    history.append({
                        "op": "add",
                        "value": item,
                        "confidence": confidence,
                        "source": source,
                        "timestamp": now_str
                    })
                    
        elif operation == "remove":
            if isinstance(value, list):
                to_remove = value
            else:
                to_remove = [value]
                
            for item in to_remove:
                if item in current_values:
                    # Confidence resolution check
                    can_remove = True
                    # If we have a higher confidence user source, prefer it
                    for hist in reversed(history):
                        if hist["value"] == item and hist["source"] == "user" and not is_user_override:
                            can_remove = False
                            break
                    if can_remove:
                        current_values.remove(item)
                        history.append({
                            "op": "remove",
                            "value": item,
                            "confidence": confidence,
                            "source": source,
                            "timestamp": now_str
                        })
                        
        elif operation == "set":
            # Set overrides completely, but must check confidence
            can_set = True
            if existing:
                existing_confidence = existing.get("confidence", 0.0)
                # If existing is source 'user' and new is 'llm', keep existing unless confidence is higher
                has_user_hist = any(h.get("source") == "user" for h in history)
                if has_user_hist and not is_user_override:
                    can_set = False
                    
            if can_set:
                current_values = value if isinstance(value, list) else [value]
                history.append({
                    "op": "set",
                    "value": value,
                    "confidence": confidence,
                    "source": source,
                    "timestamp": now_str
                })

        # Save to repo
        new_val_dict = {
            "values": current_values,
            "history": history[-50:]  # cap history size
        }
        
        updated = await self.profile_repo.update_profile(
            session_id=session_id,
            key=key_norm,
            value_dict=new_val_dict,
            confidence=confidence,
            source_memory_id=source_memory_id
        )
        return updated

    async def extract_and_update_profile(self, text: str, session_id: str) -> None:
        """
        Uses LLM to extract user preference/skill updates and commits them to DB.
        """
        if not self.llm:
            logger.warning("No LLM injected in UserProfileEngine, skipping profile extraction.")
            return

        system_prompt = (
            "You are a user profile extractor. Analyze the input text and extract structured changes to the user's profile.\n"
            "Output ONLY a valid JSON object matching this schema:\n\n"
            "{\n"
            '  "updates": [\n'
            '    {"key": "languages|skills|ide|frameworks|interests|career|preferences|goals|education|habits|routines", "operation": "add|remove|set", "value": "value", "confidence": 0.0-1.0}\n'
            "  ]\n"
            "}\n\n"
            "Rules:\n"
            "1. Do not output any thinking or conversational text.\n"
            "2. Ensure all fields are included in the JSON.\n"
            "3. Normalize operations: 'add' (append item to list), 'remove' (delete item from list), 'set' (override key value).\n"
            "4. Only extract explicit changes mentioned by the user.\n"
            "5. For 'habits' and 'routines', only extract them if recurring behavior is explicitly described (e.g. 'every day', 'weekly', 'routinely'). Do not extract single occurrences."
        )

        try:
            from app.services.llm.generation_config import GenerationConfig
            import json
            import re
            
            from app.models.chat_models import ChatRequest
            chat_req = ChatRequest(message=f"Text:\n{text}")
            
            result = await self.llm.generate_response(
                request=chat_req,
                system_prompt=system_prompt,
                config=GenerationConfig(temperature=0.0)
            )
            
            resp_text = result.response.strip()
            if resp_text.startswith("```"):
                resp_text = re.sub(r"^```(?:json)?\n", "", resp_text)
                resp_text = re.sub(r"\n```$", "", resp_text)
                
            parsed = json.loads(resp_text)
            updates = parsed.get("updates", [])
            
            for up in updates:
                key = up.get("key")
                op = up.get("operation")
                val = up.get("value")
                conf = up.get("confidence", 1.0)
                
                if key and op and val:
                    await self.update_profile_key(
                        session_id=session_id,
                        key=key,
                        operation=op,
                        value=val,
                        confidence=conf,
                        source="llm"
                    )
        except Exception as e:
            logger.error(f"Failed user profile extraction/update: {e}", exc_info=True)
