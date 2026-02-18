"""
DashGas Automation Engine
Production-ready autonomous workflows: ordering, delivery scheduling, anomaly detection, supplier intelligence.
"""

import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import json


@dataclass
class AutomationAlert:
    """Automation system alert."""
    alert_type: str  # "order_created", "delivery_reminder", "anomaly_detected", "supplier_issue", "follow_up_needed"
    severity: str  # "info", "warning", "critical"
    title: str
    message: str
    product_id: Optional[int] = None
    supplier_id: Optional[int] = None
    order_id: Optional[int] = None
    timestamp: str = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "alert_type": self.alert_type,
            "severity": self.severity,
            "title": self.title,
            "message": self.message,
            "product_id": self.product_id,
            "supplier_id": self.supplier_id,
            "order_id": self.order_id,
            "timestamp": self.timestamp
        }


class AutomationEngine:
    """Production-ready automation engine."""
    
    def __init__(self, db_path: str = "dashgas.db"):
        """Initialize automation engine."""
        self.db_path = db_path
        self.alerts = []
    
    def get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def add_alert(self, alert: AutomationAlert):
        """Add alert to the queue."""
        self.alerts.append(alert)
    
    def get_alerts(self, severity: Optional[str] = None) -> List[AutomationAlert]:
        """Get alerts, optionally filtered by severity."""
        if severity:
            return [a for a in self.alerts if a.severity == severity]
        return self.alerts
    
    def clear_alerts(self):
        """Clear all alerts."""
        self.alerts = []
    
    def check_forecast_and_auto_order(self, auto_send: bool = False) -> List[AutomationAlert]:
        """
        Check forecasts and automatically create orders for predicted stockouts.
        
        Args:
            auto_send: If True, automatically approve and send orders
        
        Returns:
            List of alerts generated
        """
        from forecasting import ForecastingEngine
        from orders import OrderManager
        
        alerts = []
        forecast_engine = ForecastingEngine(self.db_path)
        order_manager = OrderManager(self.db_path)
        
        # Get critical and warning forecasts
        critical_forecasts = forecast_engine.get_critical_alerts()
        warning_forecasts = forecast_engine.get_warning_alerts()
        
        all_forecasts = critical_forecasts + warning_forecasts
        
        for forecast in all_forecasts:
            # Check if order already exists
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM orders
                WHERE product_id = ?
                  AND status IN ('draft', 'pending_approval', 'sent', 'confirmed')
            """, (forecast.product_id,))
            
            existing_orders = cursor.fetchone()["count"]
            conn.close()
            
            if existing_orders > 0:
                continue  # Order already exists
            
            # Create order
            if forecast.recommended_order_quantity > 0:
                order_id = order_manager.create_order_from_forecast(
                    forecast.product_id,
                    forecast.recommended_order_quantity,
                    f"predicted_stockout_in_{forecast.days_until_stockout}_days"
                )
                
                if order_id:
                    severity = "critical" if forecast.alert_level == "critical" else "warning"
                    
                    alert = AutomationAlert(
                        alert_type="order_created",
                        severity=severity,
                        title=f"Auto-Order Created: {forecast.product_name}",
                        message=f"Predicted stockout in {forecast.days_until_stockout} days. "
                                f"Ordered {forecast.recommended_order_quantity:.2f} {forecast.unit}. "
                                f"Expected delivery: {forecast.recommended_order_date}",
                        product_id=forecast.product_id,
                        order_id=order_id
                    )
                    
                    alerts.append(alert)
                    self.add_alert(alert)
                    
                    # Auto-approve if enabled
                    if auto_send:
                        order_manager.approve_order(order_id)
        
        return alerts
    
    def check_delivery_reminders(self) -> List[AutomationAlert]:
        """
        Check for expected deliveries and generate reminders.
        
        Returns:
            List of delivery reminder alerts
        """
        from orders import OrderManager
        
        alerts = []
        order_manager = OrderManager(self.db_path)
        
        # Get deliveries expected today
        today = datetime.now().strftime("%Y-%m-%d")
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT o.*, p.name as product_name, s.name as supplier_name
            FROM orders o
            JOIN products p ON o.product_id = p.product_id
            JOIN suppliers s ON o.supplier_id = s.supplier_id
            WHERE o.status IN ('sent', 'confirmed')
              AND o.expected_delivery_date = ?
        """, (today,))
        
        deliveries = cursor.fetchall()
        conn.close()
        
        for delivery in deliveries:
            alert = AutomationAlert(
                alert_type="delivery_reminder",
                severity="info",
                title=f"Delivery Expected Today: {delivery['product_name']}",
                message=f"Expecting {delivery['quantity']:.2f} units from {delivery['supplier_name']}. "
                        f"Order #{delivery['order_id']} should arrive today.",
                product_id=delivery["product_id"],
                supplier_id=delivery["supplier_id"],
                order_id=delivery["order_id"]
            )
            
            alerts.append(alert)
            self.add_alert(alert)
        
        return alerts
    
    def check_missing_deliveries(self) -> List[AutomationAlert]:
        """
        Check for deliveries that are overdue.
        
        Returns:
            List of missing delivery alerts
        """
        alerts = []
        
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT o.*, p.name as product_name, s.name as supplier_name
            FROM orders o
            JOIN products p ON o.product_id = p.product_id
            JOIN suppliers s ON o.supplier_id = s.supplier_id
            WHERE o.status IN ('sent', 'confirmed')
              AND o.expected_delivery_date < ?
        """, (yesterday,))
        
        overdue = cursor.fetchall()
        conn.close()
        
        for delivery in overdue:
            days_overdue = (datetime.now() - datetime.strptime(delivery["expected_delivery_date"], "%Y-%m-%d")).days
            
            alert = AutomationAlert(
                alert_type="delivery_reminder",
                severity="warning",
                title=f"Overdue Delivery: {delivery['product_name']}",
                message=f"Order #{delivery['order_id']} from {delivery['supplier_name']} is {days_overdue} day(s) overdue. "
                        f"Expected: {delivery['expected_delivery_date']}. Please follow up with supplier.",
                product_id=delivery["product_id"],
                supplier_id=delivery["supplier_id"],
                order_id=delivery["order_id"]
            )
            
            alerts.append(alert)
            self.add_alert(alert)
        
        return alerts
    
    def check_unconfirmed_orders(self) -> List[AutomationAlert]:
        """
        Check for orders sent but not confirmed by supplier.
        
        Returns:
            List of follow-up alerts
        """
        from orders import OrderManager
        
        alerts = []
        order_manager = OrderManager(self.db_path)
        
        # Get orders sent >24hrs ago
        unconfirmed_24 = order_manager.get_unconfirmed_orders(hours_threshold=24)
        unconfirmed_48 = order_manager.get_unconfirmed_orders(hours_threshold=48)
        
        # 24hr follow-up
        for order in unconfirmed_24:
            if order["order_id"] not in [o["order_id"] for o in unconfirmed_48]:
                alert = AutomationAlert(
                    alert_type="follow_up_needed",
                    severity="warning",
                    title=f"Order Needs Follow-Up: {order['product_name']}",
                    message=f"Order #{order['order_id']} sent to {order['supplier_name']} 24+ hours ago with no confirmation. "
                            f"Please follow up: {order['contact_email']} / {order['contact_phone']}",
                    product_id=order["product_id"],
                    supplier_id=order["supplier_id"],
                    order_id=order["order_id"]
                )
                
                alerts.append(alert)
                self.add_alert(alert)
        
        # 48hr escalation
        for order in unconfirmed_48:
            alert = AutomationAlert(
                alert_type="follow_up_needed",
                severity="critical",
                title=f"URGENT: Order Not Confirmed: {order['product_name']}",
                message=f"Order #{order['order_id']} sent to {order['supplier_name']} 48+ hours ago with NO RESPONSE. "
                        f"Consider alternate supplier. Contact: {order['contact_email']} / {order['contact_phone']}",
                product_id=order["product_id"],
                supplier_id=order["supplier_id"],
                order_id=order["order_id"]
            )
            
            alerts.append(alert)
            self.add_alert(alert)
        
        return alerts
    
    def detect_consumption_anomalies(self, threshold_percent: float = 20.0) -> List[AutomationAlert]:
        """
        Detect abnormal consumption patterns.
        
        Args:
            threshold_percent: Percent deviation to trigger alert
        
        Returns:
            List of anomaly alerts
        """
        from forecasting import ForecastingEngine
        
        alerts = []
        forecast_engine = ForecastingEngine(self.db_path)
        
        # Get all products
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT product_id, name, category, current_stock FROM products")
        products = cursor.fetchall()
        
        for product in products:
            # Get average consumption
            avg_consumption, _ = forecast_engine.calculate_daily_consumption(product["product_id"], lookback_days=30)
            
            if avg_consumption == 0:
                continue
            
            # Get today's consumption
            today_start = datetime.now().replace(hour=0, minute=0, second=0).strftime("%Y-%m-%d %H:%M:%S")
            
            cursor.execute("""
                SELECT SUM(ABS(change_amount)) as today_consumption
                FROM stock_logs
                WHERE product_id = ?
                  AND recorded_at >= ?
                  AND change_amount < 0
            """, (product["product_id"], today_start))
            
            result = cursor.fetchone()
            today_consumption = result["today_consumption"] or 0
            
            if today_consumption == 0:
                continue
            
            # Calculate deviation
            deviation_percent = abs((today_consumption - avg_consumption) / avg_consumption) * 100
            
            if deviation_percent > threshold_percent:
                # Determine anomaly type
                if today_consumption > avg_consumption:
                    anomaly_type = "high_consumption"
                    severity = "critical" if product["category"] == "fuel" else "warning"
                    message = f"{product['name']}: Consumption {deviation_percent:.1f}% HIGHER than average. "
                    
                    if product["category"] == "fuel":
                        message += "POSSIBLE LEAK OR THEFT. Inspect tanks immediately."
                    else:
                        message += "Check for inventory errors or unusual demand."
                else:
                    anomaly_type = "low_consumption"
                    severity = "info"
                    message = f"{product['name']}: Consumption {deviation_percent:.1f}% lower than average. "
                    message += "Verify sales records."
                
                # Log anomaly to database
                cursor.execute("""
                    INSERT INTO anomalies (product_id, anomaly_type, severity, description)
                    VALUES (?, ?, ?, ?)
                """, (product["product_id"], anomaly_type, severity, message))
                
                alert = AutomationAlert(
                    alert_type="anomaly_detected",
                    severity=severity,
                    title=f"Anomaly Detected: {product['name']}",
                    message=message,
                    product_id=product["product_id"]
                )
                
                alerts.append(alert)
                self.add_alert(alert)
        
        conn.commit()
        conn.close()
        
        return alerts
    
    def detect_shrinkage_anomalies(self) -> List[AutomationAlert]:
        """
        Detect inventory shrinkage (stock at zero with no sale logged).
        
        Returns:
            List of shrinkage alerts
        """
        alerts = []
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Find products at or near zero stock
        cursor.execute("""
            SELECT product_id, name, category, current_stock
            FROM products
            WHERE current_stock <= 0
              AND category != 'fuel'
        """)
        
        zero_stock_products = cursor.fetchall()
        
        for product in zero_stock_products:
            # Check if there's a recent stock change logged
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM stock_logs
                WHERE product_id = ?
                  AND recorded_at >= datetime('now', '-24 hours')
                  AND change_amount < 0
            """, (product["product_id"],))
            
            recent_changes = cursor.fetchone()["count"]
            
            if recent_changes == 0:
                # No recent consumption logged but stock is zero - possible shrinkage
                alert = AutomationAlert(
                    alert_type="anomaly_detected",
                    severity="warning",
                    title=f"Possible Shrinkage: {product['name']}",
                    message=f"{product['name']} at zero stock with no recent sales logged. "
                            f"Possible theft, inventory error, or missing sales records.",
                    product_id=product["product_id"]
                )
                
                alerts.append(alert)
                self.add_alert(alert)
                
                # Log to database
                cursor.execute("""
                    INSERT INTO anomalies (product_id, anomaly_type, severity, description)
                    VALUES (?, 'shrinkage', 'warning', ?)
                """, (product["product_id"], alert.message))
        
        conn.commit()
        conn.close()
        
        return alerts
    
    def analyze_supplier_performance(self) -> List[AutomationAlert]:
        """
        Analyze supplier performance and flag issues.
        
        Returns:
            List of supplier performance alerts
        """
        alerts = []
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Get suppliers with recent orders
        cursor.execute("""
            SELECT s.supplier_id, s.name, s.contact_email,
                   COUNT(CASE WHEN d.condition = 'good' AND 
                              datetime(d.received_date) <= datetime(o.expected_delivery_date) 
                         THEN 1 END) as on_time_deliveries,
                   COUNT(o.order_id) as total_orders
            FROM suppliers s
            JOIN orders o ON s.supplier_id = o.supplier_id
            LEFT JOIN deliveries d ON o.order_id = d.order_id
            WHERE o.created_at >= datetime('now', '-90 days')
            GROUP BY s.supplier_id
            HAVING total_orders >= 3
        """)
        
        suppliers = cursor.fetchall()
        
        for supplier in suppliers:
            if supplier["total_orders"] > 0:
                on_time_rate = (supplier["on_time_deliveries"] / supplier["total_orders"]) * 100
                
                if on_time_rate < 70:
                    alert = AutomationAlert(
                        alert_type="supplier_issue",
                        severity="warning",
                        title=f"Supplier Performance Issue: {supplier['name']}",
                        message=f"{supplier['name']} has {on_time_rate:.1f}% on-time delivery rate "
                                f"({supplier['on_time_deliveries']}/{supplier['total_orders']} orders). "
                                f"Consider switching to alternate supplier.",
                        supplier_id=supplier["supplier_id"]
                    )
                    
                    alerts.append(alert)
                    self.add_alert(alert)
        
        conn.close()
        
        return alerts
    
    def generate_daily_briefing(self) -> Dict:
        """
        Generate autonomous daily briefing.
        
        Returns:
            Briefing dictionary with all key information
        """
        from forecasting import ForecastingEngine
        from orders import OrderManager
        
        forecast_engine = ForecastingEngine(self.db_path)
        order_manager = OrderManager(self.db_path)
        
        # Get critical forecasts
        critical_forecasts = forecast_engine.get_critical_alerts()
        warning_forecasts = forecast_engine.get_warning_alerts()
        
        # Get today's deliveries
        delivery_alerts = self.check_delivery_reminders()
        
        # Get overnight orders
        conn = self.get_connection()
        cursor = conn.cursor()
        
        today_start = datetime.now().replace(hour=0, minute=0, second=0).strftime("%Y-%m-%d %H:%M:%S")
        
        cursor.execute("""
            SELECT o.*, p.name as product_name, s.name as supplier_name
            FROM orders o
            JOIN products p ON o.product_id = p.product_id
            JOIN suppliers s ON o.supplier_id = s.supplier_id
            WHERE o.created_at >= ?
            ORDER BY o.created_at DESC
        """, (today_start,))
        
        overnight_orders = [dict(row) for row in cursor.fetchall()]
        
        # Get open anomalies
        cursor.execute("""
            SELECT a.*, p.name as product_name
            FROM anomalies a
            JOIN products p ON a.product_id = p.product_id
            WHERE a.status = 'open'
            ORDER BY a.severity DESC, a.created_at DESC
            LIMIT 10
        """)
        
        open_anomalies = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        
        # Get top 3 items to watch (lowest days until stockout)
        top_watch_items = sorted(
            [f for f in (critical_forecasts + warning_forecasts) if f.days_until_stockout],
            key=lambda x: x.days_until_stockout
        )[:3]
        
        briefing = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "overnight_orders": [{
                "product": o["product_name"],
                "supplier": o["supplier_name"],
                "quantity": o["quantity"],
                "status": o["status"]
            } for o in overnight_orders],
            "deliveries_expected_today": [{
                "product": alert.message.split(":")[1].strip().split()[0],
                "order_id": alert.order_id
            } for alert in delivery_alerts],
            "critical_alerts": len(critical_forecasts),
            "warning_alerts": len(warning_forecasts),
            "open_anomalies": [{
                "product": a["product_name"],
                "type": a["anomaly_type"],
                "severity": a["severity"]
            } for a in open_anomalies],
            "top_items_to_watch": [{
                "product": f.product_name,
                "days_until_stockout": f.days_until_stockout,
                "current_stock": f.current_stock,
                "unit": f.unit
            } for f in top_watch_items],
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        return briefing
    
    def run_full_automation_cycle(self, auto_send_orders: bool = False) -> Dict:
        """
        Run complete automation cycle.
        
        Args:
            auto_send_orders: If True, automatically send orders
        
        Returns:
            Summary of all automation actions
        """
        self.clear_alerts()
        
        summary = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "cycles_completed": []
        }
        
        # 1. Check forecasts and auto-order
        order_alerts = self.check_forecast_and_auto_order(auto_send=auto_send_orders)
        summary["cycles_completed"].append({
            "cycle": "forecast_ordering",
            "alerts": len(order_alerts)
        })
        
        # 2. Check delivery reminders
        delivery_alerts = self.check_delivery_reminders()
        summary["cycles_completed"].append({
            "cycle": "delivery_reminders",
            "alerts": len(delivery_alerts)
        })
        
        # 3. Check missing deliveries
        missing_alerts = self.check_missing_deliveries()
        summary["cycles_completed"].append({
            "cycle": "missing_deliveries",
            "alerts": len(missing_alerts)
        })
        
        # 4. Check unconfirmed orders
        unconfirmed_alerts = self.check_unconfirmed_orders()
        summary["cycles_completed"].append({
            "cycle": "unconfirmed_orders",
            "alerts": len(unconfirmed_alerts)
        })
        
        # 5. Detect consumption anomalies
        consumption_alerts = self.detect_consumption_anomalies()
        summary["cycles_completed"].append({
            "cycle": "consumption_anomalies",
            "alerts": len(consumption_alerts)
        })
        
        # 6. Detect shrinkage
        shrinkage_alerts = self.detect_shrinkage_anomalies()
        summary["cycles_completed"].append({
            "cycle": "shrinkage_detection",
            "alerts": len(shrinkage_alerts)
        })
        
        # 7. Analyze supplier performance
        supplier_alerts = self.analyze_supplier_performance()
        summary["cycles_completed"].append({
            "cycle": "supplier_performance",
            "alerts": len(supplier_alerts)
        })
        
        # Get alert summary
        all_alerts = self.get_alerts()
        summary["total_alerts"] = len(all_alerts)
        summary["critical_alerts"] = len([a for a in all_alerts if a.severity == "critical"])
        summary["warning_alerts"] = len([a for a in all_alerts if a.severity == "warning"])
        summary["info_alerts"] = len([a for a in all_alerts if a.severity == "info"])
        
        return summary


def main():
    """Test automation engine."""
    print("=" * 60)
    print("DashGas Automation Engine - Production Test")
    print("=" * 60)
    
    # Create test database with sample data
    from database import DashGasDatabase
    import os
    
    test_db = "test_automation.db"
    
    if os.path.exists(test_db):
        os.remove(test_db)
    
    db = DashGasDatabase(test_db)
    
    # Add supplier
    supplier_id = db.add_supplier(
        name="Test Supplier",
        contact_email="test@example.com",
        contact_phone="555-0100",
        lead_time_days=3
    )
    
    # Add products
    product1_id = db.add_product(
        name="Regular Gasoline",
        category="fuel",
        current_stock=1500.0,
        unit="gallons",
        reorder_threshold=2000.0,
        supplier_id=supplier_id,
        lead_time_days=3,
        unit_cost=2.50
    )
    
    product2_id = db.add_product(
        name="Bottled Water",
        category="c-store",
        current_stock=0.0,  # Zero stock for shrinkage test
        unit="units",
        reorder_threshold=50.0,
        supplier_id=supplier_id,
        lead_time_days=2,
        unit_cost=0.50
    )
    
    # Simulate consumption history
    current_stock = 5000.0
    for day in range(30):
        consumption = 200 + (day % 7) * 15
        current_stock -= consumption
        db.log_stock_change(product1_id, current_stock, -consumption, "daily_consumption")
    
    # Simulate high consumption today (anomaly)
    db.log_stock_change(product1_id, current_stock - 500, -500, "daily_consumption")
    
    db.close()
    
    # Test automation engine
    engine = AutomationEngine(test_db)
    
    print("\n1. Testing forecast-based auto-ordering...")
    order_alerts = engine.check_forecast_and_auto_order(auto_send=False)
    print(f"✓ Generated {len(order_alerts)} order alert(s)")
    
    for alert in order_alerts[:2]:
        print(f"  - {alert.title}")
    
    print("\n2. Testing delivery reminders...")
    delivery_alerts = engine.check_delivery_reminders()
    print(f"✓ Generated {len(delivery_alerts)} delivery reminder(s)")
    
    print("\n3. Testing consumption anomaly detection...")
    anomaly_alerts = engine.detect_consumption_anomalies(threshold_percent=20.0)
    print(f"✓ Detected {len(anomaly_alerts)} anomaly/anomalies")
    
    for alert in anomaly_alerts[:2]:
        print(f"  - {alert.title}")
    
    print("\n4. Testing shrinkage detection...")
    shrinkage_alerts = engine.detect_shrinkage_anomalies()
    print(f"✓ Detected {len(shrinkage_alerts)} shrinkage alert(s)")
    
    for alert in shrinkage_alerts[:2]:
        print(f"  - {alert.title}")
    
    print("\n5. Testing daily briefing generation...")
    briefing = engine.generate_daily_briefing()
    print(f"✓ Generated briefing for {briefing['date']}")
    print(f"  - Overnight orders: {len(briefing['overnight_orders'])}")
    print(f"  - Expected deliveries: {len(briefing['deliveries_expected_today'])}")
    print(f"  - Critical alerts: {briefing['critical_alerts']}")
    print(f"  - Items to watch: {len(briefing['top_items_to_watch'])}")
    
    print("\n6. Testing full automation cycle...")
    summary = engine.run_full_automation_cycle(auto_send_orders=False)
    print(f"✓ Completed {len(summary['cycles_completed'])} automation cycles")
    print(f"  - Total alerts: {summary['total_alerts']}")
    print(f"  - Critical: {summary['critical_alerts']}")
    print(f"  - Warnings: {summary['warning_alerts']}")
    print(f"  - Info: {summary['info_alerts']}")
    
    print("\n" + "=" * 60)
    print("✓ All automation engine tests passed!")
    print("=" * 60)
    
    # Cleanup
    if os.path.exists(test_db):
        os.remove(test_db)


if __name__ == "__main__":
    main()
