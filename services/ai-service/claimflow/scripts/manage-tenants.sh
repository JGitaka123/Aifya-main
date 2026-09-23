#!/bin/bash
set -e

# ClaimFlow Tenant & Facility Management Utility
# Usage: ./scripts/manage-tenants.sh [command] [args]

DB_CONTAINER="claimflow-postgres-1"
DB_USER="claimflow"
DB_NAME="claimflow"
export PGPASSWORD="${PGPASSWORD:?PGPASSWORD environment variable required}"

function query() {
  docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -t -c "$1"
}

function list_tenants() {
  echo "Existing Hospitals (Tenants):"
  docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c "SELECT id, name, slug, is_active FROM tenants ORDER BY created_at DESC;"
}

function add_tenant() {
  local name="$1"
  local slug="$2"
  
  if [ -z "$name" ] || [ -z "$slug" ]; then
    echo "Usage: add-hospital \"Hospital Name\" hospital-slug"
    exit 1
  fi

  echo "Adding hospital: $name ($slug)..."
  docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c \
    "INSERT INTO tenants (name, slug) VALUES ('$name', '$slug') ON CONFLICT (slug) DO NOTHING RETURNING id, name, slug;"
}

function add_facility() {
  local tenant_slug="$1"
  local facility_name="$2"
  local facility_code="$3"
  
  if [ -z "$tenant_slug" ] || [ -z "$facility_name" ]; then
    echo "Usage: add-facility hospital-slug \"Facility Name\" [facility-code]"
    exit 1
  fi

  local tenant_id=$(query "SELECT id FROM tenants WHERE slug = '$tenant_slug';" | tr -d '[:space:]')
  
  if [ -z "$tenant_id" ]; then
    echo "Error: Hospital with slug '$tenant_slug' not found."
    exit 1
  fi

  local code=${facility_code:-"FID-$(date +%s)"}

  echo "Adding facility '$facility_name' to hospital '$tenant_slug'..."
  docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c \
    "INSERT INTO facilities (tenant_id, name, sha_facility_code, sha_provider_id, tier_level, county) 
     VALUES ('$tenant_id', '$facility_name', '$code', 'PROV-$(date +%s)', 'LEVEL_4', 'Nairobi') 
     RETURNING id, name;"
}

function add_user() {
  local tenant_slug="$1"
  local email="$2"
  local password="$3"
  local display_name="$4"
  
  if [ -z "$tenant_slug" ] || [ -z "$email" ] || [ -z "$password" ]; then
    echo "Usage: add-user hospital-slug email password \"Display Name\""
    exit 1
  fi

  local tenant_id=$(query "SELECT id FROM tenants WHERE slug = '$tenant_slug';" | tr -d '[:space:]')
  
  if [ -z "$tenant_id" ]; then
    echo "Error: Hospital with slug '$tenant_slug' not found."
    exit 1
  fi

  # Note: This is a simplified hash for dev. For real use, use bcrypt.
  # But since this is a developer tool, we can use the DB's crypt if available.
  echo "Creating admin user $email for hospital $tenant_slug..."
  docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c \
    "INSERT INTO users (tenant_id, email, password_hash, display_name, role, is_active, must_change_password)
     VALUES (
       '$tenant_id', 
       '$email', 
       crypt('$password', gen_salt('bf', 12)), 
       '${display_name:-Admin}', 
       'admin', 
       true, 
       false
     ) RETURNING id, email, role;"
}

case "$1" in
  list)
    list_tenants
    ;;
  add-hospital)
    add_tenant "$2" "$3"
    ;;
  add-facility)
    add_facility "$2" "$3" "$4"
    ;;
  add-user)
    add_user "$2" "$3" "$4" "$5"
    ;;
  *)
    echo "ClaimFlow Management Tool"
    echo "Commands:"
    echo "  list                                 - List all hospitals"
    echo "  add-hospital \"Name\" slug           - Add a new hospital"
    echo "  add-facility slug \"Name\" [code]    - Add a facility to a hospital"
    echo "  add-user slug email pass \"Name\"    - Add an admin user to a hospital"
    ;;
esac
