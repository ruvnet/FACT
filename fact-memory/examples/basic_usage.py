#!/usr/bin/env python3
"""
FACT Memory System - Basic Usage Examples

This example demonstrates basic memory operations using the FACT Memory System
including adding memories, searching, and retrieving user memories.
"""

import asyncio
from typing import List, Dict, Any
from fact_memory import FactMemoryManager, MemoryType, MemoryEntry


async def basic_memory_operations():
    """Demonstrate basic memory operations."""

    # Initialize memory manager with FACT cache integration
    memory_manager = FactMemoryManager(
        cache_config={
            "prefix": "fact_memory_demo",
            "min_tokens": 50,  # Lower for demo
            "max_size": "1MB",
            "ttl_seconds": 3600,
        }
    )

    user_id = "demo_user_123"

    print("=== FACT Memory System - Basic Usage Demo ===\n")

    # 1. Add various types of memories
    print("1. Adding memories...")

    memories = [
        {
            "content": "User prefers dark mode interface with high contrast colors",
            "memory_type": MemoryType.PREFERENCE,
            "tags": ["ui", "accessibility", "dark-mode"],
        },
        {
            "content": "User is a software engineer working on AI/ML projects",
            "memory_type": MemoryType.FACT,
            "tags": ["profession", "ai", "ml"],
        },
        {
            "content": "User frequently asks about Python optimization techniques",
            "memory_type": MemoryType.BEHAVIOR,
            "tags": ["python", "optimization", "patterns"],
        },
        {
            "content": "Always provide code examples with detailed explanations",
            "memory_type": MemoryType.INSTRUCTION,
            "tags": ["communication", "code", "teaching"],
        },
    ]

    added_memories = []
    for memory_data in memories:
        memory = await memory_manager.add_memory(
            user_id=user_id,
            content=memory_data["content"],
            memory_type=memory_data["memory_type"],
            tags=memory_data["tags"],
        )
        added_memories.append(memory)
        print(f"✓ Added {memory_data['memory_type'].value}: {memory.id}")

    print(f"\nAdded {len(added_memories)} memories for user {user_id}\n")

    # 2. Search for memories
    print("2. Searching memories...")

    search_queries = [
        "What are the user's interface preferences?",
        "Tell me about the user's profession",
        "How should I communicate with this user?",
        "What programming topics interest the user?",
    ]

    for query in search_queries:
        print(f"\nQuery: '{query}'")
        results = await memory_manager.search_memories(
            user_id=user_id, query=query, limit=3
        )

        for i, memory in enumerate(results, 1):
            print(f"  {i}. [{memory.memory_type.value}] {memory.content[:60]}...")
            print(
                f"     Relevance: {memory.relevance_score:.2f} | Tags: {', '.join(memory.tags)}"
            )

    # 3. Get all memories by type
    print("\n3. Retrieving memories by type...")

    for memory_type in MemoryType:
        memories = await memory_manager.get_memories_by_type(user_id, memory_type)
        print(f"{memory_type.value.title()}: {len(memories)} memories")

    # 4. Update a memory
    print("\n4. Updating a memory...")

    preference_memory = next(
        m for m in added_memories if m.memory_type == MemoryType.PREFERENCE
    )
    updated_memory = await memory_manager.update_memory(
        user_id=user_id,
        memory_id=preference_memory.id,
        content="User prefers dark mode with blue accent colors and large fonts for accessibility",
        tags=["ui", "accessibility", "dark-mode", "fonts", "colors"],
    )
    print(f"✓ Updated memory: {updated_memory.id}")

    # 5. Get memory statistics
    print("\n5. Memory statistics...")

    stats = await memory_manager.get_user_stats(user_id)
    print(f"Total memories: {stats['total_memories']}")
    print(f"Memory types: {stats['memory_by_type']}")
    print(f"Cache hit rate: {stats['cache_hit_rate']:.1%}")
    print(f"Average access time: {stats['avg_access_time_ms']}ms")

    return added_memories


async def advanced_search_examples():
    """Demonstrate advanced search capabilities."""

    memory_manager = FactMemoryManager()
    user_id = "advanced_user_456"

    print("\n=== Advanced Search Examples ===\n")

    # Add some complex memories for advanced search
    complex_memories = [
        "User is building a machine learning pipeline using Python and scikit-learn for customer churn prediction",
        "Prefers to use Docker containers for deployment with Kubernetes orchestration",
        "Working on a React frontend with TypeScript and Material-UI components",
        "Uses VS Code with Copilot extension and prefers vim keybindings",
        "Interested in functional programming concepts, especially in JavaScript and Python",
        "Team lead responsible for code reviews and architecture decisions",
        "Prefers Test-Driven Development approach with pytest for Python projects",
    ]

    for i, content in enumerate(complex_memories):
        await memory_manager.add_memory(
            user_id=user_id,
            content=content,
            memory_type=MemoryType.FACT,
            tags=[f"tech_{i}", "development"],
        )

    # Advanced search scenarios
    search_scenarios = [
        {
            "query": "What technologies does the user work with?",
            "description": "Technology stack inquiry",
        },
        {
            "query": "How does the user prefer to develop software?",
            "description": "Development methodology preferences",
        },
        {
            "query": "What is the user's role and responsibilities?",
            "description": "Professional role inquiry",
        },
        {
            "query": "Tell me about the user's deployment preferences",
            "description": "Infrastructure and deployment",
        },
    ]

    for scenario in search_scenarios:
        print(f"Scenario: {scenario['description']}")
        print(f"Query: '{scenario['query']}'")

        results = await memory_manager.search_memories(
            user_id=user_id, query=scenario["query"], limit=5, min_relevance=0.3
        )

        print(f"Found {len(results)} relevant memories:")
        for i, memory in enumerate(results, 1):
            print(f"  {i}. {memory.content[:80]}...")
            print(f"     Relevance: {memory.relevance_score:.2f}")
        print()


async def mcp_integration_example():
    """Demonstrate MCP server integration."""

    print("=== MCP Integration Example ===\n")

    # This would typically be done in a separate process/server
    from fact_memory.mcp import FactMemoryMCPServer

    # Initialize MCP server
    mcp_server = FactMemoryMCPServer(
        host="localhost",
        port=8080,
        memory_config={"max_memories_per_user": 1000, "cache_ttl_seconds": 3600},
    )

    print("MCP Server initialized with tools:")
    for tool_name in mcp_server.get_available_tools():
        print(f"  - {tool_name}")

    # Simulate MCP client interactions
    client_requests = [
        {
            "tool": "add-memory",
            "params": {
                "content": "User prefers concise explanations with practical examples",
                "userId": "mcp_user_789",
                "memoryType": "instruction",
                "tags": ["communication", "learning"],
            },
        },
        {
            "tool": "search-memories",
            "params": {
                "query": "How should I communicate with this user?",
                "userId": "mcp_user_789",
                "limit": 3,
            },
        },
    ]

    print("\nSimulating MCP client requests:")
    for request in client_requests:
        print(f"\nRequest: {request['tool']}")
        print(f"Params: {request['params']}")

        # Simulate tool execution
        response = await mcp_server.handle_tool_request(
            tool_name=request["tool"], parameters=request["params"]
        )

        print(f"Response: {response['content'][0]['text'][:100]}...")


if __name__ == "__main__":

    async def main():
        try:
            await basic_memory_operations()
            await advanced_search_examples()
            await mcp_integration_example()

            print("\n✓ All examples completed successfully!")

        except Exception as e:
            print(f"\n❌ Error running examples: {e}")
            import traceback

            traceback.print_exc()

    asyncio.run(main())
