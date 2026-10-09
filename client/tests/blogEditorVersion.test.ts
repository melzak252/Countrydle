import { afterEach, expect, test } from 'bun:test';
import { AxiosError, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios';
import api, { blogService } from '../src/services/api';

const originalAdapter = api.defaults.adapter;
afterEach(() => { api.defaults.adapter = originalAdapter; });

function response(config: InternalAxiosRequestConfig, data: unknown, status = 200): AxiosResponse {
  return { config, data, status, statusText: status === 409 ? 'Conflict' : 'OK', headers: {} };
}

const initialVersion = '2026-10-01T12:34:56.123456+00:00';
const correctedVersion = '2026-10-01T12:34:56.123457+00:00';

test('editing sends the exact loaded timestamp without losing sub-millisecond precision', async () => {
  let requestBody: unknown;
  let requestUrl: string | undefined;
  api.defaults.adapter = async (config) => {
    requestBody = JSON.parse(config.data);
    requestUrl = config.url;
    return response(config, { id: 7, title: 'Corrected title', updated_at: correctedVersion });
  };

  const edits = Object.freeze({ title: 'Corrected title', editorial_note: null });
  await blogService.updatePost(7, edits, initialVersion);

  expect(requestUrl).toBe('/blog/admin/posts/7');
  expect(requestBody).toEqual({ ...edits, expected_updated_at: initialVersion });
});

test('two loaded versions do not retry or overwrite the first correction after a stale PATCH returns 409', async () => {
  // Disposable HTTP-boundary fixture: only the matching raw version permits a save.
  let saved = { id: 7, title: 'Original title', created_at: null, updated_at: initialVersion };
  const requests: { title: string; expected_updated_at: string }[] = [];
  api.defaults.adapter = async (config) => {
    if (config.method === 'get') return response(config, { ...saved });
    const body = JSON.parse(config.data) as { title: string; expected_updated_at: string };
    requests.push(body);
    if (body.expected_updated_at !== saved.updated_at) {
      throw new AxiosError('The post changed after loading.', 'ERR_BAD_REQUEST', config, undefined,
        response(config, { detail: 'Reload the latest saved version.' }, 409));
    }
    saved = {
      ...saved, title: body.title,
      updated_at: saved.updated_at === initialVersion ? correctedVersion : '2026-10-01T12:34:56.123458+00:00',
    };
    return response(config, { ...saved });
  };

  const firstEditor = await blogService.getAdminPost(7);
  const secondEditor = await blogService.getAdminPost(7);
  await blogService.updatePost(7, { title: 'First editor correction' }, firstEditor.updated_at);
  const secondEdits = Object.freeze({ title: 'Second editor unsaved draft' });

  try {
    await blogService.updatePost(7, secondEdits, secondEditor.updated_at);
    throw new Error('A stale edit unexpectedly succeeded.');
  } catch (failure) {
    expect(failure).toBeInstanceOf(AxiosError);
    expect((failure as AxiosError).response?.status).toBe(409);
  }

  expect(requests).toHaveLength(2);
  expect(requests[1]).toEqual({ ...secondEdits, expected_updated_at: initialVersion });
  expect(saved.title).toBe('First editor correction');
  expect(saved.updated_at).toBe(correctedVersion);

  const reloaded = await blogService.getAdminPost(7);
  await blogService.updatePost(7, { title: 'Deliberate edit after reload' }, reloaded.updated_at);
  expect(requests).toHaveLength(3);
  expect(requests[2].expected_updated_at).toBe(correctedVersion);
  expect(saved.title).toBe('Deliberate edit after reload');
  expect(saved.updated_at).toBe('2026-10-01T12:34:56.123458+00:00');
});

test('review retains the exact version and propagates 409 without an automatic retry', async () => {
  const requests: unknown[] = [];
  api.defaults.adapter = async (config) => {
    requests.push(JSON.parse(config.data));
    throw new AxiosError('The post changed after loading.', 'ERR_BAD_REQUEST', config, undefined,
      response(config, { detail: 'No review was recorded.' }, 409));
  };

  try {
    await blogService.reviewPost(7, initialVersion);
    throw new Error('A stale review unexpectedly succeeded.');
  } catch (failure) {
    expect(failure).toBeInstanceOf(AxiosError);
    expect((failure as AxiosError).response?.status).toBe(409);
  }

  expect(requests).toEqual([{ expected_updated_at: initialVersion }]);
});
