"""
DashGas Web Dashboard
Production-ready Flask web dashboard with Chart.js visualizations.
"""

from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from functools import wraps
import sqlite3
from datetime import datetime, timedelta
import json
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from forecasting import ForecastingEngine
from orders import OrderManager
from automation import AutomationEngine
from database import DashGasDatabase
from invoicing import InvoicingEngine


app = Flask(__name__)
app.secret_key = "dashgas_secret_key_change_in_production"  # Change in production!

# Configuration
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dashgas.db")
USERNAME = "admin"  # Change in production
PASSWORD = "dashgas123"  # Change in production


def get_db_connection():
    """Get database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def login_required(f):
    """Decorator for protected routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page."""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == USERNAME and password == PASSWORD:
            session['logged_in'] = True
            session['username'] = username
            flash('Login successful!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid credentials', 'error')
    
    return render_template('login.html')


@app.route('/logout')
def logout():
    """Logout."""
    session.clear()
    flash('Logged out successfully', 'info')
    return redirect(url_for('login'))


@app.route('/')
@login_required
def index():
    """Dashboard overview page."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get inventory summary
    cursor.execute("""
        SELECT 
            COUNT(*) as total_products,
            SUM(CASE WHEN current_stock <= reorder_threshold THEN 1 ELSE 0 END) as low_stock_count,
            SUM(current_stock * unit_cost) as total_value
        FROM products
    """)
    inventory_summary = dict(cursor.fetchone())
    
    # Get category breakdown
    cursor.execute("""
        SELECT category, COUNT(*) as count,
               SUM(CASE WHEN current_stock <= reorder_threshold THEN 1 ELSE 0 END) as low_stock
        FROM products
        GROUP BY category
    """)
    categories = [dict(row) for row in cursor.fetchall()]
    
    # Get open anomalies
    cursor.execute("""
        SELECT COUNT(*) as count
        FROM anomalies
        WHERE status = 'open'
    """)
    open_anomalies = cursor.fetchone()['count']
    
    conn.close()
    
    # Get forecasts
    forecast_engine = ForecastingEngine(DB_PATH)
    critical_forecasts = forecast_engine.get_critical_alerts()
    warning_forecasts = forecast_engine.get_warning_alerts()
    
    # Get order summary
    order_manager = OrderManager(DB_PATH)
    order_summary = order_manager.get_order_summary()
    
    return render_template('index.html',
                         inventory_summary=inventory_summary,
                         categories=categories,
                         critical_forecasts=len(critical_forecasts),
                         warning_forecasts=len(warning_forecasts),
                         pending_orders=order_summary['pending_orders'],
                         open_anomalies=open_anomalies)


@app.route('/inventory')
@login_required
def inventory():
    """Inventory management page."""
    category_filter = request.args.get('category', '')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if category_filter:
        cursor.execute("""
            SELECT p.*, s.name as supplier_name
            FROM products p
            JOIN suppliers s ON p.supplier_id = s.supplier_id
            WHERE p.category = ?
            ORDER BY p.name
        """, (category_filter,))
    else:
        cursor.execute("""
            SELECT p.*, s.name as supplier_name
            FROM products p
            JOIN suppliers s ON p.supplier_id = s.supplier_id
            ORDER BY p.category, p.name
        """)
    
    products = [dict(row) for row in cursor.fetchall()]
    
    # Get categories for filter
    cursor.execute("SELECT DISTINCT category FROM products ORDER BY category")
    categories = [row['category'] for row in cursor.fetchall()]
    
    conn.close()
    
    return render_template('inventory.html',
                         products=products,
                         categories=categories,
                         selected_category=category_filter)


@app.route('/inventory/update/<int:product_id>', methods=['POST'])
@login_required
def update_inventory(product_id):
    """Update product inventory."""
    new_stock = float(request.form.get('stock', 0))
    reason = request.form.get('reason', 'manual_update')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get current stock
    cursor.execute("SELECT current_stock, name FROM products WHERE product_id = ?", (product_id,))
    product = cursor.fetchone()
    
    if product:
        previous_stock = product['current_stock']
        change_amount = new_stock - previous_stock
        
        # Update stock
        cursor.execute("""
            UPDATE products
            SET current_stock = ?, updated_at = CURRENT_TIMESTAMP
            WHERE product_id = ?
        """, (new_stock, product_id))
        
        # Log change
        cursor.execute("""
            INSERT INTO stock_logs (product_id, previous_stock, current_stock, change_amount, reason)
            VALUES (?, ?, ?, ?, ?)
        """, (product_id, previous_stock, new_stock, change_amount, reason))
        
        conn.commit()
        flash(f"Updated {product['name']}: {previous_stock:.2f} → {new_stock:.2f}", 'success')
    
    conn.close()
    
    return redirect(url_for('inventory'))


@app.route('/orders')
@login_required
def orders():
    """Orders management page."""
    order_manager = OrderManager(DB_PATH)
    
    # Get pending orders grouped by supplier
    supplier_orders = order_manager.get_pending_orders_by_supplier()
    
    # Get expected deliveries
    deliveries = order_manager.get_expected_deliveries(days_ahead=7)
    
    return render_template('orders.html',
                         supplier_orders=supplier_orders.values(),
                         deliveries=deliveries)


@app.route('/orders/create', methods=['POST'])
@login_required
def create_order():
    """Create manual order."""
    product_id = int(request.form.get('product_id'))
    quantity = float(request.form.get('quantity'))
    reason = request.form.get('reason', 'manual_order')
    
    order_manager = OrderManager(DB_PATH)
    order_id = order_manager.create_order_from_forecast(product_id, quantity, reason)
    
    if order_id:
        flash(f'Order #{order_id} created successfully', 'success')
    else:
        flash('Failed to create order', 'error')
    
    return redirect(url_for('orders'))


@app.route('/orders/approve/<int:order_id>', methods=['POST'])
@login_required
def approve_order(order_id):
    """Approve order."""
    order_manager = OrderManager(DB_PATH)
    success = order_manager.approve_order(order_id)
    
    if success:
        flash(f'Order #{order_id} approved', 'success')
    else:
        flash('Failed to approve order', 'error')
    
    return redirect(url_for('orders'))


@app.route('/forecast')
@login_required
def forecast():
    """Forecast page."""
    category_filter = request.args.get('category', '')
    
    forecast_engine = ForecastingEngine(DB_PATH)
    
    if category_filter:
        forecasts = forecast_engine.get_forecasts_by_category(category_filter)
    else:
        forecasts = forecast_engine.forecast_all_products()
    
    # Get categories
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT category FROM products ORDER BY category")
    categories = [row['category'] for row in cursor.fetchall()]
    conn.close()
    
    return render_template('forecast.html',
                         forecasts=forecasts,
                         categories=categories,
                         selected_category=category_filter)


@app.route('/api/forecast/<int:product_id>')
@login_required
def api_forecast(product_id):
    """API endpoint for forecast data (for charts)."""
    forecast_engine = ForecastingEngine(DB_PATH)
    forecast = forecast_engine.forecast_product(product_id, forecast_days=30)
    
    if forecast:
        return jsonify(forecast.to_dict())
    else:
        return jsonify({"error": "Forecast not found"}), 404


@app.route('/api/inventory/summary')
@login_required
def api_inventory_summary():
    """API endpoint for inventory summary (for charts)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT category, 
               SUM(current_stock * unit_cost) as value,
               COUNT(*) as count
        FROM products
        GROUP BY category
    """)
    
    data = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return jsonify(data)


@app.route('/api/consumption/<int:product_id>')
@login_required
def api_consumption(product_id):
    """API endpoint for consumption history (for charts)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT DATE(recorded_at) as date,
               SUM(ABS(change_amount)) as consumption
        FROM stock_logs
        WHERE product_id = ?
          AND change_amount < 0
          AND recorded_at >= datetime('now', '-30 days')
        GROUP BY DATE(recorded_at)
        ORDER BY date
    """, (product_id,))
    
    data = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return jsonify(data)


@app.route('/alerts')
@login_required
def alerts():
    """Active alerts page."""
    automation_engine = AutomationEngine(DB_PATH)
    
    # Run full cycle to get latest alerts
    summary = automation_engine.run_full_automation_cycle(auto_send_orders=False)
    all_alerts = automation_engine.get_alerts()
    
    return render_template('alerts.html',
                         alerts=all_alerts,
                         summary=summary)


@app.template_filter('format_datetime')
def format_datetime(value):
    """Template filter for datetime formatting."""
    if isinstance(value, str):
        try:
            dt = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
            return dt.strftime("%b %d, %Y %I:%M %p")
        except:
            return value
    return value


@app.template_filter('format_date')
def format_date(value):
    """Template filter for date formatting."""
    if isinstance(value, str):
        try:
            dt = datetime.strptime(value, "%Y-%m-%d")
            return dt.strftime("%b %d, %Y")
        except:
            return value
    return value


# ============================================================================
# INVOICING ROUTES - Cost Tracking and Financial Management
# ============================================================================

@app.route('/invoices')
@login_required
def invoices():
    """Invoice management and financial overview page."""
    from invoicing import InvoicingEngine
    
    db = DashGasDatabase(DB_PATH)
    engine = InvoicingEngine(db)
    
    # Get financial summary
    financial_summary = engine.get_financial_summary()
    
    # Get payment schedule
    payment_schedule = engine.get_payment_schedule()
    
    db.close()
    
    return render_template('invoices.html',
                         financial_summary=financial_summary,
                         payment_schedule=payment_schedule)


@app.route('/invoices/supplier/<int:supplier_id>')
@login_required
def supplier_invoices(supplier_id):
    """View invoices and cost breakdown for a specific supplier."""
    from invoicing import InvoicingEngine
    
    db = DashGasDatabase(DB_PATH)
    engine = InvoicingEngine(db)
    
    try:
        # Get supplier metrics
        metrics = engine.get_supplier_metrics(supplier_id)
        
        # Get invoices for supplier
        invoices_list = db.get_supplier_invoices(supplier_id)
        
        db.close()
        
        return render_template('supplier_invoices.html',
                             supplier_id=supplier_id,
                             supplier_name=metrics['supplier']['supplier_name'],
                             metrics=metrics,
                             invoices=invoices_list)
    except Exception as e:
        db.close()
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('invoices'))


@app.route('/invoices/details/<int:invoice_id>')
@login_required
def invoice_details(invoice_id):
    """View detailed invoice information."""
    db = DashGasDatabase(DB_PATH)
    
    try:
        invoice = db.get_invoice(invoice_id)
        if not invoice:
            flash('Invoice not found', 'error')
            return redirect(url_for('invoices'))
        
        items = db.get_invoice_items(invoice_id)
        
        # Get supplier name
        cursor = db._get_connection().cursor()
        cursor.execute("SELECT name FROM suppliers WHERE supplier_id = ?", 
                      (invoice['supplier_id'],))
        supplier = cursor.fetchone()
        supplier_name = supplier[0] if supplier else "Unknown"
        
        db.close()
        
        return render_template('invoice_details.html',
                             invoice=invoice,
                             items=items,
                             supplier_name=supplier_name)
    except Exception as e:
        db.close()
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('invoices'))


@app.route('/invoices/create/<int:order_id>', methods=['POST'])
@login_required
def create_invoice(order_id):
    """Create invoice from a purchase order."""
    from invoicing import InvoicingEngine
    
    invoice_number = request.form.get('invoice_number')
    invoice_date = request.form.get('invoice_date')
    due_date = request.form.get('due_date')
    
    db = DashGasDatabase(DB_PATH)
    engine = InvoicingEngine(db)
    
    try:
        invoice_id = engine.create_invoice_from_order(
            order_id, invoice_number, invoice_date, due_date
        )
        db.close()
        flash(f'Invoice #{invoice_id} created successfully', 'success')
        return redirect(url_for('invoice_details', invoice_id=invoice_id))
    except Exception as e:
        db.close()
        flash(f'Error creating invoice: {str(e)}', 'error')
        return redirect(url_for('orders'))


@app.route('/invoices/update/<int:invoice_id>', methods=['POST'])
@login_required
def update_invoice(invoice_id):
    """Update invoice status and payment."""
    status = request.form.get('status')
    paid_amount = float(request.form.get('paid_amount', 0))
    
    db = DashGasDatabase(DB_PATH)
    
    try:
        db.update_invoice_status(invoice_id, status, paid_amount)
        flash(f'Invoice #{invoice_id} updated', 'success')
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
    finally:
        db.close()
    
    return redirect(request.referrer or url_for('invoices'))


@app.route('/invoices/report/financials')
@login_required
def financial_report():
    """View comprehensive financial report."""
    from invoicing import InvoicingEngine
    
    db = DashGasDatabase(DB_PATH)
    engine = InvoicingEngine(db)
    
    # Get budget analysis
    budget_analysis = engine.get_budget_analysis()
    
    # Get financial summary
    financial_summary = engine.get_financial_summary()
    
    db.close()
    
    return render_template('financial_report.html',
                         budget_analysis=budget_analysis,
                         financial_summary=financial_summary)


@app.route('/invoices/report/export')
@login_required
def export_financials():
    """Export financial data."""
    from invoicing import InvoicingEngine
    
    db = DashGasDatabase(DB_PATH)
    engine = InvoicingEngine(db)
    
    try:
        json_export = engine.export_financials()
        db.close()
        
        # Return as file download
        response = jsonify(json.loads(json_export))
        response.headers['Content-Disposition'] = 'attachment; filename=dashgas_financials.json'
        return response
    except Exception as e:
        db.close()
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('invoices'))


# ============================================================================
# MONTH-END FINANCIAL REPORTING - Automatic, No User Work Required
# ============================================================================

@app.route('/financials/month')
@login_required
def month_end_financials():
    """Automatic month-end financial summary (current month by default)."""
    from invoicing import InvoicingEngine
    from datetime import datetime
    
    # Get month/year from query params or use current
    year = request.args.get('year', type=int) or datetime.now().year
    month = request.args.get('month', type=int) or datetime.now().month
    
    db = DashGasDatabase(DB_PATH)
    engine = InvoicingEngine(db)
    
    try:
        monthly_report = engine.get_monthly_financials(year, month)
        
        # Get available months for selector
        cursor = db._get_connection().cursor()
        cursor.execute("""
            SELECT DISTINCT 
                strftime('%Y', invoice_date) as year,
                strftime('%m', invoice_date) as month
            FROM invoices
            ORDER BY year DESC, month DESC
        """)
        available_months = []
        for row in cursor.fetchall():
            if row[0] and row[1]:
                available_months.append({
                    'year': int(row[0]),
                    'month': int(row[1]),
                    'display': datetime(int(row[0]), int(row[1]), 1).strftime("%B %Y")
                })
        
        db.close()
        
        return render_template('month_end_report.html',
                             monthly_report=monthly_report,
                             available_months=available_months,
                             current_year=year,
                             current_month=month)
    except Exception as e:
        db.close()
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('invoices'))


@app.route('/financials/year')
@login_required
def fiscal_year_summary():
    """Automatic fiscal year financial summary."""
    from invoicing import InvoicingEngine
    from datetime import datetime
    
    year = request.args.get('year', type=int) or datetime.now().year
    
    db = DashGasDatabase(DB_PATH)
    engine = InvoicingEngine(db)
    
    try:
        fiscal_report = engine.get_fiscal_year_summary(year)
        
        # Get available years
        cursor = db._get_connection().cursor()
        cursor.execute("""
            SELECT DISTINCT strftime('%Y', invoice_date) as year
            FROM invoices
            ORDER BY year DESC
        """)
        available_years = [int(row[0]) for row in cursor.fetchall() if row[0]]
        
        db.close()
        
        return render_template('fiscal_year_report.html',
                             fiscal_report=fiscal_report,
                             available_years=available_years,
                             current_year=year)
    except Exception as e:
        db.close()
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('invoices'))


@app.route('/financials/dashboard')
@login_required
def financial_dashboard():
    """Quick financial dashboard - current month at a glance."""
    from invoicing import InvoicingEngine
    from datetime import datetime
    
    db = DashGasDatabase(DB_PATH)
    engine = InvoicingEngine(db)
    
    try:
        # Get current month
        now = datetime.now()
        current_month = engine.get_monthly_financials(now.year, now.month)
        
        # Get last 3 months for comparison
        last_month = engine.get_monthly_financials(now.year, now.month - 1 if now.month > 1 else now.month - 1)
        
        db.close()
        
        return render_template('financial_dashboard.html',
                             current_month=current_month,
                             last_month=last_month)
    except Exception as e:
        db.close()
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('invoices'))


@app.route('/financials/export/month')
@login_required
def export_month_report():
    """Export month-end report as JSON."""
    from invoicing import InvoicingEngine
    from datetime import datetime
    
    year = request.args.get('year', type=int) or datetime.now().year
    month = request.args.get('month', type=int) or datetime.now().month
    
    db = DashGasDatabase(DB_PATH)
    engine = InvoicingEngine(db)
    
    try:
        json_export = engine.export_month_end_report(year, month)
        db.close()
        
        response = jsonify(json.loads(json_export))
        response.headers['Content-Disposition'] = f'attachment; filename=dashgas_month_{year:04d}_{month:02d}.json'
        return response
    except Exception as e:
        db.close()
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('invoices'))


@app.route('/financials/export/year')
@login_required
def export_fiscal_report():
    """Export fiscal year report as JSON."""
    from invoicing import InvoicingEngine
    from datetime import datetime
    
    year = request.args.get('year', type=int) or datetime.now().year
    
    db = DashGasDatabase(DB_PATH)
    engine = InvoicingEngine(db)
    
    try:
        json_export = engine.export_fiscal_report(year)
        db.close()
        
        response = jsonify(json.loads(json_export))
        response.headers['Content-Disposition'] = f'attachment; filename=dashgas_fiscal_{year:04d}.json'
        return response
    except Exception as e:
        db.close()
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('invoices'))


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
