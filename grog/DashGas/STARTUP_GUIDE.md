# DashGas Startup Guide
**Get from Zero to Running in 10 Minutes**

This guide walks you through installing, setting up, and running DashGas with sample data. Perfect for demos and first-time use.

---

## Part 1: Installation (2 minutes)

### Prerequisites
- Python 3.7+
- Git
- Internet connection

### Step 1: Clone the Repository
```bash
git clone https://github.com/devsgithubaccount/Projects.git
cd Projects/grog/DashGas
```

### Step 2: Install Dependencies
```bash
# Create virtual environment (optional but recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install requirements
pip install -r requirements.txt
```

**What gets installed:**
- Flask (web dashboard)
- pytest (testing)
- black & flake8 (code quality)

### Step 3: Verify Installation
```bash
python3 validate_system.py
```

**Expected output:**
```
================================================================================
DashGas System Validation
================================================================================
...
✓ SYSTEM VALIDATION COMPLETE - PRODUCTION READY
```

---

## Part 2: Run the Dashboard (1 minute)

### Start the Flask App
```bash
python3 dashboard/app.py
```

**Expected output:**
```
 * Running on http://0.0.0.0:5000
 * Debug mode: on
```

### Access the Dashboard
Open your browser and go to:
```
http://localhost:5000/login
```

**Login credentials:**
- Username: `admin`
- Password: `dashgas123`

---

## Part 3: Setup Sample Data (3 minutes)

Run the setup script to populate realistic sample data:

```bash
# In another terminal (keep Flask running)
python3 << 'EOF'
from database import DashGasDatabase
from invoicing import InvoicingEngine
from datetime import datetime, timedelta

db = DashGasDatabase("dashgas.db")
engine = InvoicingEngine(db)

print("Setting up sample data for demo...\n")

# Create suppliers
print("1. Creating suppliers...")
suppliers = {
    "shell": db.add_supplier("Shell Wholesale", "shell@example.com", "555-0001", 2),
    "chevron": db.add_supplier("Chevron Distributor", "chevron@example.com", "555-0002", 3),
    "bp": db.add_supplier("BP Fuel Co", "bp@example.com", "555-0003", 1),
}
print(f"   ✓ Created {len(suppliers)} suppliers")

# Create products
print("\n2. Creating product catalog...")
products = {
    "regular": db.add_product("Regular Gasoline", "fuel", 15000, "gallons", 3000, suppliers["shell"], 2, unit_cost=2.35),
    "premium": db.add_product("Premium Gasoline", "fuel", 10000, "gallons", 2000, suppliers["shell"], 2, unit_cost=2.85),
    "diesel": db.add_product("Diesel", "fuel", 12000, "gallons", 2500, suppliers["chevron"], 3, unit_cost=2.45),
    "water": db.add_product("Bottled Water", "c-store", 800, "units", 150, suppliers["chevron"], 1, unit_cost=0.75),
    "coffee": db.add_product("Premium Coffee", "c-store", 400, "lbs", 50, suppliers["bp"], 2, unit_cost=8.50),
    "marlboro": db.add_product("Marlboro Cigarettes", "tobacco", 300, "packs", 50, suppliers["shell"], 2, unit_cost=4.50),
}
print(f"   ✓ Created {len(products)} products")

# Simulate 7 days of consumption
print("\n3. Simulating 7 days of operations...")
for day in range(1, 8):
    # Regular gas (800 gal/day)
    current = db.get_product_by_id(products["regular"])['current_stock']
    db.log_stock_change(products["regular"], current - 800, -800, "daily_consumption")
    
    # Premium gas (500 gal/day)
    current = db.get_product_by_id(products["premium"])['current_stock']
    db.log_stock_change(products["premium"], current - 500, -500, "daily_consumption")
    
    # Diesel (700 gal/day)
    current = db.get_product_by_id(products["diesel"])['current_stock']
    db.log_stock_change(products["diesel"], current - 700, -700, "daily_consumption")
    
    # Coffee (25 lbs/day)
    current = db.get_product_by_id(products["coffee"])['current_stock']
    db.log_stock_change(products["coffee"], current - 25, -25, "daily_consumption")

print(f"   ✓ Simulated 7 days of consumption")

# Create purchase orders
print("\n4. Creating purchase orders...")
orders = [
    db.create_order(products["regular"], suppliers["shell"], 8000, "2026-02-20", 2.35),
    db.create_order(products["premium"], suppliers["shell"], 5000, "2026-02-20", 2.85),
    db.create_order(products["diesel"], suppliers["chevron"], 6000, "2026-02-21", 2.45),
]
print(f"   ✓ Created {len(orders)} purchase orders")

# Record deliveries
print("\n5. Recording deliveries...")
for order_id in orders:
    cursor = db._get_connection().cursor()
    cursor.execute("SELECT quantity FROM orders WHERE order_id = ?", (order_id,))
    qty = cursor.fetchone()[0]
    db.record_delivery(order_id, qty, "good", "Delivered on time")
print(f"   ✓ Recorded {len(orders)} deliveries")

# Create invoices
print("\n6. Creating invoices...")
invoices = []
for idx, order_id in enumerate(orders, 1):
    inv_id = engine.create_invoice_from_order(order_id, f"INV-2026-02-{idx:03d}")
    invoices.append(inv_id)
    
    # Add a partial payment to first invoice for demo
    if idx == 1:
        db.update_invoice_status(inv_id, "partial", 5000)
print(f"   ✓ Created {len(invoices)} invoices")

# Show summary
print("\n" + "="*70)
print("SAMPLE DATA READY FOR DEMO")
print("="*70)

summary = engine.get_financial_summary()
print(f"\nFinancial Summary:")
print(f"  Total Spending: ${summary['total_cost']:.2f}")
print(f"  Amount Paid: ${summary['total_paid']:.2f}")
print(f"  Outstanding: ${summary['total_outstanding']:.2f}")
print(f"  Pending Invoices: {summary['pending_invoices']}")

print(f"\nSupplier Breakdown:")
for supplier in summary['suppliers'][:3]:
    print(f"  - {supplier['name']}: ${supplier['total_cost']:.2f}")

db.close()
print("\n✓ Setup complete! Visit http://localhost:5000 to view the dashboard.")
EOF
```

---

## Part 4: Explore the Dashboard (4 minutes)

### 1. Financial Dashboard (Current Month Overview)
**Navigate to:** `/financials/dashboard`

See at a glance:
- This month's total cost
- Amount paid vs outstanding
- Top suppliers and products
- Month-over-month comparison

### 2. Month-End Financial Report
**Navigate to:** `/financials/month`

Shows:
- Detailed monthly breakdown
- Supplier cost breakdown (who costs the most?)
- Product cost breakdown (which products cost the most?)
- Invoice status distribution (pending/partial/paid)
- Month selector to view historical months

### 3. Fiscal Year Summary
**Navigate to:** `/financials/year`

Shows:
- Annual spending trends
- Monthly breakdown table
- Highest/lowest spending months
- Monthly detail accordion

### 4. Invoice Management
**Navigate to:** `/invoices`

Shows:
- Payment schedule (upcoming due dates)
- Supplier cost summary
- Which suppliers still owe money

### 5. Inventory Management
**Navigate to:** `/inventory`

Shows:
- Current stock levels
- Low stock alerts
- Product categories

---

## Demo Talking Points

### "Real-Time Visibility"
> "See your financial position instantly. No spreadsheets, no manual work. All automatically aggregated from your invoices."

**Show:** Financial Dashboard → Point to total cost and outstanding balance

### "Complete Cost Tracking"
> "Track costs at every level - per unit, per supplier, per product, per month."

**Show:** Month-End Report → Supplier breakdown → Show Shell's $11,750 cost breakdown

### "Automatic Financial Reporting"
> "Month-end reports generate automatically. No manual data entry. Open the dashboard, your numbers are there."

**Show:** Month selector → Change month → Data updates instantly

### "Payment Management"
> "See exactly who owes what and when it's due. Track partial payments in real-time."

**Show:** Invoices page → Payment schedule → Show partial payment status

### "Accounting Integration"
> "Export everything as JSON for your accounting system. Ready to integrate with QuickBooks, FreshBooks, Wave, or custom systems."

**Show:** Financial Report → Export button → Show JSON structure

---

## Common Demo Scenarios

### Scenario 1: "Show me September's financials"
1. Go to `/financials/month`
2. Use month selector to pick September
3. Show: Total cost, supplier breakdown, payment status

**Time:** 30 seconds

### Scenario 2: "What's our top supplier?"
1. Go to `/financials/dashboard`
2. Show "Top Suppliers This Month"
3. Click supplier name for detailed breakdown

**Time:** 20 seconds

### Scenario 3: "What invoices are outstanding?"
1. Go to `/invoices`
2. Show payment schedule
3. Point out unpaid and partial invoices

**Time:** 20 seconds

### Scenario 4: "What happened with diesel costs?"
1. Go to `/financials/month`
2. Scroll to Product Breakdown
3. Show diesel line item

**Time:** 15 seconds

---

## Troubleshooting

### Flask Won't Start
```bash
pip install flask
# Then try again
python3 dashboard/app.py
```

### Database Already Exists
```bash
# Remove old database to start fresh
rm dashgas.db
# Re-run sample data setup above
```

### Port 5000 Already in Use
```bash
# Use a different port
python3 dashboard/app.py --port 5001
# Visit http://localhost:5001
```

### Login Not Working
Check credentials:
- Username: `admin`
- Password: `dashgas123`

If still stuck, restart Flask.

---

## What Happens Next?

### For Personal Use
1. **Add your suppliers** (Inventory page)
2. **Add your products** (Inventory page)
3. **Start logging consumption** (Inventory page)
4. **Create purchase orders** (Orders page)
5. **Create invoices from orders** (Invoices page)
6. **View financial reports** (Financials pages)

### For Customer Demo
1. **Show sample data** (already loaded)
2. **Walk through financial dashboard** (2 minutes)
3. **Show month-end reports** (1 minute)
4. **Answer questions** about customization
5. **Offer to set up with their suppliers/products**

---

## Next Steps

### Documentation
- **README.md** - Complete API reference and usage
- **DEPLOYMENT.md** - Production deployment guide
- **This file** - Startup and demo guide

### Customization
- Edit supplier names/contacts (database.py)
- Add your own products (database.py)
- Customize invoice format (dashboard/templates/)

### Integration
- Connect to accounting software (JSON export)
- Add supplier APIs for real-time pricing
- Build custom reporting

---

## Support

**Issues?**
1. Check troubleshooting section above
2. Run `python3 validate_system.py` to verify installation
3. Check logs in Flask terminal window

**Have questions about the system?**
Review the DEPLOYMENT.md and README.md files for detailed documentation.

---

**Ready to demo?** You're good to go! 🚀

Start with the Financial Dashboard, and let the data speak for itself.
