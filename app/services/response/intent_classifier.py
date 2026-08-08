import re

class IntentClassifier:
    """
    Lightweight, deterministic classifier for user request intents.
    """
    @staticmethod
    def classify(query: str) -> str:
        q_lower = query.lower().strip()
        
        # 1. Greeting
        greeting_patterns = [
            r"^(hello|hi|hey|greetings|good\s+morning|good\s+afternoon|good\s+evening|howdy|yo|sup|nice\s+to\s+meet\s+you)(\s+|$|[,.!])",
        ]
        if any(re.match(p, q_lower) for p in greeting_patterns) or q_lower in {"hello", "hi", "hey"}:
            return "greeting"
            
        # Task & Habit Classification (Phase 5.3)
        task_create_patterns = [
            r"\b(add|create|new|schedule|insert)\s+(a\s+)?task\b",
            r"\badd\s+(a\s+)?todo\b",
            r"\bneed\s+to\s+(remember\s+to\s+)?(do|finish|complete|write|call|check|send)\b",
            r"\badd\s+(.+)\s+to\s+(my\s+)?(tasks|todo|todo\s+list)\b"
        ]
        if any(re.search(p, q_lower) for p in task_create_patterns):
            return "task_create"

        task_query_patterns = [
            r"\bshow\s+(my\s+)?(tasks|todo|todos|pending\s+tasks|active\s+tasks|completed\s+tasks)\b",
            r"\bwhat\s+are\s+my\s+(tasks|todos|pending\s+tasks|active\s+tasks)\b",
            r"\blist\s+(my\s+)?(tasks|todos|pending\s+tasks|active\s+tasks)\b",
            r"\bget\s+(my\s+)?(tasks|todos|pending\s+tasks)\b"
        ]
        if any(re.search(p, q_lower) for p in task_query_patterns):
            return "task_query"

        task_update_patterns = [
            r"\b(complete|finish|done|cancel|reopen|archive|delete|remove)\s+(the\s+)?task\b",
            r"\bmark\s+(the\s+)?task\s+(as\s+)?(completed|complete|done|cancelled|pending)\b",
            r"\b(complete|finish|cancel|reopen|archive|delete|remove)\s+task\s+#?\d+\b",
            r"\bupdate\s+task\b"
        ]
        if any(re.search(p, q_lower) for p in task_update_patterns):
            return "task_update"

        habit_query_patterns = [
            r"\bwhat\s+are\s+my\s+(habits|routines)\b",
            r"\blist\s+(my\s+)?(habits|routines)\b",
            r"\bshow\s+(my\s+)?(habits|routines)\b"
        ]
        if any(re.search(p, q_lower) for p in habit_query_patterns):
            return "habit_query"

        habit_update_patterns = [
            r"\b(add|create|new|save|remember|routinely)\s+(habit|routine)\b",
            r"\bi\s+(always|usually|routinely|every\s+day|every\s+week)\s+\w+\b"
        ]
        if any(re.search(p, q_lower) for p in habit_update_patterns):
            return "habit_update"
            
        # 1a. Schedule Query
        schedule_patterns = [
            r"\b(today|tomorrow|yesterday|monday|tuesday|wednesday|thursday|friday|saturday|sunday)'?s?\s+schedule\b",
            r"\bshow\s+(today|tomorrow|yesterday|monday|tuesday|wednesday|thursday|friday|saturday|sunday)'?s?\s+(schedule|calendar|meetings|events|agenda)\b",
            r"\bwhat\s+(am\s+i\s+doing|do\s+i\s+have|meetings\s+do\s+i\s+have|is\s+my\s+schedule|is\s+on\s+my\s+calendar|is\s+scheduled)\s+(today|tomorrow|yesterday|this\s+week|next\s+week|on\s+\w+)\b",
            r"\bshow\s+(my\s+)?(schedule|agenda|calendar)\b"
        ]
        if any(re.search(p, q_lower) for p in schedule_patterns) or q_lower in {"schedule", "calendar", "agenda"}:
            return "schedule_query"

        # 1b. Timeline Query
        timeline_patterns = [
            r"\bwhat\s+happened\s+(last|yesterday|this|next|past|previous)\b",
            r"\bshow\s+(my\s+)?timeline\b",
            r"\b(daily|weekly|monthly)\s+timeline\b",
            r"\bhistory\s+of\s+events\b",
            r"\bwhat\s+was\s+my\s+timeline\b"
        ]
        if any(re.search(p, q_lower) for p in timeline_patterns) or "timeline" in q_lower:
            return "timeline_query"

        # 1c. Event Query
        event_patterns = [
            r"\bwhen\s+is\s+my\s+\w+\b",
            r"\bdo\s+i\s+have\s+(any\s+)?(meetings|tasks|interviews|milestones|deadlines)\b",
            r"\bwhat\s+(meetings|milestones|deadlines|tasks)\s+do\s+i\s+have\b",
            r"\bwhen\s+is\s+the\s+(interview|meeting|deadline|milestone)\b",
            r"\bget\s+(upcoming|overdue|completed|cancelled|planned)\s+(events|meetings|tasks|milestones)\b"
        ]
        if any(re.search(p, q_lower) for p in event_patterns):
            return "event_query"

        # Complex Goal / Agentic Loop Classification (Phase 7)
        complex_patterns = [
            r"\b(then|and\s+then|after\s+that|sequentially|multiple\s+steps|complex\s+plan)\b",
            r"\b(open|launch|run|click|type|write|focus|close)\b.+\b(then|afterwards|and\s+also|finally)\b",
            r"\bexecute\s+goal\b",
            r"\brun\s+plan\b"
        ]
        if any(re.search(p, q_lower) for p in complex_patterns):
            return "complex_goal"

        # Browser Action Classification (Phase 8)
        browser_patterns = [
            r"\b(open|launch|close)\s+(the\s+)?browser\b",
            r"\b(navigate|go)\s+to\b",
            r"\bopen\s+url\b",
            r"\bclick\s+(button|link|element)\s+on\s+page\b",
            r"\bclick\s+selector\b",
            r"\btype\s+.+\s+in\s+browser\b",
            r"\bread\s+(the\s+)?page\s+content\b",
            r"\bextract\s+page\s+text\b",
            r"\bswitch\s+(browser\s+)?tab\b",
            r"\bclose\s+(browser\s+)?tab\b",
            r"\bscroll\s+(up|down)\s+in\s+browser\b",
            r"\bdownload\s+file\b",
            r"\bupload\s+file\b"
        ]
        if any(re.search(p, q_lower) for p in browser_patterns):
            return "browser_action"

        # Vision Action Classification (Phase 9)
        vision_patterns = [
            r"\b(describe|what\s+is\s+on|see|read|find|look\s+at)\s+(the\s+)?(screen|monitor|display)\b",
            r"\b(ocr\s+screen|screen\s+text)\b"
        ]
        if any(re.search(p, q_lower) for p in vision_patterns):
            return "vision_action"

        # Desktop Action Classification (Phase 6)
        desktop_patterns = [
            r"\b(open|launch)\s+(the\s+)?(notepad|chrome|vscode|explorer)\b",
            r"\b(move\s+(the\s+)?mouse|click\s+(the\s+)?mouse|click\s+at|double\s+click|drag\s+(the\s+)?mouse)\b",
            r"\b(type\s+text|type\s+\w+|press\s+(the\s+)?key|press\s+enter|press\s+space|hit\s+hotkey|execute\s+hotkey)\b",
            r"\b(minimize|maximize|close|focus)\s+(the\s+)?window\b",
            r"\b(list\s+windows|show\s+active\s+window|active\s+window\s+title)\b",
            r"\b(lock\s+(the\s+)?(screen|workstation)|take\s+(a\s+)?screenshot|screenshot|mute\s+volume|set\s+volume|adjust\s+volume)\b",
            r"\b(set\s+brightness|toggle\s+audio|audio\s+output\s+device)\b"
        ]
        if any(re.search(p, q_lower) for p in desktop_patterns):
            return "desktop_action"

        # 2. Memory Recall (asking about stored memories/facts)
        recall_patterns = [
            r"^(what|who|where|when|which|how|do)\s+(is|was|are|were|do|know|remember|recall)\s+(my|favorite|favourite|previously|previously\s+my)\b",
            r"\b(what|which)\s+(languages|language|color|colour|name|birthday|age|location|occupation)\b.*\b(do\s+i|my)\b",
            r"\bdo\s+you\s+(know|remember|recall)\s+(my|who\s+i|what\s+i)\b",
            r"^what\s+is\s+my\s+",
            r"^what\s+was\s+my\s+",
            r"^tell\s+me\s+my\s+"
        ]
        if any(re.search(p, q_lower) for p in recall_patterns):
            return "memory_recall"
            
        # 3. Memory Update (declaring facts/preferences)
        update_patterns = [
            r"^(my\s+(name|age|birthday|location|occupation|goal)\s+is)\b",
            r"^(my\s+(?:favorite|favourite)(?:\s+\w+)?\s+is)\b",
            r"^(i\s+(like|love|prefer|work\s+as|live\s+in|am))\b",
            r"^(actually\s+)?my\s+(name|age|location)\s+(is|was)\b",
            r"^(actually\s+)?my\s+(?:favorite|favourite)(?:\s+\w+)?\s+(is|was)\b",
            r"^remember\s+(that|to)\b"
        ]
        if any(re.search(p, q_lower) for p in update_patterns):
            return "memory_update"
            
        # 4. Coding Help
        coding_keywords = {
            "code", "python", "java", "javascript", "c++", "c#", "rust", "golang", "programming",
            "function", "class", "method", "variable", "syntax", "compile", "debug", "html", "css",
            "json", "yaml", "sql", "git", "github", "refactor", "algorithm", "regex", "array", "list",
            "dict", "dictionary", "loop", "recursion", "api", "database", "orm", "fastapi"
        }
        words = set(re.findall(r"\b\w+\b", q_lower))
        if words.intersection(coding_keywords):
            return "coding_help"
            
        # 5. Explanation
        explanation_patterns = [
            r"^explain\b",
            r"^what\s+is\s+(the|a|an)?\s*(architecture|concept|difference|theory|purpose|jvm|framework)\b",
            r"^how\s+(does|do|can|is)\s+\w+\s+(work|interact|process|happen)\b",
            r"^why\s+(is|does|do|are|can)\b",
            r"^describe\b"
        ]
        if any(re.search(p, q_lower) for p in explanation_patterns) or "explain" in q_lower or "difference between" in q_lower:
            return "explanation"
            
        # 6. Brainstorming
        brainstorm_keywords = {
            "brainstorm", "ideas", "suggest", "recommend", "create a list", "creative",
            "inspiration", "alternatives", "options", "give me some", "write a story"
        }
        if any(kw in q_lower for kw in brainstorm_keywords):
            return "brainstorming"
            
        # 7. Simple Fact Question (general knowledge questions)
        fact_indicators = {"what is", "who is", "where is", "when did", "capital of", "population of", "distance to"}
        if any(q_lower.startswith(fi) for fi in fact_indicators):
            return "simple_fact_question"
            
        # 8. Conversation (fallback)
        return "conversation"
