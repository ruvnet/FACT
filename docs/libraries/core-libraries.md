# FACT Core Libraries

> Essential Python libraries powering the FACT system

## Overview

The FACT (Fast Augmented Context Tools) system relies on a carefully selected set of Python libraries that provide robust functionality for AI integration, data validation, async operations, and system reliability.

## Primary Dependencies

### 🤖 AI & LLM Integration

#### Anthropic SDK 0.19.1
**The Claude AI powerhouse for FACT**

```python
from anthropic import AsyncAnthropic

async def generate_tool_code(specification: str) -> str:
    client = AsyncAnthropic()
    
    async with client.messages.stream(
        model="claude-3-5-sonnet-latest",
        max_tokens=2048,
        messages=[{
            "role": "user",
            "content": f"Generate Python tool code for: {specification}"
        }]
    ) as stream:
        code_parts = []
        async for text in stream.text_stream:
            code_parts.append(text)
        
        return "".join(code_parts)
```

**Key Benefits:**
- Native async/await support
- Streaming responses for real-time feedback
- Advanced tool use capabilities
- Robust error handling

#### LiteLLM 1.0.0
**Universal LLM gateway for provider flexibility**

```python
from litellm import completion

# Works with 100+ LLM providers
response = completion(
    model="claude-3-5-sonnet-latest",  # or gpt-4, gemini-pro, etc.
    messages=[{"role": "user", "content": "Analyze this code..."}],
    temperature=0.3
)
```

**Configuration Example:**
```yaml
# config.yaml
model_list:
  - model_name: claude-sonnet
    litellm_params:
      model: anthropic/claude-3-5-sonnet-latest
      api_key: os.environ/ANTHROPIC_API_KEY
  - model_name: gpt-4
    litellm_params:
      model: openai/gpt-4
      api_key: os.environ/OPENAI_API_KEY

litellm_settings:
  success_callback: ["prometheus"]
  cache: true
```

### 📊 Data Validation & Models

#### Pydantic 2.8.2
**Type-safe data validation and serialization**

```python
from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import Optional

class ToolMetadata(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str
    version: str = Field(..., regex=r'^\d+\.\d+\.\d+$')
    created_at: datetime
    tags: list[str] = []
    complexity_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    
    @validator('tags')
    def validate_tags(cls, v):
        return [tag.lower().strip() for tag in v if tag.strip()]

# Usage
tool_data = {
    "name": "Data Processor",
    "description": "Processes CSV data files",
    "version": "1.0.0",
    "created_at": "2025-01-23T18:30:00Z",
    "tags": ["Data", "CSV", "Processing"]
}

tool = ToolMetadata(**tool_data)
print(tool.model_dump_json(indent=2))
```

**Advanced Features:**
- Automatic type coercion
- Custom validators
- JSON Schema generation
- Performance-optimized with Rust core

### ⚡ Async Operations

#### aiohttp 3.9.5
**High-performance async HTTP client/server**

```python
import aiohttp
from typing import Dict, Any

class HTTPConnector:
    def __init__(self):
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.session.close()
    
    async def fetch_data(self, url: str, headers: Dict[str, str] = None) -> Dict[Any, Any]:
        async with self.session.get(url, headers=headers) as response:
            response.raise_for_status()
            return await response.json()

# Usage
async def main():
    async with HTTPConnector() as connector:
        data = await connector.fetch_data("https://api.example.com/data")
        return data
```

#### aiosqlite 0.20.0
**Async SQLite for local data persistence**

```python
import aiosqlite
import json
from datetime import datetime

class ToolStorage:
    def __init__(self, db_path: str = "fact.db"):
        self.db_path = db_path
    
    async def save_tool_execution(self, tool_id: str, input_data: dict, output_data: dict):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO tool_executions (tool_id, input_data, output_data, executed_at)
                VALUES (?, ?, ?, ?)
            """, (
                tool_id,
                json.dumps(input_data),
                json.dumps(output_data),
                datetime.utcnow().isoformat()
            ))
            await db.commit()
    
    async def get_tool_history(self, tool_id: str, limit: int = 10):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT input_data, output_data, executed_at
                FROM tool_executions
                WHERE tool_id = ?
                ORDER BY executed_at DESC
                LIMIT ?
            """, (tool_id, limit)) as cursor:
                rows = await cursor.fetchall()
                return [
                    {
                        "input": json.loads(row[0]),
                        "output": json.loads(row[1]),
                        "executed_at": row[2]
                    }
                    for row in rows
                ]
```

### 🛡️ Security & Configuration

#### python-dotenv 1.0.1
**Secure environment configuration**

```python
from dotenv import load_dotenv
import os
from pathlib import Path

# Load environment variables
env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)

class SecurityConfig:
    # API Keys
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    
    # Database
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///fact.db")
    
    # Security
    SECRET_KEY = os.getenv("SECRET_KEY")
    JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
    
    # Validation
    @classmethod
    def validate(cls):
        required_vars = ["ANTHROPIC_API_KEY", "SECRET_KEY"]
        missing = [var for var in required_vars if not getattr(cls, var)]
        if missing:
            raise ValueError(f"Missing required environment variables: {missing}")

# .env file example:
"""
ANTHROPIC_API_KEY=sk-ant-api03-xxx
SECRET_KEY=your-secret-key-here
DATABASE_URL=sqlite:///fact_production.db
LOG_LEVEL=INFO
"""
```

### 📝 Logging & Monitoring

#### structlog 24.1.0
**Structured logging for better observability**

```python
import structlog
from datetime import datetime

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

class ToolExecutionLogger:
    def __init__(self, tool_id: str):
        self.logger = logger.bind(tool_id=tool_id)
    
    def log_execution_start(self, input_data: dict):
        self.logger.info(
            "Tool execution started",
            input_size=len(str(input_data)),
            started_at=datetime.utcnow().isoformat()
        )
    
    def log_execution_complete(self, output_data: dict, duration_ms: float):
        self.logger.info(
            "Tool execution completed",
            output_size=len(str(output_data)),
            duration_ms=duration_ms,
            completed_at=datetime.utcnow().isoformat()
        )
    
    def log_execution_error(self, error: Exception):
        self.logger.error(
            "Tool execution failed",
            error_type=type(error).__name__,
            error_message=str(error),
            failed_at=datetime.utcnow().isoformat()
        )
```

## Integration Patterns

### Complete Tool Execution Pattern

```python
import asyncio
from typing import Dict, Any
import structlog
from pydantic import BaseModel

class ToolInput(BaseModel):
    operation: str
    parameters: Dict[str, Any]
    timeout_seconds: int = 30

class ToolOutput(BaseModel):
    success: bool
    result: Any
    execution_time_ms: float
    metadata: Dict[str, Any] = {}

class FactToolExecutor:
    def __init__(self):
        self.logger = structlog.get_logger().bind(component="tool_executor")
        self.storage = ToolStorage()
        self.llm_client = AsyncAnthropic()
    
    async def execute_tool(self, tool_input: ToolInput) -> ToolOutput:
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Log execution start
            self.logger.info("Starting tool execution", operation=tool_input.operation)
            
            # Validate input
            validated_input = ToolInput.model_validate(tool_input.model_dump())
            
            # Execute the tool logic
            result = await self._execute_operation(validated_input)
            
            # Calculate execution time
            execution_time_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            
            # Create output
            output = ToolOutput(
                success=True,
                result=result,
                execution_time_ms=execution_time_ms,
                metadata={"operation": tool_input.operation}
            )
            
            # Store execution record
            await self.storage.save_tool_execution(
                tool_id=f"tool_{tool_input.operation}",
                input_data=validated_input.model_dump(),
                output_data=output.model_dump()
            )
            
            self.logger.info("Tool execution completed", 
                           duration_ms=execution_time_ms,
                           success=True)
            
            return output
            
        except Exception as e:
            execution_time_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            
            self.logger.error("Tool execution failed",
                            duration_ms=execution_time_ms,
                            error=str(e))
            
            return ToolOutput(
                success=False,
                result=None,
                execution_time_ms=execution_time_ms,
                metadata={"error": str(e), "operation": tool_input.operation}
            )
    
    async def _execute_operation(self, tool_input: ToolInput) -> Any:
        # This would contain the actual tool logic
        # For example, calling an LLM, processing data, etc.
        pass
```

## Performance Considerations

### Memory Management
- Use async context managers for proper resource cleanup
- Implement connection pooling for database and HTTP operations
- Stream large responses instead of loading into memory

### Concurrency
- Leverage asyncio for I/O-bound operations
- Use semaphores to limit concurrent operations
- Implement proper backpressure handling

### Caching
- Cache validated Pydantic models to avoid re-validation
- Use Redis or in-memory caching for frequently accessed data
- Implement cache warming strategies for critical data

## Testing Strategy

```python
import pytest
from unittest.mock import AsyncMock
import aioresponses

@pytest.fixture
async def tool_executor():
    executor = FactToolExecutor()
    yield executor
    # Cleanup if needed

@pytest.mark.asyncio
async def test_tool_execution_success(tool_executor):
    # Arrange
    tool_input = ToolInput(
        operation="test_operation",
        parameters={"key": "value"}
    )
    
    # Act
    result = await tool_executor.execute_tool(tool_input)
    
    # Assert
    assert result.success is True
    assert result.execution_time_ms > 0
    assert "operation" in result.metadata

@pytest.mark.asyncio
async def test_http_connector():
    with aioresponses.aioresponses() as m:
        m.get('http://example.com/api', payload={'status': 'ok'})
        
        async with HTTPConnector() as connector:
            data = await connector.fetch_data('http://example.com/api')
            assert data['status'] == 'ok'
```

## Migration & Maintenance

### Version Updates
1. **Pin specific versions** in requirements.txt for stability
2. **Test in staging** before production deployment
3. **Review breaking changes** in library release notes
4. **Update incrementally** one library at a time

### Monitoring
- Track library performance metrics
- Monitor error rates and types
- Set up alerts for dependency vulnerabilities
- Regular security audits of dependencies

---

*This document serves as a practical guide for working with FACT's core libraries and implementing reliable, maintainable Python applications.*