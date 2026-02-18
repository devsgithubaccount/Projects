"""
DashGas Simulators Module
Provides realistic mock data and consumption simulation for inventory testing.
"""

import json
import random
from datetime import datetime, timedelta
from typing import Dict, List, Any, Callable
from dataclasses import dataclass, asdict
from abc import ABC, abstractmethod


@dataclass
class ProductSnapshot:
    """Represents product state at a point in time."""
    product: str
    category: str
    current_stock: float
    unit: str
    last_updated: str
    
    def to_json(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return asdict(self)
    
    def to_json_string(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_json())


class ProductSimulator(ABC):
    """Base class for product simulators."""
    
    def __init__(self, product_name: str, category: str, unit: str,
                 initial_stock: float, daily_consumption_range: tuple):
        """
        Initialize simulator.
        
        Args:
            product_name: Name of the product
            category: Product category
            unit: Unit of measurement
            initial_stock: Starting stock quantity
            daily_consumption_range: (min, max) daily consumption tuple
        """
        self.product_name = product_name
        self.category = category
        self.unit = unit
        self.current_stock = initial_stock
        self.initial_stock = initial_stock
        self.daily_consumption_range = daily_consumption_range
        self.consumption_history = []
        self.last_updated = datetime.now()
    
    def get_snapshot(self) -> ProductSnapshot:
        """Get current product state as snapshot."""
        return ProductSnapshot(
            product=self.product_name,
            category=self.category,
            current_stock=self.current_stock,
            unit=self.unit,
            last_updated=self.last_updated.isoformat()
        )
    
    def simulate_consumption(self, days: int = 1) -> List[ProductSnapshot]:
        """
        Simulate consumption over multiple days.
        
        Args:
            days: Number of days to simulate
            
        Returns:
            List of snapshots for each day
        """
        snapshots = []
        min_consumption, max_consumption = self.daily_consumption_range
        
        for day in range(days):
            daily_consumption = random.uniform(min_consumption, max_consumption)
            self.current_stock = max(0, self.current_stock - daily_consumption)
            self.consumption_history.append(daily_consumption)
            self.last_updated = datetime.now() + timedelta(days=day)
            
            snapshots.append(self.get_snapshot())
        
        return snapshots
    
    def restock(self, quantity: float):
        """Add stock (simulates delivery)."""
        self.current_stock += quantity
        self.last_updated = datetime.now()
    
    def get_consumption_average(self) -> float:
        """Get average daily consumption."""
        if not self.consumption_history:
            return 0
        return sum(self.consumption_history) / len(self.consumption_history)
    
    def get_days_until_empty(self) -> float:
        """Estimate days until stock depleted."""
        avg_consumption = self.get_consumption_average()
        if avg_consumption == 0:
            return float('inf')
        return self.current_stock / avg_consumption
    
    def reset(self):
        """Reset simulator to initial state."""
        self.current_stock = self.initial_stock
        self.consumption_history = []
        self.last_updated = datetime.now()


class GasolineSimulator(ProductSimulator):
    """Simulator for gasoline products."""
    
    def __init__(self, grade: str = "Regular", initial_stock: float = 10000):
        """
        Initialize gasoline simulator.
        
        Args:
            grade: Fuel grade (Regular, Mid-Grade, Premium)
            initial_stock: Initial gallons in stock
        """
        product_name = f"{grade} Gasoline"
        # Typical gas station pumps 200-500 gallons per day per pump
        # Assume 8 pumps with varied usage
        daily_consumption = (1600, 4000)  # gallons per day
        
        super().__init__(
            product_name=product_name,
            category="fuel",
            unit="gallons",
            initial_stock=initial_stock,
            daily_consumption_range=daily_consumption
        )
        self.grade = grade


class DieselSimulator(ProductSimulator):
    """Simulator for diesel fuel."""
    
    def __init__(self, initial_stock: float = 8000):
        """Initialize diesel simulator."""
        daily_consumption = (800, 2000)  # gallons per day
        
        super().__init__(
            product_name="Diesel",
            category="fuel",
            unit="gallons",
            initial_stock=initial_stock,
            daily_consumption_range=daily_consumption
        )


class ConvenienceStoreItemSimulator(ProductSimulator):
    """Simulator for convenience store items (snacks, drinks, etc)."""
    
    def __init__(self, product_name: str = "Bottled Water",
                 initial_stock: float = 200):
        """Initialize c-store item simulator."""
        # Typical c-store items sell 50-150 units per day
        daily_consumption = (50, 150)
        
        super().__init__(
            product_name=product_name,
            category="c-store",
            unit="units",
            initial_stock=initial_stock,
            daily_consumption_range=daily_consumption
        )


class TobaccoSimulator(ProductSimulator):
    """Simulator for tobacco products."""
    
    def __init__(self, product_name: str = "Marlboro", initial_stock: float = 150):
        """
        Initialize tobacco simulator.
        
        Args:
            product_name: Brand/type of tobacco
            initial_stock: Number of packs/units
        """
        # Tobacco moves steadily but regulated
        daily_consumption = (10, 30)  # packs per day
        
        super().__init__(
            product_name=product_name,
            category="tobacco",
            unit="packs",
            initial_stock=initial_stock,
            daily_consumption_range=daily_consumption
        )


class VapeSimulator(ProductSimulator):
    """Simulator for vape and e-cigarette products."""
    
    def __init__(self, product_name: str = "Vape Juice 60ml",
                 initial_stock: float = 100):
        """Initialize vape product simulator."""
        # Vape products have moderate, steady demand
        daily_consumption = (5, 20)  # bottles per day
        
        super().__init__(
            product_name=product_name,
            category="vape",
            unit="bottles",
            initial_stock=initial_stock,
            daily_consumption_range=daily_consumption
        )


class CoffeeSimulator(ProductSimulator):
    """Simulator for coffee products and supplies."""
    
    def __init__(self, product_name: str = "Coffee Beans Premium",
                 initial_stock: float = 80):
        """Initialize coffee simulator."""
        # Coffee has high morning/afternoon peaks
        daily_consumption = (15, 40)  # cups/servings per day
        
        super().__init__(
            product_name=product_name,
            category="coffee",
            unit="pounds",
            initial_stock=initial_stock,
            daily_consumption_range=daily_consumption
        )


class GasStationInventorySimulator:
    """
    Complete gas station inventory simulator.
    Manages multiple product simulators and provides coordinated simulation.
    """
    
    def __init__(self):
        """Initialize all product simulators."""
        self.simulators: Dict[str, ProductSimulator] = {}
        self._initialize_products()
    
    def _initialize_products(self):
        """Initialize all product simulators with realistic data."""
        # Fuel products
        self.simulators["regular_gas"] = GasolineSimulator("Regular", 12000)
        self.simulators["midgrade_gas"] = GasolineSimulator("Mid-Grade", 8000)
        self.simulators["premium_gas"] = GasolineSimulator("Premium", 6000)
        self.simulators["diesel"] = DieselSimulator(8000)
        
        # Convenience store items
        self.simulators["bottled_water"] = ConvenienceStoreItemSimulator("Bottled Water", 300)
        self.simulators["soda"] = ConvenienceStoreItemSimulator("Soda Mix", 250)
        self.simulators["snacks"] = ConvenienceStoreItemSimulator("Snack Assortment", 400)
        self.simulators["energy_drinks"] = ConvenienceStoreItemSimulator("Energy Drinks", 150)
        
        # Tobacco products
        self.simulators["marlboro"] = TobaccoSimulator("Marlboro", 200)
        self.simulators["camel"] = TobaccoSimulator("Camel", 150)
        self.simulators["newport"] = TobaccoSimulator("Newport", 180)
        
        # Vape products
        self.simulators["vape_juice_regular"] = VapeSimulator("Vape Juice 60ml Standard", 120)
        self.simulators["vape_juice_premium"] = VapeSimulator("Vape Juice 60ml Premium", 80)
        self.simulators["vape_coils"] = VapeSimulator("Replacement Coils Pack", 100)
        
        # Coffee products
        self.simulators["coffee_premium"] = CoffeeSimulator("Premium Coffee Beans", 100)
        self.simulators["coffee_standard"] = CoffeeSimulator("Standard Coffee Beans", 120)
        self.simulators["coffee_supplies"] = CoffeeSimulator("Coffee Filters & Supplies", 150)
    
    def get_product(self, product_id: str) -> ProductSimulator:
        """Get a specific product simulator."""
        if product_id not in self.simulators:
            raise KeyError(f"Product {product_id} not found")
        return self.simulators[product_id]
    
    def get_all_products(self) -> Dict[str, ProductSnapshot]:
        """Get snapshots of all products."""
        return {
            product_id: simulator.get_snapshot()
            for product_id, simulator in self.simulators.items()
        }
    
    def get_all_products_json(self) -> str:
        """Get all products as JSON string."""
        products = self.get_all_products()
        return json.dumps({
            k: v.to_json() for k, v in products.items()
        }, indent=2)
    
    def simulate_day(self) -> Dict[str, ProductSnapshot]:
        """Simulate one day of consumption across all products."""
        results = {}
        for product_id, simulator in self.simulators.items():
            snapshots = simulator.simulate_consumption(days=1)
            results[product_id] = snapshots[0]
        return results
    
    def simulate_days(self, days: int) -> Dict[str, List[ProductSnapshot]]:
        """
        Simulate multiple days of consumption.
        
        Args:
            days: Number of days to simulate
            
        Returns:
            Dictionary with product IDs mapping to lists of snapshots
        """
        results = {}
        for product_id, simulator in self.simulators.items():
            results[product_id] = simulator.simulate_consumption(days=days)
        return results
    
    def restock_product(self, product_id: str, quantity: float):
        """Restock a specific product."""
        simulator = self.get_product(product_id)
        simulator.restock(quantity)
    
    def get_inventory_report(self) -> Dict[str, Any]:
        """Get comprehensive inventory report."""
        products = self.get_all_products()
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "total_products": len(self.simulators),
            "categories": {},
            "products": {}
        }
        
        for product_id, simulator in self.simulators.items():
            snapshot = products[product_id]
            
            # Category statistics
            category = snapshot.category
            if category not in report["categories"]:
                report["categories"][category] = {
                    "count": 0,
                    "total_stock": 0,
                    "products": []
                }
            
            report["categories"][category]["count"] += 1
            report["categories"][category]["total_stock"] += snapshot.current_stock
            report["categories"][category]["products"].append(product_id)
            
            # Product details
            report["products"][product_id] = {
                **snapshot.to_json(),
                "days_until_empty": simulator.get_days_until_empty(),
                "avg_daily_consumption": round(simulator.get_consumption_average(), 2),
                "consumption_history_days": len(simulator.consumption_history)
            }
        
        return report
    
    def get_category_report(self, category: str) -> Dict[str, Any]:
        """Get report for specific category."""
        products = self.get_all_products()
        
        category_products = {
            product_id: simulator
            for product_id, simulator in self.simulators.items()
            if simulator.category == category
        }
        
        if not category_products:
            raise ValueError(f"Category {category} not found")
        
        report = {
            "category": category,
            "timestamp": datetime.now().isoformat(),
            "product_count": len(category_products),
            "products": {}
        }
        
        for product_id, simulator in category_products.items():
            snapshot = products[product_id]
            report["products"][product_id] = {
                **snapshot.to_json(),
                "days_until_empty": simulator.get_days_until_empty(),
                "avg_daily_consumption": round(simulator.get_consumption_average(), 2)
            }
        
        return report
    
    def reset_all(self):
        """Reset all simulators to initial state."""
        for simulator in self.simulators.values():
            simulator.reset()
    
    def get_low_stock_alerts(self, threshold_percent: float = 25) -> Dict[str, List[str]]:
        """
        Get products below stock threshold.
        
        Args:
            threshold_percent: Percentage threshold (0-100)
            
        Returns:
            Dictionary with low stock alerts by category
        """
        alerts = {}
        
        for product_id, simulator in self.simulators.items():
            threshold = simulator.initial_stock * (threshold_percent / 100)
            
            if simulator.current_stock <= threshold:
                category = simulator.category
                if category not in alerts:
                    alerts[category] = []
                
                alerts[category].append({
                    "product_id": product_id,
                    "product_name": simulator.product_name,
                    "current_stock": simulator.current_stock,
                    "threshold": threshold,
                    "percent_remaining": (simulator.current_stock / simulator.initial_stock) * 100
                })
        
        return alerts


# Standalone convenience functions for quick testing
def get_gas_simulator() -> GasolineSimulator:
    """Get a quick gasoline simulator."""
    return GasolineSimulator("Regular", 10000)


def get_coffee_simulator() -> CoffeeSimulator:
    """Get a quick coffee simulator."""
    return CoffeeSimulator("Premium Coffee", 80)


def get_vape_simulator() -> VapeSimulator:
    """Get a quick vape simulator."""
    return VapeSimulator("Vape Juice 60ml", 100)


def get_tobacco_simulator() -> TobaccoSimulator:
    """Get a quick tobacco simulator."""
    return TobaccoSimulator("Marlboro", 200)


def get_cstore_simulator() -> ConvenienceStoreItemSimulator:
    """Get a quick c-store item simulator."""
    return ConvenienceStoreItemSimulator("Bottled Water", 300)


if __name__ == "__main__":
    import sys
    
    print("=" * 70)
    print("DashGas Simulators - Comprehensive Test Suite")
    print("=" * 70)
    
    # Test 1: Individual simulators
    print("\n[TEST 1] Individual Product Simulators")
    print("-" * 70)
    
    gas_sim = get_gas_simulator()
    print(f"\n1. Gasoline Simulator Initial State:")
    print(f"   {gas_sim.get_snapshot().to_json_string()}")
    
    gas_snapshots = gas_sim.simulate_consumption(days=5)
    print(f"\n   After 5 days of consumption:")
    print(f"   {gas_snapshots[-1].to_json_string()}")
    print(f"   Average daily consumption: {gas_sim.get_consumption_average():.2f} gallons")
    print(f"   Days until empty: {gas_sim.get_days_until_empty():.2f}")
    
    gas_sim.restock(5000)
    print(f"\n   After restocking 5000 gallons:")
    print(f"   Current stock: {gas_sim.current_stock} gallons")
    
    # Test 2: Coffee simulator
    print(f"\n2. Coffee Simulator:")
    coffee_sim = get_coffee_simulator()
    coffee_snapshots = coffee_sim.simulate_consumption(days=3)
    print(f"   Initial: {coffee_snapshots[0].current_stock:.1f} {coffee_snapshots[0].unit}")
    print(f"   After 3 days: {coffee_snapshots[-1].current_stock:.1f} {coffee_snapshots[-1].unit}")
    
    # Test 3: Full station simulator
    print(f"\n[TEST 2] Full Gas Station Simulator")
    print("-" * 70)
    
    station = GasStationInventorySimulator()
    print(f"\nInitialized with {len(station.simulators)} products")
    
    # Get category breakdown
    categories = {}
    for sim_id, sim in station.simulators.items():
        if sim.category not in categories:
            categories[sim.category] = 0
        categories[sim.category] += 1
    
    print(f"\nProducts by category:")
    for category, count in sorted(categories.items()):
        print(f"  - {category}: {count} products")
    
    # Test 4: Daily simulation
    print(f"\n[TEST 3] Day-by-Day Simulation")
    print("-" * 70)
    
    station.reset_all()
    print("\nSimulating 7 days of operations...")
    
    daily_results = station.simulate_days(days=7)
    
    # Show fuel products progression
    print(f"\nFuel Products - Stock Progression:")
    for product_id in ["regular_gas", "diesel"]:
        snapshots = daily_results[product_id]
        initial = snapshots[0].current_stock
        final = snapshots[-1].current_stock
        consumed = initial - final
        print(f"  {product_id}:")
        print(f"    Day 1: {initial:.0f} gallons")
        print(f"    Day 7: {final:.0f} gallons")
        print(f"    Total consumed: {consumed:.0f} gallons")
    
    # Test 5: Inventory report
    print(f"\n[TEST 4] Comprehensive Inventory Report")
    print("-" * 70)
    
    station.reset_all()
    station.simulate_days(days=10)
    report = station.get_inventory_report()
    
    print(f"\nTotal products: {report['total_products']}")
    print(f"\nStock by category:")
    for category, data in sorted(report['categories'].items()):
        print(f"  {category}: {data['count']} products, {data['total_stock']:.0f} units total")
    
    # Test 6: Low stock alerts
    print(f"\n[TEST 5] Low Stock Alerts")
    print("-" * 70)
    
    station.reset_all()
    station.simulate_days(days=20)  # Simulate longer to trigger some low stock
    
    alerts = station.get_low_stock_alerts(threshold_percent=25)
    
    if alerts:
        print(f"\nProducts below 25% stock:")
        for category, products in sorted(alerts.items()):
            print(f"\n  {category}:")
            for product in products:
                pct = product["percent_remaining"]
                print(f"    - {product['product_name']}: {product['current_stock']:.0f} " +
                      f"({pct:.1f}% of initial)")
    else:
        print("\nNo products below threshold")
    
    # Test 7: JSON output
    print(f"\n[TEST 6] JSON Output Examples")
    print("-" * 70)
    
    station.reset_all()
    station.simulate_day()
    
    print(f"\nAll products JSON (first 500 chars):")
    json_output = station.get_all_products_json()
    print(json_output[:500] + "...")
    
    # Test 8: Category report
    print(f"\n[TEST 7] Category Report")
    print("-" * 70)
    
    category_report = station.get_category_report("tobacco")
    print(f"\nTobacco Category Report:")
    print(f"  Products: {category_report['product_count']}")
    for product_id, details in category_report['products'].items():
        print(f"    - {details['product']}: {details['current_stock']:.0f} {details['unit']}")
    
    print(f"\n{'=' * 70}")
    print("✓ All tests passed successfully!")
    print("=" * 70)
