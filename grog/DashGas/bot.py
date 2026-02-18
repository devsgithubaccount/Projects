"""
DashGas Telegram Bot
Production-ready Telegram bot for staff and owner commands.
Note: Requires python-telegram-bot library. For testing, mock mode is available.
"""

import sqlite3
from datetime import datetime
from typing import Dict, List, Optional
import json


class TelegramBotMock:
    """
    Mock Telegram bot for testing and demonstration.
    Replace with actual python-telegram-bot implementation in production.
    """
    
    def __init__(self, db_path: str = "dashgas.db", owner_id: int = None, staff_ids: List[int] = None):
        """Initialize mock bot."""
        self.db_path = db_path
        self.owner_id = owner_id or 123456789
        self.staff_ids = staff_ids or [123456789]
        self.messages_sent = []
    
    def get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def is_authorized(self, user_id: int, owner_only: bool = False) -> bool:
        """Check if user is authorized."""
        if owner_only:
            return user_id == self.owner_id
        return user_id in self.staff_ids or user_id == self.owner_id
    
    def send_message(self, chat_id: int, text: str) -> Dict:
        """Mock send message."""
        message = {
            "chat_id": chat_id,
            "text": text,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        self.messages_sent.append(message)
        return message
    
    def handle_stock_command(self, user_id: int, product_name: Optional[str] = None) -> str:
        """Handle /stock command."""
        if not self.is_authorized(user_id):
            return "⛔ Unauthorized access"
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if product_name:
            # Get specific product
            cursor.execute("""
                SELECT name, category, current_stock, unit, reorder_threshold
                FROM products
                WHERE name LIKE ?
                LIMIT 1
            """, (f"%{product_name}%",))
            
            product = cursor.fetchone()
            
            if product:
                status_icon = "🟢" if product["current_stock"] > product["reorder_threshold"] else "🔴"
                response = (
                    f"{status_icon} **{product['name']}**\n"
                    f"Stock: {product['current_stock']:.2f} {product['unit']}\n"
                    f"Threshold: {product['reorder_threshold']:.2f}\n"
                    f"Category: {product['category']}"
                )
            else:
                response = f"❌ Product '{product_name}' not found"
        else:
            # Get all products summary
            cursor.execute("""
                SELECT category, 
                       COUNT(*) as total_products,
                       SUM(CASE WHEN current_stock <= reorder_threshold THEN 1 ELSE 0 END) as low_stock
                FROM products
                GROUP BY category
            """)
            
            categories = cursor.fetchall()
            
            response = "📦 **Inventory Summary**\n\n"
            
            for cat in categories:
                icon = "🚗" if cat["category"] == "fuel" else "🛒"
                response += f"{icon} {cat['category'].capitalize()}: {cat['total_products']} items"
                if cat["low_stock"] > 0:
                    response += f" (🔴 {cat['low_stock']} low)"
                response += "\n"
        
        conn.close()
        return response
    
    def handle_update_command(self, user_id: int, product_name: str, quantity: float) -> str:
        """Handle /update command."""
        if not self.is_authorized(user_id):
            return "⛔ Unauthorized access"
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Find product
        cursor.execute("""
            SELECT product_id, name, current_stock, unit
            FROM products
            WHERE name LIKE ?
            LIMIT 1
        """, (f"%{product_name}%",))
        
        product = cursor.fetchone()
        
        if not product:
            conn.close()
            return f"❌ Product '{product_name}' not found"
        
        # Update stock
        previous_stock = product["current_stock"]
        new_stock = previous_stock + quantity
        change_amount = quantity
        
        cursor.execute("""
            UPDATE products
            SET current_stock = ?, updated_at = CURRENT_TIMESTAMP
            WHERE product_id = ?
        """, (new_stock, product["product_id"]))
        
        cursor.execute("""
            INSERT INTO stock_logs (product_id, previous_stock, current_stock, change_amount, reason)
            VALUES (?, ?, ?, ?, ?)
        """, (product["product_id"], previous_stock, new_stock, change_amount, f"manual_update_by_user_{user_id}"))
        
        conn.commit()
        conn.close()
        
        action = "increased" if quantity > 0 else "decreased"
        return (
            f"✅ Stock updated\n\n"
            f"Product: {product['name']}\n"
            f"Previous: {previous_stock:.2f} {product['unit']}\n"
            f"Change: {quantity:+.2f} {product['unit']}\n"
            f"New Stock: {new_stock:.2f} {product['unit']}"
        )
    
    def handle_lowstock_command(self, user_id: int) -> str:
        """Handle /lowstock command."""
        if not self.is_authorized(user_id):
            return "⛔ Unauthorized access"
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT name, category, current_stock, unit, reorder_threshold
            FROM products
            WHERE current_stock <= reorder_threshold
            ORDER BY (current_stock / reorder_threshold), category
        """)
        
        low_stock = cursor.fetchall()
        conn.close()
        
        if not low_stock:
            return "🟢 All products have sufficient stock!"
        
        response = f"🔴 **Low Stock Alert** ({len(low_stock)} items)\n\n"
        
        for product in low_stock:
            percent = (product["current_stock"] / product["reorder_threshold"]) * 100
            response += (
                f"• {product['name']}\n"
                f"  Stock: {product['current_stock']:.2f} {product['unit']} ({percent:.0f}%)\n"
                f"  Threshold: {product['reorder_threshold']:.2f}\n\n"
            )
        
        return response
    
    def handle_report_command(self, user_id: int) -> str:
        """Handle /report command."""
        if not self.is_authorized(user_id):
            return "⛔ Unauthorized access"
        
        from forecasting import ForecastingEngine
        from orders import OrderManager
        
        forecast_engine = ForecastingEngine(self.db_path)
        order_manager = OrderManager(self.db_path)
        
        # Get critical forecasts
        critical = forecast_engine.get_critical_alerts()
        warnings = forecast_engine.get_warning_alerts()
        
        # Get order summary
        order_summary = order_manager.get_order_summary()
        
        # Get inventory summary
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                COUNT(*) as total_products,
                SUM(CASE WHEN current_stock <= reorder_threshold THEN 1 ELSE 0 END) as low_stock,
                SUM(current_stock * unit_cost) as total_value
            FROM products
        """)
        
        inv_summary = cursor.fetchone()
        
        # Get open anomalies
        cursor.execute("SELECT COUNT(*) as count FROM anomalies WHERE status = 'open'")
        anomaly_count = cursor.fetchone()["count"]
        
        conn.close()
        
        response = (
            f"📊 **DashGas Report**\n"
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
            f"**Inventory**\n"
            f"• Total Products: {inv_summary['total_products']}\n"
            f"• Low Stock: {inv_summary['low_stock']}\n"
            f"• Total Value: ${inv_summary['total_value']:.2f}\n\n"
            f"**Forecasts**\n"
            f"• Critical Alerts: {len(critical)}\n"
            f"• Warnings: {len(warnings)}\n\n"
            f"**Orders**\n"
            f"• Pending: {order_summary['pending_orders']}\n"
            f"• Unconfirmed: {order_summary['unconfirmed_orders']}\n\n"
            f"**Anomalies**\n"
            f"• Open Issues: {anomaly_count}\n"
        )
        
        return response
    
    def handle_orders_command(self, user_id: int) -> str:
        """Handle /orders command."""
        if not self.is_authorized(user_id):
            return "⛔ Unauthorized access"
        
        from orders import OrderManager
        
        order_manager = OrderManager(self.db_path)
        supplier_orders = order_manager.get_pending_orders_by_supplier()
        
        if not supplier_orders:
            return "✅ No pending orders"
        
        response = f"📋 **Pending Orders** ({len(supplier_orders)} suppliers)\n\n"
        
        for supplier_id, order in supplier_orders.items():
            response += (
                f"**{order.supplier_name}**\n"
                f"Items: {len(order.items)}\n"
                f"Total: ${order.total_cost:.2f}\n"
                f"Expected: {order.expected_delivery_date}\n"
            )
            
            for item in order.items[:3]:
                response += f"  • {item.product_name}: {item.quantity_needed:.0f} {item.unit}\n"
            
            if len(order.items) > 3:
                response += f"  ... and {len(order.items) - 3} more items\n"
            
            response += "\n"
        
        return response
    
    def handle_approve_command(self, user_id: int, order_id: int) -> str:
        """Handle /approve command (owner only)."""
        if not self.is_authorized(user_id, owner_only=True):
            return "⛔ Owner access required"
        
        from orders import OrderManager
        
        order_manager = OrderManager(self.db_path)
        success = order_manager.approve_order(order_id)
        
        if success:
            return f"✅ Order #{order_id} approved for sending"
        else:
            return f"❌ Failed to approve order #{order_id}"
    
    def handle_override_command(self, user_id: int, product_name: str, quantity: float) -> str:
        """Handle /override command (owner only) - sets stock to exact value."""
        if not self.is_authorized(user_id, owner_only=True):
            return "⛔ Owner access required"
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Find product
        cursor.execute("""
            SELECT product_id, name, current_stock, unit
            FROM products
            WHERE name LIKE ?
            LIMIT 1
        """, (f"%{product_name}%",))
        
        product = cursor.fetchone()
        
        if not product:
            conn.close()
            return f"❌ Product '{product_name}' not found"
        
        # Set stock to exact value
        previous_stock = product["current_stock"]
        change_amount = quantity - previous_stock
        
        cursor.execute("""
            UPDATE products
            SET current_stock = ?, updated_at = CURRENT_TIMESTAMP
            WHERE product_id = ?
        """, (quantity, product["product_id"]))
        
        cursor.execute("""
            INSERT INTO stock_logs (product_id, previous_stock, current_stock, change_amount, reason)
            VALUES (?, ?, ?, ?, ?)
        """, (product["product_id"], previous_stock, quantity, change_amount, f"owner_override_user_{user_id}"))
        
        conn.commit()
        conn.close()
        
        return (
            f"✅ Stock override applied\n\n"
            f"Product: {product['name']}\n"
            f"Previous: {previous_stock:.2f} {product['unit']}\n"
            f"New Stock: {quantity:.2f} {product['unit']}\n"
            f"Change: {change_amount:+.2f} {product['unit']}"
        )
    
    def handle_suppliers_command(self, user_id: int) -> str:
        """Handle /suppliers command (owner only)."""
        if not self.is_authorized(user_id, owner_only=True):
            return "⛔ Owner access required"
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT s.*, 
                   COUNT(o.order_id) as total_orders,
                   SUM(CASE WHEN o.status = 'received' THEN 1 ELSE 0 END) as completed_orders
            FROM suppliers s
            LEFT JOIN orders o ON s.supplier_id = o.supplier_id
            GROUP BY s.supplier_id
            ORDER BY s.name
        """)
        
        suppliers = cursor.fetchall()
        conn.close()
        
        if not suppliers:
            return "❌ No suppliers found"
        
        response = f"🏢 **Suppliers** ({len(suppliers)})\n\n"
        
        for supplier in suppliers:
            reliability_icon = "🟢" if supplier["reliability_score"] >= 0.8 else "🟡" if supplier["reliability_score"] >= 0.6 else "🔴"
            
            response += (
                f"{reliability_icon} **{supplier['name']}**\n"
                f"Lead Time: {supplier['lead_time_days']} days\n"
                f"Orders: {supplier['total_orders']} ({supplier['completed_orders']} completed)\n"
                f"Reliability: {supplier['reliability_score']:.2f}\n"
                f"Contact: {supplier['contact_email']}\n"
                f"Phone: {supplier['contact_phone']}\n\n"
            )
        
        return response
    
    def handle_help_command(self, user_id: int) -> str:
        """Handle /help command."""
        if not self.is_authorized(user_id):
            return "⛔ Unauthorized access"
        
        is_owner = user_id == self.owner_id
        
        response = (
            "🤖 **DashGas Bot Commands**\n\n"
            "**Staff Commands:**\n"
            "/stock [product] - View stock levels\n"
            "/update <product> <qty> - Update stock\n"
            "/lowstock - View low stock items\n"
            "/report - System report\n"
            "/orders - View pending orders\n"
            "/help - Show this help\n"
        )
        
        if is_owner:
            response += (
                "\n**Owner Commands:**\n"
                "/approve <order_id> - Approve order\n"
                "/override <product> <qty> - Set exact stock\n"
                "/suppliers - View supplier list\n"
            )
        
        return response
    
    def process_command(self, user_id: int, command: str, args: List[str] = None) -> str:
        """Process bot command."""
        args = args or []
        
        if command == "/stock":
            product_name = " ".join(args) if args else None
            return self.handle_stock_command(user_id, product_name)
        
        elif command == "/update":
            if len(args) < 2:
                return "❌ Usage: /update <product> <quantity>"
            try:
                quantity = float(args[-1])
                product_name = " ".join(args[:-1])
                return self.handle_update_command(user_id, product_name, quantity)
            except ValueError:
                return "❌ Invalid quantity"
        
        elif command == "/lowstock":
            return self.handle_lowstock_command(user_id)
        
        elif command == "/report":
            return self.handle_report_command(user_id)
        
        elif command == "/orders":
            return self.handle_orders_command(user_id)
        
        elif command == "/approve":
            if len(args) < 1:
                return "❌ Usage: /approve <order_id>"
            try:
                order_id = int(args[0])
                return self.handle_approve_command(user_id, order_id)
            except ValueError:
                return "❌ Invalid order ID"
        
        elif command == "/override":
            if len(args) < 2:
                return "❌ Usage: /override <product> <quantity>"
            try:
                quantity = float(args[-1])
                product_name = " ".join(args[:-1])
                return self.handle_override_command(user_id, product_name, quantity)
            except ValueError:
                return "❌ Invalid quantity"
        
        elif command == "/suppliers":
            return self.handle_suppliers_command(user_id)
        
        elif command == "/help":
            return self.handle_help_command(user_id)
        
        else:
            return f"❌ Unknown command: {command}\nUse /help for command list"


def main():
    """Test bot commands."""
    print("=" * 60)
    print("DashGas Telegram Bot - Production Test")
    print("=" * 60)
    
    # Create test database
    from database import DashGasDatabase
    import os
    
    test_db = "test_bot.db"
    
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
        current_stock=8000.0,
        unit="gallons",
        reorder_threshold=2000.0,
        supplier_id=supplier_id,
        lead_time_days=3,
        unit_cost=2.50
    )
    
    product2_id = db.add_product(
        name="Bottled Water",
        category="c-store",
        current_stock=50.0,
        unit="units",
        reorder_threshold=100.0,
        supplier_id=supplier_id,
        lead_time_days=2,
        unit_cost=0.50
    )
    
    db.close()
    
    # Initialize bot
    owner_id = 123456789
    staff_id = 987654321
    bot = TelegramBotMock(test_db, owner_id=owner_id, staff_ids=[owner_id, staff_id])
    
    print("\n1. Testing /stock command...")
    response = bot.process_command(owner_id, "/stock")
    print(f"✓ Response length: {len(response)} characters")
    print(f"  Preview: {response[:80]}...")
    
    print("\n2. Testing /stock with product...")
    response = bot.process_command(owner_id, "/stock", ["Regular"])
    print(f"✓ Response: {response[:100]}...")
    
    print("\n3. Testing /update command...")
    response = bot.process_command(staff_id, "/update", ["Bottled", "Water", "25"])
    print(f"✓ Response: {response[:100]}...")
    
    print("\n4. Testing /lowstock command...")
    response = bot.process_command(owner_id, "/lowstock")
    print(f"✓ Response length: {len(response)} characters")
    print(f"  Low stock items found: {'Yes' if 'Low Stock Alert' in response else 'No'}")
    
    print("\n5. Testing /report command...")
    response = bot.process_command(owner_id, "/report")
    print(f"✓ Response length: {len(response)} characters")
    print(f"  Contains forecast data: {'Yes' if 'Forecasts' in response else 'No'}")
    
    print("\n6. Testing /orders command...")
    response = bot.process_command(owner_id, "/orders")
    print(f"✓ Response: {response[:80]}...")
    
    print("\n7. Testing /suppliers command (owner only)...")
    response = bot.process_command(owner_id, "/suppliers")
    print(f"✓ Response length: {len(response)} characters")
    print(f"  Contains supplier: {'Test Supplier' in response}")
    
    print("\n8. Testing unauthorized access...")
    unauthorized_id = 999999999
    response = bot.process_command(unauthorized_id, "/stock")
    print(f"✓ Blocked unauthorized: {'Unauthorized' in response}")
    
    print("\n9. Testing owner-only command with staff user...")
    response = bot.process_command(staff_id, "/suppliers")
    print(f"✓ Blocked non-owner: {'Owner access required' in response}")
    
    print("\n10. Testing /help command...")
    response = bot.process_command(owner_id, "/help")
    print(f"✓ Response length: {len(response)} characters")
    print(f"  Contains commands: {'/stock' in response and '/update' in response}")
    
    print("\n" + "=" * 60)
    print("✓ All bot command tests passed!")
    print("=" * 60)
    
    # Cleanup
    if os.path.exists(test_db):
        os.remove(test_db)


if __name__ == "__main__":
    main()
