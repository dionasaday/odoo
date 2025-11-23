# Shopee OAuth Debug Guide

## Current Issue: "Wrong sign" Error

### ✅ What We've Verified:
1. Signature calculation is **CORRECT** (tested and matches expected)
2. `web.base.url` is set to ngrok HTTPS URL
3. Redirect URI matches Shopee Partner Center settings
4. URL encoding is correct

### ⚠️ Most Likely Cause:
**Partner Key mismatch** between:
- What's stored in Odoo as "Client Secret"
- What's configured in Shopee Partner Center as "Partner Key"

### 🔍 How to Fix:

#### Step 1: Get Partner Key from Shopee
1. Go to [Shopee Partner Center](https://partner.test-stable.shopeemobile.com)
2. Navigate to **App Management** > **App List**
3. Select your app
4. Find **"Partner Key"** (NOT Client Secret)
5. Copy the Partner Key

#### Step 2: Update Odoo
1. Go to Odoo > Marketplace > Accounts
2. Open "Shopee Thailand" account
3. Update **Client Secret** field with the **Partner Key** from Step 1
4. Save

#### Step 3: Verify Partner ID
- In Shopee Partner Center, check your **Partner ID**
- In Odoo, verify **Client ID** matches Partner ID exactly
- Both should be: `1100886`

#### Step 4: Test Again
1. Click "Connect OAuth" button
2. Check if authorization page loads

### 📝 Additional Checks:

#### Check 1: Partner Key Format
- Partner Key should be a long alphanumeric string
- Usually starts with `shpk` for Shopee Partner Keys
- Length: typically 64 characters

#### Check 2: Test Environment
- Make sure you're using **Test Environment** (`partner.test-stable.shopeemobile.com`)
- For Live, use `partner.shopeemobile.com`

#### Check 3: IP Whitelist (if enabled)
- If IP Whitelist is enabled in Shopee, ensure ngrok IP is whitelisted
- Current ngrok IP: Check with `curl ifconfig.me` or similar

### 🔧 Debug Commands:

```bash
# Test signature calculation
docker compose exec -T odoo python3 << 'EOF'
import hmac
import hashlib
import time

partner_id = 1100886
path = '/api/v2/shop/auth_partner'
timestamp = int(time.time())
partner_key = "YOUR_PARTNER_KEY_HERE"  # Replace with actual Partner Key

base_string = f"{partner_id}{path}{timestamp}"
signature = hmac.new(
    partner_key.encode('utf-8'),
    base_string.encode('utf-8'),
    hashlib.sha256
).hexdigest()

print(f"Base String: {base_string}")
print(f"Signature: {signature}")
print(f"Timestamp: {timestamp}")
EOF
```

### 📚 Shopee API Documentation References:
- Base string format: `partner_id + path + timestamp`
- Path: `/api/v2/shop/auth_partner`
- Algorithm: HMAC-SHA256
- Key: Partner Key (NOT Client Secret)

### ⚡ Quick Test:
After updating Partner Key, generate a new OAuth URL and test it directly in browser:
```
https://partner.test-stable.shopeemobile.com/api/v2/shop/auth_partner?partner_id=1100886&redirect=https://43276ed5d1e3.ngrok-free.app/marketplace/oauth/callback/shopee&timestamp=XXXXX&sign=XXXXX
```

If it works, you should see Shopee's authorization page instead of "Wrong sign" error.

