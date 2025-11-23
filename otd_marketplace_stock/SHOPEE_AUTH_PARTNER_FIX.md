# Shopee OAuth auth_partner Endpoint - Troubleshooting Guide

## Current Status
✅ Partner ID: Correct (1100886)
✅ Partner Key: Correct (shpk6b6174484e4f4e575a4f7a646644646a4a7077796a4f774c6b5257614b76)
✅ Signature Calculation: Correct (Public API format: partner_id + api_path + timestamp)
✅ URL Format: Correct (https://partner.test-stable.shopeemobile.com/api/v2/shop/auth_partner)
❌ Still getting "Wrong sign" error from Shopee

## Possible Issues

### 1. Timestamp Expiration (5 minutes)
- Shopee API requires timestamp to be within 5 minutes
- If URL is generated but not used immediately, it may expire
- **Solution**: Generate fresh timestamp when clicking "Connect OAuth"

### 2. Redirect URI Domain Mismatch
- Shopee validates redirect URI against configured domain
- Check in Shopee Partner Center > App Management > Your App
- "Test Redirect URL Domain" should be: `43276ed5d1e3.ngrok-free.app` (without https://)
- **Current setting**: Verify this matches exactly

### 3. IP Whitelist
- If IP Whitelist is enabled, ngrok IP must be whitelisted
- **Check**: Shopee Partner Center > App Management > Your App > IP Address Whitelist
- **Current status**: Disabled (should be OK)

### 4. Shopee API Validation Bug
- Sometimes Shopee's validation has temporary issues
- **Solution**: Try again after a few minutes, or contact Shopee Support

## Verification Steps

### Step 1: Verify Redirect URI Domain in Shopee
1. Go to Shopee Partner Center
2. App Management > App List > CafeAtHome
3. Check "Test Redirect URL Domain"
4. Should be: `43276ed5d1e3.ngrok-free.app` (no https://, no trailing slash)

### Step 2: Test with Fresh URL
1. Generate a new OAuth URL (click "Connect OAuth")
2. Use it immediately (within 5 minutes)
3. Check browser console for any errors

### Step 3: Check ngrok Status
```bash
# Verify ngrok is running and accessible
curl https://43276ed5d1e3.ngrok-free.app
```

### Step 4: Test OAuth Callback Endpoint
```bash
# Test if callback endpoint is accessible
curl https://43276ed5d1e3.ngrok-free.app/marketplace/oauth/callback/shopee
```

## Code Implementation

Current implementation in `shopee_adapter.py`:
- Base string: `partner_id + path + timestamp` ✅
- Path: `/api/v2/shop/auth_partner` ✅
- Signature: HMAC-SHA256 ✅
- URL: `https://partner.test-stable.shopeemobile.com/api/v2/shop/auth_partner` ✅

## Next Steps

If all above checks pass but still getting "Wrong sign":
1. Contact Shopee Support with:
   - Partner ID: 1100886
   - Request ID from error response
   - Timestamp used
   - Signature generated
2. Ask them to verify:
   - Partner Key validation
   - Redirect URI domain validation
   - Any additional requirements for auth_partner endpoint

## References
- Shopee API Documentation: Signature Calculation
- Public API Base String: `partner_id + api_path + timestamp`
- Timestamp validity: 5 minutes

