import sys, unittest
sys.path.insert(0, ".")
from app.core.auth import (LoginLimiter, dummy_hash, hash_password, hash_token, new_session_token,
                           normalize_username, validate_password, verify_password)


class PasswordTests(unittest.TestCase):
    def test_roundtrip_and_wrong_password(self):
        h = hash_password("a-good-passphrase-1", iterations=1000)
        self.assertTrue(verify_password("a-good-passphrase-1", h))
        self.assertFalse(verify_password("a-good-passphrase-2", h))
        self.assertFalse(verify_password("", h))

    def test_salted_and_not_plaintext(self):
        a, b = hash_password("same-password-xyz", 1000), hash_password("same-password-xyz", 1000)
        self.assertNotEqual(a, b)
        self.assertNotIn("same-password-xyz", a)
        self.assertTrue(a.startswith("pbkdf2_sha256$"))

    def test_default_iterations_are_strong(self):
        self.assertEqual(hash_password("another-strong-pass").split("$")[1], "600000")

    def test_malformed_hashes_never_verify(self):
        for bad in ["", "plain", "a$b$c", "md5$1$x$y", "pbkdf2_sha256$notint$AAAA$AAAA", "pbkdf2_sha256$1000$!!$!!"]:
            self.assertFalse(verify_password("x", bad), bad)

    def test_dummy_hash_never_matches(self):
        self.assertFalse(verify_password("anything-at-all", dummy_hash()))
        self.assertEqual(dummy_hash(), dummy_hash())

    def test_policy(self):
        self.assertIsNone(validate_password("correct-horse-battery", "alice"))
        for pw, user in [("short", ""), ("x" * 129, ""), ("password123", ""), ("aaaaaaaaaaaa", ""), ("alice-is-great-1", "alice")]:
            self.assertIsNotNone(validate_password(pw, user), pw)


class UsernameAndTokenTests(unittest.TestCase):
    def test_username_normalisation(self):
        self.assertEqual(normalize_username("  Reviewer.One "), "reviewer.one")
        for bad in [None, "", "ab", "has space", "semi;colon", "x" * 51, "a/b"]:
            self.assertIsNone(normalize_username(bad), bad)

    def test_tokens(self):
        t1, t2 = new_session_token(), new_session_token()
        self.assertNotEqual(t1, t2)
        self.assertGreaterEqual(len(t1), 40)
        self.assertEqual(len(hash_token(t1)), 64)
        self.assertNotEqual(hash_token(t1), t1)
        self.assertEqual(hash_token(t1), hash_token(t1))


class LimiterTests(unittest.TestCase):
    def setUp(self):
        self.now = 1000.0
        self.lim = LoginLimiter(max_failures=3, window_seconds=60, clock=lambda: self.now)

    def test_locks_after_max_failures_then_unlocks(self):
        for _ in range(2):
            self.lim.record_failure("k")
        self.assertFalse(self.lim.is_locked("k"))
        self.lim.record_failure("k")
        self.assertTrue(self.lim.is_locked("k"))
        self.assertGreater(self.lim.retry_after("k"), 0)
        self.now += 61
        self.assertFalse(self.lim.is_locked("k"))
        self.assertEqual(self.lim.retry_after("k"), 0)

    def test_keys_are_independent_and_reset_works(self):
        for _ in range(3):
            self.lim.record_failure("a")
        self.assertTrue(self.lim.is_locked("a"))
        self.assertFalse(self.lim.is_locked("b"))
        self.lim.reset("a")
        self.assertFalse(self.lim.is_locked("a"))

    def test_old_failures_age_out(self):
        self.lim.record_failure("k"); self.lim.record_failure("k")
        self.now += 61
        self.lim.record_failure("k")
        self.assertFalse(self.lim.is_locked("k"))


if __name__ == "__main__":
    unittest.main()
