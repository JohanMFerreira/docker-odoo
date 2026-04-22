from odoo import fields, models


OPERATION_TYPE_SELECTION = [
    ("receipt", "Recepción"),
    ("delivery", "Entrega"),
    ("internal", "Transferencia Interna"),
    ("all", "Todos"),
]


class StockOperationTag(models.Model):
    _name = "stock.operation.tag"
    _description = "Etiqueta de Operación de Inventario"
    _order = "name"

    name = fields.Char(string="Nombre", required=True)
    color = fields.Integer(string="Color")
    description = fields.Text(string="Descripción")
    operation_type = fields.Selection(
        selection=OPERATION_TYPE_SELECTION,
        string="Tipo de Operación",
        default="all",
        required=True,
    )
    product_template_ids = fields.Many2many(
        comodel_name="product.template",
        relation="product_template_stock_operation_tag_rel",
        column1="tag_id",
        column2="product_template_id",
        string="Productos",
    )
