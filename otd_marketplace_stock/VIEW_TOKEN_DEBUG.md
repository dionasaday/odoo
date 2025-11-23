# How to View Access Token (Debug Only)

## ⚠️ Security Warning
Access Tokens should **NEVER** be displayed in production. Only use these methods for debugging.

## Method 1: Via Odoo Shell (Recommended for Debug)

```bash
docker compose exec -T odoo python3 << 'EOF'
from odoo import api, SUPERUSER_ID
from odoo.api import Environment

db = 'odoo'
with api.Environment.manage():
    env = api.Environment(odoo.registry(db), SUPERUSER_ID, {})
    account = env['marketplace.account'].search([('name', '=', 'Shopee Thailand')], limit=1)
    if account:
        print(f"Access Token: {account.access_token[:50] if account.access_token else 'None'}...")
        print(f"Refresh Token: {account.refresh_token[:50] if account.refresh_token else 'None'}...")
        print(f"Expires At: {account.access_token_expire_at}")
    else:
        print("Account not found")
EOF
```

## Method 2: Via Odoo UI (Temporary)

If you need to see tokens temporarily, you can modify the view (NOT RECOMMENDED for production):

1. Go to **Settings** > **Technical** > **User Interface** > **Views**
2. Search for `marketplace.account` view
3. Find the `access_token` field
4. Remove `password="True"` attribute (temporarily)
5. Save and view
6. **IMPORTANT**: Change it back to `password="True"` after debugging!

## Method 3: Check Logs

```bash
docker compose logs odoo | grep -i "token exchange"
```

## Best Practice

✅ **Keep tokens masked** (password="True") in production
✅ **Use readonly** (readonly="1") to prevent editing
✅ **Check Token Expires At** to verify token exists
✅ **Use logs** for debugging instead of exposing tokens

## Verification

To verify tokens are working:
1. Check **Token Expires At** - should have a future date
2. Try using the API (e.g., fetch orders)
3. Check logs for successful API calls

