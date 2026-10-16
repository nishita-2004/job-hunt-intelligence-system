
import os
import psycopg

password = os.environ.get("PGPASSWORD")

if not password:
    raise RuntimeError(
        "PGPASSWORD is not set. Set it in your PowerShell terminal first."
    )

try:
    with psycopg.connect(
        "host=localhost dbname=job_hunt_intelligence user=postgres",
        password=password,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database();")
            database_name = cur.fetchone()[0]

            print("Connection successful!")
            print("Database:", database_name)

except psycopg.Error as error:
    print("Database connection failed.")
    print(error)