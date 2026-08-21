class KamailioRouter:
    """Ensures Django never runs migrations against the 'kamailio' alias
    — that schema is owned and managed by kamailio-db-modules (kamdbctl).
    We only ever issue raw SQL against it via apps.voip.services."""

    def db_for_read(self, model, **hints):
        return None

    def db_for_write(self, model, **hints):
        return None

    def allow_relation(self, obj1, obj2, **hints):
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if db == "kamailio":
            return False
        return None
