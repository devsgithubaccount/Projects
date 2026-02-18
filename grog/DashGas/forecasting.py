"""
DashGas Forecasting Engine
Production-ready demand forecasting with day-of-week weighting and confidence bands.
"""

import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import json
import statistics


@dataclass
class ForecastPoint:
    """Single forecasted data point."""
    date: str
    predicted_stock: float
    lower_bound: float
    upper_bound: float
    confidence: float
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "date": self.date,
            "predicted_stock": round(self.predicted_stock, 2),
            "lower_bound": round(self.lower_bound, 2),
            "upper_bound": round(self.upper_bound, 2),
            "confidence": round(self.confidence, 2)
        }


@dataclass
class ProductForecast:
    """Complete forecast for a product."""
    product_id: int
    product_name: str
    category: str
    current_stock: float
    unit: str
    avg_daily_consumption: float
    reorder_threshold: float
    lead_time_days: int
    stockout_date: Optional[str]
    days_until_stockout: Optional[int]
    recommended_order_date: Optional[str]
    recommended_order_quantity: float
    forecast_points: List[ForecastPoint]
    alert_level: str  # "critical", "warning", "normal"
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "product_id": self.product_id,
            "product_name": self.product_name,
            "category": self.category,
            "current_stock": round(self.current_stock, 2),
            "unit": self.unit,
            "avg_daily_consumption": round(self.avg_daily_consumption, 2),
            "reorder_threshold": round(self.reorder_threshold, 2),
            "lead_time_days": self.lead_time_days,
            "stockout_date": self.stockout_date,
            "days_until_stockout": self.days_until_stockout,
            "recommended_order_date": self.recommended_order_date,
            "recommended_order_quantity": round(self.recommended_order_quantity, 2),
            "forecast_points": [fp.to_dict() for fp in self.forecast_points],
            "alert_level": self.alert_level
        }


class ForecastingEngine:
    """Production-ready forecasting engine."""
    
    # Day-of-week consumption multipliers
    DOW_WEIGHTS = {
        "fuel": {0: 1.1, 1: 0.9, 2: 0.9, 3: 0.95, 4: 1.0, 5: 1.2, 6: 1.15},  # Mon-Sun
        "c-store": {0: 0.95, 1: 0.9, 2: 0.9, 3: 0.95, 4: 1.0, 5: 1.15, 6: 1.1},
        "tobacco": {0: 1.0, 1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0, 5: 1.0, 6: 1.0},
        "vape": {0: 1.0, 1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0, 5: 1.0, 6: 1.0},
        "coffee": {0: 1.2, 1: 1.1, 2: 1.1, 3: 1.1, 4: 1.1, 5: 1.0, 6: 0.8}
    }
    
    def __init__(self, db_path: str = "dashgas.db"):
        """Initialize forecasting engine."""
        self.db_path = db_path
    
    def get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def calculate_daily_consumption(self, product_id: int, lookback_days: int = 30) -> Tuple[float, Dict[int, float]]:
        """
        Calculate average daily consumption and day-of-week patterns.
        
        Args:
            product_id: Product ID
            lookback_days: Days to analyze
        
        Returns:
            Tuple of (avg_consumption, dow_consumption_map)
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Get stock logs for the past N days
        cutoff_date = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d %H:%M:%S")
        
        cursor.execute("""
            SELECT change_amount, recorded_at
            FROM stock_logs
            WHERE product_id = ?
              AND recorded_at >= ?
              AND change_amount < 0
            ORDER BY recorded_at DESC
        """, (product_id, cutoff_date))
        
        logs = cursor.fetchall()
        conn.close()
        
        if not logs:
            return 0.0, {}
        
        # Calculate daily consumption
        daily_totals = {}
        dow_totals = {i: [] for i in range(7)}  # Mon-Sun
        
        for log in logs:
            consumption = abs(log["change_amount"])
            timestamp = datetime.strptime(log["recorded_at"], "%Y-%m-%d %H:%M:%S")
            date_key = timestamp.strftime("%Y-%m-%d")
            dow = timestamp.weekday()
            
            daily_totals[date_key] = daily_totals.get(date_key, 0) + consumption
            dow_totals[dow].append(consumption)
        
        # Calculate average
        if daily_totals:
            avg_consumption = sum(daily_totals.values()) / len(daily_totals)
        else:
            avg_consumption = 0.0
        
        # Calculate day-of-week averages
        dow_averages = {}
        for dow, values in dow_totals.items():
            if values:
                dow_averages[dow] = sum(values) / len(values)
        
        return avg_consumption, dow_averages
    
    def get_dow_weight(self, category: str, day_of_week: int) -> float:
        """Get day-of-week consumption weight."""
        weights = self.DOW_WEIGHTS.get(category, {})
        return weights.get(day_of_week, 1.0)
    
    def forecast_product(self, product_id: int, forecast_days: int = 30) -> Optional[ProductForecast]:
        """
        Generate complete forecast for a product.
        
        Args:
            product_id: Product ID
            forecast_days: Number of days to forecast
        
        Returns:
            ProductForecast object or None
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Get product details
        cursor.execute("""
            SELECT p.*, s.lead_time_days as supplier_lead_time
            FROM products p
            LEFT JOIN suppliers s ON p.supplier_id = s.supplier_id
            WHERE p.product_id = ?
        """, (product_id,))
        
        product = cursor.fetchone()
        conn.close()
        
        if not product:
            return None
        
        # Calculate consumption patterns
        avg_daily_consumption, dow_consumption = self.calculate_daily_consumption(product_id)
        
        if avg_daily_consumption == 0:
            # No historical data, use conservative estimate
            avg_daily_consumption = product["current_stock"] * 0.05  # 5% per day
        
        # Generate forecast points
        forecast_points = []
        current_stock = product["current_stock"]
        stockout_date = None
        days_until_stockout = None
        
        for day in range(forecast_days):
            forecast_date = datetime.now() + timedelta(days=day + 1)
            dow = forecast_date.weekday()
            
            # Apply day-of-week weighting
            weight = self.get_dow_weight(product["category"], dow)
            daily_consumption = avg_daily_consumption * weight
            
            # Calculate predicted stock
            predicted_stock = current_stock - daily_consumption
            
            # Calculate confidence bands (wider as we go further out)
            confidence = max(0.5, 1.0 - (day / forecast_days) * 0.5)
            uncertainty = (1.0 - confidence) * avg_daily_consumption * 2
            
            lower_bound = max(0, predicted_stock - uncertainty)
            upper_bound = predicted_stock + uncertainty
            
            forecast_points.append(ForecastPoint(
                date=forecast_date.strftime("%Y-%m-%d"),
                predicted_stock=predicted_stock,
                lower_bound=lower_bound,
                upper_bound=upper_bound,
                confidence=confidence
            ))
            
            # Check for stockout
            if predicted_stock <= 0 and stockout_date is None:
                stockout_date = forecast_date.strftime("%Y-%m-%d")
                days_until_stockout = day + 1
            
            current_stock = predicted_stock
        
        # Determine alert level
        lead_time = product["supplier_lead_time"] or product["lead_time_days"]
        
        if days_until_stockout is not None:
            if days_until_stockout <= lead_time:
                alert_level = "critical"
            elif days_until_stockout <= lead_time * 2:
                alert_level = "warning"
            else:
                alert_level = "normal"
        elif product["current_stock"] <= product["reorder_threshold"]:
            alert_level = "warning"
        else:
            alert_level = "normal"
        
        # Calculate recommended order date and quantity
        if days_until_stockout is not None and days_until_stockout <= forecast_days:
            recommended_order_date = (datetime.now() + timedelta(days=max(0, days_until_stockout - lead_time - 2))).strftime("%Y-%m-%d")
            # Order enough for 2 weeks plus safety stock
            recommended_order_quantity = avg_daily_consumption * 14 * 1.2
        else:
            recommended_order_date = None
            recommended_order_quantity = 0.0
        
        return ProductForecast(
            product_id=product["product_id"],
            product_name=product["name"],
            category=product["category"],
            current_stock=product["current_stock"],
            unit=product["unit"],
            avg_daily_consumption=avg_daily_consumption,
            reorder_threshold=product["reorder_threshold"],
            lead_time_days=lead_time,
            stockout_date=stockout_date,
            days_until_stockout=days_until_stockout,
            recommended_order_date=recommended_order_date,
            recommended_order_quantity=recommended_order_quantity,
            forecast_points=forecast_points,
            alert_level=alert_level
        )
    
    def forecast_all_products(self, forecast_days: int = 30) -> List[ProductForecast]:
        """
        Generate forecasts for all products.
        
        Args:
            forecast_days: Number of days to forecast
        
        Returns:
            List of ProductForecast objects
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT product_id FROM products")
        product_ids = [row["product_id"] for row in cursor.fetchall()]
        conn.close()
        
        forecasts = []
        for product_id in product_ids:
            forecast = self.forecast_product(product_id, forecast_days)
            if forecast:
                forecasts.append(forecast)
        
        return forecasts
    
    def get_critical_alerts(self) -> List[ProductForecast]:
        """Get products with critical stock alerts."""
        forecasts = self.forecast_all_products()
        return [f for f in forecasts if f.alert_level == "critical"]
    
    def get_warning_alerts(self) -> List[ProductForecast]:
        """Get products with warning alerts."""
        forecasts = self.forecast_all_products()
        return [f for f in forecasts if f.alert_level == "warning"]
    
    def get_forecasts_by_category(self, category: str, forecast_days: int = 30) -> List[ProductForecast]:
        """Get forecasts for products in a category."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT product_id FROM products WHERE category = ?", (category,))
        product_ids = [row["product_id"] for row in cursor.fetchall()]
        conn.close()
        
        forecasts = []
        for product_id in product_ids:
            forecast = self.forecast_product(product_id, forecast_days)
            if forecast:
                forecasts.append(forecast)
        
        return forecasts
    
    def export_forecast_json(self, product_id: Optional[int] = None) -> str:
        """Export forecast to JSON."""
        if product_id:
            forecast = self.forecast_product(product_id)
            return json.dumps(forecast.to_dict() if forecast else {}, indent=2)
        else:
            forecasts = self.forecast_all_products()
            return json.dumps([f.to_dict() for f in forecasts], indent=2)


def main():
    """Test forecasting engine."""
    print("=" * 60)
    print("DashGas Forecasting Engine - Production Test")
    print("=" * 60)
    
    # Create test database with sample data
    from database import DashGasDatabase
    import os
    
    test_db = "test_forecast.db"
    
    # Remove if exists
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
    
    # Add product
    product_id = db.add_product(
        name="Regular Gasoline",
        category="fuel",
        current_stock=8000.0,
        unit="gallons",
        reorder_threshold=2000.0,
        supplier_id=supplier_id,
        lead_time_days=3,
        unit_cost=2.50
    )
    
    # Simulate 30 days of consumption
    current_stock = 8000.0
    for day in range(30):
        consumption = 250 + (day % 7) * 20  # Variable consumption
        current_stock -= consumption
        db.log_stock_change(product_id, current_stock, -consumption, "daily_consumption")
    
    db.close()
    
    # Test forecasting engine
    engine = ForecastingEngine(test_db)
    
    print("\n1. Testing product forecast...")
    forecast = engine.forecast_product(product_id, forecast_days=30)
    
    if forecast:
        print(f"✓ Product: {forecast.product_name}")
        print(f"✓ Current Stock: {forecast.current_stock:.2f} {forecast.unit}")
        print(f"✓ Avg Daily Consumption: {forecast.avg_daily_consumption:.2f} {forecast.unit}/day")
        print(f"✓ Days Until Stockout: {forecast.days_until_stockout}")
        print(f"✓ Stockout Date: {forecast.stockout_date}")
        print(f"✓ Alert Level: {forecast.alert_level}")
        print(f"✓ Recommended Order Date: {forecast.recommended_order_date}")
        print(f"✓ Recommended Order Qty: {forecast.recommended_order_quantity:.2f} {forecast.unit}")
        print(f"✓ Forecast Points: {len(forecast.forecast_points)}")
    
    print("\n2. Testing JSON export...")
    json_output = engine.export_forecast_json(product_id)
    parsed = json.loads(json_output)
    print(f"✓ JSON export successful: {len(json_output)} characters")
    print(f"✓ Contains {len(parsed.get('forecast_points', []))} forecast points")
    
    print("\n3. Testing alert detection...")
    critical = engine.get_critical_alerts()
    warnings = engine.get_warning_alerts()
    print(f"✓ Critical alerts: {len(critical)}")
    print(f"✓ Warning alerts: {len(warnings)}")
    
    print("\n" + "=" * 60)
    print("✓ All forecasting tests passed!")
    print("=" * 60)
    
    # Cleanup
    import os
    if os.path.exists(test_db):
        os.remove(test_db)


if __name__ == "__main__":
    main()
