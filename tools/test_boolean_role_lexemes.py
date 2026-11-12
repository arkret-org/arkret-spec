"""Bare words cannot erase the axis of an owned permission or obligation."""
import unittest
from .artifact_lint.naming import nc_bool_001, nc_set_001


class BooleanRoleLexemesTest(unittest.TestCase):
    def test_bare_roles_rejected(self):
        for name in ("required", "allowed", "allow_access", "no_history"):
            self.assertTrue(nc_bool_001(name), name)

    def test_qualified_roles_and_facts(self):
        for name in ("verification_required", "reading_allowed", "active", "include_payload"):
            self.assertFalse(nc_bool_001(name), name)

    def test_allowlist_suffix_cannot_hide_set_role(self):
        for name in ("organization_allowlist", "account_denylist", "link_kind_allow", "allowlist"):
            self.assertTrue(nc_set_001(name), name)
        for name in ("allowed_organization_labels", "denied_account_ids", "supported_link_kinds"):
            self.assertFalse(nc_set_001(name), name)


if __name__ == '__main__':
    unittest.main()
