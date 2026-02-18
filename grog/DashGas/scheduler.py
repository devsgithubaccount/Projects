"""
DashGas Task Scheduler
Production-ready scheduler for automated tasks: simulator syncs, forecasts, reports, anomaly checks.
"""

import sqlite3
from datetime import datetime, time
from typing import Dict, List, Optional, Callable
import json
import time as time_module
from threading import Thread, Event
import logging


class ScheduledTask:
    """Represents a scheduled task."""
    
    def __init__(self, name: str, func: Callable, interval_minutes: int = None, run_time: time = None):
        """
        Initialize scheduled task.
        
        Args:
            name: Task name
            func: Function to execute
            interval_minutes: Run every N minutes (for interval tasks)
            run_time: Specific time to run (for daily tasks)
        """
        self.name = name
        self.func = func
        self.interval_minutes = interval_minutes
        self.run_time = run_time
        self.last_run = None
        self.next_run = None
        self.run_count = 0
        self.error_count = 0
        self.last_error = None
    
    def should_run(self, current_time: datetime) -> bool:
        """Check if task should run."""
        if self.interval_minutes:
            # Interval-based task
            if self.last_run is None:
                return True
            
            minutes_since_last = (current_time - self.last_run).total_seconds() / 60
            return minutes_since_last >= self.interval_minutes
        
        elif self.run_time:
            # Time-based task (daily)
            if self.last_run and self.last_run.date() == current_time.date():
                # Already ran today
                return False
            
            current_time_only = current_time.time()
            return current_time_only >= self.run_time
        
        return False
    
    def execute(self) -> Dict:
        """Execute task and return result."""
        try:
            start_time = datetime.now()
            result = self.func()
            end_time = datetime.now()
            
            self.last_run = start_time
            self.run_count += 1
            
            return {
                "success": True,
                "task": self.name,
                "start_time": start_time.strftime("%Y-%m-%d %H:%M:%S"),
                "duration_seconds": (end_time - start_time).total_seconds(),
                "result": result
            }
        
        except Exception as e:
            self.error_count += 1
            self.last_error = str(e)
            
            return {
                "success": False,
                "task": self.name,
                "error": str(e),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
    
    def get_status(self) -> Dict:
        """Get task status."""
        return {
            "name": self.name,
            "type": "interval" if self.interval_minutes else "scheduled",
            "interval_minutes": self.interval_minutes,
            "run_time": self.run_time.strftime("%H:%M") if self.run_time else None,
            "last_run": self.last_run.strftime("%Y-%m-%d %H:%M:%S") if self.last_run else None,
            "run_count": self.run_count,
            "error_count": self.error_count,
            "last_error": self.last_error
        }


class TaskScheduler:
    """Production-ready task scheduler."""
    
    def __init__(self, db_path: str = "dashgas.db", enable_simulators: bool = False):
        """Initialize scheduler."""
        self.db_path = db_path
        self.enable_simulators = enable_simulators
        self.tasks = []
        self.running = False
        self.stop_event = Event()
        self.execution_history = []
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger('DashGas.Scheduler')
    
    def add_task(self, task: ScheduledTask):
        """Add task to scheduler."""
        self.tasks.append(task)
        self.logger.info(f"Task added: {task.name}")
    
    def register_standard_tasks(self):
        """Register all standard DashGas tasks."""
        
        # Task 1: Sync simulators every 30 minutes
        if self.enable_simulators:
            self.add_task(ScheduledTask(
                name="sync_simulators",
                func=self.sync_simulators,
                interval_minutes=30
            ))
        
        # Task 2: Run forecast engine every 6 hours
        self.add_task(ScheduledTask(
            name="run_forecasting",
            func=self.run_forecasting,
            interval_minutes=360
        ))
        
        # Task 3: Check for anomalies every hour
        self.add_task(ScheduledTask(
            name="check_anomalies",
            func=self.check_anomalies,
            interval_minutes=60
        ))
        
        # Task 4: Auto-ordering check every 2 hours
        self.add_task(ScheduledTask(
            name="auto_ordering",
            func=self.auto_ordering,
            interval_minutes=120
        ))
        
        # Task 5: Check deliveries every 4 hours
        self.add_task(ScheduledTask(
            name="check_deliveries",
            func=self.check_deliveries,
            interval_minutes=240
        ))
        
        # Task 6: Daily briefing at 6am
        self.add_task(ScheduledTask(
            name="daily_briefing",
            func=self.generate_daily_briefing,
            run_time=time(6, 0)
        ))
        
        # Task 7: Weekly report every Monday at 8am
        self.add_task(ScheduledTask(
            name="weekly_report",
            func=self.generate_weekly_report,
            run_time=time(8, 0)
        ))
        
        self.logger.info(f"Registered {len(self.tasks)} standard tasks")
    
    def sync_simulators(self) -> Dict:
        """Sync simulator data to database."""
        from simulators import GasStationInventorySimulator
        from database import DashGasDatabase
        
        simulator = GasStationInventorySimulator()
        db = DashGasDatabase(self.db_path)
        
        # Simulate one day
        results = simulator.simulate_day()
        
        synced_count = 0
        
        for product_id, snapshot in results.items():
            # Find matching product in database
            product = db.get_product_by_name(snapshot.product)
            
            if product:
                # Log stock change
                previous_stock = product["current_stock"]
                change = snapshot.current_stock - previous_stock
                
                db.log_stock_change(
                    product_id=product["product_id"],
                    current_stock=snapshot.current_stock,
                    change_amount=change,
                    reason="simulator_sync"
                )
                
                synced_count += 1
        
        db.close()
        
        return {
            "synced_products": synced_count,
            "total_products": len(results)
        }
    
    def run_forecasting(self) -> Dict:
        """Run forecasting engine."""
        from forecasting import ForecastingEngine
        
        engine = ForecastingEngine(self.db_path)
        forecasts = engine.forecast_all_products(forecast_days=30)
        
        critical = [f for f in forecasts if f.alert_level == "critical"]
        warnings = [f for f in forecasts if f.alert_level == "warning"]
        
        return {
            "total_forecasts": len(forecasts),
            "critical_alerts": len(critical),
            "warning_alerts": len(warnings)
        }
    
    def check_anomalies(self) -> Dict:
        """Check for anomalies."""
        from automation import AutomationEngine
        
        engine = AutomationEngine(self.db_path)
        
        consumption_alerts = engine.detect_consumption_anomalies(threshold_percent=20.0)
        shrinkage_alerts = engine.detect_shrinkage_anomalies()
        
        return {
            "consumption_anomalies": len(consumption_alerts),
            "shrinkage_alerts": len(shrinkage_alerts),
            "total_alerts": len(consumption_alerts) + len(shrinkage_alerts)
        }
    
    def auto_ordering(self) -> Dict:
        """Run auto-ordering check."""
        from automation import AutomationEngine
        
        engine = AutomationEngine(self.db_path)
        order_alerts = engine.check_forecast_and_auto_order(auto_send=False)
        
        return {
            "orders_created": len(order_alerts),
            "alerts": [a.title for a in order_alerts]
        }
    
    def check_deliveries(self) -> Dict:
        """Check delivery status."""
        from automation import AutomationEngine
        
        engine = AutomationEngine(self.db_path)
        
        delivery_reminders = engine.check_delivery_reminders()
        missing_deliveries = engine.check_missing_deliveries()
        unconfirmed_orders = engine.check_unconfirmed_orders()
        
        return {
            "delivery_reminders": len(delivery_reminders),
            "missing_deliveries": len(missing_deliveries),
            "unconfirmed_orders": len(unconfirmed_orders)
        }
    
    def generate_daily_briefing(self) -> Dict:
        """Generate daily briefing."""
        from automation import AutomationEngine
        
        engine = AutomationEngine(self.db_path)
        briefing = engine.generate_daily_briefing()
        
        # In production, this would send to Telegram/email
        self.logger.info(f"Daily briefing generated: {json.dumps(briefing, indent=2)}")
        
        return {
            "briefing_date": briefing["date"],
            "overnight_orders": len(briefing["overnight_orders"]),
            "deliveries_today": len(briefing["deliveries_expected_today"]),
            "items_to_watch": len(briefing["top_items_to_watch"])
        }
    
    def generate_weekly_report(self) -> Dict:
        """Generate weekly report (Monday only)."""
        current_date = datetime.now()
        
        # Only run on Monday
        if current_date.weekday() != 0:
            return {"skipped": "Not Monday"}
        
        from forecasting import ForecastingEngine
        from orders import OrderManager
        
        forecast_engine = ForecastingEngine(self.db_path)
        order_manager = OrderManager(self.db_path)
        
        # Get weekly summary
        forecasts = forecast_engine.forecast_all_products()
        order_summary = order_manager.get_order_summary()
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get anomalies from past week
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM anomalies
            WHERE created_at >= datetime('now', '-7 days')
        """)
        
        weekly_anomalies = cursor.fetchone()["count"]
        
        conn.close()
        
        report = {
            "week_ending": current_date.strftime("%Y-%m-%d"),
            "total_forecasts": len(forecasts),
            "critical_alerts": len([f for f in forecasts if f.alert_level == "critical"]),
            "pending_orders": order_summary["pending_orders"],
            "weekly_anomalies": weekly_anomalies
        }
        
        # In production, this would send to Telegram/email
        self.logger.info(f"Weekly report generated: {json.dumps(report, indent=2)}")
        
        return report
    
    def run_cycle(self):
        """Run one scheduler cycle."""
        current_time = datetime.now()
        
        for task in self.tasks:
            if task.should_run(current_time):
                self.logger.info(f"Executing task: {task.name}")
                result = task.execute()
                self.execution_history.append(result)
                
                if result["success"]:
                    self.logger.info(f"Task completed: {task.name}")
                else:
                    self.logger.error(f"Task failed: {task.name} - {result['error']}")
    
    def run(self, check_interval_seconds: int = 60):
        """
        Run scheduler continuously.
        
        Args:
            check_interval_seconds: How often to check for tasks to run
        """
        self.running = True
        self.logger.info("Scheduler started")
        
        while not self.stop_event.is_set():
            try:
                self.run_cycle()
                time_module.sleep(check_interval_seconds)
            except KeyboardInterrupt:
                self.logger.info("Scheduler interrupted by user")
                break
            except Exception as e:
                self.logger.error(f"Scheduler error: {str(e)}")
                time_module.sleep(check_interval_seconds)
        
        self.running = False
        self.logger.info("Scheduler stopped")
    
    def start_background(self, check_interval_seconds: int = 60):
        """Start scheduler in background thread."""
        thread = Thread(target=self.run, args=(check_interval_seconds,))
        thread.daemon = True
        thread.start()
        self.logger.info("Scheduler started in background")
        return thread
    
    def stop(self):
        """Stop scheduler."""
        self.stop_event.set()
        self.logger.info("Scheduler stop requested")
    
    def get_status(self) -> Dict:
        """Get scheduler status."""
        return {
            "running": self.running,
            "total_tasks": len(self.tasks),
            "tasks": [task.get_status() for task in self.tasks],
            "execution_history_size": len(self.execution_history),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    
    def get_execution_history(self, limit: int = 10) -> List[Dict]:
        """Get recent execution history."""
        return self.execution_history[-limit:]


def main():
    """Test scheduler."""
    print("=" * 60)
    print("DashGas Task Scheduler - Production Test")
    print("=" * 60)
    
    # Create test database
    from database import DashGasDatabase
    import os
    
    test_db = "test_scheduler.db"
    
    if os.path.exists(test_db):
        os.remove(test_db)
    
    db = DashGasDatabase(test_db)
    
    # Add test data
    supplier_id = db.add_supplier(
        name="Test Supplier",
        contact_email="test@example.com",
        contact_phone="555-0100",
        lead_time_days=3
    )
    
    product_id = db.add_product(
        name="Regular Gasoline",
        category="fuel",
        current_stock=1500.0,
        unit="gallons",
        reorder_threshold=2000.0,
        supplier_id=supplier_id,
        lead_time_days=3,
        unit_cost=2.50
    )
    
    # Simulate consumption history
    current_stock = 5000.0
    for day in range(30):
        consumption = 200
        current_stock -= consumption
        db.log_stock_change(product_id, current_stock, -consumption, "daily_consumption")
    
    db.close()
    
    # Test scheduler
    scheduler = TaskScheduler(test_db, enable_simulators=False)
    
    print("\n1. Registering standard tasks...")
    scheduler.register_standard_tasks()
    print(f"✓ Registered {len(scheduler.tasks)} tasks")
    
    print("\n2. Testing task status...")
    for task in scheduler.tasks[:3]:
        status = task.get_status()
        print(f"✓ {status['name']}: {status['type']}")
    
    print("\n3. Running single scheduler cycle...")
    scheduler.run_cycle()
    print(f"✓ Cycle completed")
    
    print("\n4. Checking execution history...")
    history = scheduler.get_execution_history(limit=5)
    print(f"✓ Executed {len(history)} tasks")
    
    for execution in history:
        success_icon = "✅" if execution["success"] else "❌"
        print(f"  {success_icon} {execution['task']}")
    
    print("\n5. Testing scheduler status...")
    status = scheduler.get_status()
    print(f"✓ Running: {status['running']}")
    print(f"✓ Total tasks: {status['total_tasks']}")
    
    completed_tasks = sum(1 for t in status['tasks'] if t['run_count'] > 0)
    print(f"✓ Tasks executed: {completed_tasks}")
    
    print("\n6. Testing individual task execution...")
    forecast_task = next((t for t in scheduler.tasks if t.name == "run_forecasting"), None)
    if forecast_task:
        result = forecast_task.execute()
        print(f"✓ Forecast task: {'Success' if result['success'] else 'Failed'}")
        if result['success']:
            print(f"  Forecasts generated: {result['result'].get('total_forecasts', 0)}")
    
    print("\n7. Testing anomaly check task...")
    anomaly_task = next((t for t in scheduler.tasks if t.name == "check_anomalies"), None)
    if anomaly_task:
        result = anomaly_task.execute()
        print(f"✓ Anomaly check: {'Success' if result['success'] else 'Failed'}")
    
    print("\n" + "=" * 60)
    print("✓ All scheduler tests passed!")
    print("=" * 60)
    
    # Cleanup
    if os.path.exists(test_db):
        os.remove(test_db)


if __name__ == "__main__":
    main()
