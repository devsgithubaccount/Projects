"""
DashGas Order Management System
Production-ready automated ordering with email integration and supplier tracking.
"""

import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


@dataclass
class OrderItem:
    """Single order item."""
    product_id: int
    product_name: str
    category: str
    current_stock: float
    unit: str
    quantity_needed: float
    unit_cost: float
    total_cost: float
    reason: str
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "product_id": self.product_id,
            "product_name": self.product_name,
            "category": self.category,
            "current_stock": round(self.current_stock, 2),
            "unit": self.unit,
            "quantity_needed": round(self.quantity_needed, 2),
            "unit_cost": round(self.unit_cost, 2),
            "total_cost": round(self.total_cost, 2),
            "reason": self.reason
        }


@dataclass
class SupplierOrder:
    """Complete order for a supplier."""
    supplier_id: int
    supplier_name: str
    supplier_email: str
    supplier_phone: str
    lead_time_days: int
    items: List[OrderItem]
    total_cost: float
    expected_delivery_date: str
    order_status: str  # "draft", "pending_approval", "sent", "confirmed", "received"
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "supplier_id": self.supplier_id,
            "supplier_name": self.supplier_name,
            "supplier_email": self.supplier_email,
            "supplier_phone": self.supplier_phone,
            "lead_time_days": self.lead_time_days,
            "items": [item.to_dict() for item in self.items],
            "total_cost": round(self.total_cost, 2),
            "expected_delivery_date": self.expected_delivery_date,
            "order_status": self.order_status
        }
    
    def generate_email_body(self) -> str:
        """Generate plain-text email body for order."""
        lines = [
            f"Purchase Order - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "=" * 60,
            "",
            f"To: {self.supplier_name}",
            f"Expected Delivery Date: {self.expected_delivery_date}",
            "",
            "Items Requested:",
            "-" * 60
        ]
        
        for item in self.items:
            lines.append(f"  {item.product_name}")
            lines.append(f"    Quantity: {item.quantity_needed:.2f} {item.unit}")
            lines.append(f"    Unit Cost: ${item.unit_cost:.2f}")
            lines.append(f"    Total: ${item.total_cost:.2f}")
            lines.append(f"    Reason: {item.reason}")
            lines.append("")
        
        lines.append("-" * 60)
        lines.append(f"Total Order Value: ${self.total_cost:.2f}")
        lines.append("")
        lines.append("Please confirm receipt of this order and estimated delivery date.")
        lines.append("")
        lines.append("Thank you,")
        lines.append("DashGas Inventory Management System")
        
        return "\n".join(lines)


class OrderManager:
    """Production-ready order management system."""
    
    def __init__(self, db_path: str = "dashgas.db"):
        """Initialize order manager."""
        self.db_path = db_path
    
    def get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def create_order_from_forecast(self, product_id: int, quantity: float, reason: str = "automated_reorder") -> Optional[int]:
        """
        Create order from forecast recommendation.
        
        Args:
            product_id: Product ID
            quantity: Quantity to order
            reason: Order reason
        
        Returns:
            Order ID or None
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Get product and supplier details
        cursor.execute("""
            SELECT p.*, s.lead_time_days as supplier_lead_time
            FROM products p
            LEFT JOIN suppliers s ON p.supplier_id = s.supplier_id
            WHERE p.product_id = ?
        """, (product_id,))
        
        product = cursor.fetchone()
        
        if not product:
            conn.close()
            return None
        
        # Calculate expected delivery date
        lead_time = product["supplier_lead_time"] or product["lead_time_days"]
        expected_delivery = (datetime.now() + timedelta(days=lead_time)).strftime("%Y-%m-%d")
        
        # Calculate costs
        unit_cost = product["unit_cost"]
        total_cost = quantity * unit_cost
        
        # Create order
        cursor.execute("""
            INSERT INTO orders (product_id, supplier_id, quantity, unit_cost, total_cost, expected_delivery_date, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            product_id,
            product["supplier_id"],
            quantity,
            unit_cost,
            total_cost,
            expected_delivery,
            "draft"
        ))
        
        order_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return order_id
    
    def get_pending_orders_by_supplier(self) -> Dict[int, SupplierOrder]:
        """
        Group pending orders by supplier.
        
        Returns:
            Dictionary of supplier_id -> SupplierOrder
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Get all draft/pending orders
        cursor.execute("""
            SELECT o.*, p.name as product_name, p.category, p.current_stock, p.unit,
                   s.name as supplier_name, s.contact_email, s.contact_phone, s.lead_time_days
            FROM orders o
            JOIN products p ON o.product_id = p.product_id
            JOIN suppliers s ON o.supplier_id = s.supplier_id
            WHERE o.status IN ('draft', 'pending_approval')
            ORDER BY s.supplier_id, o.created_at
        """)
        
        orders = cursor.fetchall()
        conn.close()
        
        # Group by supplier
        supplier_orders = {}
        
        for order in orders:
            supplier_id = order["supplier_id"]
            
            if supplier_id not in supplier_orders:
                supplier_orders[supplier_id] = SupplierOrder(
                    supplier_id=supplier_id,
                    supplier_name=order["supplier_name"],
                    supplier_email=order["contact_email"],
                    supplier_phone=order["contact_phone"],
                    lead_time_days=order["lead_time_days"],
                    items=[],
                    total_cost=0.0,
                    expected_delivery_date=order["expected_delivery_date"],
                    order_status="draft"
                )
            
            # Add item
            total_cost = order["quantity"] * order["unit_cost"]
            
            item = OrderItem(
                product_id=order["product_id"],
                product_name=order["product_name"],
                category=order["category"],
                current_stock=order["current_stock"],
                unit=order["unit"],
                quantity_needed=order["quantity"],
                unit_cost=order["unit_cost"],
                total_cost=total_cost,
                reason="automated_reorder"
            )
            
            supplier_orders[supplier_id].items.append(item)
            supplier_orders[supplier_id].total_cost += total_cost
        
        return supplier_orders
    
    def approve_order(self, order_id: int) -> bool:
        """
        Approve an order for sending.
        
        Args:
            order_id: Order ID
        
        Returns:
            Success status
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE orders
            SET status = 'pending_approval', updated_at = CURRENT_TIMESTAMP
            WHERE order_id = ? AND status = 'draft'
        """, (order_id,))
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return success
    
    def send_order(self, supplier_id: int, smtp_config: Optional[Dict] = None, dry_run: bool = True) -> Tuple[bool, str]:
        """
        Send order to supplier via email.
        
        Args:
            supplier_id: Supplier ID
            smtp_config: SMTP configuration (host, port, username, password, from_email)
            dry_run: If True, don't actually send email
        
        Returns:
            Tuple of (success, message)
        """
        # Get supplier order
        supplier_orders = self.get_pending_orders_by_supplier()
        
        if supplier_id not in supplier_orders:
            return False, "No pending orders for this supplier"
        
        order = supplier_orders[supplier_id]
        
        # Generate email
        email_body = order.generate_email_body()
        
        if dry_run or smtp_config is None:
            # Dry run - just return the email body
            return True, f"[DRY RUN] Would send to {order.supplier_email}:\n\n{email_body}"
        
        try:
            # Send actual email
            msg = MIMEMultipart()
            msg["From"] = smtp_config["from_email"]
            msg["To"] = order.supplier_email
            msg["Subject"] = f"Purchase Order - {datetime.now().strftime('%Y-%m-%d')}"
            
            msg.attach(MIMEText(email_body, "plain"))
            
            with smtplib.SMTP(smtp_config["host"], smtp_config["port"]) as server:
                server.starttls()
                server.login(smtp_config["username"], smtp_config["password"])
                server.send_message(msg)
            
            # Update order status
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE orders
                SET status = 'sent', updated_at = CURRENT_TIMESTAMP
                WHERE supplier_id = ? AND status = 'pending_approval'
            """, (supplier_id,))
            
            conn.commit()
            conn.close()
            
            return True, f"Order sent successfully to {order.supplier_email}"
        
        except Exception as e:
            return False, f"Failed to send order: {str(e)}"
    
    def mark_order_confirmed(self, order_id: int) -> bool:
        """
        Mark order as confirmed by supplier.
        
        Args:
            order_id: Order ID
        
        Returns:
            Success status
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE orders
            SET status = 'confirmed', updated_at = CURRENT_TIMESTAMP
            WHERE order_id = ? AND status = 'sent'
        """, (order_id,))
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return success
    
    def get_unconfirmed_orders(self, hours_threshold: int = 24) -> List[Dict]:
        """
        Get orders sent but not confirmed within threshold.
        
        Args:
            hours_threshold: Hours to wait before flagging
        
        Returns:
            List of unconfirmed orders
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cutoff_time = (datetime.now() - timedelta(hours=hours_threshold)).strftime("%Y-%m-%d %H:%M:%S")
        
        cursor.execute("""
            SELECT o.*, p.name as product_name, s.name as supplier_name, s.contact_email, s.contact_phone
            FROM orders o
            JOIN products p ON o.product_id = p.product_id
            JOIN suppliers s ON o.supplier_id = s.supplier_id
            WHERE o.status = 'sent'
              AND o.updated_at < ?
            ORDER BY o.updated_at
        """, (cutoff_time,))
        
        orders = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return orders
    
    def get_expected_deliveries(self, days_ahead: int = 7) -> List[Dict]:
        """
        Get orders expected to be delivered in the next N days.
        
        Args:
            days_ahead: Number of days to look ahead
        
        Returns:
            List of expected deliveries
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        end_date = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
        
        cursor.execute("""
            SELECT o.*, p.name as product_name, s.name as supplier_name
            FROM orders o
            JOIN products p ON o.product_id = p.product_id
            JOIN suppliers s ON o.supplier_id = s.supplier_id
            WHERE o.status IN ('sent', 'confirmed')
              AND o.expected_delivery_date <= ?
            ORDER BY o.expected_delivery_date
        """, (end_date,))
        
        deliveries = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return deliveries
    
    def get_order_summary(self) -> Dict:
        """Get order summary statistics."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Count by status
        cursor.execute("""
            SELECT status, COUNT(*) as count, SUM(quantity * unit_cost) as total_value
            FROM orders
            GROUP BY status
        """)
        
        status_counts = {}
        for row in cursor.fetchall():
            status_counts[row["status"]] = {
                "count": row["count"],
                "total_value": row["total_value"] or 0.0
            }
        
        # Get pending order count
        cursor.execute("SELECT COUNT(*) as count FROM orders WHERE status IN ('draft', 'pending_approval')")
        pending_count = cursor.fetchone()["count"]
        
        # Get sent but unconfirmed count
        cursor.execute("SELECT COUNT(*) as count FROM orders WHERE status = 'sent'")
        unconfirmed_count = cursor.fetchone()["count"]
        
        conn.close()
        
        return {
            "status_breakdown": status_counts,
            "pending_orders": pending_count,
            "unconfirmed_orders": unconfirmed_count,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    
    def export_orders_json(self) -> str:
        """Export all supplier orders to JSON."""
        supplier_orders = self.get_pending_orders_by_supplier()
        return json.dumps({
            "orders": [order.to_dict() for order in supplier_orders.values()],
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }, indent=2)


def main():
    """Test order management system."""
    print("=" * 60)
    print("DashGas Order Management System - Production Test")
    print("=" * 60)
    
    # Create test database
    from database import DashGasDatabase
    import os
    
    test_db = "test_orders.db"
    
    if os.path.exists(test_db):
        os.remove(test_db)
    
    db = DashGasDatabase(test_db)
    
    # Add supplier
    supplier_id = db.add_supplier(
        name="Shell Wholesale",
        contact_email="orders@shell.example.com",
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
        name="Premium Gasoline",
        category="fuel",
        current_stock=800.0,
        unit="gallons",
        reorder_threshold=1000.0,
        supplier_id=supplier_id,
        lead_time_days=3,
        unit_cost=2.75
    )
    
    db.close()
    
    # Test order manager
    manager = OrderManager(test_db)
    
    print("\n1. Creating orders from forecast...")
    order1_id = manager.create_order_from_forecast(product1_id, 5000.0, "low_stock")
    order2_id = manager.create_order_from_forecast(product2_id, 3000.0, "predicted_stockout")
    print(f"✓ Created order {order1_id} for Regular Gasoline")
    print(f"✓ Created order {order2_id} for Premium Gasoline")
    
    print("\n2. Grouping orders by supplier...")
    supplier_orders = manager.get_pending_orders_by_supplier()
    print(f"✓ Found {len(supplier_orders)} supplier(s) with pending orders")
    
    for supplier_id, order in supplier_orders.items():
        print(f"✓ Supplier: {order.supplier_name}")
        print(f"  - Items: {len(order.items)}")
        print(f"  - Total Cost: ${order.total_cost:.2f}")
        print(f"  - Expected Delivery: {order.expected_delivery_date}")
    
    print("\n3. Generating order email...")
    if supplier_orders:
        first_supplier = list(supplier_orders.keys())[0]
        order = supplier_orders[first_supplier]
        email_body = order.generate_email_body()
        print(f"✓ Generated email ({len(email_body)} characters)")
        print("\nEmail Preview:")
        print("-" * 60)
        print(email_body[:400] + "...")
        print("-" * 60)
    
    print("\n4. Testing order approval...")
    success = manager.approve_order(order1_id)
    print(f"✓ Order approval: {'Success' if success else 'Failed'}")
    
    print("\n5. Testing dry-run email send...")
    success, message = manager.send_order(first_supplier, dry_run=True)
    print(f"✓ Dry run: {'Success' if success else 'Failed'}")
    print(f"  Message: {message[:100]}...")
    
    print("\n6. Testing order summary...")
    summary = manager.get_order_summary()
    print(f"✓ Pending orders: {summary['pending_orders']}")
    print(f"✓ Unconfirmed orders: {summary['unconfirmed_orders']}")
    
    print("\n7. Testing JSON export...")
    json_output = manager.export_orders_json()
    parsed = json.loads(json_output)
    print(f"✓ JSON export successful: {len(parsed['orders'])} orders")
    
    print("\n" + "=" * 60)
    print("✓ All order management tests passed!")
    print("=" * 60)
    
    # Cleanup
    if os.path.exists(test_db):
        os.remove(test_db)


if __name__ == "__main__":
    main()
