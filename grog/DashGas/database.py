"""
DashGas Database Module
Manages SQLite database for gas station inventory management system.
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Any


class DashGasDatabase:
    """Production-ready SQLite database for DashGas inventory system."""
    
    def __init__(self, db_path: str = "dashgas.db"):
        """Initialize database connection and create schema if needed."""
        self.db_path = Path(db_path)
        self.connection = None
        self.initialize_database()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self.connection is None:
            self.connection = sqlite3.connect(str(self.db_path))
            self.connection.row_factory = sqlite3.Row
            # Enable foreign keys
            self.connection.execute("PRAGMA foreign_keys = ON")
        return self.connection
    
    def initialize_database(self):
        """Create all tables with proper schema."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Drop existing tables for clean initialization (dev mode)
        # In production, use migrations instead
        tables = [
            "deliveries", "orders", "stock_logs", "anomalies",
            "supplier_performance", "products", "suppliers"
        ]
        for table in tables:
            cursor.execute(f"DROP TABLE IF EXISTS {table}")
        
        # Suppliers table
        cursor.execute("""
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
        """)
        
        # Products table
        cursor.execute("""
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
                FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id) ON DELETE RESTRICT
            )
        """)
        
        # Stock logs table
        cursor.execute("""
            CREATE TABLE stock_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                previous_stock REAL NOT NULL,
                current_stock REAL NOT NULL,
                change_amount REAL NOT NULL,
                reason TEXT,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE CASCADE
            )
        """)
        
        # Orders table
        cursor.execute("""
            CREATE TABLE orders (
                order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                supplier_id INTEGER NOT NULL,
                quantity REAL NOT NULL,
                order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expected_delivery_date TIMESTAMP NOT NULL,
                status TEXT DEFAULT 'pending',
                unit_cost REAL NOT NULL,
                total_cost REAL NOT NULL,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE CASCADE,
                FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id) ON DELETE RESTRICT
            )
        """)
        
        # Deliveries table
        cursor.execute("""
            CREATE TABLE deliveries (
                delivery_id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                received_quantity REAL NOT NULL,
                received_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                condition TEXT DEFAULT 'good',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE,
                FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE CASCADE
            )
        """)
        
        # Anomalies table
        cursor.execute("""
            CREATE TABLE anomalies (
                anomaly_id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                anomaly_type TEXT NOT NULL,
                severity TEXT DEFAULT 'medium',
                description TEXT,
                detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP,
                status TEXT DEFAULT 'open',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE CASCADE
            )
        """)
        
        # Supplier performance table
        cursor.execute("""
            CREATE TABLE supplier_performance (
                performance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                supplier_id INTEGER NOT NULL,
                total_orders INTEGER DEFAULT 0,
                on_time_deliveries INTEGER DEFAULT 0,
                complete_deliveries INTEGER DEFAULT 0,
                average_delivery_days REAL DEFAULT 0,
                reliability_score REAL DEFAULT 1.0,
                quality_rating REAL DEFAULT 5.0,
                last_evaluated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id) ON DELETE CASCADE
            )
        """)
        
        # Create indexes for performance
        cursor.execute("CREATE INDEX idx_products_category ON products(category)")
        cursor.execute("CREATE INDEX idx_products_supplier ON products(supplier_id)")
        cursor.execute("CREATE INDEX idx_stock_logs_product ON stock_logs(product_id)")
        cursor.execute("CREATE INDEX idx_orders_status ON orders(status)")
        cursor.execute("CREATE INDEX idx_orders_product ON orders(product_id)")
        cursor.execute("CREATE INDEX idx_anomalies_status ON anomalies(status)")
        cursor.execute("CREATE INDEX idx_anomalies_product ON anomalies(product_id)")
        
        conn.commit()
    
    def add_supplier(self, name: str, contact_email: str, contact_phone: str,
                     lead_time_days: int = 3) -> int:
        """Add a new supplier."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO suppliers (name, contact_email, contact_phone, lead_time_days)
            VALUES (?, ?, ?, ?)
        """, (name, contact_email, contact_phone, lead_time_days))
        conn.commit()
        return cursor.lastrowid
    
    def add_product(self, name: str, category: str, current_stock: float,
                    unit: str, reorder_threshold: float, supplier_id: int,
                    lead_time_days: int, min_stock: float = 0,
                    max_stock: float = 10000, unit_cost: float = 0) -> int:
        """Add a new product."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO products 
            (name, category, current_stock, unit, reorder_threshold, supplier_id,
             lead_time_days, min_stock, max_stock, unit_cost)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, category, current_stock, unit, reorder_threshold, supplier_id,
              lead_time_days, min_stock, max_stock, unit_cost))
        conn.commit()
        return cursor.lastrowid
    
    def log_stock_change(self, product_id: int, current_stock: float,
                         change_amount: float, reason: str = "consumption") -> int:
        """Log a stock change."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Get previous stock
        cursor.execute("SELECT current_stock FROM products WHERE product_id = ?",
                      (product_id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Product {product_id} not found")
        
        previous_stock = row[0]
        
        # Insert log
        cursor.execute("""
            INSERT INTO stock_logs 
            (product_id, previous_stock, current_stock, change_amount, reason)
            VALUES (?, ?, ?, ?, ?)
        """, (product_id, previous_stock, current_stock, change_amount, reason))
        
        # Update product current_stock
        cursor.execute("""
            UPDATE products SET current_stock = ?, updated_at = CURRENT_TIMESTAMP
            WHERE product_id = ?
        """, (current_stock, product_id))
        
        conn.commit()
        return cursor.lastrowid
    
    def create_order(self, product_id: int, supplier_id: int, quantity: float,
                    expected_delivery_date: str, unit_cost: float) -> int:
        """Create a purchase order."""
        conn = self._get_connection()
        cursor = conn.cursor()
        total_cost = quantity * unit_cost
        
        cursor.execute("""
            INSERT INTO orders 
            (product_id, supplier_id, quantity, expected_delivery_date, unit_cost, total_cost, status)
            VALUES (?, ?, ?, ?, ?, ?, 'pending')
        """, (product_id, supplier_id, quantity, expected_delivery_date, unit_cost, total_cost))
        
        conn.commit()
        return cursor.lastrowid
    
    def record_delivery(self, order_id: int, received_quantity: float,
                       condition: str = "good", notes: str = "") -> int:
        """Record a delivery."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Get order info
        cursor.execute("""
            SELECT product_id, supplier_id, quantity FROM orders WHERE order_id = ?
        """, (order_id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Order {order_id} not found")
        
        product_id, supplier_id, quantity = row
        
        # Insert delivery record
        cursor.execute("""
            INSERT INTO deliveries (order_id, product_id, received_quantity, condition, notes)
            VALUES (?, ?, ?, ?, ?)
        """, (order_id, product_id, received_quantity, condition, notes))
        
        # Update order status
        status = "complete" if received_quantity >= quantity else "partial"
        cursor.execute("""
            UPDATE orders SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE order_id = ?
        """, (status, order_id))
        
        conn.commit()
        return cursor.lastrowid
    
    def log_anomaly(self, product_id: int, anomaly_type: str, severity: str,
                   description: str) -> int:
        """Log an inventory anomaly."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO anomalies 
            (product_id, anomaly_type, severity, description, status)
            VALUES (?, ?, ?, ?, 'open')
        """, (product_id, anomaly_type, severity, description))
        
        conn.commit()
        return cursor.lastrowid
    
    def resolve_anomaly(self, anomaly_id: int):
        """Mark an anomaly as resolved."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE anomalies 
            SET status = 'resolved', resolved_at = CURRENT_TIMESTAMP
            WHERE anomaly_id = ?
        """, (anomaly_id,))
        conn.commit()
    
    def get_product_by_id(self, product_id: int) -> Optional[Dict]:
        """Get product details."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM products WHERE product_id = ?", (product_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_product_by_name(self, name: str) -> Optional[Dict]:
        """Get product by name."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM products WHERE name = ?", (name,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_products_by_category(self, category: str) -> List[Dict]:
        """Get all products in a category."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM products WHERE category = ?", (category,))
        return [dict(row) for row in cursor.fetchall()]
    
    def get_low_stock_products(self) -> List[Dict]:
        """Get products below reorder threshold."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM products WHERE current_stock <= reorder_threshold
            ORDER BY current_stock ASC
        """)
        return [dict(row) for row in cursor.fetchall()]
    
    def get_stock_logs(self, product_id: int, limit: int = 100) -> List[Dict]:
        """Get recent stock logs for a product."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM stock_logs 
            WHERE product_id = ?
            ORDER BY recorded_at DESC, log_id DESC
            LIMIT ?
        """, (product_id, limit))
        return [dict(row) for row in cursor.fetchall()]
    
    def get_open_anomalies(self) -> List[Dict]:
        """Get all open anomalies."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM anomalies 
            WHERE status = 'open'
            ORDER BY detected_at DESC
        """)
        return [dict(row) for row in cursor.fetchall()]
    
    def get_pending_orders(self) -> List[Dict]:
        """Get all pending orders."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM orders 
            WHERE status = 'pending'
            ORDER BY order_date DESC
        """)
        return [dict(row) for row in cursor.fetchall()]
    
    def get_inventory_summary(self) -> Dict[str, Any]:
        """Get inventory summary statistics."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM products")
        total_products = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM products WHERE current_stock <= reorder_threshold")
        low_stock = cursor.fetchone()[0]
        
        cursor.execute("SELECT SUM(current_stock) FROM products")
        total_stock = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT COUNT(*) FROM anomalies WHERE status = 'open'")
        open_anomalies = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM orders WHERE status = 'pending'")
        pending_orders = cursor.fetchone()[0]
        
        return {
            "total_products": total_products,
            "low_stock_count": low_stock,
            "total_stock_value": total_stock,
            "open_anomalies": open_anomalies,
            "pending_orders": pending_orders,
            "timestamp": datetime.now().isoformat()
        }
    
    def close(self):
        """Close database connection."""
        if self.connection:
            self.connection.close()
            self.connection = None
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


if __name__ == "__main__":
    # Test database initialization
    db = DashGasDatabase(":memory:")
    print("✓ Database initialized successfully")
    
    # Add test supplier
    supplier_id = db.add_supplier("Shell Wholesale", "shell@example.com", "555-0100", 2)
    print(f"✓ Supplier added: {supplier_id}")
    
    # Add test product
    product_id = db.add_product(
        name="Premium Gasoline",
        category="fuel",
        current_stock=5000,
        unit="gallons",
        reorder_threshold=1000,
        supplier_id=supplier_id,
        lead_time_days=2,
        unit_cost=2.50
    )
    print(f"✓ Product added: {product_id}")
    
    # Test stock log
    log_id = db.log_stock_change(product_id, 4950, -50, "consumption")
    print(f"✓ Stock log recorded: {log_id}")
    
    # Test order creation
    order_id = db.create_order(product_id, supplier_id, 1000, "2026-02-19", 2.50)
    print(f"✓ Order created: {order_id}")
    
    # Test delivery
    delivery_id = db.record_delivery(order_id, 1000, "good", "Delivered on time")
    print(f"✓ Delivery recorded: {delivery_id}")
    
    # Test anomaly
    anomaly_id = db.log_anomaly(product_id, "unusually_high_consumption", "medium",
                                "Consumption 50% above normal")
    print(f"✓ Anomaly logged: {anomaly_id}")
    
    # Test queries
    summary = db.get_inventory_summary()
    print(f"✓ Inventory summary: {json.dumps(summary, indent=2)}")
    
    db.close()
    print("\n✓ All database tests passed!")
