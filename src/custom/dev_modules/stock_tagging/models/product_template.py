from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    x_operation_tag_ids = fields.Many2many(
        comodel_name="stock.operation.tag",
        relation="product_template_stock_operation_tag_rel",
        column1="product_template_id",
        column2="tag_id",
        string="Etiquetas Operativas",
    )
