import { createRemoteJWKSet, jwtVerify, type JWTPayload } from 'jose';
import type { ValidatorConfig } from './config.js';

/**
 * Build a Keycloak JWT verifier. When no realm URL is configured (dev/test),
 * verification is disabled and every request is allowed — production must
 * set KEYCLOAK_URL so the internal call is authenticated end-to-end.
 *
 * @param config - Validator configuration
 * @returns A verify function returning the token payload, or null when auth is off
 */
export function makeVerifier(
  config: ValidatorConfig,
): (authHeader: string | undefined) => Promise<JWTPayload | null> {
  if (!config.keycloakRealmUrl) {
    return async () => null; // auth disabled
  }

  const jwks = createRemoteJWKSet(
    new URL(`${config.keycloakRealmUrl}/protocol/openid-connect/certs`),
  );

  return async (authHeader: string | undefined): Promise<JWTPayload | null> => {
    if (!authHeader?.startsWith('Bearer ')) {
      throw new Error('missing bearer token');
    }
    const token = authHeader.slice('Bearer '.length);
    const { payload } = await jwtVerify(token, jwks, {
      issuer: config.keycloakRealmUrl,
      audience: config.keycloakAudience,
    });
    return payload;
  };
}
