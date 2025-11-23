#!/bin/bash
# Check image sync status

echo "🔍 Checking image sync status..."
echo ""

# Check latest image sync job
echo "📋 Latest Image Sync Jobs:"
docker compose exec odoo odoo shell -d odoo --no-http << 'EOF'
env = self.env

# Find latest image update job
latest_job = env['marketplace.job'].search([
    ('job_type', '=', 'sync_product_from_zortout'),
    ('payload', 'like', '%update_images_only%'),
], order='create_date desc', limit=5)

if latest_job:
    for job in latest_job:
        print(f"\n📦 Job: {job.name}")
        print(f"   State: {job.state}")
        print(f"   Created: {job.create_date}")
        if job.started_at:
            print(f"   Started: {job.started_at}")
        if job.completed_at:
            print(f"   Completed: {job.completed_at}")
        if job.result:
            import json
            try:
                result = json.loads(job.result)
                print(f"   Images Downloaded: {result.get('images_downloaded', 0)}")
                print(f"   Images Skipped: {result.get('images_skipped', 0)}")
                print(f"   Products Processed: {result.get('products_fetched', 0)}")
            except:
                print(f"   Result: {job.result[:200]}...")
        if job.last_error:
            print(f"   Error: {job.last_error[:200]}...")
else:
    print("❌ No image sync jobs found")
EOF

echo ""
echo "📊 Products with/without images:"
docker compose exec odoo odoo shell -d odoo --no-http << 'EOF'
env = self.env

# Count products with images
products_with_images = env['product.template'].search_count([
    ('image_1920', '!=', False),
    ('default_code', '!=', False),
])

products_without_images = env['product.template'].search_count([
    ('image_1920', '=', False),
    ('default_code', '!=', False),
])

total = products_with_images + products_without_images

print(f"   Total products with SKU: {total}")
print(f"   ✅ With images: {products_with_images}")
print(f"   ❌ Without images: {products_without_images}")
if total > 0:
    percentage = (products_with_images / total) * 100
    print(f"   📈 Coverage: {percentage:.1f}%")
EOF


