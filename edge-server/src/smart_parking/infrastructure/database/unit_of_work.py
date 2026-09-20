"""Unit of Work Pattern."""
class UnitOfWork:
    def __init__(self, db):
        self.db = db