import os, sys, requests, json
from fpdf import FPDF

TOKEN = os.environ["GUMROAD_TOKEN"]
PDF_PATH = "test_product.pdf"

print("=== Gumroad Upload Test ===")

# Create a simple test PDF
pdf = FPDF()
pdf.add_page()
pdf.set_font("Helvetica", size=12)
pdf.cell(200, 10, text="Test PDF content for Gumroad upload verification.")
pdf.output(PDF_PATH)
print("✅ Test PDF created.")

# 1. Presign
resp = requests.post(
    "https://api.gumroad.com/v2/files/presign",
    headers={"Authorization": f"Bearer {TOKEN}"},
    json={"filename": "test.pdf", "file_size": os.path.getsize(PDF_PATH)},
    timeout=30
)
print("Presign status:", resp.status_code)
print("Presign response JSON:", json.dumps(resp.json(), indent=2))   # <-- SEE EVERYTHING

if resp.status_code != 200:
    print("❌ Presign failed.")
    sys.exit(1)

data = resp.json()

# Try multiple possible keys (Gumroad documentation varies)
upload_url = data.get("upload_url") or data.get("url") or data.get("presigned_url")
file_id = data.get("id") or data.get("file_id")

if not upload_url or not file_id:
    print("❌ Missing upload_url or file_id. Full response above.")
    sys.exit(1)

print(f"✅ Using upload_url: {upload_url[:80]}...")
print(f"✅ File ID: {file_id}")

# 2. Upload to S3
with open(PDF_PATH, "rb") as f:
    put_resp = requests.put(upload_url, data=f, headers={"Content-Type": "application/pdf"}, timeout=60)
print("S3 upload status:", put_resp.status_code)
if put_resp.status_code not in (200, 201, 204):
    print("❌ S3 upload failed.")
    sys.exit(1)
print("✅ File uploaded to S3.")

# 3. Complete
resp = requests.post(
    "https://api.gumroad.com/v2/files/complete",
    headers={"Authorization": f"Bearer {TOKEN}"},
    json={"id": file_id},
    timeout=30
)
print("Complete status:", resp.status_code)
print("Complete response:", resp.text[:200])
if resp.status_code != 200:
    print("❌ File completion failed.")
    sys.exit(1)

file_url = resp.json()["url"]
print(f"✅ File ready: {file_url}")

# 4. Create a test product
product_data = {
    "name": "Test Product (auto)",
    "description": "Temporary test product.",
    "price": "99",
    "published": "false",
    "files": [{"url": file_url}]
}
resp = requests.post(
    "https://api.gumroad.com/v2/products",
    headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
    json=product_data,
    timeout=30
)
if resp.status_code == 200:
    short_url = resp.json()["product"]["short_url"]
    print(f"🎉 Test product created: {short_url}")
else:
    print(f"❌ Product creation failed: {resp.status_code} {resp.text}")

print("=== Test finished ===")
