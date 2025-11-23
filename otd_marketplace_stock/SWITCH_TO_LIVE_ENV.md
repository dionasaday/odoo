# Switch Shopee Integration to Live Environment

## Prerequisites
1. **Live Partner ID** from Shopee Console (from screenshot: `2001559`)
2. **Live API Partner Key** from Shopee Console (need to copy from Shopee)
3. **Live Redirect URL Domain** - Your production domain or ngrok URL

## Step 1: Get Live Credentials from Shopee

1. Go to **Shopee Partner Center** > **App Management** > **App List** > **CafeAtHome**
2. Find **"Live Partner_id"**: `2001559`
3. Find **"Live API Partner Key"**: Click eye icon to reveal
4. Copy both values

## Step 2: Update Odoo Base URL Configuration

### Option A: Via Odoo UI (Recommended)
1. Go to **Settings** > **Technical** > **Parameters** > **System Parameters**
2. Search for `marketplace.shopee.base_url`
3. If exists, edit it to: `https://partner.shopeemobile.com/api/v2`
4. If not exists, create new:
   - **Key**: `marketplace.shopee.base_url`
   - **Value**: `https://partner.shopeemobile.com/api/v2`

### Option B: Via Odoo Shell
```bash
docker compose exec -T odoo python3 << 'EOF'
from odoo import api, SUPERUSER_ID
from odoo.api import Environment

# Connect to database
db = 'odoo'
with api.Environment.manage():
    env = api.Environment(odoo.registry(db), SUPERUSER_ID, {})
    env['ir.config_parameter'].sudo().set_param(
        'marketplace.shopee.base_url',
        'https://partner.shopeemobile.com/api/v2'
    )
    print("✅ Base URL updated to Live environment")
EOF
```

## Step 3: Update Marketplace Account in Odoo

1. Go to **Marketplace** > **Accounts** > **Shopee Thailand**
2. Update:
   - **Client ID**: `2001559` (Live Partner ID)
   - **Client Secret**: [Paste Live API Partner Key from Step 1]
3. **Save**

## Step 4: Configure Live Redirect URL in Shopee Console

1. Go to **Shopee Partner Center** > **App Management** > **App List** > **CafeAtHome**
2. Find **"Live Redirect URL Domain"** field
3. Enter your production domain:
   - If using ngrok: `https://43276ed5d1e3.ngrok-free.app` (or your current ngrok URL)
   - If using production: `https://yourdomain.com`
4. **Save**

## Step 5: Update Odoo web.base.url (if needed)

If you're using ngrok for Live testing:
1. Go to **Settings** > **Technical** > **Parameters** > **System Parameters**
2. Find `web.base.url`
3. Update to your ngrok URL: `https://43276ed5d1e3.ngrok-free.app` (or your current ngrok URL)
4. **Save**

## Step 6: Test OAuth Connection

1. Go to **Marketplace** > **Accounts** > **Shopee Thailand**
2. Click **"Connect OAuth"**
3. Should redirect to Shopee Live authorization page
4. Authorize the connection
5. Check if tokens are saved in Odoo

## Verification

After setup, verify:
- ✅ Base URL: `https://partner.shopeemobile.com/api/v2` (Live)
- ✅ Partner ID: `2001559` (Live)
- ✅ Partner Key: [Live Key from Shopee]
- ✅ Redirect URI Domain: Configured in Shopee Console
- ✅ web.base.url: Matches redirect domain

## Important Notes

⚠️ **Live Environment Considerations:**
- Live environment uses real Shopee data
- Make sure you have proper error handling
- Test thoroughly before using in production
- Keep credentials secure

⚠️ **Ngrok for Live Testing:**
- If using ngrok, the URL will change when you restart ngrok
- You'll need to update both:
  - `web.base.url` in Odoo
  - `Live Redirect URL Domain` in Shopee Console

## Troubleshooting

### Still getting "Wrong sign"?
1. Verify Live Partner Key is copied correctly (no spaces)
2. Check that base URL is set to Live: `https://partner.shopeemobile.com/api/v2`
3. Verify Live Redirect URL Domain in Shopee Console matches `web.base.url` in Odoo
4. Check Odoo logs for debug messages

### OAuth redirects to wrong URL?
- Check `web.base.url` in Odoo matches `Live Redirect URL Domain` in Shopee Console
- Both should use `https://` prefix

### Need to switch back to Test?
- Set `marketplace.shopee.base_url` to: `https://partner.test-stable.shopeemobile.com/api/v2`
- Update Client ID to Test Partner ID: `1100886`
- Update Client Secret to Test Partner Key

