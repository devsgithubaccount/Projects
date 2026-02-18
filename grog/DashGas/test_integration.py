"""
Integration tests for DashGas - Database and Simulators
Tests both modules working together in a realistic workflow.
"""

import json
import sys
from database import DashGasDatabase
from simulators import GasStationInventorySimulator
from datetime import datetime, timedelta


def test_database_creation():
    """Test database initialization and basic operations."""
    print("\n[TEST 1] Database Creation and Basic Operations")
    print("-" * 70)
    
    db = DashGasDatabase(":memory:")
    
    # Add suppliers
    supplier1 = db.add_supplier("Shell Wholesale", "shell@example.com", "555-0100", 2)
    supplier2 = db.add_supplier("Chevron Supply", "chevron@example.com", "555-0200", 3)
    print(f"✓ Added 2 suppliers: {supplier1}, {supplier2}")
    
    # Add products
    regular_gas = db.add_product(
        name="Regular Gasoline",
        category="fuel",
        current_stock=10000,
        unit="gallons",
        reorder_threshold=2000,
        supplier_id=supplier1,
        lead_time_days=2,
        min_stock=1000,
        max_stock=15000,
        unit_cost=2.50
    )
    
    premium_gas = db.add_product(
        name="Premium Gasoline",
        category="fuel",
        current_stock=6000,
        unit="gallons",
        reorder_threshold=1500,
        supplier_id=supplier1,
        lead_time_days=2,
        unit_cost=3.50
    )
    
    diesel = db.add_product(
        name="Diesel",
        category="fuel",
        current_stock=8000,
        unit="gallons",
        reorder_threshold=2000,
        supplier_id=supplier2,
        lead_time_days=3,
        unit_cost=2.75
    )
    
    print(f"✓ Added 3 fuel products: Regular, Premium, Diesel")
    
    # Test product queries
    product = db.get_product_by_name("Regular Gasoline")
    assert product["name"] == "Regular Gasoline"
    assert product["current_stock"] == 10000
    print(f"✓ Product query works correctly")
    
    # Test category queries
    fuel_products = db.get_products_by_category("fuel")
    assert len(fuel_products) == 3
    print(f"✓ Category query returned {len(fuel_products)} products")
    
    # Test stock logging
    log1 = db.log_stock_change(regular_gas, 9500, -500, "consumption")
    log2 = db.log_stock_change(regular_gas, 9200, -300, "consumption")
    assert log1 and log2
    print(f"✓ Stock change logging works (2 logs created)")
    
    # Test stock log retrieval
    logs = db.get_stock_logs(regular_gas, limit=10)
    assert len(logs) == 2
    # Logs are in reverse chronological order (most recent first)
    assert logs[0]["change_amount"] == -300  # Most recent: second insertion
    assert logs[1]["change_amount"] == -500  # Older: first insertion
    print(f"✓ Stock log retrieval returns {len(logs)} logs in reverse chronological order")
    
    db.close()
    print("✓ Database tests passed!")
    return True


def test_order_and_delivery():
    """Test order creation and delivery recording."""
    print("\n[TEST 2] Order Creation and Delivery Recording")
    print("-" * 70)
    
    db = DashGasDatabase(":memory:")
    
    # Setup
    supplier = db.add_supplier("Shell Wholesale", "shell@example.com", "555-0100", 2)
    product = db.add_product(
        name="Regular Gasoline",
        category="fuel",
        current_stock=5000,
        unit="gallons",
        reorder_threshold=2000,
        supplier_id=supplier,
        lead_time_days=2,
        unit_cost=2.50
    )
    
    # Create order
    tomorrow = (datetime.now() + timedelta(days=2)).isoformat()
    order_id = db.create_order(
        product_id=product,
        supplier_id=supplier,
        quantity=5000,
        expected_delivery_date=tomorrow,
        unit_cost=2.50
    )
    
    print(f"✓ Order created: {order_id}")
    
    # Check pending orders
    pending = db.get_pending_orders()
    assert len(pending) == 1
    assert pending[0]["status"] == "pending"
    print(f"✓ Pending order retrieval works ({len(pending)} orders)")
    
    # Record delivery
    delivery_id = db.record_delivery(order_id, 5000, "good", "Delivered on time")
    assert delivery_id
    print(f"✓ Delivery recorded: {delivery_id}")
    
    # Verify order status changed
    pending = db.get_pending_orders()
    assert len(pending) == 0
    print(f"✓ Order status updated to 'complete'")
    
    db.close()
    print("✓ Order and delivery tests passed!")
    return True


def test_anomaly_detection():
    """Test anomaly logging and resolution."""
    print("\n[TEST 3] Anomaly Detection and Management")
    print("-" * 70)
    
    db = DashGasDatabase(":memory:")
    
    # Setup
    supplier = db.add_supplier("Shell Wholesale", "shell@example.com", "555-0100", 2)
    product = db.add_product(
        name="Regular Gasoline",
        category="fuel",
        current_stock=10000,
        unit="gallons",
        reorder_threshold=2000,
        supplier_id=supplier,
        lead_time_days=2,
        unit_cost=2.50
    )
    
    # Log anomalies
    anomaly1 = db.log_anomaly(
        product_id=product,
        anomaly_type="high_consumption",
        severity="high",
        description="Consumption 75% above normal"
    )
    
    anomaly2 = db.log_anomaly(
        product_id=product,
        anomaly_type="delivery_delay",
        severity="medium",
        description="Expected delivery delayed by 2 days"
    )
    
    print(f"✓ Anomalies logged: {anomaly1}, {anomaly2}")
    
    # Get open anomalies
    open_anomalies = db.get_open_anomalies()
    assert len(open_anomalies) == 2
    assert all(a["status"] == "open" for a in open_anomalies)
    print(f"✓ Open anomalies retrieved: {len(open_anomalies)}")
    
    # Resolve one anomaly
    db.resolve_anomaly(anomaly1)
    open_anomalies = db.get_open_anomalies()
    assert len(open_anomalies) == 1
    print(f"✓ Anomaly resolved, {len(open_anomalies)} open remaining")
    
    db.close()
    print("✓ Anomaly detection tests passed!")
    return True


def test_inventory_summary():
    """Test inventory summary statistics."""
    print("\n[TEST 4] Inventory Summary Statistics")
    print("-" * 70)
    
    db = DashGasDatabase(":memory:")
    
    # Setup multiple products
    supplier = db.add_supplier("Shell Wholesale", "shell@example.com", "555-0100", 2)
    
    products = []
    for i, (name, stock) in enumerate([
        ("Regular Gasoline", 10000),
        ("Premium Gasoline", 1000),  # Low stock
        ("Diesel", 5000),
        ("Coffee", 100),  # Low stock
    ]):
        product = db.add_product(
            name=name,
            category="fuel" if "Gasoline" in name or "Diesel" in name else "coffee",
            current_stock=stock,
            unit="gallons" if "Gasoline" in name or "Diesel" in name else "units",
            reorder_threshold=2000 if "Gasoline" in name else 500,
            supplier_id=supplier,
            lead_time_days=2,
            unit_cost=2.50
        )
        products.append(product)
    
    # Get summary
    summary = db.get_inventory_summary()
    
    assert summary["total_products"] == 4
    assert summary["low_stock_count"] == 2
    assert summary["total_stock_value"] == 16100
    
    print(f"✓ Total products: {summary['total_products']}")
    print(f"✓ Low stock count: {summary['low_stock_count']}")
    print(f"✓ Total stock value: {summary['total_stock_value']} units")
    
    db.close()
    print("✓ Inventory summary tests passed!")
    return True


def test_simulator_integration():
    """Test simulator data with database."""
    print("\n[TEST 5] Simulator Integration with Database")
    print("-" * 70)
    
    # Create simulators
    sim = GasStationInventorySimulator()
    print(f"✓ Simulator initialized with {len(sim.simulators)} products")
    
    # Create database
    db = DashGasDatabase(":memory:")
    
    # Add supplier
    supplier = db.add_supplier("Fuel Distributor", "fuel@example.com", "555-1000", 2)
    
    # Simulate 1 day and log to database
    results = sim.simulate_day()
    
    added_products = 0
    for sim_id, simulator in sim.simulators.items():
        product_id = db.add_product(
            name=simulator.product_name,
            category=simulator.category,
            current_stock=simulator.current_stock,
            unit=simulator.unit,
            reorder_threshold=simulator.initial_stock * 0.25,
            supplier_id=supplier,
            lead_time_days=2,
            unit_cost=2.50
        )
        
        # Log stock change
        db.log_stock_change(
            product_id=product_id,
            current_stock=simulator.current_stock,
            change_amount=simulator.consumption_history[0] * -1,
            reason="daily_consumption"
        )
        
        added_products += 1
    
    print(f"✓ Added {added_products} products to database from simulator")
    
    # Get database summary
    summary = db.get_inventory_summary()
    print(f"✓ Database inventory: {summary['total_products']} products")
    print(f"✓ Low stock alerts: {summary['low_stock_count']}")
    
    db.close()
    print("✓ Simulator integration tests passed!")
    return True


def test_full_workflow():
    """Test complete workflow: simulate, log, order, deliver."""
    print("\n[TEST 6] Complete Business Workflow")
    print("-" * 70)
    
    # Initialize
    sim = GasStationInventorySimulator()
    db = DashGasDatabase(":memory:")
    
    # Setup suppliers
    supplier1 = db.add_supplier("Shell", "shell@example.com", "555-0100", 2)
    supplier2 = db.add_supplier("Chevron", "chevron@example.com", "555-0200", 3)
    
    # Create products from simulators
    product_map = {}
    for sim_id, simulator in list(sim.simulators.items())[:5]:  # Use first 5 products
        supplier = supplier1 if simulator.category == "fuel" else supplier2
        product_id = db.add_product(
            name=simulator.product_name,
            category=simulator.category,
            current_stock=simulator.current_stock,
            unit=simulator.unit,
            reorder_threshold=simulator.initial_stock * 0.25,
            supplier_id=supplier,
            lead_time_days=2,
            unit_cost=2.50
        )
        product_map[sim_id] = (product_id, supplier)
    
    print(f"✓ Created {len(product_map)} products in database")
    
    # Simulate 5 days
    sim.simulate_days(5)
    
    # Log consumption
    logs_created = 0
    for sim_id, (product_id, supplier) in product_map.items():
        simulator = sim.get_product(sim_id)
        total_consumed = sum(simulator.consumption_history)
        
        db.log_stock_change(
            product_id=product_id,
            current_stock=simulator.current_stock,
            change_amount=-total_consumed,
            reason="5_day_consumption"
        )
        logs_created += 1
    
    print(f"✓ Logged consumption for {logs_created} products")
    
    # Create orders for low stock items
    low_stock = db.get_low_stock_products()
    orders_created = 0
    for product in low_stock:
        order_id = db.create_order(
            product_id=product["product_id"],
            supplier_id=product["supplier_id"],
            quantity=product["reorder_threshold"] * 2,
            expected_delivery_date=(datetime.now() + timedelta(days=2)).isoformat(),
            unit_cost=2.50
        )
        orders_created += 1
    
    print(f"✓ Created {orders_created} reorder(s) for low stock items")
    
    # Record deliveries
    pending = db.get_pending_orders()
    for order in pending[:min(2, len(pending))]:
        db.record_delivery(
            order_id=order["order_id"],
            received_quantity=order["quantity"],
            condition="good",
            notes="Delivery completed"
        )
    
    print(f"✓ Recorded {min(2, len(pending))} deliveries")
    
    # Get final summary
    summary = db.get_inventory_summary()
    print(f"\n  Final Inventory Summary:")
    print(f"    - Total products: {summary['total_products']}")
    print(f"    - Low stock items: {summary['low_stock_count']}")
    print(f"    - Pending orders: {summary['pending_orders']}")
    print(f"    - Open anomalies: {summary['open_anomalies']}")
    
    db.close()
    print("✓ Full workflow test passed!")
    return True


def test_json_exports():
    """Test JSON export functionality."""
    print("\n[TEST 7] JSON Export Functionality")
    print("-" * 70)
    
    sim = GasStationInventorySimulator()
    sim.simulate_day()
    
    # Get all products as JSON
    json_str = sim.get_all_products_json()
    data = json.loads(json_str)
    
    assert isinstance(data, dict)
    assert "regular_gas" in data
    assert data["regular_gas"]["product"] == "Regular Gasoline"
    
    print(f"✓ JSON export successful: {len(data)} products")
    
    # Get inventory report
    report = sim.get_inventory_report()
    assert "timestamp" in report
    assert "categories" in report
    assert "products" in report
    assert report["total_products"] == 17
    
    print(f"✓ Inventory report generated: {len(report['categories'])} categories")
    
    # Get category report
    fuel_report = sim.get_category_report("fuel")
    assert fuel_report["category"] == "fuel"
    assert fuel_report["product_count"] == 4
    
    print(f"✓ Category report generated: {fuel_report['product_count']} fuel products")
    
    print("✓ JSON export tests passed!")
    return True


def main():
    """Run all integration tests."""
    print("=" * 70)
    print("DashGas Integration Test Suite")
    print("=" * 70)
    
    tests = [
        test_database_creation,
        test_order_and_delivery,
        test_anomaly_detection,
        test_inventory_summary,
        test_simulator_integration,
        test_full_workflow,
        test_json_exports,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"✗ Test failed with error: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "=" * 70)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("=" * 70)
    
    if failed == 0:
        print("✓ All integration tests passed!")
        return 0
    else:
        print(f"✗ {failed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
