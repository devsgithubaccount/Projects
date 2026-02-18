"""
DashGas Invoicing Module
Handles invoice management, cost tracking, and financial reporting.
"""

from database import DashGasDatabase
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
import json


class InvoicingEngine:
    """Comprehensive invoicing and cost tracking system."""
    
    def __init__(self, db: DashGasDatabase):
        """Initialize invoicing engine with database connection."""
        self.db = db
    
    def create_invoice_from_order(self, order_id: int, invoice_number: str,
                                 invoice_date: str = None, due_date: str = None) -> int:
        """Create an invoice from a purchase order."""
        conn = self.db._get_connection()
        cursor = conn.cursor()
        
        # Get order details
        cursor.execute("""
            SELECT o.order_id, o.product_id, o.supplier_id, o.quantity, 
                   o.unit_cost, p.name, d.delivered_quantity
            FROM orders o
            JOIN products p ON o.product_id = p.product_id
            LEFT JOIN (
                SELECT order_id, SUM(received_quantity) as delivered_quantity
                FROM deliveries
                GROUP BY order_id
            ) d ON o.order_id = d.order_id
            WHERE o.order_id = ?
        """, (order_id,))
        
        order_row = cursor.fetchone()
        if not order_row:
            raise ValueError(f"Order {order_id} not found")
        
        order_id, product_id, supplier_id, quantity, unit_cost, product_name, delivered_qty = order_row
        delivered_qty = delivered_qty or 0
        
        # Create invoice
        invoice_date = invoice_date or datetime.now().isoformat()
        due_date = due_date or (datetime.fromisoformat(invoice_date) + timedelta(days=30)).isoformat()
        
        invoice_id = self.db.create_invoice(
            supplier_id, invoice_number, invoice_date, due_date,
            notes=f"Invoice for order {order_id}"
        )
        
        # Add invoice items for delivered quantities
        if delivered_qty > 0:
            self.db.add_invoice_item(
                invoice_id, product_id, product_name,
                delivered_qty, unit_cost, order_id
            )
        
        return invoice_id
    
    def batch_create_invoices(self, supplier_id: int, invoice_number_prefix: str = "INV") -> List[int]:
        """Create invoices for all pending orders from a supplier."""
        conn = self.db._get_connection()
        cursor = conn.cursor()
        
        # Get all complete orders without invoices
        cursor.execute("""
            SELECT DISTINCT o.order_id
            FROM orders o
            WHERE o.supplier_id = ? 
            AND o.status IN ('complete', 'partial')
            AND o.order_id NOT IN (
                SELECT DISTINCT order_id FROM invoice_items WHERE order_id IS NOT NULL
            )
        """, (supplier_id,))
        
        order_ids = [row[0] for row in cursor.fetchall()]
        invoice_ids = []
        
        for idx, order_id in enumerate(order_ids, 1):
            invoice_number = f"{invoice_number_prefix}-{supplier_id}-{datetime.now().strftime('%Y%m%d')}-{idx:03d}"
            try:
                invoice_id = self.create_invoice_from_order(order_id, invoice_number)
                invoice_ids.append(invoice_id)
            except Exception as e:
                print(f"Warning: Failed to create invoice for order {order_id}: {e}")
        
        return invoice_ids
    
    def get_financial_summary(self) -> Dict[str, Any]:
        """Get overall financial summary across all suppliers."""
        suppliers = self.db.get_all_suppliers_cost_summary()
        
        total_cost = sum(s.get('total_cost') or 0 for s in suppliers)
        total_paid = sum(s.get('total_paid') or 0 for s in suppliers)
        total_outstanding = sum(s.get('outstanding') or 0 for s in suppliers)
        total_pending = sum(s.get('pending_count') or 0 for s in suppliers)
        
        return {
            "total_suppliers": len(suppliers),
            "total_cost": total_cost,
            "total_paid": total_paid,
            "total_outstanding": total_outstanding,
            "pending_invoices": total_pending,
            "suppliers": suppliers
        }
    
    def get_supplier_metrics(self, supplier_id: int) -> Dict[str, Any]:
        """Get comprehensive financial metrics for a supplier."""
        try:
            breakdown = self.db.get_supplier_cost_breakdown(supplier_id)
        except ValueError:
            # Supplier has no invoices - return empty metrics
            conn = self.db._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM suppliers WHERE supplier_id = ?", (supplier_id,))
            row = cursor.fetchone()
            supplier_name = row[0] if row else "Unknown Supplier"
            
            return {
                "supplier": {
                    "supplier_id": supplier_id,
                    "supplier_name": supplier_name,
                    "summary": {
                        "total_invoices": 0,
                        "total_cost": 0,
                        "total_paid": 0,
                        "outstanding": 0
                    },
                    "products": [],
                    "status_breakdown": []
                },
                "metrics": {
                    "total_products": 0,
                    "avg_invoice_value": 0,
                    "payment_rate": 0,
                    "cheapest_product": None,
                    "most_expensive_product": None
                }
            }
        
        # Calculate additional metrics
        summary = breakdown['summary']
        total_products = len(breakdown['products'])
        
        avg_invoice_value = (summary['total_cost'] / summary['total_invoices'] 
                            if summary['total_invoices'] > 0 else 0)
        
        payment_rate = (summary['total_paid'] / summary['total_cost'] 
                       if summary['total_cost'] > 0 else 0)
        
        # Find cheapest and most expensive products
        products = breakdown['products']
        cheapest = min(products, key=lambda p: p['avg_unit_cost']) if products else None
        most_expensive = max(products, key=lambda p: p['avg_unit_cost']) if products else None
        
        return {
            "supplier": breakdown,
            "metrics": {
                "total_products": total_products,
                "avg_invoice_value": avg_invoice_value,
                "payment_rate": payment_rate,
                "cheapest_product": {
                    "name": cheapest['product_name'],
                    "unit_cost": cheapest['avg_unit_cost']
                } if cheapest else None,
                "most_expensive_product": {
                    "name": most_expensive['product_name'],
                    "unit_cost": most_expensive['avg_unit_cost']
                } if most_expensive else None
            }
        }
    
    def get_cost_trends(self, product_id: int, days: int = 90) -> Dict[str, Any]:
        """Get unit cost trends for a product over time."""
        conn = self.db._get_connection()
        cursor = conn.cursor()
        
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        # Get product name first
        cursor.execute("SELECT name FROM products WHERE product_id = ?", (product_id,))
        product_row = cursor.fetchone()
        product_name = product_row[0] if product_row else "Unknown Product"
        
        # Get cost trends
        cursor.execute("""
            SELECT 
                ii.unit_cost,
                DATE(ii.created_at) as cost_date,
                COUNT(*) as occurrences
            FROM invoice_items ii
            WHERE ii.product_id = ?
            AND ii.created_at > ?
            GROUP BY DATE(ii.created_at), ii.unit_cost
            ORDER BY ii.created_at ASC
        """, (product_id, cutoff_date))
        
        records = [dict(row) for row in cursor.fetchall()]
        
        # Calculate statistics
        if records:
            unit_costs = [r['unit_cost'] for r in records]
            min_cost = min(unit_costs)
            max_cost = max(unit_costs)
            avg_cost = sum(unit_costs) / len(unit_costs)
            cost_variance = max_cost - min_cost
        else:
            min_cost = max_cost = avg_cost = cost_variance = 0
        
        return {
            "product_id": product_id,
            "product_name": product_name,
            "period_days": days,
            "records": records,
            "statistics": {
                "min_cost": min_cost,
                "max_cost": max_cost,
                "avg_cost": avg_cost,
                "cost_variance": cost_variance,
                "total_records": len(records)
            }
        }
    
    def get_budget_analysis(self) -> Dict[str, Any]:
        """Analyze spending patterns and identify cost optimization opportunities."""
        suppliers = self.db.get_all_suppliers_cost_summary()
        
        # Sort by cost
        by_cost = sorted(suppliers, key=lambda x: x.get('total_cost') or 0, reverse=True)
        
        # Identify top spenders
        total_cost = sum(s.get('total_cost') or 0 for s in suppliers)
        top_spenders = []
        cumulative = 0
        
        for supplier in by_cost:
            cost = supplier.get('total_cost') or 0
            cumulative += cost
            percentage = (cost / total_cost * 100) if total_cost > 0 else 0
            
            top_spenders.append({
                "supplier_id": supplier['supplier_id'],
                "supplier_name": supplier['name'],
                "cost": cost,
                "percentage": percentage,
                "cumulative_percentage": cumulative / total_cost * 100 if total_cost > 0 else 0
            })
        
        # Identify opportunities (suppliers with pending invoices)
        pending_count = sum(s.get('pending_count') or 0 for s in suppliers)
        outstanding_value = sum(s.get('outstanding') or 0 for s in suppliers)
        
        return {
            "total_spending": total_cost,
            "pending_invoices": pending_count,
            "outstanding_value": outstanding_value,
            "top_spenders": top_spenders,
            "supplier_count": len(suppliers)
        }
    
    def export_financials(self, format: str = "json", start_date: str = None, 
                         end_date: str = None) -> str:
        """Export financial data in specified format."""
        suppliers = self.db.get_all_suppliers_cost_summary()
        
        data = {
            "export_date": datetime.now().isoformat(),
            "summary": {
                "total_suppliers": len(suppliers),
                "total_cost": sum(s.get('total_cost') or 0 for s in suppliers),
                "total_paid": sum(s.get('total_paid') or 0 for s in suppliers),
                "outstanding": sum(s.get('outstanding') or 0 for s in suppliers)
            },
            "suppliers": suppliers
        }
        
        if format == "json":
            return json.dumps(data, indent=2, default=str)
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def get_payment_schedule(self) -> List[Dict[str, Any]]:
        """Get upcoming invoice due dates sorted by date."""
        conn = self.db._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                i.invoice_id,
                i.invoice_number,
                s.name as supplier_name,
                i.total_amount,
                i.paid_amount,
                i.total_amount - i.paid_amount as outstanding,
                i.due_date,
                i.status
            FROM invoices i
            JOIN suppliers s ON i.supplier_id = s.supplier_id
            WHERE i.status IN ('pending', 'partial')
            AND i.due_date IS NOT NULL
            ORDER BY i.due_date ASC
        """)
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_monthly_financials(self, year: int = None, month: int = None) -> Dict[str, Any]:
        """Get automatic month-end financial summary (no work required from user)."""
        from datetime import datetime, date
        
        if year is None or month is None:
            now = datetime.now()
            year = now.year
            month = now.month
        
        conn = self.db._get_connection()
        cursor = conn.cursor()
        
        # Build date range for the month
        first_day = f"{year:04d}-{month:02d}-01"
        if month == 12:
            last_day = f"{year + 1:04d}-01-01"
        else:
            last_day = f"{year:04d}-{month + 1:02d}-01"
        
        month_name = datetime(year, month, 1).strftime("%B %Y")
        
        # Get summary for the month
        cursor.execute("""
            SELECT 
                COUNT(DISTINCT invoice_id) as total_invoices,
                SUM(total_amount) as total_cost,
                SUM(paid_amount) as total_paid,
                SUM(total_amount - paid_amount) as outstanding,
                COUNT(DISTINCT CASE WHEN status = 'pending' THEN invoice_id END) as pending_count,
                COUNT(DISTINCT CASE WHEN status = 'partial' THEN invoice_id END) as partial_count,
                COUNT(DISTINCT CASE WHEN status = 'paid' THEN invoice_id END) as paid_count,
                COUNT(DISTINCT supplier_id) as supplier_count
            FROM invoices
            WHERE invoice_date >= ? AND invoice_date < ?
        """, (first_day, last_day))
        
        summary = dict(cursor.fetchone())
        
        # Get supplier breakdown for the month
        cursor.execute("""
            SELECT 
                s.supplier_id,
                s.name,
                COUNT(i.invoice_id) as invoice_count,
                SUM(i.total_amount) as total_cost,
                SUM(i.paid_amount) as total_paid,
                SUM(i.total_amount - i.paid_amount) as outstanding
            FROM suppliers s
            LEFT JOIN invoices i ON s.supplier_id = i.supplier_id 
                AND i.invoice_date >= ? AND i.invoice_date < ?
            WHERE i.invoice_id IS NOT NULL
            GROUP BY s.supplier_id, s.name
            ORDER BY total_cost DESC
        """, (first_day, last_day))
        
        supplier_breakdown = [dict(row) for row in cursor.fetchall()]
        
        # Get product cost breakdown for the month
        cursor.execute("""
            SELECT 
                ii.product_name,
                SUM(ii.quantity) as total_quantity,
                AVG(ii.unit_cost) as avg_unit_cost,
                SUM(ii.total_cost) as total_cost
            FROM invoice_items ii
            JOIN invoices i ON ii.invoice_id = i.invoice_id
            WHERE i.invoice_date >= ? AND i.invoice_date < ?
            GROUP BY ii.product_name
            ORDER BY total_cost DESC
        """, (first_day, last_day))
        
        product_breakdown = [dict(row) for row in cursor.fetchall()]
        
        # Calculate metrics
        total_cost = summary.get('total_cost') or 0
        total_paid = summary.get('total_paid') or 0
        payment_rate = (total_paid / total_cost * 100) if total_cost > 0 else 0
        
        return {
            "month": month_name,
            "year": year,
            "period": f"{year:04d}-{month:02d}",
            "summary": {
                "total_invoices": summary.get('total_invoices') or 0,
                "total_cost": total_cost,
                "total_paid": total_paid,
                "outstanding": summary.get('outstanding') or 0,
                "supplier_count": summary.get('supplier_count') or 0,
                "payment_rate": payment_rate,
                "status_breakdown": {
                    "pending": summary.get('pending_count') or 0,
                    "partial": summary.get('partial_count') or 0,
                    "paid": summary.get('paid_count') or 0
                }
            },
            "suppliers": supplier_breakdown,
            "products": product_breakdown
        }
    
    def get_fiscal_year_summary(self, year: int = None) -> Dict[str, Any]:
        """Get annual financial summary with monthly breakdown."""
        from datetime import datetime
        
        if year is None:
            year = datetime.now().year
        
        conn = self.db._get_connection()
        cursor = conn.cursor()
        
        # Get monthly data for all 12 months
        monthly_data = []
        yearly_totals = {
            "total_invoices": 0,
            "total_cost": 0,
            "total_paid": 0,
            "total_outstanding": 0
        }
        
        for month in range(1, 13):
            monthly = self.get_monthly_financials(year, month)
            monthly_data.append(monthly)
            
            yearly_totals["total_invoices"] += monthly["summary"]["total_invoices"]
            yearly_totals["total_cost"] += monthly["summary"]["total_cost"]
            yearly_totals["total_paid"] += monthly["summary"]["total_paid"]
            yearly_totals["total_outstanding"] += monthly["summary"]["outstanding"]
        
        # Calculate annual payment rate
        annual_payment_rate = (yearly_totals["total_paid"] / yearly_totals["total_cost"] * 100 \
                              if yearly_totals["total_cost"] > 0 else 0)
        
        return {
            "year": year,
            "summary": {
                **yearly_totals,
                "payment_rate": annual_payment_rate,
                "avg_monthly_cost": yearly_totals["total_cost"] / 12 if yearly_totals["total_cost"] > 0 else 0,
                "months_with_invoices": sum(1 for m in monthly_data if m["summary"]["total_invoices"] > 0)
            },
            "monthly_breakdown": monthly_data
        }
    
    def export_month_end_report(self, year: int = None, month: int = None) -> str:
        """Export month-end financial report as JSON."""
        monthly = self.get_monthly_financials(year, month)
        return json.dumps(monthly, indent=2, default=str)
    
    def export_fiscal_report(self, year: int = None) -> str:
        """Export fiscal year report as JSON."""
        fiscal = self.get_fiscal_year_summary(year)
        return json.dumps(fiscal, indent=2, default=str)


if __name__ == "__main__":
    # Test invoicing engine
    db = DashGasDatabase(":memory:")
    engine = InvoicingEngine(db)
    
    # Create test data
    supplier_id = db.add_supplier("Fuel Co", "fuel@example.com", "555-1234")
    product_id = db.add_product("Regular Gas", "fuel", 10000, "gallons", 2000, supplier_id, 2, unit_cost=2.50)
    order_id = db.create_order(product_id, supplier_id, 1000, "2026-02-19", 2.50)
    db.record_delivery(order_id, 1000)
    
    # Test invoicing
    invoice_id = engine.create_invoice_from_order(order_id, "INV-001")
    print(f"✓ Invoice created from order: {invoice_id}")
    
    # Test financial summary
    summary = engine.get_financial_summary()
    print(f"✓ Financial summary: ${summary['total_cost']:.2f} total cost")
    
    # Test supplier metrics
    metrics = engine.get_supplier_metrics(supplier_id)
    print(f"✓ Supplier metrics retrieved")
    
    db.close()
    print("\n✓ All invoicing tests passed!")
