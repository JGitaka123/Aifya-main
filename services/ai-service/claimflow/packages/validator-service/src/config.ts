/**
 * Validator-service configuration from the environment.
 */
export interface ValidatorConfig {
  port: number;
  host: string;
  rulepackDir: string;
  rulepackVersion: string;
  /** Keycloak realm URL, e.g. http://keycloak:8080/realms/aifya. Empty disables JWT auth (dev/test). */
  keycloakRealmUrl: string;
  /** Expected token audience. */
  keycloakAudience: string;
}

/**
 * Read validator config from process.env.
 * @returns Resolved configuration
 */
export function loadConfig(): ValidatorConfig {
  const keycloakUrl = (process.env.KEYCLOAK_URL ?? '').replace(/\/$/, '');
  const realm = process.env.KEYCLOAK_REALM ?? 'aifya';
  return {
    port: Number(process.env.PORT ?? 8030),
    host: process.env.HOST ?? '0.0.0.0',
    rulepackDir: process.env.RULEPACK_DIR ?? '/app/rulepacks',
    rulepackVersion: process.env.RULEPACK_VERSION ?? '1.0.0',
    keycloakRealmUrl: keycloakUrl ? `${keycloakUrl}/realms/${realm}` : '',
    keycloakAudience: process.env.KEYCLOAK_AUDIENCE ?? 'account',
  };
}
