import duckdb
from pathlib import Path
import re
import os

# ── Path resolution ───────────────────────────────────────────────────────────
# When running normally (development), these resolve relative to cwd.
# When running inside the macOS .app bundle, the launcher sets environment
# variables NEISS_DATA_DIR and NEISS_OUTPUT_DIR to the correct bundle paths.
# We check the env vars first; fall back to the development defaults.

_data_dir_env   = os.environ.get("NEISS_DATA_DIR")
_output_dir_env = os.environ.get("NEISS_OUTPUT_DIR")

DATA_DIR = Path(_data_dir_env)   if _data_dir_env   else Path("data")
DB_PATH  = Path(_output_dir_env) / "neiss.duckdb" \
           if _output_dir_env else Path("output/neiss.duckdb")


def find_csv_files():
    """Find all CSV files in the data folder."""
    csv_files = sorted(DATA_DIR.glob("*.csv"))

    if not csv_files:
        raise FileNotFoundError(
            "No CSV files found in the data/ folder. "
            "Please add your NEISS CSV files first."
        )

    return csv_files


def extract_year_from_filename(filename):
    """Extract a 4-digit year from a filename like neiss2019.csv."""
    match = re.search(r"(20\d{2})", filename)
    if match:
        return int(match.group(1))
    return None


def connect():
    """Connect to local DuckDB database."""
    DB_PATH.parent.mkdir(exist_ok=True)
    return duckdb.connect(str(DB_PATH))


def build_database():
    """
    Load all CSV files from data/ into one DuckDB table.

    This creates or replaces a table called neiss_cases.
    """
    csv_files = find_csv_files()
    con = connect()

    con.execute("DROP TABLE IF EXISTS neiss_cases")

    first_file = True

    for csv_file in csv_files:
        year = extract_year_from_filename(csv_file.name)

        if year is None:
            print(f"Skipping {csv_file.name}: no year found in filename")
            continue

        print(f"Loading {csv_file.name} as year {year}...")

        query = f"""
        SELECT
            *,
            {year} AS year
        FROM read_csv_auto('{csv_file.as_posix()}', ignore_errors=true)
        """

        if first_file:
            con.execute(f"CREATE TABLE neiss_cases AS {query}")
            first_file = False
        else:
            con.execute(f"INSERT INTO neiss_cases {query}")

    if first_file:
        raise RuntimeError("No valid CSV files were loaded.")

    return con


def get_connection():
    """
    Connect to the existing database.
    If it does not exist yet, build it.
    """
    if not DB_PATH.exists():
        return build_database()

    con = connect()

    try:
        con.execute("SELECT COUNT(*) FROM neiss_cases").fetchone()
        return con
    except Exception:
        return build_database()


def get_columns():
    """Return column names from the NEISS table."""
    con = get_connection()
    result = con.execute("DESCRIBE neiss_cases").fetchall()
    return [row[0] for row in result]


def get_year_range():
    """Return minimum and maximum years available."""
    con = get_connection()
    result = con.execute("SELECT MIN(year), MAX(year) FROM neiss_cases").fetchone()
    return result[0], result[1]
