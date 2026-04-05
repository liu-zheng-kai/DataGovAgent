from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)

print('GET /auth/me')
print(client.get('/auth/me').json())

print('GET /auth/login (without oauth settings)')
resp = client.get('/auth/login', follow_redirects=False)
if 'application/json' in resp.headers.get('content-type', ''):
    print(resp.status_code, resp.json())
else:
    print(resp.status_code, resp.headers.get('location'))

print('GET /auth/done')
done = client.get('/auth/done')
print(done.status_code, 'OAuth authentication completed.' in done.text)

print('POST /auth/refresh (without session)')
refresh = client.post('/auth/refresh')
print(refresh.status_code, refresh.json())

print('GET /auth/refresh (without session)')
refresh_get = client.get('/auth/refresh')
print(refresh_get.status_code, refresh_get.json())

print('POST /chat')
chat = client.post('/chat', json={'question': 'Which teams are impacted by silver.customer_contact failure?'})
print(chat.status_code)
if chat.headers.get('content-type', '').startswith('application/json'):
    print(chat.json())
else:
    print(chat.text[:500])
