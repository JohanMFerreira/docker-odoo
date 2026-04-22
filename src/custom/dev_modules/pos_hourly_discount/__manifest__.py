# -*- coding: utf-8 -*-
{
    'name': 'POS Hourly Discount',
    'version': '17.0.1',
    'summary': 'Aplica descuentos automáticos en pedidos de TPV según franjas horarias.',
    'description': """
        Permite configurar reglas de descuento vinculadas a intervalos de tiempo. 
        Cuando se crea un pedido en el punto de venta, la regla activa cuyo intervalo 
        coincida con la hora actual se aplica automáticamente a todas las líneas del pedido.
    """,
    'category': 'Point of Sale',
    'author': 'Johan Ferreira',
    'depends': ['point_of_sale'],
    'data': [
        'security/ir.model.access.csv',
        'views/pos_discount_rule_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
