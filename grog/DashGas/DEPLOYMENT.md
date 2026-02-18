# DashGas Deployment Guide

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/devsgithubaccount/Projects.git
cd Projects/Projects/grog/DashGas

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install development dependencies
pip install -r requirements.txt
```

### Run Tests

```bash
# Run all integration tests
pytest test_integration.py -v

# Run with coverage
pytest test_integration.py --cov=. --cov-report=html

# Validate production readiness
python validate_system.py
```

### Quick Usage

```python
from database import DashGasDatabase
from simulators import GasStationInventorySimulator

# Initialize database
db = DashGasDatabase("dashgas.db")

# Initialize simulator
station = GasStationInventorySimulator()

# Simulate 7 days
results = station.simulate_days(7)

# Get inventory report
report = station.get_inventory_report()
print(report)

# Get JSON export
json_data = station.get_all_products_json()

db.close()
```

## Production Deployment

### Prerequisites
- Python 3.7 or higher
- SQLite 3 (included with Python)
- No external dependencies required

### Steps

1. **Deploy Code**
   ```bash
   git clone https://github.com/devsgithubaccount/Projects.git /opt/dashgas
   cd /opt/dashgas/Projects/grog/DashGas
   ```

2. **Set Permissions**
   ```bash
   chmod 755 /opt/dashgas
   chmod -R 755 /opt/dashgas/Projects/grog/DashGas
   ```

3. **Initialize Database**
   ```bash
   python -c "from database import DashGasDatabase; db = DashGasDatabase('/var/lib/dashgas/dashgas.db'); db.close()"
   ```

4. **Configure Database Path**
   - Update database path in your application code
   - Ensure `/var/lib/dashgas/` directory exists and is writable

5. **Run Tests**
   ```bash
   python validate_system.py
   ```

## Database Backup

```bash
# Backup database
cp /var/lib/dashgas/dashgas.db /var/backups/dashgas_$(date +%Y%m%d).db

# Restore from backup
cp /var/backups/dashgas_YYYYMMDD.db /var/lib/dashgas/dashgas.db
```

## Monitoring

### Health Check
```bash
python validate_system.py
```

This validates:
- All required files present
- Database schema correct
- All functions operational
- No code quality issues

### Log Database Operations
```python
from database import DashGasDatabase

db = DashGasDatabase("dashgas.db")
summary = db.get_inventory_summary()
print(f"Inventory Summary: {summary}")
db.close()
```

## CI/CD Integration

The project includes GitHub Actions workflows:

- **test.yml**: Runs tests on Python 3.8-3.11
- **Triggers**: Push to main/develop, Pull Requests
- **Coverage**: Full test suite + validation

View results at: https://github.com/devsgithubaccount/Projects/actions

## Performance Tuning

### Database
- Queries are indexed for performance
- Foreign key constraints enabled
- Single-threaded model is optimized

### Scaling
- To handle more products, increase:
  - GasStationInventorySimulator configuration
  - Database max_stock limits
  
- Multi-location support available through:
  - Multiple database instances per location
  - Central aggregation layer

## Troubleshooting

### Database Locked Error
```bash
# Ensure no other processes using database
lsof /var/lib/dashgas/dashgas.db

# If needed, delete lock file
rm /var/lib/dashgas/dashgas.db-*
```

### Test Failures
1. Run validation: `python validate_system.py`
2. Check Python version: `python --version` (3.7+ required)
3. Verify all files present in directory
4. Review test output for specific errors

### Performance Issues
1. Check database file size: `ls -lh dashgas.db`
2. Run vacuum: `sqlite3 dashgas.db VACUUM`
3. Verify indexes: `sqlite3 dashgas.db ".indices"`

## Support

- **Issues**: https://github.com/devsgithubaccount/Projects/issues
- **Documentation**: See README.md for complete API reference
- **Tests**: Run `pytest test_integration.py -v` to see working examples

---

**DashGas is production-ready and fully tested.**
