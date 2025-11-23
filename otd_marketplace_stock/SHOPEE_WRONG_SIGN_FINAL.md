# Shopee "Wrong sign" Error - Final Troubleshooting

## Current Status
- ✅ Signature calculation: CORRECT (matches Shopee documentation)
- ✅ Partner ID: 1100886 (matches Shopee Console)
- ✅ Partner Key format: Correct (64 characters)
- ✅ Redirect URI: Correct (`https://43276ed5d1e3.ngrok-free.app/marketplace/oauth/callback/shopee`)
- ✅ Base string format: `partner_id + api_path + timestamp` (Public API)
- ❌ Still getting "Wrong sign" error

## Error Details
- **Error**: `error_sign`
- **Message**: `Wrong sign.`
- **Request ID**: `e3e3e7f342d9387c21a04a200c707b01`

## Possible Causes

### 1. Partner Key Mismatch (Most Likely)
Even though keys look identical, there might be:
- Hidden whitespace (leading/trailing spaces)
- Newline characters
- Encoding issues
- Copy-paste errors

**Solution**: 
1. Go to Shopee Partner Center > App Management > CafeAtHome
2. Copy the **Test API Partner Key** again
3. In Odoo: Marketplace > Accounts > Shopee Thailand
4. Clear the "Client Secret" field completely
5. Paste the Partner Key again (make sure no extra spaces)
6. Save and test again

### 2. Partner Key Regeneration
If the above doesn't work, try:
1. In Shopee Partner Center, check if you can regenerate the Test Partner Key
2. If yes, regenerate it and update in Odoo

### 3. Shopee API Validation Issue
Shopee might have additional validation that's not documented:
- URL parameter order
- Case sensitivity
- Additional validation rules

### 4. Test Environment Issue
The test environment (`partner.test-stable.shopeemobile.com`) might have:
- Temporary issues
- Different validation rules than documented
- Cache issues

## Recommended Actions

### Step 1: Verify Partner Key Exactly
1. Open Shopee Partner Center
2. Copy Test API Partner Key (click eye icon to show)
3. Copy to a text editor (Notepad, TextEdit)
4. Check for any spaces or hidden characters
5. Copy from text editor to Odoo (Client Secret field)
6. Make sure no trailing spaces

### Step 2: Test with Fresh URL
1. Generate new OAuth URL (click "Connect OAuth")
2. Use immediately (within 5 minutes)
3. Check logs for exact signature used

### Step 3: Contact Shopee Support
If still failing, contact Shopee Support with:
- **Partner ID**: 1100886
- **Request ID**: e3e3e7f342d9387c21a04a200c707b01
- **Endpoint**: `/api/v2/shop/auth_partner`
- **Base String Format**: `partner_id + api_path + timestamp`
- **Signature Algorithm**: HMAC-SHA256
- **Redirect URI**: `https://43276ed5d1e3.ngrok-free.app/marketplace/oauth/callback/shopee`
- **Test Redirect URL Domain in Console**: `https://43276ed5d1e3.ngrok-free.app`
- **Timestamp used**: [from logs]
- **Signature calculated**: [from logs]

Ask them to:
1. Verify Partner Key validation on their side
2. Check if there are any additional requirements for `auth_partner` endpoint
3. Verify the redirect URI domain validation

## Alternative: Try Live Environment
If test environment continues to fail:
1. Get Live Partner ID and Partner Key from Shopee Console
2. Update Odoo account with Live credentials
3. Change base URL to `https://partner.shopeemobile.com`
4. Update Redirect URI Domain in Shopee Console for Live environment
5. Test OAuth again

## Debugging Commands

### Check Odoo Logs
```bash
docker compose logs -f odoo | grep -i "shopee.*oauth"
```

### Verify Signature Calculation
```python
import hmac
import hashlib

partner_id = 1100886
api_path = '/api/v2/shop/auth_partner'
timestamp = [current_timestamp]
partner_key = "shpk6b6174484e4f4e575a4f7a646644646a4a7077796a4f774c6b5257614b76"

base_string = f"{partner_id}{api_path}{timestamp}"
signature = hmac.new(
    partner_key.encode('utf-8'),
    base_string.encode('utf-8'),
    hashlib.sha256
).hexdigest()
```

## Next Steps
1. ✅ Verify Partner Key has no hidden characters
2. ✅ Try regenerating Partner Key (if possible)
3. ✅ Contact Shopee Support with request_id
4. ⚠️ Consider trying Live environment if test continues to fail

