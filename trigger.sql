CREATE OR REPLACE FUNCTION sync_employee_to_staff()
RETURNS TRIGGER AS $func$
DECLARE
    v_staff_id uuid;
    v_first_name varchar;
    v_last_name varchar;
BEGIN
    v_first_name := split_part(NEW.full_name, ' ', 1);
    v_last_name := substr(NEW.full_name, length(v_first_name) + 2);
    INSERT INTO staff (
        id, facility_id, keycloak_user_id, employee_number,
        first_name, last_name, role, email, phone, is_active,
        created_at, updated_at, is_deleted
    ) VALUES (
        gen_random_uuid(), NEW.facility_id, gen_random_uuid(), NEW.staff_id,
        v_first_name, v_last_name, 'staff', NEW.email, NEW.phone, NEW.is_active,
        now(), now(), false
    ) ON CONFLICT DO NOTHING RETURNING id INTO v_staff_id;
    IF v_staff_id IS NOT NULL THEN
        INSERT INTO staff_profiles (
            id, facility_id, staff_id, employment_type,
            employment_date, national_id, kra_pin, nssf_number,
            created_at, updated_at, is_deleted
        ) VALUES (
            gen_random_uuid(), NEW.facility_id, v_staff_id, NEW.employment_type,
            NEW.hire_date, NEW.id_number, NEW.kra_pin, NEW.nssf_number,
            now(), now(), false
        );
    END IF;
    RETURN NEW;
END;
$func$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_sync_employee_to_staff
AFTER INSERT ON employees
FOR EACH ROW EXECUTE FUNCTION sync_employee_to_staff();
