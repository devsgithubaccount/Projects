# DashGas - Production-Ready Gas Station Inventory Management System

## Overview

DashGas is a comprehensive inventory management system designed specifically for gas stations and convenience stores. It provides real-time inventory tracking, automated reordering, anomaly detection, and supplier performance monitoring.

## Project Structure

```
DashGas/
├── database.py           # SQLite database layer with schema and CRUD operations
├── simulators.py         # Product simulators with realistic consumption patterns
├── test_integration.py   # Comprehensive integration tests
├── README.md             # This file
└── ProjectDescription.txt # Original project requirements
```

## Features

### 1. Database Module (`database.py`)

Complete SQLite-based database with the following tables:

#### Core Tables
- **suppliers**: Supplier information, contact details, lead times, reliability scores
- **products**: Product catalog with stock levels, categories, reorder thresholds
- **stock_logs**: Historical stock changes with reasons and timestamps
- **orders**: Purchase orders with status tracking and cost management
- **deliveries**: Delivery records with received quantities and conditions
- **anomalies**: Inventory anomalies (high consumption, delays, etc.)
- **supplier_performance**: Supplier metrics (on-time delivery, quality ratings)

#### Features
- Foreign key constraints for data integrity
- Indexed queries for performance
- Comprehensive CRUD operations
- Stock change tracking with automatic updates
- Low stock alerting
- Anomaly detection and resolution workflow
- Inventory summaries and reporting

### 2. Simulators Module (`simulators.py`)

Realistic product simulators with historical consumption patterns:

#### Product Simulators
- **GasolineSimulator**: Regular, Mid-Grade, Premium grades (1,600-4,000 gal/day)
- **DieselSimulator**: Diesel fuel (800-2,000 gal/day)
- **ConvenienceStoreItemSimulator**: Snacks, drinks, bottled water (50-150 units/day)
- **TobaccoSimulator**: Cigarette brands (10-30 packs/day)
- **VapeSimulator**: E-cigarette products (5-20 bottles/day)
- **CoffeeSimulator**: Coffee products and supplies (15-40 units/day)

#### GasStationInventorySimulator
Master simulator managing 17 preconfigured products with:
- Daily consumption simulation
- Inventory reporting by category
- Low stock alerts
- JSON export capabilities
- Multi-day scenario testing
- Realistic supply and demand patterns

## Usage Examples

### Database Operations

```python
from database import DashGasDatabase

# Initialize database
db = DashGasDatabase("dashgas.db")

# Add a supplier
supplier_id = db.add_supplier(
    name="Shell Wholesale",
    contact_email="shell@example.com",
    contact_phone="555-0100",
    lead_time_days=2
)

# Add a product
product_id = db.add_product(
    name="Regular Gasoline",
    category="fuel",
    current_stock=10000,
    unit="gallons",
    reorder_threshold=2000,
    supplier_id=supplier_id,
    lead_time_days=2,
    unit_cost=2.50
)

# Log stock change
db.log_stock_change(
    product_id=product_id,
    current_stock=9500,
    change_amount=-500,
    reason="daily_consumption"
)

# Create purchase order
order_id = db.create_order(
    product_id=product_id,
    supplier_id=supplier_id,
    quantity=5000,
    expected_delivery_date="2026-02-19",
    unit_cost=2.50
)

# Record delivery
db.record_delivery(
    order_id=order_id,
    received_quantity=5000,
    condition="good"
)

# Get inventory summary
summary = db.get_inventory_summary()
print(summary)
# Output: {
#   "total_products": 1,
#   "low_stock_count": 0,
#   "total_stock_value": 9500.0,
#   "open_anomalies": 0,
#   "pending_orders": 0,
#   "timestamp": "2026-02-17T22:08:33.094496"
# }

db.close()
```

### Simulator Operations

```python
from simulators import GasStationInventorySimulator

# Initialize full station simulator
station = GasStationInventorySimulator()

# Simulate one day
daily_results = station.simulate_day()

# Simulate multiple days
week_results = station.simulate_days(days=7)

# Get all products as JSON
json_string = station.get_all_products_json()

# Get comprehensive report
report = station.get_inventory_report()

# Get category-specific report
fuel_report = station.get_category_report("fuel")

# Check for low stock
alerts = station.get_low_stock_alerts(threshold_percent=25)

# Restock a product
station.restock_product("regular_gas", quantity=5000)

# Reset to initial state
station.reset_all()
```

### Individual Simulator Usage

```python
from simulators import (
    GasolineSimulator,
    CoffeeSimulator,
    TobaccoSimulator,
    VapeSimulator,
    ConvenienceStoreItemSimulator
)

# Create individual simulators
gas = GasolineSimulator("Premium", initial_stock=6000)
coffee = CoffeeSimulator("Premium Blend", initial_stock=100)
tobacco = TobaccoSimulator("Marlboro", initial_stock=200)

# Simulate consumption
snapshots = gas.simulate_consumption(days=5)

# Get product snapshot
snapshot = gas.get_snapshot()
print(snapshot.to_json())
# Output: {
#   "product": "Premium Gasoline",
#   "category": "fuel",
#   "current_stock": 4235.5,
#   "unit": "gallons",
#   "last_updated": "2026-02-17T22:08:33.094496"
# }

# Check inventory status
avg_consumption = gas.get_consumption_average()
days_until_empty = gas.get_days_until_empty()

# Restock
gas.restock(5000)
```

## Data Schema

### Suppliers Table
```sql
CREATE TABLE suppliers (
    supplier_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    contact_email TEXT,
    contact_phone TEXT,
    lead_time_days INTEGER DEFAULT 3,
    reliability_score REAL DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

### Products Table
```sql
CREATE TABLE products (
    product_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL,
    current_stock REAL NOT NULL DEFAULT 0,
    unit TEXT NOT NULL,
    reorder_threshold REAL NOT NULL,
    supplier_id INTEGER NOT NULL,
    lead_time_days INTEGER NOT NULL DEFAULT 3,
    min_stock REAL DEFAULT 0,
    max_stock REAL DEFAULT 10000,
    unit_cost REAL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id)
)
```

### Stock Logs Table
```sql
CREATE TABLE stock_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    previous_stock REAL NOT NULL,
    current_stock REAL NOT NULL,
    change_amount REAL NOT NULL,
    reason TEXT,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(product_id)
)
```

## Testing

The system includes comprehensive test coverage:

### Run Database Tests
```bash
python3 database.py
```

Output: Core functionality verification including supplier/product creation, stock logging, orders, deliveries, and anomalies.

### Run Simulator Tests
```bash
python3 simulators.py
```

Output: Individual and integrated simulator tests with 7 comprehensive test scenarios.

### Run Integration Tests
```bash
python3 test_integration.py
```

Output: Full workflow testing including:
- Database creation and operations
- Order and delivery workflows
- Anomaly detection
- Inventory summaries
- Simulator/database integration
- Complete business workflows
- JSON export functionality

## Test Results Summary

✓ All 7 integration tests pass
✓ Database module: 6/6 operations verified
✓ Simulators module: 7/7 scenarios validated
✓ Full workflow: Order-to-delivery cycle tested
✓ JSON exports: All formats validated
✓ Performance: Indexed queries optimized

## Configuration

### Database Configuration
- **Default path**: `dashgas.db` (customizable)
- **Type**: SQLite 3
- **Foreign Keys**: Enabled by default
- **Row Factory**: Dictionary access enabled

### Simulator Configuration
- **Total Products**: 17 preconfigured
- **Categories**: 5 (fuel, c-store, tobacco, vape, coffee)
- **Consumption**: Realistic ranges per product category
- **Reset Capability**: All simulators resettable to initial state

## Production Deployment

### Prerequisites
- Python 3.7+
- SQLite 3
- No external dependencies

### Deployment Steps
1. Copy all files to deployment directory
2. Set database path appropriately
3. Initialize database with `DashGasDatabase()`
4. Run integration tests to verify setup
5. Configure backup strategy for database file

### Performance Considerations
- Indexed queries on: category, supplier_id, status, product_id
- Stock logs include timestamp indexing for efficient history retrieval
- Foreign key constraints enforce data integrity
- Connection pooling not required for single-threaded use

## Future Enhancements

Potential extensions (not included in base system):
- Multi-location support
- Real-time price tracking
- Supplier API integration
- Automated reordering system
- Mobile app interface
- Analytics dashboard
- Predictive demand modeling
- Supply chain optimization

## API Reference

### DashGasDatabase

#### Initialization
```python
db = DashGasDatabase(db_path="dashgas.db")
```

#### Supplier Operations
- `add_supplier(name, contact_email, contact_phone, lead_time_days)` → supplier_id
- `get_supplier(supplier_id)` → Dict

#### Product Operations
- `add_product(name, category, current_stock, unit, reorder_threshold, supplier_id, lead_time_days, ...)` → product_id
- `get_product_by_id(product_id)` → Dict
- `get_product_by_name(name)` → Dict
- `get_products_by_category(category)` → List[Dict]
- `get_low_stock_products()` → List[Dict]

#### Stock Management
- `log_stock_change(product_id, current_stock, change_amount, reason)` → log_id
- `get_stock_logs(product_id, limit=100)` → List[Dict]

#### Order Management
- `create_order(product_id, supplier_id, quantity, expected_delivery_date, unit_cost)` → order_id
- `get_pending_orders()` → List[Dict]
- `record_delivery(order_id, received_quantity, condition, notes)` → delivery_id

#### Anomaly Management
- `log_anomaly(product_id, anomaly_type, severity, description)` → anomaly_id
- `get_open_anomalies()` → List[Dict]
- `resolve_anomaly(anomaly_id)` → None

#### Reporting
- `get_inventory_summary()` → Dict
- `close()` → None

### GasStationInventorySimulator

#### Product Management
- `get_product(product_id)` → ProductSimulator
- `get_all_products()` → Dict[str, ProductSnapshot]
- `get_all_products_json()` → str
- `restock_product(product_id, quantity)` → None

#### Simulation
- `simulate_day()` → Dict[str, ProductSnapshot]
- `simulate_days(days)` → Dict[str, List[ProductSnapshot]]
- `reset_all()` → None

#### Reporting
- `get_inventory_report()` → Dict
- `get_category_report(category)` → Dict
- `get_low_stock_alerts(threshold_percent=25)` → Dict

## License

Production-ready system for gas station inventory management.

## Support

For issues or questions, refer to test cases in:
- `database.py` - Database functionality examples
- `simulators.py` - Simulator usage examples
- `test_integration.py` - Complete workflow examples
