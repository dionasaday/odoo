# Fix Shopee Redirect URI Domain Configuration

## Problem Found
The "Test Redirect URL Domain" in Shopee Partner Center is set to:
```
https://43276ed5d1e3.ngrok-free.app
```

But Shopee typically validates **only the domain** (without `https://`).

## Solution

### Step 1: Update Shopee Partner Center
1. Go to **Shopee Partner Center** > **App Management** > **App List** > **CafeAtHome**
2. Find **"Test Redirect URL Domain"** field
3. Change from:
   ```
   https://43276ed5d1e3.ngrok-free.app
   ```
   To:
   ```
   43276ed5d1e3.ngrok-free.app
   ```
   (Remove `https://` prefix)
4. Click **Save**

### Step 2: Verify Odoo Redirect URI
Odoo is correctly sending:
```
https://43276ed5d1e3.ngrok-free.app/marketplace/oauth/callback/shopee
```

Shopee will extract the domain (`43276ed5d1e3.ngrok-free.app`) and match it against the configured domain.

### Step 3: Test OAuth Again
1. After updating Shopee Console, wait a few seconds
2. Go to Odoo > Marketplace > Accounts > Shopee Thailand
3. Click **"Connect OAuth"**
4. Should now work without "Wrong sign" error!

## Why This Matters
Shopee validates the **domain** part of the redirect_uri against the configured "Test Redirect URL Domain". 

- ✅ Correct: Domain only (`43276ed5d1e3.ngrok-free.app`)
- ❌ Wrong: Full URL with https:// (`https://43276ed5d1e3.ngrok-free.app`)

The redirect_uri sent in the OAuth request is:
```
https://43276ed5d1e3.ngrok-free.app/marketplace/oauth/callback/shopee
```

Shopee extracts the domain (`43276ed5d1e3.ngrok-free.app`) and compares it with the configured domain. If they don't match, it can cause validation errors.

## Verification
After updating, the configuration should be:
- **Shopee Console**: `43276ed5d1e3.ngrok-free.app` (domain only)
- **Odoo redirect_uri**: `https://43276ed5d1e3.ngrok-free.app/marketplace/oauth/callback/shopee` (full URL)
- **Domain extraction**: `43276ed5d1e3.ngrok-free.app` ✅ Match!

