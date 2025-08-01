# FACT System Deployment Guide

## Overview

This guide provides comprehensive instructions for deploying the FACT (Fast Augmented Context Tools) system across different environments using Docker Compose or Kubernetes.

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.11+
- kubectl (for Kubernetes deployments)
- Valid API keys for Anthropic and Arcade

### Environment Setup

1. **Copy environment configuration:**
   ```bash
   cp .env.example .env
   ```

2. **Configure API keys in `.env`:**
   ```bash
   ANTHROPIC_API_KEY=your_anthropic_api_key_here
   ARCADE_API_KEY=your_arcade_api_key_here
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

### Development Deployment (Docker Compose)

```bash
# Deploy to development environment
./scripts/deploy.sh -e development -t docker

# Or manually with Docker Compose
cd deployment/docker
docker-compose up -d
```

**Access Points:**
- Application: http://localhost:8000
- Grafana: http://localhost:3000 (admin/admin123)
- Prometheus: http://localhost:9090

### Production Deployment

#### Option 1: Docker Compose Production

```bash
# Deploy to production with Docker Compose
./scripts/deploy.sh -e production -t docker -v v1.0.0
```

#### Option 2: Kubernetes Production

```bash
# Deploy to Kubernetes
./scripts/deploy.sh -e production -t kubernetes -v v1.0.0
```

## Deployment Architecture

### Docker Compose Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Nginx Proxy   │    │   FACT App      │    │   Monitoring    │
│   (Port 80/443) │────┤   (Port 8000)   │    │   Stack         │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                       ┌────────┴────────┐
                       │                 │
                ┌──────▼──────┐   ┌──────▼──────┐
                │   Redis     │   │ PostgreSQL  │
                │ (Port 6379) │   │ (Port 5432) │
                └─────────────┘   └─────────────┘
```

### Kubernetes Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│    Ingress      │    │  FACT Service   │    │  ConfigMaps &   │
│   Controller    │────┤   (ClusterIP)   │    │    Secrets      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                       ┌────────┴────────┐
                       │                 │
                ┌──────▼──────┐   ┌──────▼──────┐
                │ Redis Pod   │   │Postgres Pod │
                │             │   │             │
                └─────────────┘   └─────────────┘
```

## Configuration Management

### Environment Variables

#### Required Variables
- `ANTHROPIC_API_KEY`: Anthropic Claude API key
- `ARCADE_API_KEY`: Arcade platform API key

#### Optional Variables
- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR)
- `DATABASE_PATH`: SQLite database file path
- `CACHE_PREFIX`: Redis cache key prefix
- `MAX_RETRIES`: Maximum retry attempts for API calls

### Security Configuration

#### Environment-Specific Security
- **Development**: Basic security, debug logging enabled
- **Staging**: Enhanced security, limited debug access
- **Production**: Maximum security, audit logging, rate limiting

#### Secret Management
- Use Kubernetes secrets for production deployments
- Implement secret rotation policies
- Never commit secrets to version control

### Database Configuration

#### SQLite (Development)
- File-based database for local development
- Automatic schema creation and migration

#### PostgreSQL (Production)
- Dedicated PostgreSQL instance
- Connection pooling and optimization
- Automated backups and point-in-time recovery

## Deployment Environments

### Development Environment

**Purpose**: Local development and testing

**Configuration**:
- Single-node Docker Compose setup
- Debug logging enabled
- Hot-reload for code changes
- In-memory caching for faster iteration

**Resources**:
- CPU: 0.5 cores per service
- Memory: 512MB per service
- Storage: Local volumes

### Staging Environment

**Purpose**: Pre-production testing and validation

**Configuration**:
- Production-like infrastructure
- Reduced resource allocation
- Performance monitoring enabled
- Integration testing

**Resources**:
- CPU: 1 core per service
- Memory: 1GB per service
- Storage: Persistent volumes

### Production Environment

**Purpose**: Live production workloads

**Configuration**:
- High availability setup
- Auto-scaling enabled
- Comprehensive monitoring
- Security hardening
- Backup and disaster recovery

**Resources**:
- CPU: 2+ cores per service
- Memory: 2GB+ per service
- Storage: Enterprise-grade persistent storage

## Monitoring and Observability

### Metrics Collection

**Prometheus Metrics**:
- Application performance metrics
- Business logic metrics (query success rate, cache hit ratio)
- Infrastructure metrics (CPU, memory, disk)
- Custom business metrics

**Key Performance Indicators**:
- Cache hit rate: >80%
- Response time: <100ms (95th percentile)
- Error rate: <1%
- Availability: >99.9%

### Alerting Rules

**Critical Alerts**:
- Application down
- High error rate (>5%)
- Memory usage >90%
- Disk space <15%

**Warning Alerts**:
- High response time (>500ms)
- Cache hit rate <80%
- CPU usage >80%

### Log Management

**Structured Logging**:
- JSON format for machine parsing
- Correlation IDs for request tracing
- Security event logging
- Performance metrics logging

**Log Retention**:
- Development: 7 days
- Staging: 30 days
- Production: 90 days

## Scaling and Performance

### Horizontal Scaling

**Docker Compose**:
```bash
# Scale application instances
docker-compose up -d --scale fact-app=3
```

**Kubernetes**:
```bash
# Scale deployment
kubectl scale deployment fact-app --replicas=3 -n fact-system
```

### Auto-scaling Configuration

**Kubernetes HPA**:
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: fact-app-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: fact-app
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

### Performance Optimization

**Caching Strategy**:
- Multi-level caching (in-memory + Redis)
- Cache warming for frequently accessed data
- Intelligent cache eviction policies

**Database Optimization**:
- Connection pooling
- Query optimization
- Indexing strategy
- Read replicas for scaling

## Security Considerations

### Network Security

**Container Security**:
- Non-root user execution
- Minimal base images
- Regular security updates
- Container scanning

**Network Policies**:
- Kubernetes network policies for traffic isolation
- TLS encryption for all communication
- Rate limiting and DDoS protection

### Authentication and Authorization

**API Security**:
- JWT token-based authentication
- OAuth 2.0 integration
- Role-based access control (RBAC)
- API key management

**Secrets Management**:
- Kubernetes secrets for sensitive data
- Secret rotation policies
- Encryption at rest and in transit

## Disaster Recovery

### Backup Strategy

**Database Backups**:
- Daily automated backups
- Point-in-time recovery capability
- Cross-region backup replication
- Backup validation and testing

**Configuration Backups**:
- Infrastructure as Code (IaC) version control
- Configuration drift detection
- Automated configuration restoration

### Recovery Procedures

**RTO/RPO Targets**:
- Recovery Time Objective (RTO): 15 minutes
- Recovery Point Objective (RPO): 1 hour

**Disaster Recovery Steps**:
1. Assess impact and scope
2. Activate backup infrastructure
3. Restore data from latest backup
4. Validate system functionality
5. Redirect traffic to restored system
6. Monitor and optimize performance

## Troubleshooting

### Common Issues

#### Application Won't Start
```bash
# Check container logs
docker-compose logs fact-app

# Check Kubernetes pod logs
kubectl logs -n fact-system deployment/fact-app
```

#### Database Connection Issues
```bash
# Test database connectivity
docker-compose exec fact-app python -c "from src.db.connection import test_connection; test_connection()"

# Check database status
kubectl exec -n fact-system deployment/fact-postgres -- pg_isready
```

#### Performance Issues
```bash
# Check resource usage
docker stats

# Kubernetes resource usage
kubectl top pods -n fact-system
```

### Health Checks

**Application Health**:
```bash
curl http://localhost:8000/health
```

**Database Health**:
```bash
# PostgreSQL
kubectl exec -n fact-system deployment/fact-postgres -- pg_isready

# Redis
kubectl exec -n fact-system deployment/fact-redis -- redis-cli ping
```

## Maintenance and Updates

### Rolling Updates

**Docker Compose**:
```bash
# Update with zero downtime
./scripts/deploy.sh -e production -t docker -v v1.1.0
```

**Kubernetes**:
```bash
# Rolling update deployment
kubectl set image deployment/fact-app fact-app=ghcr.io/fact-system:v1.1.0 -n fact-system
kubectl rollout status deployment/fact-app -n fact-system
```

### Rollback Procedures

**Docker Compose**:
```bash
# Rollback to previous version
docker-compose down
docker-compose up -d --force-recreate
```

**Kubernetes**:
```bash
# Rollback deployment
kubectl rollout undo deployment/fact-app -n fact-system
kubectl rollout status deployment/fact-app -n fact-system
```

## Support and Documentation

### Additional Resources

- [Architecture Documentation](../architecture/)
- [API Documentation](../docs/api/)
- [Security Guide](../docs/security/)
- [Performance Tuning Guide](../docs/performance/)

### Getting Help

1. Check application logs for error details
2. Review monitoring dashboards for system health
3. Consult troubleshooting section above
4. Contact the development team with detailed error information

---

**Last Updated**: 2025-05-24
**Version**: 1.0.0