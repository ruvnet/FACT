"""
FACT System Database Models

This module defines the database schema and models for the FACT system,
including sample financial data for demonstration purposes.
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class FinancialRecord:
    """Represents a financial record in the database."""

    id: int
    company: str
    quarter: str
    year: int
    revenue: float
    profit: float
    expenses: float
    created_at: datetime
    updated_at: datetime


@dataclass
class Company:
    """Represents a company in the database."""

    id: int
    name: str
    symbol: str
    sector: str
    founded_year: int
    employees: int
    market_cap: float
    created_at: datetime
    updated_at: datetime


@dataclass
class QueryResult:
    """Represents the result of a database query."""

    rows: List[Dict[str, Any]]
    row_count: int
    columns: List[str]
    execution_time_ms: float


# Database schema for SQLite
DATABASE_SCHEMA = """
-- Companies table
CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    symbol TEXT NOT NULL UNIQUE,
    sector TEXT NOT NULL,
    founded_year INTEGER,
    employees INTEGER,
    market_cap REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Financial records table
CREATE TABLE IF NOT EXISTS financial_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    quarter TEXT NOT NULL,
    year INTEGER NOT NULL,
    revenue REAL NOT NULL,
    profit REAL NOT NULL,
    expenses REAL NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies (id),
    UNIQUE(company_id, quarter, year)
);

-- Financial data table (alias/view for validation compatibility)
CREATE TABLE IF NOT EXISTS financial_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    quarter TEXT NOT NULL,
    year INTEGER NOT NULL,
    revenue REAL NOT NULL,
    profit REAL NOT NULL,
    expenses REAL NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies (id),
    UNIQUE(company_id, quarter, year)
);

-- Benchmarks table for performance tracking
CREATE TABLE IF NOT EXISTS benchmarks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    test_name TEXT NOT NULL,
    test_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    duration_ms REAL NOT NULL,
    queries_executed INTEGER DEFAULT 0,
    cache_hit_rate REAL DEFAULT 0.0,
    average_response_time_ms REAL DEFAULT 0.0,
    success_rate REAL DEFAULT 1.0,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_financial_records_company_id ON financial_records(company_id);
CREATE INDEX IF NOT EXISTS idx_financial_records_year ON financial_records(year);
CREATE INDEX IF NOT EXISTS idx_financial_records_quarter ON financial_records(quarter);
CREATE INDEX IF NOT EXISTS idx_financial_data_company_id ON financial_data(company_id);
CREATE INDEX IF NOT EXISTS idx_financial_data_year ON financial_data(year);
CREATE INDEX IF NOT EXISTS idx_financial_data_quarter ON financial_data(quarter);
CREATE INDEX IF NOT EXISTS idx_companies_symbol ON companies(symbol);
CREATE INDEX IF NOT EXISTS idx_companies_sector ON companies(sector);
CREATE INDEX IF NOT EXISTS idx_benchmarks_test_name ON benchmarks(test_name);
CREATE INDEX IF NOT EXISTS idx_benchmarks_test_date ON benchmarks(test_date);
"""

# Sample data for demonstration
SAMPLE_COMPANIES = [
    {
        "name": "TechCorp Inc.",
        "symbol": "TECH",
        "sector": "Technology",
        "founded_year": 1995,
        "employees": 50000,
        "market_cap": 250000000000.0,
    },
    {
        "name": "FinanceFirst LLC",
        "symbol": "FINF",
        "sector": "Financial Services",
        "founded_year": 1988,
        "employees": 25000,
        "market_cap": 125000000000.0,
    },
    {
        "name": "HealthTech Solutions",
        "symbol": "HLTH",
        "sector": "Healthcare",
        "founded_year": 2005,
        "employees": 15000,
        "market_cap": 75000000000.0,
    },
    {
        "name": "Green Energy Corp",
        "symbol": "GREN",
        "sector": "Energy",
        "founded_year": 2010,
        "employees": 8000,
        "market_cap": 45000000000.0,
    },
    {
        "name": "RetailMax Group",
        "symbol": "RTLM",
        "sector": "Retail",
        "founded_year": 1975,
        "employees": 120000,
        "market_cap": 95000000000.0,
    },
]

SAMPLE_FINANCIAL_RECORDS = [
    # TechCorp Inc. (company_id: 1)
    {
        "company_id": 1,
        "quarter": "Q1",
        "year": 2025,
        "revenue": 25000000000.0,
        "profit": 5000000000.0,
        "expenses": 20000000000.0,
    },
    {
        "company_id": 1,
        "quarter": "Q4",
        "year": 2024,
        "revenue": 28000000000.0,
        "profit": 6000000000.0,
        "expenses": 22000000000.0,
    },
    {
        "company_id": 1,
        "quarter": "Q3",
        "year": 2024,
        "revenue": 26000000000.0,
        "profit": 5500000000.0,
        "expenses": 20500000000.0,
    },
    {
        "company_id": 1,
        "quarter": "Q2",
        "year": 2024,
        "revenue": 24000000000.0,
        "profit": 4800000000.0,
        "expenses": 19200000000.0,
    },
    {
        "company_id": 1,
        "quarter": "Q1",
        "year": 2024,
        "revenue": 23000000000.0,
        "profit": 4600000000.0,
        "expenses": 18400000000.0,
    },
    # FinanceFirst LLC (company_id: 2)
    {
        "company_id": 2,
        "quarter": "Q1",
        "year": 2025,
        "revenue": 12000000000.0,
        "profit": 3000000000.0,
        "expenses": 9000000000.0,
    },
    {
        "company_id": 2,
        "quarter": "Q4",
        "year": 2024,
        "revenue": 13500000000.0,
        "profit": 3200000000.0,
        "expenses": 10300000000.0,
    },
    {
        "company_id": 2,
        "quarter": "Q3",
        "year": 2024,
        "revenue": 13000000000.0,
        "profit": 3100000000.0,
        "expenses": 9900000000.0,
    },
    {
        "company_id": 2,
        "quarter": "Q2",
        "year": 2024,
        "revenue": 12500000000.0,
        "profit": 2900000000.0,
        "expenses": 9600000000.0,
    },
    {
        "company_id": 2,
        "quarter": "Q1",
        "year": 2024,
        "revenue": 11800000000.0,
        "profit": 2800000000.0,
        "expenses": 9000000000.0,
    },
    # HealthTech Solutions (company_id: 3)
    {
        "company_id": 3,
        "quarter": "Q1",
        "year": 2025,
        "revenue": 8000000000.0,
        "profit": 1200000000.0,
        "expenses": 6800000000.0,
    },
    {
        "company_id": 3,
        "quarter": "Q4",
        "year": 2024,
        "revenue": 8500000000.0,
        "profit": 1300000000.0,
        "expenses": 7200000000.0,
    },
    {
        "company_id": 3,
        "quarter": "Q3",
        "year": 2024,
        "revenue": 8200000000.0,
        "profit": 1250000000.0,
        "expenses": 6950000000.0,
    },
    {
        "company_id": 3,
        "quarter": "Q2",
        "year": 2024,
        "revenue": 7800000000.0,
        "profit": 1150000000.0,
        "expenses": 6650000000.0,
    },
    {
        "company_id": 3,
        "quarter": "Q1",
        "year": 2024,
        "revenue": 7500000000.0,
        "profit": 1100000000.0,
        "expenses": 6400000000.0,
    },
    # Green Energy Corp (company_id: 4)
    {
        "company_id": 4,
        "quarter": "Q1",
        "year": 2025,
        "revenue": 5500000000.0,
        "profit": 800000000.0,
        "expenses": 4700000000.0,
    },
    {
        "company_id": 4,
        "quarter": "Q4",
        "year": 2024,
        "revenue": 6000000000.0,
        "profit": 900000000.0,
        "expenses": 5100000000.0,
    },
    {
        "company_id": 4,
        "quarter": "Q3",
        "year": 2024,
        "revenue": 5800000000.0,
        "profit": 850000000.0,
        "expenses": 4950000000.0,
    },
    {
        "company_id": 4,
        "quarter": "Q2",
        "year": 2024,
        "revenue": 5200000000.0,
        "profit": 750000000.0,
        "expenses": 4450000000.0,
    },
    {
        "company_id": 4,
        "quarter": "Q1",
        "year": 2024,
        "revenue": 4800000000.0,
        "profit": 680000000.0,
        "expenses": 4120000000.0,
    },
    # RetailMax Group (company_id: 5)
    {
        "company_id": 5,
        "quarter": "Q1",
        "year": 2025,
        "revenue": 18000000000.0,
        "profit": 1800000000.0,
        "expenses": 16200000000.0,
    },
    {
        "company_id": 5,
        "quarter": "Q4",
        "year": 2024,
        "revenue": 22000000000.0,
        "profit": 2400000000.0,
        "expenses": 19600000000.0,
    },  # Holiday season
    {
        "company_id": 5,
        "quarter": "Q3",
        "year": 2024,
        "revenue": 19000000000.0,
        "profit": 2000000000.0,
        "expenses": 17000000000.0,
    },
    {
        "company_id": 5,
        "quarter": "Q2",
        "year": 2024,
        "revenue": 17500000000.0,
        "profit": 1750000000.0,
        "expenses": 15750000000.0,
    },
    {
        "company_id": 5,
        "quarter": "Q1",
        "year": 2024,
        "revenue": 16800000000.0,
        "profit": 1650000000.0,
        "expenses": 15150000000.0,
    },
]


def get_sample_queries() -> List[str]:
    """
    Get list of sample queries for testing and demonstration.

    Returns:
        List of sample SQL queries
    """
    return [
        "SELECT * FROM companies WHERE sector = 'Technology'",
        "SELECT company_id, SUM(revenue) as total_revenue FROM financial_records WHERE year = 2024 GROUP BY company_id",
        "SELECT c.name, f.revenue, f.profit FROM companies c JOIN financial_records f ON c.id = f.company_id WHERE f.quarter = 'Q1' AND f.year = 2025",
        "SELECT sector, COUNT(*) as company_count FROM companies GROUP BY sector",
        "SELECT c.name, f.quarter, f.year, f.revenue FROM companies c JOIN financial_records f ON c.id = f.company_id WHERE c.symbol = 'TECH' ORDER BY f.year DESC, f.quarter DESC",
        "SELECT AVG(revenue) as avg_revenue, AVG(profit) as avg_profit FROM financial_records WHERE year = 2024",
        "SELECT c.name, c.market_cap, f.revenue FROM companies c JOIN financial_records f ON c.id = f.company_id WHERE f.year = 2025 AND f.quarter = 'Q1' ORDER BY c.market_cap DESC",
    ]


def validate_schema_integrity(tables_info: List[Dict[str, Any]]) -> bool:
    """
    Validate that the database schema matches expected structure.

    Args:
        tables_info: Information about database tables

    Returns:
        True if schema is valid, False otherwise
    """
    expected_tables = {"companies", "financial_records", "financial_data", "benchmarks"}
    actual_tables = {table["name"] for table in tables_info}

    if not expected_tables.issubset(actual_tables):
        missing_tables = expected_tables - actual_tables
        logger.error("Missing database tables", missing=list(missing_tables))
        return False

    logger.info("Database schema validation passed")
    return True
