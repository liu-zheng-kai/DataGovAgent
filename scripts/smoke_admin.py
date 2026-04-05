from fastapi.testclient import TestClient

from app.main import app


def main():
    with TestClient(app) as client:
        health = client.get('/health')
        assert health.status_code == 200, health.text

        dashboard = client.get('/api/admin/dashboard')
        assert dashboard.status_code == 200, dashboard.text

        tools = client.get('/api/admin/tools')
        assert tools.status_code == 200, tools.text

        assets = client.get('/api/admin/assets?limit=5')
        assert assets.status_code == 200, assets.text
        asset_rows = assets.json()
        if asset_rows:
            qn = asset_rows[0]['qualified_name']
            lineage = client.get(
                '/api/admin/lineage',
                params={'asset_name': qn, 'direction': 'downstream'},
            )
            assert lineage.status_code == 200, lineage.text

        admin_page = client.get('/admin')
        assert admin_page.status_code == 200, admin_page.text

        print('smoke_admin ok')


if __name__ == '__main__':
    main()
