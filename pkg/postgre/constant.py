# PostgreSQL Defaults
DEFAULT_POOL_SIZE = 20
DEFAULT_MAX_OVERFLOW = 10
DEFAULT_POOL_RECYCLE = 3600
DEFAULT_POOL_PRE_PING = True
DEFAULT_ECHO = False
DEFAULT_ECHO_POOL = False
DEFAULT_SCHEMA = "public"

# Error Messages
ERROR_DATABASE_URL_EMPTY = "database_url is required"
ERROR_INVALID_DATABASE_URL = "database_url must be a PostgreSQL connection string"
ERROR_POOL_SIZE_POSITIVE = "pool_size must be > 0"
ERROR_MAX_OVERFLOW_NON_NEGATIVE = "max_overflow must be >= 0"
ERROR_POOL_RECYCLE_POSITIVE = "pool_recycle must be > 0"
ERROR_SCHEMA_EMPTY = "schema cannot be empty"
ERROR_DATABASE_NOT_INITIALIZED = "Database not initialized"
