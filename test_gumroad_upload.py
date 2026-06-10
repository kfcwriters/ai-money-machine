import os, sys, requests, json
from fpdf import FPDF

TOKEN = os.environ["GUMROAD_TOKEN"]
PDF_PATH = "test_product.pdf"

print("=== Gumroad Upload Test (v3) ===")

# Create test PDF
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
if resp.status_code != 200:
    print("❌ Presign failed:", resp.text)
    sys.exit(1)

data = resp.json()
print("Presign response:", json.dumps(data, indent=2))

upload_id = data["upload_id"]
part = data["parts"][0]
presigned_url = part["presigned_url"]

# 2. Upload to the presigned URL
with open(PDF_PATH, "rb") as f:
    put_resp = requests.put(presigned_url, data=f, headers={"Content-Type": "application/pdf"}, timeout=60)
print("S3 upload status:", put_resp.status_code)
if put_resp.status_code not in (200, 201, 204):
    print("❌ Upload failed.")
    sys.exit(1)
print("✅ File uploaded.")

# 3. Complete multipart upload
resp = requests.post(
    "https://api.gumroad.com/v2/files/complete",
    headers={"Authorization": f"Bearer {TOKEN}"},
    json={"upload_id": upload_id},      # this is the key
    timeout=30
)
print("Complete status:", resp.status_code, resp.text[:200])
if resp.status_code != 200:
    print("❌ Completion failed.")
    sys.exit(1)

file_url = data["file_url"]   # this was already given; we can also use the completion response
print(f"✅ File ready: {file_url}")

# 4. Create product with file
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
