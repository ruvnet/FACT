"""
FACT System Conversation Management

This module handles conversation context, multi-turn interactions,
and maintains conversation state to improve agentic flow continuity.
"""

import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class ConversationTurn:
    """Represents a single conversation turn."""

    timestamp: float
    user_input: str
    assistant_response: str
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    tool_results: List[Dict[str, Any]] = field(default_factory=list)
    context_used: Optional[str] = None


@dataclass
class ConversationContext:
    """Manages conversation context and state."""

    conversation_id: str
    turns: List[ConversationTurn] = field(default_factory=list)
    current_topic: Optional[str] = None
    pending_actions: List[str] = field(default_factory=list)
    database_context: Dict[str, Any] = field(default_factory=dict)

    def add_turn(
        self,
        user_input: str,
        assistant_response: str,
        tool_calls: List[Dict[str, Any]] = None,
        tool_results: List[Dict[str, Any]] = None,
    ) -> None:
        """Add a new conversation turn."""
        turn = ConversationTurn(
            timestamp=time.time(),
            user_input=user_input,
            assistant_response=assistant_response,
            tool_calls=tool_calls or [],
            tool_results=tool_results or [],
        )
        self.turns.append(turn)

        # Detect incomplete responses and add pending actions
        incomplete_actions = self.detect_incomplete_response(assistant_response)
        for action in incomplete_actions:
            self.add_pending_action(action)

        # Keep only last 10 turns to manage memory
        if len(self.turns) > 10:
            self.turns = self.turns[-10:]

    def get_context_summary(self) -> str:
        """Generate a context summary for the LLM."""
        if not self.turns:
            return ""

        context_parts = []

        # Add current topic if available
        if self.current_topic:
            context_parts.append(f"Current conversation topic: {self.current_topic}")

        # Add pending actions
        if self.pending_actions:
            context_parts.append(f"Pending actions: {', '.join(self.pending_actions)}")

        # Add recent conversation history (last 3 turns)
        recent_turns = self.turns[-3:]
        if len(recent_turns) > 1:  # Only add if there's actual history
            context_parts.append("Recent conversation:")
            for i, turn in enumerate(recent_turns[:-1], 1):  # Exclude current turn
                context_parts.append(f"  {i}. User: {turn.user_input[:100]}...")
                if turn.assistant_response:
                    context_parts.append(
                        f"     Assistant: {turn.assistant_response[:100]}..."
                    )

        return "\n".join(context_parts) if context_parts else ""

    def detect_topic(self, user_input: str) -> None:
        """Detect and update current conversation topic."""
        # Simple keyword-based topic detection
        topics = {
            "revenue": ["revenue", "sales", "income", "earnings"],
            "companies": ["company", "companies", "business", "organization"],
            "financial_analysis": ["compare", "trend", "analysis", "performance"],
            "database_schema": ["schema", "tables", "structure", "database"],
        }

        user_lower = user_input.lower()
        for topic, keywords in topics.items():
            if any(keyword in user_lower for keyword in keywords):
                self.current_topic = topic
                break

    def add_pending_action(self, action: str) -> None:
        """Add a pending action to be completed."""
        if action not in self.pending_actions:
            self.pending_actions.append(action)
            logger.info("Added pending action", action=action)

    def complete_action(self, action: str) -> None:
        """Mark an action as completed."""
        if action in self.pending_actions:
            self.pending_actions.remove(action)
            logger.info("Completed action", action=action)

    def clear_pending_actions(self) -> None:
        """Clear all pending actions."""
        self.pending_actions.clear()
        logger.info("Cleared all pending actions")

    def detect_incomplete_response(self, response: str) -> List[str]:
        """Detect if response is incomplete and suggest follow-up actions."""
        incomplete_indicators = [
            "Next, I will",
            "I will now",
            "Let me",
            "I'll retrieve",
            "I'll query",
            "I'll get",
            "I'll show",
            "I'll analyze",
            "Looking at",
            "I see that",
        ]

        suggested_actions = []
        response_lower = response.lower()

        # Check for incomplete indicators
        for indicator in incomplete_indicators:
            if indicator.lower() in response_lower:
                # Extract what was promised
                if "retrieve" in response_lower or "query" in response_lower:
                    suggested_actions.append(
                        "Execute the database query to get the data"
                    )
                elif "show" in response_lower or "display" in response_lower:
                    suggested_actions.append("Display the requested information")
                elif "analyze" in response_lower or "compare" in response_lower:
                    suggested_actions.append("Perform the analysis as mentioned")
                break

        # Check for specific incomplete patterns
        if "companies in the technology sector" in response_lower:
            suggested_actions.append("Query and display Technology sector companies")
        elif "revenue trends" in response_lower:
            suggested_actions.append(
                "Query and analyze revenue trends across companies"
            )
        elif "compare" in response_lower and "companies" in response_lower:
            suggested_actions.append("Compare companies as requested")

        return suggested_actions


class ConversationManager:
    """Manages conversation contexts and provides enhanced prompting."""

    def __init__(self):
        """Initialize conversation manager."""
        self.conversations: Dict[str, ConversationContext] = {}
        self.current_conversation_id: Optional[str] = None

    def start_conversation(self, conversation_id: Optional[str] = None) -> str:
        """Start a new conversation or get existing one."""
        if conversation_id is None:
            conversation_id = f"conv_{int(time.time() * 1000)}"

        if conversation_id not in self.conversations:
            self.conversations[conversation_id] = ConversationContext(conversation_id)
            logger.info("Started new conversation", conversation_id=conversation_id)

        self.current_conversation_id = conversation_id
        return conversation_id

    def get_current_context(self) -> Optional[ConversationContext]:
        """Get current conversation context."""
        if self.current_conversation_id:
            return self.conversations.get(self.current_conversation_id)
        return None

    def enhance_system_prompt(self, base_prompt: str, user_input: str) -> str:
        """Enhance system prompt with conversation context."""
        context = self.get_current_context()
        if not context:
            return base_prompt

        # Update topic based on current input
        context.detect_topic(user_input)

        # Get context summary
        context_summary = context.get_context_summary()

        enhanced_prompt = base_prompt

        if context_summary:
            enhanced_prompt += f"\n\nCONVERSATION CONTEXT:\n{context_summary}"

        # Add specific guidance based on context
        if context.pending_actions:
            enhanced_prompt += "\n\nIMPORTANT: You have pending actions to complete. Make sure to follow through with the necessary tool calls to provide complete answers."

        # Add topic-specific guidance
        if context.current_topic == "revenue":
            enhanced_prompt += "\n\nCONTEXT: User is interested in revenue/financial data. Use SQL tools to get specific numbers and trends."
        elif context.current_topic == "companies":
            enhanced_prompt += "\n\nCONTEXT: User is asking about companies. Use SQL tools to get company information and details."
        elif context.current_topic == "financial_analysis":
            enhanced_prompt += "\n\nCONTEXT: User wants financial analysis/comparisons. Execute queries to get data, then provide insights and comparisons."

        enhanced_prompt += "\n\nCRITICAL: Always complete your analysis. If you identify relevant data to retrieve, execute the SQL queries and provide the actual results, not just acknowledgments."

        return enhanced_prompt

    def should_auto_continue(self) -> bool:
        """Check if system should automatically continue with pending actions."""
        context = self.get_current_context()
        return bool(context and context.pending_actions)

    def generate_follow_up_prompt(self) -> Optional[str]:
        """Generate a follow-up prompt to complete pending actions."""
        context = self.get_current_context()
        if not context or not context.pending_actions:
            return None

        # Generate prompt based on pending actions
        action = context.pending_actions[0]  # Take first pending action

        if "query" in action.lower() and "technology sector" in action.lower():
            return "Show me all companies in the Technology sector"
        elif "revenue trends" in action.lower():
            return "Compare revenue trends across companies"
        elif "analysis" in action.lower():
            return "Please complete the analysis as mentioned"
        elif "query" in action.lower() or "database" in action.lower():
            return "Please execute the database query to get the data"
        else:
            return "Please continue and complete the previous response"

    def add_turn(
        self,
        user_input: str,
        assistant_response: str,
        tool_calls: List[Dict[str, Any]] = None,
        tool_results: List[Dict[str, Any]] = None,
    ) -> None:
        """Add a turn to current conversation."""
        context = self.get_current_context()
        if context:
            context.add_turn(user_input, assistant_response, tool_calls, tool_results)

    def detect_incomplete_response(
        self, user_input: str, assistant_response: str
    ) -> bool:
        """Detect if the assistant response seems incomplete."""
        # Check for common incomplete response patterns
        incomplete_indicators = [
            "I will now",
            "Next, I will",
            "I see that there is",
            "I'll retrieve",
            "Let me get",
            "I'll check",
        ]

        # Check if response contains tool identification without execution
        if any(indicator in assistant_response for indicator in incomplete_indicators):
            # Check if it actually contains meaningful data/results
            data_indicators = [
                "Found",
                "Results:",
                "shows",
                "Total:",
                "revenue of",
                "companies are",
            ]
            if not any(data in assistant_response for data in data_indicators):
                return True

        # Check for very short responses that don't answer the question
        if len(assistant_response.strip()) < 100 and "?" not in user_input:
            return True

        return False

    def get_continuation_prompt(self) -> str:
        """Get a prompt to encourage continuation of incomplete responses."""
        return """Continue with your analysis. Execute the necessary SQL queries to get the actual data and provide specific results to the user. Don't just describe what you will do - do it and show the results."""


# Global conversation manager instance
_conversation_manager: Optional[ConversationManager] = None


def get_conversation_manager() -> ConversationManager:
    """Get or create global conversation manager."""
    global _conversation_manager
    if _conversation_manager is None:
        _conversation_manager = ConversationManager()
    return _conversation_manager
