from odoo.tests.common import TransactionCase


class TestStockTagging(TransactionCase):
    """Tests unitarios para el módulo stock_tagging."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ProductTemplate = cls.env["product.template"]
        cls.StockOperationTag = cls.env["stock.operation.tag"]

    # ------------------------------------------------------------------
    # Auxiliares
    # ------------------------------------------------------------------

    def _create_tag(self, name, operation_type="all", color=1):
        return self.StockOperationTag.create(
            {
                "name": name,
                "operation_type": operation_type,
                "color": color,
            }
        )

    def _create_product(self, name):
        return self.ProductTemplate.create({"name": name, "type": "consu"})

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    def test_create_tag(self):
        """Se puede crear un stock.operation.tag con todos los campos esperados."""
        tag = self._create_tag(
            name="Entrada Urgente",
            operation_type="receipt",
            color=3,
        )
        self.assertTrue(tag.id, "El tag debe tener un ID asignado tras su creación.")
        self.assertEqual(tag.name, "Entrada Urgente")
        self.assertEqual(tag.operation_type, "receipt")
        self.assertEqual(tag.color, 3)

    def test_assign_tag_to_product(self):
        """Se puede asignar un tag a un product.template mediante x_operation_tag_ids."""
        tag = self._create_tag("Devolución Rápida", operation_type="delivery", color=5)
        product = self._create_product("Producto Test")

        product.x_operation_tag_ids = [(4, tag.id)]

        self.assertIn(
            tag,
            product.x_operation_tag_ids,
            "El tag debe aparecer en x_operation_tag_ids del producto.",
        )

    def test_many2many_relationship(self):
        """La relación Many2Many funciona en ambas direcciones."""
        tag_a = self._create_tag("Tag A", color=1)
        tag_b = self._create_tag("Tag B", color=2)
        product_1 = self._create_product("Producto 1")
        product_2 = self._create_product("Producto 2")

        # Asignar ambos tags a product_1 y solo tag_b a product_2
        product_1.x_operation_tag_ids = [(6, 0, [tag_a.id, tag_b.id])]
        product_2.x_operation_tag_ids = [(6, 0, [tag_b.id])]

        self.assertEqual(len(product_1.x_operation_tag_ids), 2)
        self.assertIn(tag_a, product_1.x_operation_tag_ids)
        self.assertIn(tag_b, product_1.x_operation_tag_ids)

        self.assertEqual(len(product_2.x_operation_tag_ids), 1)
        self.assertIn(tag_b, product_2.x_operation_tag_ids)

        # Verificar inverso: tag_b debe estar vinculado a ambos productos
        self.assertIn(product_1, tag_b.product_template_ids)
        self.assertIn(product_2, tag_b.product_template_ids)

        # tag_a solo debe estar vinculado a product_1
        self.assertIn(product_1, tag_a.product_template_ids)
        self.assertNotIn(product_2, tag_a.product_template_ids)

    def test_tag_default_operation_type(self):
        """El operation_type por defecto de un nuevo tag es 'all'."""
        tag = self.StockOperationTag.create({"name": "Sin tipo explícito"})
        self.assertEqual(
            tag.operation_type,
            "all",
            "El tipo de operación por defecto debe ser 'all'.",
        )

    def test_remove_tag_from_product(self):
        """Se puede eliminar un tag de un producto sin eliminar el tag."""
        tag = self._create_tag("Tag Removible", color=7)
        product = self._create_product("Producto con tag")
        product.x_operation_tag_ids = [(4, tag.id)]

        # Eliminar el tag
        product.x_operation_tag_ids = [(3, tag.id)]

        self.assertNotIn(
            tag,
            product.x_operation_tag_ids,
            "El tag no debe estar en el producto después de ser eliminado.",
        )
        # El tag debe seguir existiendo en la base de datos
        self.assertTrue(
            self.StockOperationTag.browse(tag.id).exists(),
            "El tag no debe ser eliminado de la base de datos al desvincularse.",
        )
