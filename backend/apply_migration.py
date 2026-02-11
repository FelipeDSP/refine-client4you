#!/usr/bin/env python3
"""
Apply Supabase migrations manually
"""
import os
from supabase import create_client

# Read environment variables
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_SERVICE_ROLE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY')

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    print("Error: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    exit(1)

# Create client with service role key
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

# Read migration file
with open('/app/frontend/supabase/migrations/20260129_create_campaigns.sql', 'r') as f:
    sql = f.read()

print("Applying migration: 20260129_create_campaigns.sql")
print("=" * 60)

try:
    # Execute SQL using Supabase RPC
    result = supabase.rpc('exec_sql', {'sql_query': sql}).execute()
    print("✅ Migration applied successfully!")
    print(result)
except Exception as e:
    # If RPC doesn't exist, we need to execute via psql or use the Supabase API directly
    print(f"Note: Direct SQL execution requires using psql or Supabase Dashboard SQL Editor")
    print(f"Error: {e}")
    print("\n" + "=" * 60)
    print("MANUAL STEPS:")
    print("1. Go to your Supabase Dashboard")
    print("2. Click on 'SQL Editor'")
    print("3. Copy the contents of: /app/frontend/supabase/migrations/20260129_create_campaigns.sql")
    print("4. Paste and run the SQL")
    print("=" * 60)
