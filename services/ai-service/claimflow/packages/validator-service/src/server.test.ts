import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRuleEngine } from '@claimflow/rule-engine';
import { describe, expect, it } from 'vitest';
import { buildApp } from './server.js';

const RULEPACK_DIR = path.join(
  path.dirname(fileURLToPath(import.meta.url)),
  '../../../rulepacks',
);

function makeApp() {
  const engine = createRuleEngine(RULEPACK_DIR, '1.0.0');
  return buildApp(engine);
}

describe('validator-service', () => {
  it('reports the loaded rulepack version on /health', async () => {
    const app = makeApp();
    const res = await app.inject({ method: 'GET', url: '/health' });
    expect(res.statusCode).toBe(200);
    expect(res.json().status).toBe('ok');
    expect(res.json().rulepackVersion).toBe('1.0.0');
    await app.close();
  });

  it('422s when the claim is missing', async () => {
    const app = makeApp();
    const res = await app.inject({
      method: 'POST',
      url: '/validate',
      payload: { facilityContext: { facilityId: 'f1' } },
    });
    expect(res.statusCode).toBe(422);
    await app.close();
  });

  it('evaluates a claim against all 121 rules and returns a decision', async () => {
    const app = makeApp();
    const res = await app.inject({
      method: 'POST',
      url: '/validate',
      payload: {
        claim: {
          id: 'clm-1',
          claimType: 'OUTPATIENT',
          tenantId: 't1',
          facilityId: 'f1',
          patientShaId: 'CR000000001-1',
          lines: [],
        },
        facilityContext: { facilityId: 'f1', facilityTier: 'level_4' },
        registryResults: { available: false },
      },
    });
    expect(res.statusCode).toBe(200);
    const body = res.json();
    expect(['PASSED', 'FAILED', 'WARNING']).toContain(body.decision);
    expect(body.totalRules).toBe(121);
    expect(Array.isArray(body.results)).toBe(true);
    expect(typeof body.fixReportMarkdown).toBe('string');
    await app.close();
  });
});
