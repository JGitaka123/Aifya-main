import Fastify, { type FastifyReply, type FastifyRequest } from 'fastify';
import {
  createRuleEngine,
  type RuleEngine,
  type RuleEngineInput,
  type TariffRecord,
} from '@claimflow/rule-engine';
import { makeVerifier } from './auth.js';
import { loadConfig } from './config.js';

/**
 * Wire-format the api-gateway sends. Lookups the engine expects as Maps or
 * function objects are supplied as plain JSON arrays here and assembled
 * server-side into the shapes the rule engine consumes.
 */
interface ValidateRequestBody {
  claim: RuleEngineInput['claim'];
  extractedFields?: Record<string, RuleEngineInput['extractedFields'] extends Map<string, infer V> ? V : never>;
  documents?: RuleEngineInput['documents'];
  facilityContext: RuleEngineInput['facilityContext'];
  /** Tariff rows keyed later by serviceCode; matches the engine's TariffRecord. */
  tariffs?: TariffRecord[];
  /** ICD codes considered valid, and the subset that are leaf codes. */
  icdValidCodes?: string[];
  icdLeafCodes?: string[];
  registryResults?: RuleEngineInput['registryResults'];
  locale?: string;
}

/**
 * Build the rule-engine tariff lookup from a flat list of tariff rows.
 * @param rows - Tariff records
 * @returns TariffLookup with a byServiceCode index
 */
function buildTariffLookup(rows: TariffRecord[]): RuleEngineInput['tariffs'] {
  const byServiceCode: Record<string, TariffRecord[]> = {};
  for (const row of rows) {
    const key = row.serviceCode.trim().toUpperCase();
    (byServiceCode[key] ??= []).push(row);
  }
  return { byServiceCode };
}

/**
 * Build the ICD lookup from valid/leaf code lists.
 * @param valid - All valid codes
 * @param leaf - Codes that are leaf (billable) nodes
 * @returns IcdCodeLookup
 */
function buildIcdLookup(valid: string[], leaf: string[]): RuleEngineInput['icdLookup'] {
  const validSet = new Set(valid.map((c) => c.trim().toUpperCase()));
  const leafSet = new Set(leaf.map((c) => c.trim().toUpperCase()));
  return {
    isValidCode: (code: string) => validSet.has(code.trim().toUpperCase()),
    isLeafCode: (code: string) => leafSet.has(code.trim().toUpperCase()),
  };
}

/**
 * Build the Fastify app.
 * @param engine - Rule engine instance (injectable for tests)
 * @returns Configured Fastify instance
 */
export function buildApp(engine: RuleEngine) {
  const config = loadConfig();
  const verify = makeVerifier(config);
  const app = Fastify({ logger: true });

  app.get('/health', async () => ({
    status: 'ok',
    rulepackVersion: engine.activeVersion,
  }));

  app.post('/validate', async (request: FastifyRequest, reply: FastifyReply) => {
    try {
      await verify(request.headers.authorization);
    } catch {
      return reply.code(401).send({ error: 'unauthorized' });
    }

    const body = request.body as ValidateRequestBody;
    if (!body?.claim || !body?.facilityContext) {
      return reply.code(422).send({ error: 'claim and facilityContext are required' });
    }

    const input: RuleEngineInput = {
      claim: body.claim,
      extractedFields: new Map(Object.entries(body.extractedFields ?? {})),
      documents: body.documents ?? [],
      facilityContext: body.facilityContext,
      tariffs: buildTariffLookup(body.tariffs ?? []),
      icdLookup:
        body.icdValidCodes || body.icdLeafCodes
          ? buildIcdLookup(body.icdValidCodes ?? [], body.icdLeafCodes ?? [])
          : undefined,
      registryResults: body.registryResults ?? { available: false },
    };

    const output = await engine.evaluate(input, body.locale ?? 'en');
    return reply.send(output);
  });

  return app;
}

/**
 * Boot the service.
 */
async function main(): Promise<void> {
  const config = loadConfig();
  const engine = createRuleEngine(config.rulepackDir, config.rulepackVersion);
  const app = buildApp(engine);
  await app.listen({ port: config.port, host: config.host });
}

// Only auto-start when run directly (not when imported by tests).
if (process.argv[1] && process.argv[1].endsWith('server.js')) {
  main().catch((err) => {
    console.error(err);
    process.exit(1);
  });
}
