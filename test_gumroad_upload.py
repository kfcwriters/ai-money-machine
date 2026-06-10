import os, sys, requests, json
from fpdf import FPDF

TOKEN = os.environ["GUMROAD_TOKEN"]
PDF_PATH = "test_product.pdf"

print("=== Gumroad Upload Test (Final‑final) ===")

# ---- Create a simple test PDF ----
pdf = FPDF()
pdf.add_page()
pdf.set_font("Helvetica", size=12)
pdf.cell(200, 10, text="Test PDF content for Gumroad upload verification.")
pdf.output(PDF_PATH)
print("✅ Test PDF created.")

# ---- 1. Presign ----
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

# ---- 2. Upload to S3 ----
with open(PDF_PATH, "rb") as f:
    put_resp = requests.put(presigned_url, data=f, headers={"Content-Type": "application/pdf"}, timeout=60)
print("S3 upload status:", put_resp.status_code)
if put_resp.status_code not in (200, 201, 204):
    print("❌ Upload failed.")
    sys.exit(1)
# The ETag is returned in the response headers (usually with quotes)
etag = put_resp.headers.get("ETag", "")
print("ETag:", etag)
print("✅ File uploaded to S3.")

# ---- 3. Complete multipart upload ----
parts_array = [
    {
        "part_number": part["part_number"],
        "etag": etag
    }
]
complete_body = {
    "upload_id": upload_id,
    "key": data["key"],
    "parts": parts_array
}
resp = requests.post(
    "https://api.gumroad.com/v2/files/complete",
    headers={"Authorization": f"Bearer {TOKEN}"},
    json=complete_body,
    timeout=30
)
print("Complete status:", resp.status_code, resp.text[:400])
if resp.status_code != 200:
    print("❌ Completion failed.")
    sys.exit(1)

completed_data = resp.json()
file_url = completed_data.get("url") or data["file_url"]
print(f"✅ File ready: {file_url}")

# ---- 4. Create a test product ----
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
