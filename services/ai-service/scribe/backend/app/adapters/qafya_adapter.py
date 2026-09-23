import time
import json
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
import asyncpg
from structlog import get_logger
from datetime import datetime

from app.config import get_settings, QAfyaConfig

logger = get_logger(__name__)
settings = get_settings()


class CircuitBreakerOpenException(Exception):
    pass


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failures = 0
        self.last_failure_time = 0
        self.is_open = False

    def record_failure(self):
        self.failures += 1
        self.last_failure_time = time.time()
        if self.failures >= self.failure_threshold:
            self.is_open = True
            logger.error("circuit_breaker_opened", target="QAfya")

    def record_success(self):
        self.failures = 0
        self.is_open = False

    def check_state(self):
        if self.is_open:
            if time.time() - self.last_failure_time > self.recovery_timeout:
                return  # Half-open state
            raise CircuitBreakerOpenException("Circuit breaker to Q-Afya EMR is open")


class EMRAdapter(ABC):
    @abstractmethod
    async def get_patient(self, identifier: str) -> Optional[Dict[str, Any]]: pass

    @abstractmethod
    async def get_patient_encounters(self, patient_id: str, limit: int = 20) -> List[Dict[str, Any]]: pass

    @abstractmethod
    async def get_encounter_labs(self, encounter_id: str) -> List[Dict[str, Any]]: pass

    @abstractmethod
    async def get_encounter_medications(self, encounter_id: str) -> List[Dict[str, Any]]: pass

    @abstractmethod
    async def write_clinical_note(self, encounter_id: str, soap_json: Dict[str, Any]) -> bool: pass

    @abstractmethod
    async def write_discharge_summary(self, admission_id: str, summary: Dict[str, Any]) -> bool: pass

    @abstractmethod
    async def check_sha_status(self, sha_member_no: str) -> Optional[Dict[str, Any]]: pass


class QAfyaAdapter(EMRAdapter):
    def __init__(self, config: QAfyaConfig):
        self.config = config
        self.pool: Optional[asyncpg.Pool] = None
        self.breaker = CircuitBreaker(
            failure_threshold=config.circuit_breaker_failure_threshold,
            recovery_timeout=config.circuit_breaker_recovery_timeout,
        )
        self.last_success_timestamp: Optional[datetime] = None
        self.current_latency_ms: Optional[float] = None

    async def connect(self):
        if not self.pool:
            try:
                logger.info("qafya_connecting", host=self.config.db_host, port=self.config.db_port, user=self.config.db_user, database=self.config.db_name)
                self.pool = await asyncpg.create_pool(
                    host=self.config.db_host,
                    port=self.config.db_port,
                    user=self.config.db_user,
                    password=self.config.db_password,
                    database=self.config.db_name,
                    min_size=2,
                    max_size=10,
                    command_timeout=30.0,
                )
                logger.info("qafya_pool_created", db_host=self.config.db_host)
            except Exception as e:
                logger.error("qafya_pool_creation_failed", error=str(e))
                self.breaker.record_failure()

    async def close(self):
        if self.pool:
            await self.pool.close()
            self.pool = None

    async def _execute_read(self, query: str, *args) -> List[asyncpg.Record]:
        self.breaker.check_state()
        if not self.pool:
            await self.connect()
        if not self.pool:
            return []

        start_time = time.time()
        try:
            async with self.pool.acquire() as connection:
                rows = await connection.fetch(query, *args)
            self.breaker.record_success()
            self.last_success_timestamp = datetime.utcnow()
            self.current_latency_ms = (time.time() - start_time) * 1000
            return rows
        except Exception as e:
            logger.error("qafya_read_failed", query=query[:100], error=str(e))
            self.breaker.record_failure()
            return []

    async def _execute_write(self, query: str, *args) -> bool:
        self.breaker.check_state()
        if not self.pool:
            await self.connect()
        if not self.pool:
            return False

        start_time = time.time()
        try:
            async with self.pool.acquire() as connection:
                async with connection.transaction():
                    await connection.execute(query, *args)
            self.breaker.record_success()
            self.last_success_timestamp = datetime.utcnow()
            self.current_latency_ms = (time.time() - start_time) * 1000
            return True
        except Exception as e:
            logger.error("qafya_write_failed", query=query[:100], error=str(e))
            self.breaker.record_failure()
            return False

    # =====================
    # Patient Operations
    # =====================
    async def get_patient(self, identifier: str) -> Optional[Dict[str, Any]]:
        query = """
            SELECT * FROM patient_registration
            WHERE national_id = $1 OR insurance_no = $1
            LIMIT 1
        """
        rows = await self._execute_read(query, identifier)
        return dict(rows[0]) if rows else None

    async def get_patient_encounters(self, patient_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        query = """
            SELECT * FROM patient_encounters
            WHERE patient_id = $1
            ORDER BY encounter_date DESC
            LIMIT $2
        """
        rows = await self._execute_read(query, patient_id, limit)
        return [dict(row) for row in rows]

    async def get_encounter_labs(self, encounter_id: str) -> List[Dict[str, Any]]:
        query = "SELECT test_name as name, result_value as result, loinc_code as loinc FROM lab_results WHERE encounter_id = $1"
        try:
            rows = await self._execute_read(query, encounter_id)
            return [dict(row) for row in rows]
        except Exception as e:
            logger.warning("get_labs_failed", error=str(e))
            return []

    async def get_encounter_medications(self, encounter_id: str) -> List[Dict[str, Any]]:
        query = "SELECT drug_name as name, dose, route, frequency, duration FROM prescriptions WHERE encounter_id = $1"
        try:
            rows = await self._execute_read(query, encounter_id)
            return [dict(row) for row in rows]
        except Exception as e:
            logger.warning("get_medications_failed", error=str(e))
            return []

    # =====================
    # Clinical Note Operations
    # =====================
    async def write_clinical_note(self, encounter_id: str, soap_json: Dict[str, Any]) -> bool:
        query = """
            UPDATE patient_encounters
            SET clinical_notes = $2,
                diagnosis_code = $3,
                last_modified_by = 'AIFYA_SYSTEM',
                last_modified_at = NOW()
            WHERE encounter_id = $1
        """
        soap_str = json.dumps(soap_json)
        primary_dx = soap_json.get("assessment", {}).get("primary_diagnosis_icd11", None)
        return await self._execute_write(query, encounter_id, soap_str, primary_dx)

    async def append_addendum(self, encounter_id: str, addendum_text: str, user_id: str) -> bool:
        query = """
            UPDATE patient_encounters
            SET clinical_notes = COALESCE(clinical_notes, '') || E'\n\n--- ADDENDUM (' || $3 || ') ---\n' || $2,
                last_modified_by = $3,
                last_modified_at = NOW()
            WHERE encounter_id = $1
        """
        return await self._execute_write(query, encounter_id, addendum_text, user_id or "AIFYA_SYSTEM")

    # =====================
    # Discharge Operations
    # =====================
    async def write_discharge_summary(self, admission_id: str, summary: Dict[str, Any]) -> bool:
        query = """
            INSERT INTO discharge_summaries (admission_id, summary_json, last_modified_by, last_modified_at)
            VALUES ($1, $2, 'AIFYA_SYSTEM', NOW())
            ON CONFLICT (admission_id)
            DO UPDATE SET
                summary_json = EXCLUDED.summary_json,
                last_modified_by = EXCLUDED.last_modified_by,
                last_modified_at = NOW()
        """
        return await self._execute_write(query, admission_id, json.dumps(summary, default=str))

    async def save_discharge_summary(self, summary, admission_id: str, patient_id: str, clinician_id: str) -> Optional[str]:
        query = """
            INSERT INTO discharge_summaries (
                admission_id, patient_id, generating_clinician_id,
                admission_date, discharge_date, length_of_stay,
                admission_diagnosis, final_diagnosis,
                history_of_illness, hospital_course, clinical_narrative,
                procedures, key_investigations,
                discharge_meds, status
            ) VALUES ($1, $2, $3::uuid, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, 'draft')
            ON CONFLICT (admission_id)
            DO UPDATE SET
                history_of_illness = EXCLUDED.history_of_illness,
                hospital_course = EXCLUDED.hospital_course,
                clinical_narrative = EXCLUDED.clinical_narrative,
                final_diagnosis = EXCLUDED.final_diagnosis,
                procedures = EXCLUDED.procedures,
                discharge_meds = EXCLUDED.discharge_meds,
                updated_at = NOW()
            RETURNING id::text
        """
        if not self.pool:
            await self.connect()
        try:
            async with self.pool.acquire() as connection:
                val = await connection.fetchval(
                    query,
                    admission_id, patient_id, clinician_id,
                    summary.admission_date, summary.discharge_date, summary.length_of_stay_days,
                    summary.admission_diagnosis, summary.final_diagnosis,
                    summary.history_of_present_illness, summary.hospital_course,
                    summary.clinical_narrative,
                    json.dumps([p.model_dump() for p in summary.procedures], default=str),
                    json.dumps(summary.key_investigations, default=str),
                    json.dumps([m.model_dump() for m in summary.discharge_medications], default=str),
                )
                return str(val) if val else None
        except Exception as e:
            logger.error("save_discharge_failed", error=str(e))
            return None

    async def get_discharge_by_id(self, discharge_id: str) -> Optional[Dict[str, Any]]:
        query = "SELECT * FROM discharge_summaries WHERE id::text = $1 OR admission_id = $1 LIMIT 1"
        rows = await self._execute_read(query, discharge_id)
        if not rows:
            return None
        row = dict(rows[0])
        # Parse JSONB fields
        for field in ("procedures", "key_investigations", "discharge_meds"):
            if isinstance(row.get(field), str):
                try:
                    row[field] = json.loads(row[field])
                except (json.JSONDecodeError, TypeError):
                    pass
        return row

    async def update_discharge_status(self, discharge_id: str, new_status: str, user_id: str) -> bool:
        update_field = ""
        if new_status == "reviewed":
            update_field = ", reviewed_by = $3::uuid"
        elif new_status == "approved":
            update_field = ", approved_by = $3::uuid"

        query = f"""
            UPDATE discharge_summaries
            SET status = $2, updated_at = NOW(){update_field}
            WHERE id::text = $1 OR admission_id = $1
        """
        if update_field:
            return await self._execute_write(query, discharge_id, new_status, user_id)
        return await self._execute_write(query, discharge_id, new_status)

    # =====================
    # Claims Operations
    # =====================
    async def get_claims(self, status_filter: str = None, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        if status_filter:
            query = """
                SELECT c.*, ae.qafya_patient_id
                FROM claims c
                LEFT JOIN aifya_encounters ae ON c.encounter_id = ae.id
                WHERE c.scrub_status = $1
                ORDER BY c.created_at DESC
                LIMIT $2 OFFSET $3
            """
            rows = await self._execute_read(query, status_filter, limit, offset)
        else:
            query = """
                SELECT c.*, ae.qafya_patient_id
                FROM claims c
                LEFT JOIN aifya_encounters ae ON c.encounter_id = ae.id
                ORDER BY c.created_at DESC
                LIMIT $1 OFFSET $2
            """
            rows = await self._execute_read(query, limit, offset)
        return [dict(row) for row in rows]

    async def get_claims_count(self, status_filter: str = None) -> int:
        if status_filter:
            query = "SELECT COUNT(*) as count FROM claims WHERE scrub_status = $1"
            rows = await self._execute_read(query, status_filter)
        else:
            query = "SELECT COUNT(*) as count FROM claims"
            rows = await self._execute_read(query)
        return rows[0]["count"] if rows else 0

    async def get_claim_by_id(self, claim_id: str) -> Optional[Dict[str, Any]]:
        query = "SELECT * FROM claims WHERE id::text = $1 LIMIT 1"
        rows = await self._execute_read(query, claim_id)
        if not rows:
            return None
        row = dict(rows[0])
        if isinstance(row.get("scrub_violations"), str):
            try:
                row["scrub_violations"] = json.loads(row["scrub_violations"])
            except (json.JSONDecodeError, TypeError):
                pass
        return row

    async def override_claim(self, claim_id: str, user_id: str, reason: str) -> bool:
        query = """
            UPDATE claims
            SET scrub_status = 'overridden',
                override_by = $2::uuid,
                override_reason = $3,
                override_at = NOW(),
                updated_at = NOW()
            WHERE id::text = $1
        """
        return await self._execute_write(query, claim_id, user_id, reason)

    async def submit_claim(self, claim_id: str, sha_ref: str) -> bool:
        query = """
            UPDATE claims
            SET claim_status = 'submitted',
                sha_submission_ref = $2,
                updated_at = NOW()
            WHERE id::text = $1
        """
        return await self._execute_write(query, claim_id, sha_ref)

    async def get_claims_stats(self) -> Dict[str, Any]:
        query = """
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE scrub_status = 'blocked') as blocked,
                COUNT(*) FILTER (WHERE scrub_status = 'passed') as passed,
                COUNT(*) FILTER (WHERE scrub_status = 'warnings_only') as warnings_only,
                COUNT(*) FILTER (WHERE scrub_status = 'overridden') as overridden,
                COUNT(*) FILTER (WHERE claim_status = 'submitted') as submitted,
                COALESCE(SUM(amount_billed), 0) as total_billed,
                COALESCE(SUM(amount_approved), 0) as total_approved,
                COALESCE(SUM(amount_paid), 0) as total_paid,
                COUNT(*) FILTER (WHERE created_at::date = CURRENT_DATE) as today_count
            FROM claims
        """
        rows = await self._execute_read(query)
        if rows:
            row = dict(rows[0])
            return {
                "total": row.get("total", 0),
                "blocked": row.get("blocked", 0),
                "passed": row.get("passed", 0),
                "warnings_only": row.get("warnings_only", 0),
                "overridden": row.get("overridden", 0),
                "submitted": row.get("submitted", 0),
                "total_billed": float(row.get("total_billed", 0)),
                "total_approved": float(row.get("total_approved", 0)),
                "total_paid": float(row.get("total_paid", 0)),
                "today_count": row.get("today_count", 0),
            }
        return {"total": 0, "blocked": 0, "passed": 0, "warnings_only": 0, "overridden": 0, "submitted": 0, "total_billed": 0, "total_approved": 0, "total_paid": 0, "today_count": 0}

    # =====================
    # User Operations
    # =====================
    async def create_user(self, user_id: str, email: str, password_hash: str, full_name: str, role: str, license_no: str = None) -> bool:
        query = f"""
            INSERT INTO users (id, email, password_hash, full_name, role, license_no)
            VALUES ($1::uuid, pgp_sym_encrypt($2, $6), $3, $4, $5, $7)
        """
        return await self._execute_write(
            query, user_id, email, password_hash, full_name, role,
            settings.encryption_key, license_no,
        )

    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        query = f"""
            SELECT id, pgp_sym_decrypt(email, $2) as email, password_hash, full_name, role,
                   license_no, is_active, facility_id
            FROM users
            WHERE pgp_sym_decrypt(email, $2) = $1
            LIMIT 1
        """
        rows = await self._execute_read(query, email.lower(), settings.encryption_key)
        return dict(rows[0]) if rows else None

    async def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        query = f"""
            SELECT id, pgp_sym_decrypt(email, $2) as email, password_hash, full_name, role,
                   license_no, is_active, facility_id, created_at
            FROM users
            WHERE id::text = $1
            LIMIT 1
        """
        rows = await self._execute_read(query, user_id, settings.encryption_key)
        return dict(rows[0]) if rows else None

    async def get_all_users(self, limit: int = 50) -> List[Dict[str, Any]]:
        query = f"""
            SELECT id, pgp_sym_decrypt(email, $1) as email, full_name, role,
                   license_no, is_active, created_at
            FROM users
            ORDER BY created_at DESC
            LIMIT $2
        """
        rows = await self._execute_read(query, settings.encryption_key, limit)
        return [dict(row) for row in rows]

    async def update_user_profile(self, user_id: str, updates: Dict[str, Any]) -> bool:
        """Update user profile fields dynamically."""
        set_clauses = []
        params = [user_id]
        param_idx = 2

        for field, value in updates.items():
            if field in ("full_name", "license_no"):
                set_clauses.append(f"{field} = ${param_idx}")
                params.append(value)
                param_idx += 1
            elif field == "is_active":
                set_clauses.append(f"is_active = ${param_idx}")
                params.append(value)
                param_idx += 1

        if not set_clauses:
            return False

        set_clauses.append("updated_at = NOW()")
        query = f"UPDATE users SET {', '.join(set_clauses)} WHERE id::text = $1"
        return await self._execute_write(query, *params)

    async def update_user_password(self, user_id: str, password_hash: str) -> bool:
        """Update user's password hash."""
        query = "UPDATE users SET password_hash = $2, updated_at = NOW() WHERE id::text = $1"
        return await self._execute_write(query, user_id, password_hash)

    # =====================
    # SHA Status
    # =====================
    async def check_sha_status(self, sha_member_no: str) -> Optional[Dict[str, Any]]:
        query = """
            SELECT insurance_no, insurance_status, insurance_package, max_benefit_cap
            FROM patient_registration
            WHERE insurance_no = $1
            LIMIT 1
        """
        rows = await self._execute_read(query, sha_member_no)
        return dict(rows[0]) if rows else None

    # =====================
    # Audit Log
    # =====================
    async def log_audit(self, user_id: Optional[str], action: str, entity_type: str, entity_id: str, details: Dict[str, Any] = None, ip_address: str = None) -> bool:
        query = """
            INSERT INTO audit_log (user_id, action, entity_type, entity_id, details, ip_address)
            VALUES ($1::uuid, $2, $3, $4, $5, $6::inet)
        """
        try:
            return await self._execute_write(
                query,
                user_id, action, entity_type, entity_id,
                json.dumps(details or {}, default=str),
                ip_address,
            )
        except Exception as e:
            # Audit logging should never crash the main operation
            logger.error("audit_log_write_failed", action=action, error=str(e))
            return False

    async def get_audit_logs(self, limit: int = 100, offset: int = 0, action_filter: str = None) -> List[Dict[str, Any]]:
        if action_filter:
            query = """
                SELECT al.*, u.full_name as user_name
                FROM audit_log al
                LEFT JOIN users u ON al.user_id = u.id
                WHERE al.action = $1
                ORDER BY al.created_at DESC
                LIMIT $2 OFFSET $3
            """
            rows = await self._execute_read(query, action_filter, limit, offset)
        else:
            query = """
                SELECT al.*, u.full_name as user_name
                FROM audit_log al
                LEFT JOIN users u ON al.user_id = u.id
                ORDER BY al.created_at DESC
                LIMIT $1 OFFSET $2
            """
            rows = await self._execute_read(query, limit, offset)
        return [dict(row) for row in rows]

    # =====================
    # Schema Validation
    # =====================
    async def validate_schema_on_startup(self):
        tables_to_check = [
            "patient_registration", "patient_encounters",
            "lab_results", "prescriptions", "discharge_summaries",
            "users", "claims", "audit_log", "aifya_encounters",
        ]
        query = """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
        """
        rows = await self._execute_read(query)
        existing_tables = [row["table_name"] for row in rows]

        for table in tables_to_check:
            if table not in existing_tables:
                logger.error("CRITICAL_ALERT_QAFYA_SCHEMA_DRIFT", missing_table=table)
