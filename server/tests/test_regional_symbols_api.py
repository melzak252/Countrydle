import json
import hashlib

import httpx
import pytest

from regional_symbols import catalog
from app import app



@pytest.fixture
async def async_client():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        yield client

def _write_scope(root, scope, names):
    directory = root / scope
    (directory / 'assets').mkdir(parents=True)
    entities = [dict(id=i + 1, name=name, aliases=[alias], latitude=51.5 + i * 0.001,
                     longitude=-0.1, point_source='Test points')
                for i, (name, alias) in enumerate(names)]
    (directory / 'entities.json').write_text(json.dumps({'entities': entities}))
    records = []
    for entity in entities[::2]:
        filename = f"{entity['id']}.svg"
        asset = directory / 'assets' / filename
        asset.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
        records.append(dict(id=entity['id'], filename=filename,
                            source=dict(url='https://example.org/image', license='public domain',
                                        asset_sha1=hashlib.sha1(asset.read_bytes()).hexdigest(),
                                        notes='Community symbol, not a flag of authority.',
                                        modification='Adjusted SVG namespace.',
                                        component_credits=[dict(title='Original drawing', author='Artist',
                                            url='https://example.org/original', license='CC BY-SA 4.0',
                                            license_url='https://creativecommons.org/licenses/by-sa/4.0/')])))
    for mode in ('coats', 'flags'):
        (directory / f'{mode}_catalog.json').write_text(json.dumps({'build_complete': True, 'entities': records}))
        (directory / f'daily_{mode}_v1.json').write_text(json.dumps([record['id'] for record in records]))


@pytest.fixture
def regional_catalog(tmp_path, monkeypatch):
    _write_scope(tmp_path, 'london_boroughs', [('Bexley', 'Bex'), ('Brent', 'Brent borough'), ('Camden', 'Cam')])
    _write_scope(tmp_path, 'england_counties', [('Bedfordshire', 'Beds'), ('Berkshire', 'Berks'), ('Cheshire', 'Ches')])
    monkeypatch.setattr(catalog, 'DATA_ROOT', tmp_path)
    catalog.clear_caches()
    yield
    catalog.clear_caches()


@pytest.mark.anyio
async def test_random_game_keeps_scope_and_accepts_non_target_alias(async_client, regional_catalog):
    base = '/regional-symbols/london_boroughs/coat'
    options = await async_client.get(f'{base}/counties')
    assert {item['name'] for item in options.json()} == {'Bexley', 'Brent', 'Camden'}
    catalog_response = await async_client.get(f'{base}/catalog')
    assert [item['name'] for item in catalog_response.json()] == ['Bexley', 'Camden']
    assert catalog_response.json()[0]['source_attribution']['context'] == 'Community symbol, not a flag of authority.'
    assert catalog_response.json()[0]['source_attribution']['description'] == 'Adjusted SVG namespace.'
    assert catalog_response.json()[0]['source_attribution']['component_credits'][0]['author'] == 'Artist'
    challenge = (await async_client.get(f'{base}/challenge', params={'seed': 'proof'})).json()
    token = challenge['token']
    wrong = await async_client.post(f'{base}/guess', json={'token': token, 'guess': 'Brent borough'})
    assert wrong.status_code == 200
    assert wrong.json()['guess'] == 'Brent'
    assert wrong.json()['distance_km'] > 0
    assert wrong.json()['registration_plates'] is None
    cross_scope = await async_client.post('/regional-symbols/england_counties/coat/guess',
                                          json={'token': wrong.json()['token'], 'guess': 'Beds'})
    assert cross_scope.status_code == 403
    result = await async_client.post(f'{base}/guess', json={'token': wrong.json()['token'], 'guess': 'Bex'})
    assert result.json()['won'] is True
    assert result.json()['target_powiat']['name'] == 'Bexley'
    assert result.json()['source_attribution']['context'] == 'Community symbol, not a flag of authority.'
    assert result.json()['source_attribution']['component_credits'][0]['title'] == 'Original drawing'


@pytest.mark.anyio
async def test_token_restore_scope_and_asset_version_are_isolated(async_client, regional_catalog):
    from powiatdle.heraldry import encrypt_session_token

    base = '/regional-symbols/london_boroughs/coat'
    challenge = (await async_client.get(f'{base}/challenge', params={'seed': 'proof'})).json()
    wrong = (await async_client.post(f'{base}/guess', json={
        'token': challenge['token'], 'guess': 'Brent'
    })).json()
    restored = await async_client.get(f'{base}/challenge', params={'seed': 'proof', 'token': wrong['token']})
    assert restored.status_code == 200
    assert [guess['guess'] for guess in restored.json()['guesses']] == ['Brent']
    assert restored.json()['guesses'][0]['distance_km'] == wrong['distance_km']
    assert (await async_client.get(f'{base}/assets/1?v=stale')).status_code == 404
    asset_url = challenge['coat_asset_url']
    assert '/session-asset?token=' in asset_url
    assert 'Bexley' not in asset_url and '/assets/1' not in asset_url
    assert challenge['target_powiat'] is None and challenge['source_attribution'] is None
    asset = await async_client.get(asset_url)
    assert asset.status_code == 200
    assert asset.headers['content-encoding'] == 'gzip'
    assert asset.content.startswith(b'<svg')
    assert asset.headers['cache-control'] == 'private, no-store'
    assert (await async_client.get('/regional-symbols/england_counties/coat/session-asset',
                                   params={'token': challenge['token']})).status_code == 403
    assert (await async_client.post('/regional-symbols/london_boroughs/flag/guess',
                                    json={'token': wrong['token'], 'guess': 'Bexley'})).status_code == 403
    assert (await async_client.post('/powiatdle/heraldry/guess',
                                    json={'token': wrong['token'], 'guess': 'Bexley'})).status_code == 403
    legacy = encrypt_session_token({'seed': 'legacy', 'is_daily': False, 'date': '2020-01-01',
                                    'target_id': 1, 'guesses': []})
    assert (await async_client.post(f'{base}/guess', json={'token': legacy, 'guess': 'Bexley'})).status_code == 403


@pytest.mark.anyio
async def test_single_target_pool_is_not_published_as_a_game(async_client, regional_catalog, tmp_path):
    path = tmp_path / 'england_counties' / 'flags_catalog.json'
    data = json.loads(path.read_text())
    data['entities'] = data['entities'][:1]
    path.write_text(json.dumps(data))
    catalog.clear_caches()
    base = '/regional-symbols/england_counties/flag'
    assert (await async_client.get(f'{base}/catalog')).status_code == 503
    assert (await async_client.get(f'{base}/challenge', params={'seed': 'proof'})).status_code == 503
    assert (await async_client.post(f'{base}/quiz/runs', json={})).status_code == 503


@pytest.mark.anyio
async def test_incomplete_component_credits_cannot_publish_catalog(async_client, regional_catalog, tmp_path):
    path = tmp_path / 'london_boroughs' / 'coats_catalog.json'
    data = json.loads(path.read_text())
    data['entities'][0]['source']['component_credits'][0]['license_url'] = 'javascript:alert(1)'
    path.write_text(json.dumps(data))
    catalog.clear_caches()
    assert (await async_client.get('/regional-symbols/london_boroughs/coat/catalog')).status_code == 503
