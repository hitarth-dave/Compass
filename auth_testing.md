# Auth-Gated App Testing Playbook (Compass Astro)

## Step 1: Create Test User & Session
```bash
mongosh --eval "
use('test_database');
var userId = 'test-user-' + Date.now();
var sessionToken = 'test_session_' + Date.now();
db.users.insertOne({
  user_id: userId,
  email: 'test.user.' + Date.now() + '@example.com',
  name: 'Test User',
  picture: 'https://via.placeholder.com/150',
  created_at: new Date()
});
db.user_sessions.insertOne({
  user_id: userId,
  session_token: sessionToken,
  expires_at: new Date(Date.now() + 7*24*60*60*1000),
  created_at: new Date()
});
print('Session token: ' + sessionToken);
print('User ID: ' + userId);
"
```

## Step 2: Test Backend API
```bash
# Auth endpoint
curl -X GET "$BASE/api/auth/me" -H "Authorization: Bearer $TOKEN"

# Protected endpoints
curl -X GET "$BASE/api/profile" -H "Authorization: Bearer $TOKEN"
curl -X GET "$BASE/api/threads" -H "Authorization: Bearer $TOKEN"
curl -X GET "$BASE/api/books" -H "Authorization: Bearer $TOKEN"
```

## Step 3: Browser Testing (Playwright)
```python
await page.context.add_cookies([{
    "name": "session_token",
    "value": "YOUR_SESSION_TOKEN",
    "domain": "shastra-compass.preview.emergentagent.com",
    "path": "/",
    "httpOnly": True,
    "secure": True,
    "sameSite": "None"
}])
await page.goto("https://shastra-compass.preview.emergentagent.com/dashboard")
```

## Checklist
- User document has `user_id` field (custom UUID); `_id` excluded via `{"_id": 0}` projection.
- Session `user_id` matches user's `user_id` exactly.
- Backend uses `Depends(get_current_user)` on every protected endpoint.
- Cookie auth (session_token) is primary; Authorization header is fallback for tests.
- Landing page shown to logged-out users; dashboard/chat/library are protected.
