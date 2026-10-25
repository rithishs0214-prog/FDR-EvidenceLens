import sys, unittest
sys.path.insert(0, ".")
from app.core.dburl import normalize_database_url as n


class DbUrlTests(unittest.TestCase):
    def test_postgres_variants(self):
        want = "postgresql+psycopg://u:p@host/db?sslmode=require"
        self.assertEqual(n("postgres://u:p@host/db?sslmode=require"), want)
        self.assertEqual(n("postgresql://u:p@host/db?sslmode=require"), want)
        self.assertEqual(n("  postgresql://u:p@host/db?sslmode=require \n"), want)

    def test_other_urls_untouched(self):
        for u in ("sqlite:///C:/x/app.db", "postgresql+psycopg://u:p@h/d", "postgresql+asyncpg://u:p@h/d", ""):
            self.assertEqual(n(u), u)


if __name__ == "__main__":
    unittest.main()
