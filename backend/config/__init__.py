# Use PyMySQL as the MySQLdb driver so no C compiler / system libraries
# are required (works out of the box on Windows 11, macOS and Linux).
# This is a no-op when the SQLite engine is selected.
try:
    import pymysql

    pymysql.install_as_MySQLdb()
except ImportError:  # pragma: no cover - PyMySQL always present via requirements
    pass
