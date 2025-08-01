# FACT System - Core Concepts

## Understanding FACT Architecture

FACT (Fast Augmented Context Tools) is built on several key concepts that work together to provide fast, secure, and intelligent access to financial data.

## 1. Cache-First Design

### What is Cache-First?

FACT leverages Claude Sonnet-4's native caching capabilities to store and reuse responses, dramatically reducing both response times and API costs.

### How Caching Works

```
User Query → Check Cache → If Hit: Return Cached Response
                       → If Miss: Process Query → Cache Result → Return Response
```

### Cache Hierarchy

1. **Static Cache**: System prompts and documentation (≥500 tokens)
2. **Query Cache**: Processed user queries and responses
3. **Tool Cache**: Tool execution results for identical parameters

### Cache Benefits

- **Performance**: 85%+ cache hit rate means <50ms response times
- **Cost Savings**: Up to 90% reduction in API token usage
- **Consistency**: Identical queries return identical results
- **Reliability**: Cached responses available even during API outages

### Cache Example

```python
# First query (cache miss)
query: "What's TechCorp's Q1 2025 revenue?"
response_time: 150ms
tokens_used: 1200
cost: $0.024

# Second identical query (cache hit)
query: "What's TechCorp's Q1 2025 revenue?"
response_time: 45ms
tokens_used: 0
cost: $0.000
```

## 2. Tool-Based Architecture

### What are Tools?

Tools are secure, containerized functions that FACT can call to retrieve data, perform calculations, or interact with external systems.

### Available Tools

#### SQL.QueryReadonly
**Purpose**: Execute SELECT queries on the financial database
```json
{
  "name": "SQL.QueryReadonly",
  "description": "Execute SELECT queries on the finance database",
  "parameters": {
    "statement": "SELECT revenue FROM companies WHERE name = 'TechCorp'"
  }
}
```

#### SQL.GetSchema
**Purpose**: Retrieve database schema information
```json
{
  "name": "SQL.GetSchema",
  "description": "Get database schema for query construction",
  "parameters": {}
}
```

#### SQL.GetSampleQueries
**Purpose**: Get example queries for exploration
```json
{
  "name": "SQL.GetSampleQueries",
  "description": "Retrieve sample queries for database exploration",
  "parameters": {}
}
```

### Tool Execution Flow

1. **Query Analysis**: Claude determines which tools are needed
2. **Parameter Extraction**: Extract relevant parameters from user query
3. **Tool Invocation**: Secure execution via Arcade gateway
4. **Result Processing**: Format and validate tool outputs
5. **Response Generation**: Synthesize final user response

### Tool Security

- **Sandboxed Execution**: Each tool runs in isolated container
- **Read-Only Access**: Database tools limited to SELECT operations
- **Input Validation**: All parameters validated before execution
- **Output Sanitization**: Results cleaned before return

## 3. Natural Language Processing

### Query Understanding

FACT uses Claude Sonnet-4 to understand natural language queries and convert them into structured tool calls.

#### Example Transformations

**User Query**: "What companies are in the technology sector?"
**Tool Call**: 
```sql
SELECT name, symbol FROM companies WHERE sector = 'Technology'
```

**User Query**: "Show me Q1 2025 revenue for all companies"
**Tool Call**:
```sql
SELECT c.name, fr.revenue 
FROM companies c 
JOIN financial_records fr ON c.id = fr.company_id 
WHERE fr.quarter = 'Q1' AND fr.year = 2025
```

### Query Types Supported

#### Direct Data Queries
- "What's TechCorp's revenue?"
- "Show me all healthcare companies"
- "List companies founded after 2010"

#### Analytical Queries
- "Which company has the highest market cap?"
- "Compare revenue across technology companies"
- "What's the average profit margin for Q1 2025?"

#### Exploratory Queries
- "What data is available?"
- "Show me sample queries"
- "What's the database schema?"

#### System Queries
- "What tools are available?"
- "Show me system metrics"
- "What's the current cache hit rate?"

## 4. Security Model

### Multi-Layer Security

FACT implements security at multiple levels to ensure data protection and system integrity.

#### Layer 1: Input Validation
- Query length limits (max 1000 characters)
- SQL injection detection and prevention
- Parameter type and format validation

#### Layer 2: Access Control
- Read-only database permissions
- Tool execution sandboxing
- API rate limiting

#### Layer 3: Output Sanitization
- Result formatting and cleaning
- Sensitive data filtering
- Error message sanitization

### SQL Injection Prevention

```python
# Dangerous input (blocked)
query = "SELECT * FROM companies; DROP TABLE companies; --"
result = "Error: Potentially dangerous SQL detected"

# Safe input (allowed)
query = "SELECT name FROM companies WHERE sector = 'Technology'"
result = [{"name": "TechCorp"}, {"name": "InnovateTech"}]
```

### Audit Trail

All operations are logged for security monitoring:
- User queries and responses
- Tool executions and results
- System access and errors
- Performance metrics

## 5. Performance Optimization

### Response Time Optimization

#### Cache Warming
Pre-populate cache with common queries:
```python
common_queries = [
    "What is the latest quarterly revenue?",
    "Show me all technology companies",
    "What are the key performance indicators?"
]
```

#### Query Optimization
- Database indexing on frequently queried columns
- Connection pooling for database access
- Asynchronous processing for concurrent requests

#### Memory Management
- Intelligent cache eviction policies
- Memory usage monitoring and alerts
- Garbage collection optimization

### Scalability Features

#### Horizontal Scaling
- Stateless architecture allows multiple instances
- Load balancing across multiple servers
- Database connection pooling

#### Vertical Scaling
- Efficient memory usage patterns
- CPU optimization for query processing
- I/O optimization for database access

## 6. Error Handling and Recovery

### Graceful Degradation

FACT handles failures gracefully to maintain system availability:

#### API Failures
```python
# If Claude API is unavailable
response = "I'm currently unable to process queries due to API issues. Please try again later."

# If tool execution fails
response = "I encountered an issue accessing the database. Using cached results where available."
```

#### Database Issues
- Automatic retry with exponential backoff
- Fallback to cached responses when possible
- Clear error messages for users

#### Network Problems
- Connection timeout handling
- Automatic retry mechanisms
- Offline mode with cached data

### Error Categories

#### User Errors (4xx)
- Invalid query format
- Unsupported operations
- Parameter validation failures

#### System Errors (5xx)
- Database connection failures
- API rate limiting
- Internal processing errors

#### External Errors
- Third-party API failures
- Network connectivity issues
- Authentication problems

## 7. Monitoring and Observability

### Key Metrics

#### Performance Metrics
- Query response times (avg, p50, p95, p99)
- Cache hit rates and cost savings
- Tool execution success rates
- System resource utilization

#### Business Metrics
- User query patterns and frequency
- Most popular queries and tools
- Cost analysis and optimization opportunities
- User satisfaction indicators

### Health Monitoring

#### System Health Checks
```python
health_status = {
    "database": "healthy",
    "cache": "healthy", 
    "tools": "healthy",
    "external_apis": "healthy"
}
```

#### Alerting
- Performance threshold breaches
- Error rate increases
- Resource utilization alerts
- Security incident detection

## 8. Data Model

### Core Entities

#### Companies
- **Attributes**: Name, Symbol, Sector, Founded Year, Employees, Market Cap
- **Relationships**: One-to-many with Financial Records

#### Financial Records
- **Attributes**: Quarter, Year, Revenue, Profit, Expenses
- **Relationships**: Many-to-one with Companies

### Query Patterns

#### Single Entity Queries
```sql
SELECT * FROM companies WHERE name = 'TechCorp';
```

#### Relationship Queries
```sql
SELECT c.name, fr.revenue 
FROM companies c 
JOIN financial_records fr ON c.id = fr.company_id 
WHERE fr.quarter = 'Q1' AND fr.year = 2025;
```

#### Aggregation Queries
```sql
SELECT sector, AVG(market_cap) as avg_market_cap 
FROM companies 
GROUP BY sector;
```

## Next Steps

Now that you understand FACT's core concepts:

1. **Practice with Examples**: Try the [User Guide](4_user_guide.md) examples
2. **Explore the API**: Review [API Reference](5_api_reference.md) 
3. **Performance Tuning**: Check [Advanced Usage](7_advanced_usage.md)
4. **Tool Development**: Learn [Tool Creation](docs/tool-execution-framework.md)

---

**Ready to start using FACT?** Continue to the [User Guide](4_user_guide.md) for practical examples and workflows.