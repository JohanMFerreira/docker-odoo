"""
Tests para el módulo stock_priority.

Ejecutar con:
    odoo-bin -c odoo.conf --test-enable --stop-after-init -i stock_priority
o:
    odoo-bin -c odoo.conf -d <db> --test-tags stock_priority
"""

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestStockPriority(TransactionCase):
    """Tests unitarios para ProductTemplate.action_check_reordering()."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # ── Referencias compartidas ────────────────────────────────────────
        cls.activity_type = cls.env.ref("mail.mail_activity_data_todo")

        # Garantiza que exista al menos un responsable de almacén; se crea uno dedicado
        # para aislar el test del entorno demo / usuario admin.
        manager_group = cls.env.ref("stock.group_stock_manager")
        cls.stock_manager = cls.env["res.users"].create(
            {
                "name": "Test Stock Manager",
                "login": "test_stock_manager_sp@example.com",
                "groups_id": [(4, manager_group.id)],
            }
        )

        # ── Producto con stock POR DEBAJO del objetivo ──────────────────────────
        # qty_available será 0 (sin quants), x_target_stock=100 → alerta.
        cls.product_low = cls.env["product.template"].create(
            {
                "name": "Test Product – Low Stock",
                "type": "consu",
                "x_reordering_priority": "high",
                "x_target_stock": 100.0,
            }
        )

        # ── Producto con stock EN O POR ENCIMA del objetivo ────────────────────
        # qty_available 0, x_target_stock=0 → sin alerta.
        cls.product_ok = cls.env["product.template"].create(
            {
                "name": "Test Product – OK Stock",
                "type": "consu",
                "x_reordering_priority": "low",
                "x_target_stock": 0.0,
            }
        )

    # ── Valores por defecto de campos ───────────────────────────────────────────

    def test_default_priority_is_medium(self):
        """Los productos nuevos sin prioridad explícita tienen 'medium' por defecto."""
        product = self.env["product.template"].create(
            {"name": "Default Priority Product", "type": "consu"}
        )
        self.assertEqual(product.x_reordering_priority, "medium")

    def test_default_target_stock_is_zero(self):
        """Los productos nuevos sin stock objetivo explícito tienen 0.0 por defecto."""
        product = self.env["product.template"].create(
            {"name": "Default Target Stock Product", "type": "consu"}
        )
        self.assertAlmostEqual(product.x_target_stock, 0.0)

    def test_priority_selection_values(self):
        """El campo de prioridad acepta los tres valores válidos de selección."""
        for value in ("low", "medium", "high"):
            self.product_low.x_reordering_priority = value
            self.assertEqual(self.product_low.x_reordering_priority, value)

    # ── action_check_reordering: creación de actividades ───────────────────

    def test_activity_created_when_stock_below_target(self):
        """Se crea una actividad para un producto cuyo qty_available < x_target_stock."""
        # Eliminar actividades preexistentes en este producto para empezar limpio.
        self.env["mail.activity"].search(
            [
                ("res_model", "=", "product.template"),
                ("res_id", "=", self.product_low.id),
            ]
        ).unlink()

        # Llamar con un recordset vacío para simular el comportamiento del cron.
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
            "Se esperaba al menos una actividad para el producto con stock por debajo del objetivo.",
        )

    def test_no_activity_when_target_is_zero(self):
        """No se crea actividad cuando x_target_stock es 0 (producto excluido de la búsqueda)."""
        # Eliminar actividades previas.
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
            "No debe crearse ninguna actividad para un producto con target_stock = 0.",
        )

    # ── action_check_reordering: prevención de duplicados ─────────────────

    def test_no_duplicate_activity_on_second_run(self):
        """Ejecutar el cron dos veces para el mismo producto no duplica actividades."""
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
            "Debe existir exactamente una actividad aunque el cron se ejecute dos veces.",
        )

    def test_duplicate_activity_prevented_by_summary(self):
        """Una segunda llamada con el mismo resumen no crea una nueva actividad."""
        self.env["mail.activity"].search(
            [
                ("res_model", "=", "product.template"),
                ("res_id", "=", self.product_low.id),
            ]
        ).unlink()

        # Primera ejecución — crea la actividad.
        self.env["product.template"].action_check_reordering()
        count_after_first = self.env["mail.activity"].search_count(
            [
                ("res_model", "=", "product.template"),
                ("res_id", "=", self.product_low.id),
                ("activity_type_id", "=", self.activity_type.id),
            ]
        )

        # Segunda ejecución — no debe agregar otra.
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
            "El contador de actividades no debe aumentar en ejecuciones repetidas del cron.",
        )

    # ── Usuario responsable ─────────────────────────────────────────────

    def test_activity_assigned_to_stock_manager(self):
        """La actividad creada se asigna a un usuario del grupo de responsables de almacén."""
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
        self.assertTrue(activity, "La actividad debe haber sido creada.")

        manager_group = self.env.ref("stock.group_stock_manager")
        self.assertIn(
            activity.user_id,
            manager_group.users,
            "La actividad debe asignarse a un usuario del grupo de responsables de almacén.",
        )
