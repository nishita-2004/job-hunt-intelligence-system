
import os
import psycopg


def main():
    password = os.environ.get("PGPASSWORD")

    if not password:
        print("PGPASSWORD is not set in this terminal.")
        return 1

    database = os.environ.get(
        "PGDATABASE",
        "job_hunt_intelligence",
    )

    try:
        with psycopg.connect(
            host="localhost",
            dbname=database,
            user=os.environ.get("PGUSER", "postgres"),
            password=password,
        ) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT current_database();")
                database_name = cur.fetchone()[0]

        print("Connection successful!")
        print("Database:", database_name)
        return 0

    except psycopg.Error as error:
        print("Database connection failed.")
        print(error)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
