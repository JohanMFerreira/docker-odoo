"""
Tests for the stock_priority module.

Run with:
    odoo-bin -c odoo.conf --test-enable --stop-after-init -i stock_priority
or:
    odoo-bin -c odoo.conf -d <db> --test-tags stock_priority
"""

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestStockPriority(TransactionCase):
    """Unit tests for ProductTemplate.action_check_reordering()."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # ── Shared references ────────────────────────────────────────
        cls.activity_type = cls.env.ref("mail.mail_activity_data_todo")

        # Ensure at least one stock manager exists; create a dedicated one
        # so the test is isolated from the demo / admin user setup.
        manager_group = cls.env.ref("stock.group_stock_manager")
        cls.stock_manager = cls.env["res.users"].create(
            {
                "name": "Test Stock Manager",
                "login": "test_stock_manager_sp@example.com",
                "groups_id": [(4, manager_group.id)],
            }
        )

        # ── Product with stock BELOW target ──────────────────────────
        # qty_available will be 0 (no quants), x_target_stock=100 → alert.
        cls.product_low = cls.env["product.template"].create(
            {
                "name": "Test Product – Low Stock",
                "type": "consu",
                "x_reordering_priority": "high",
                "x_target_stock": 100.0,
            }
        )

        # ── Product with stock AT OR ABOVE target ────────────────────
        # qty_available 0, x_target_stock=0 → no alert.
        cls.product_ok = cls.env["product.template"].create(
            {
                "name": "Test Product – OK Stock",
                "type": "consu",
                "x_reordering_priority": "low",
                "x_target_stock": 0.0,
            }
        )

    # ── Field defaults ───────────────────────────────────────────────

    def test_default_priority_is_medium(self):
        """New products without explicit priority default to 'medium'."""
        product = self.env["product.template"].create(
            {"name": "Default Priority Product", "type": "consu"}
        )
        self.assertEqual(product.x_reordering_priority, "medium")

    def test_default_target_stock_is_zero(self):
        """New products without explicit target stock default to 0.0."""
        product = self.env["product.template"].create(
            {"name": "Default Target Stock Product", "type": "consu"}
        )
        self.assertAlmostEqual(product.x_target_stock, 0.0)

    def test_priority_selection_values(self):
        """Priority field accepts all three valid selection values."""
        for value in ("low", "medium", "high"):
            self.product_low.x_reordering_priority = value
            self.assertEqual(self.product_low.x_reordering_priority, value)

    # ── action_check_reordering: activity creation ───────────────────

    def test_activity_created_when_stock_below_target(self):
        """An activity is created for a product whose qty_available < x_target_stock."""
        # Remove any pre-existing activities on this product to start clean.
        self.env["mail.activity"].search(
            [
                ("res_model", "=", "product.template"),
                ("res_id", "=", self.product_low.id),
            ]
        ).unlink()

        # Call via an empty recordset to simulate cron behaviour.
        self.env["product.template"].action_check_reordering()

        activities = self.env["mail.activity"].search(
            [
                ("res_model", "=", "product.template"),
                ("res_id", "=", self.product_low.id),
                ("activity_type_id", "=", self.activity_type.id),
            ]
        )
        self.assertTrue(
            activities,
            "Expected at least one activity for the product with stock below target.",
        )

    def test_no_activity_when_target_is_zero(self):
        """No activity is created when x_target_stock is 0 (product excluded from search)."""
        # Remove stale activities first.
        self.env["mail.activity"].search(
            [
                ("res_model", "=", "product.template"),
                ("res_id", "=", self.product_ok.id),
            ]
        ).unlink()

        self.env["product.template"].action_check_reordering()

        activities = self.env["mail.activity"].search(
            [
                ("res_model", "=", "product.template"),
                ("res_id", "=", self.product_ok.id),
                ("activity_type_id", "=", self.activity_type.id),
            ]
        )
        self.assertFalse(
            activities,
            "No activity should be created for a product with target_stock = 0.",
        )

    # ── action_check_reordering: duplicate prevention ─────────────────

    def test_no_duplicate_activity_on_second_run(self):
        """Running the cron twice for the same product does not duplicate activities."""
        self.env["mail.activity"].search(
            [
                ("res_model", "=", "product.template"),
                ("res_id", "=", self.product_low.id),
            ]
        ).unlink()

        ProductTemplate = self.env["product.template"]
        ProductTemplate.action_check_reordering()
        ProductTemplate.action_check_reordering()

        activities = self.env["mail.activity"].search(
            [
                ("res_model", "=", "product.template"),
                ("res_id", "=", self.product_low.id),
                ("activity_type_id", "=", self.activity_type.id),
            ]
        )
        self.assertEqual(
            len(activities),
            1,
            "Exactly one activity should exist even after two consecutive cron runs.",
        )

    def test_duplicate_activity_prevented_by_summary(self):
        """A second call with the same summary does not create a new activity."""
        self.env["mail.activity"].search(
            [
                ("res_model", "=", "product.template"),
                ("res_id", "=", self.product_low.id),
            ]
        ).unlink()

        # First run — creates the activity.
        self.env["product.template"].action_check_reordering()
        count_after_first = self.env["mail.activity"].search_count(
            [
                ("res_model", "=", "product.template"),
                ("res_id", "=", self.product_low.id),
                ("activity_type_id", "=", self.activity_type.id),
            ]
        )

        # Second run — must not add another.
        self.env["product.template"].action_check_reordering()
        count_after_second = self.env["mail.activity"].search_count(
            [
                ("res_model", "=", "product.template"),
                ("res_id", "=", self.product_low.id),
                ("activity_type_id", "=", self.activity_type.id),
            ]
        )

        self.assertEqual(
            count_after_first,
            count_after_second,
            "Activity count must not increase on repeated cron executions.",
        )

    # ── Responsible user ─────────────────────────────────────────────

    def test_activity_assigned_to_stock_manager(self):
        """The created activity is assigned to a user in the stock manager group."""
        self.env["mail.activity"].search(
            [
                ("res_model", "=", "product.template"),
                ("res_id", "=", self.product_low.id),
            ]
        ).unlink()

        self.env["product.template"].action_check_reordering()

        activity = self.env["mail.activity"].search(
            [
                ("res_model", "=", "product.template"),
                ("res_id", "=", self.product_low.id),
                ("activity_type_id", "=", self.activity_type.id),
            ],
            limit=1,
        )
        self.assertTrue(activity, "Activity must have been created.")

        manager_group = self.env.ref("stock.group_stock_manager")
        self.assertIn(
            activity.user_id,
            manager_group.users,
            "Activity must be assigned to a user belonging to the stock manager group.",
        )
