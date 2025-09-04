#!/usr/bin/env python3
"""
Create a simple test invoice PDF for testing
"""

# First, let's create a simple HTML invoice and note that it needs to be converted to PDF
html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>Invoice INV-2024-001</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        h1 { color: #333; }
        .header { display: flex; justify-content: space-between; margin-bottom: 30px; }
        .addresses { display: flex; justify-content: space-between; margin: 30px 0; }
        .address-block { width: 45%; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
        .totals { text-align: right; margin-top: 20px; }
        .total-line { margin: 5px 0; }
    </style>
</head>
<body>
    <h1>INVOICE</h1>
    
    <div class="header">
        <div>
            <strong>Invoice Number:</strong> INV-2024-001<br>
            <strong>Invoice Date:</strong> 2024-01-15<br>
            <strong>Due Date:</strong> 2024-02-15<br>
            <strong>PO Number:</strong> 12345678
        </div>
    </div>
    
    <div class="addresses">
        <div class="address-block">
            <h3>Bill To:</h3>
            Customer Company Inc.<br>
            123 Customer Street<br>
            New York, NY 10001<br>
            USA<br>
            Email: billing@customer.com
        </div>
        <div class="address-block">
            <h3>From:</h3>
            ACME Supplier Corporation<br>
            456 Vendor Avenue<br>
            Los Angeles, CA 90001<br>
            USA<br>
            Tax ID: 12-3456789<br>
            Email: invoices@acme.com
        </div>
    </div>
    
    <h3>Invoice Details</h3>
    <table>
        <thead>
            <tr>
                <th>Description</th>
                <th>Quantity</th>
                <th>Unit Price</th>
                <th>Amount</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>Professional Services - Consulting</td>
                <td>10</td>
                <td>$100.00</td>
                <td>$1,000.00</td>
            </tr>
            <tr>
                <td>Software Development</td>
                <td>20</td>
                <td>$150.00</td>
                <td>$3,000.00</td>
            </tr>
            <tr>
                <td>Project Management</td>
                <td>5</td>
                <td>$120.00</td>
                <td>$600.00</td>
            </tr>
        </tbody>
    </table>
    
    <div class="totals">
        <div class="total-line"><strong>Subtotal:</strong> $4,600.00</div>
        <div class="total-line"><strong>Tax (10%):</strong> $460.00</div>
        <div class="total-line"><strong>Shipping:</strong> $50.00</div>
        <div class="total-line" style="font-size: 1.2em; border-top: 2px solid #333; padding-top: 5px;">
            <strong>Total Amount Due:</strong> $5,110.00
        </div>
    </div>
    
    <div style="margin-top: 40px;">
        <strong>Payment Terms:</strong> Net 30<br>
        <strong>Payment Method:</strong> Bank Transfer<br>
        <strong>Bank Account:</strong> 1234567890<br>
        <strong>Routing Number:</strong> 987654321
    </div>
</body>
</html>
"""

# Save as HTML
with open("test_invoice.html", "w") as f:
    f.write(html_content)

print("✅ Created test_invoice.html")
print("\nTo convert to PDF, you can:")
print("1. Open test_invoice.html in a browser and print to PDF")
print("2. Use wkhtmltopdf: wkhtmltopdf test_invoice.html test_invoice.pdf")
print("3. Use weasyprint: weasyprint test_invoice.html test_invoice.pdf")
print("\nFor testing, you can also use any existing PDF invoice file.")