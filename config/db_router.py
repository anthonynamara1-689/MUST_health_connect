class ReportsRouter:
    """The 'reports' connection is read-only and is never migrated."""

    def db_for_read(self, model, **hints):
        return None  # the ORM always uses "default"

    def db_for_write(self, model, **hints):
        return None

    def allow_relation(self, obj1, obj2, **hints):
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        return db == "default"
