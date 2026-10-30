"""Tests for auth.py — password hashing and checking."""

import unittest

from auth import hash_password, verify_password


class TestHashPassword(unittest.TestCase):
    def test_returns_salt_and_hash(self):
        salt, digest = hash_password("secret123")
        self.assertTrue(salt)
        self.assertTrue(digest)

    def test_hash_is_not_the_plain_password(self):
        _salt, digest = hash_password("secret123")
        self.assertNotEqual(digest, "secret123")

    def test_hash_is_not_the_salt(self):
        salt, digest = hash_password("secret123")
        self.assertNotEqual(digest, salt)

    def test_same_password_twice_gives_different_hashes(self):
        # Different random salt each time, so hashes must differ.
        _, first = hash_password("secret123")
        _, second = hash_password("secret123")
        self.assertNotEqual(first, second)

    def test_salt_is_long_enough_to_be_useful(self):
        salt, _ = hash_password("secret123")
        self.assertGreaterEqual(len(salt), 16)


class TestVerifyPassword(unittest.TestCase):
    def test_correct_password_verifies(self):
        salt, digest = hash_password("secret123")
        self.assertTrue(verify_password("secret123", salt, digest))

    def test_wrong_password_fails(self):
        salt, digest = hash_password("secret123")
        self.assertFalse(verify_password("wrong", salt, digest))

    def test_wrong_salt_fails(self):
        _, digest = hash_password("secret123")
        self.assertFalse(verify_password("secret123", "othersalt1234567890", digest))

    def test_empty_password_fails(self):
        salt, digest = hash_password("secret123")
        self.assertFalse(verify_password("", salt, digest))

    def test_tampered_hash_fails(self):
        salt, digest = hash_password("secret123")
        self.assertFalse(verify_password("secret123", salt, "0" * len(digest)))
