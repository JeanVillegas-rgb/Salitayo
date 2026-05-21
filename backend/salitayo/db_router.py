"""Route Word Proficiency apps to a separate database so existing apps stay untouched."""


class WordProficiencyRouter:
    wp_app_labels = {'profiles', 'system', 'authtoken'}

    def db_for_read(self, model, **hints):
        if model._meta.app_label in self.wp_app_labels:
            return 'wp'
        return 'default'

    def db_for_write(self, model, **hints):
        if model._meta.app_label in self.wp_app_labels:
            return 'wp'
        return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        labels = {obj1._meta.app_label, obj2._meta.app_label}
        if labels <= self.wp_app_labels:
            return True
        if labels.isdisjoint(self.wp_app_labels):
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label in self.wp_app_labels:
            return db == 'wp'
        if db == 'wp':
            return False
        return True
