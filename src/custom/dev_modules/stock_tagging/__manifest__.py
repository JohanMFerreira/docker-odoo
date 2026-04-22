{
    "name": "Stock Operation Tagging",
    "summary": "Etiquetas operativas para productos en Inventario con vista Kanban agrupada.",
    "version": "17.0.1",
    "category": "Inventory",
    "author": "Johan Ferreira",
    "license": "LGPL-3",
    "depends": ["stock"],
    "data": [
        "security/ir.model.access.csv",
        "views/stock_operation_tag_views.xml",
        "views/product_template_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
