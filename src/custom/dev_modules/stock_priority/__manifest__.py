{
    "name": "Stock Priority",
    "summary": "Añade la prioridad de reposición y el stock objetivo a los productos con alertas de actividad automáticas.",
    "version": "17.0.1",
    "category": "Inventory",
    "author": "Johan Ferreira",
    "license": "LGPL-3",
    "depends": ["stock", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_cron_data.xml",
        "views/product_template_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
