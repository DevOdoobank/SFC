# -*- coding: utf-8 -*-
import logging
import json
from odoo import http, _
from odoo.http import request, Response

_logger = logging.getLogger(__name__)


class HttpRequestApi(http.Controller):

    @http.route('/api/order/create', auth='public', type='json', csrf=False)
    def order_add_order(self, **kw):
        token_id = request.httprequest.headers.get('token', False)
        invoice_token = request.env['ir.config_parameter'].sudo().get_param('invoice_api_integration.invoice_token',
                                                                            False)
        if (invoice_token or token_id) and token_id != invoice_token:
            return {
                "isSubmitted": True,
                "isSubmittedSuccessfully": False,
                "errors": ["You can't access this API Please Check Your Token"],
                "model": None}
        try:
            Client = kw.get('Client')
            items_lines = kw.get('Items')
            Amount = kw.get('Amount')
            Total = kw.get('Total')
            order = request.env['account.move'].sudo()
            partner_obj = request.env['res.partner'].sudo()
            journal_id = request.env['account.journal'].sudo().search([('is_ecommerce', '=', True)], limit=1)
            tax_id = request.env['account.tax'].sudo().search([('is_ecommerce', '=', True)], limit=1)
            team_id = request.env['crm.team'].sudo().search([('is_ecommerce', '=', True)], limit=1)
            account_id = journal_id.default_account_id
            clientID = False
            lines = []
            if Client:
                clientID = partner_obj.search([('client_id', '=', Client.get('Client_ID'))]).id
                if not clientID:
                    partner_vals = {
                        'name': Client.get('Client_Name'),
                        'client_id': Client.get('Client_ID'),
                        'is_ecommerce': True,
                        'client_nation_id': Client.get('Client_NID'),
                        'street': Client.get('Client_Address'),
                    }
                    print("VALS ->", partner_vals)
                    clientID = partner_obj.create(partner_vals).id

            for line in items_lines:
                product_id = request.env['product.product'].sudo().search(
                    [('product_type', '=', line.get('Item_Category'))], limit=1)

                analytic_account_id = request.env['account.analytic.account'].sudo().search(
                    [('product_type', '=', line.get('Item_Category'))], limit=1)

                vals = (0, 0, {
                    'name': line.get('Item_Name'),
                    'product_id': product_id.id if product_id else False,
                    'analytic_account_id': analytic_account_id.id if analytic_account_id else False,
                    'account_id': account_id.id,
                    'quantity': line.get('Quantity', 1),
                    'price_unit': line.get('Price'),
                })
                lines.append(vals)

            if kw.get('TAX', False):
                tax_value = (0, 0, {
                    'product_id': request.env['product.product'].sudo().search(
                        [('product_type', '=', 'tax')], limit=1).id,
                    'account_id': account_id.id,
                    'quantity': 1,
                    'tax_ids': [(6, 0, [tax_id.id])],
                    'price_unit': kw.get('TAX'),
                })
                lines.append(tax_value)

            if kw.get('Shipping_Fees', False):
                tax_value = (0, 0, {
                    'product_id': request.env['product.product'].sudo().search(
                        [('product_type', '=', 'shipping')], limit=1).id,
                    'account_id': account_id.id,
                    'quantity': kw.get('Shipping_Fees').get('quantity', 1),
                    'price_unit': kw.get('Shipping_Fees').get('price'),
                })
                lines.append(tax_value)

            if kw.get('Service_Charge', False):
                service_change_line = (0, 0, {
                    'product_id': request.env['product.product'].sudo().search(
                        [('product_type', '=', 'charge')], limit=1).id,
                    'account_id': account_id.id,
                    'quantity': kw.get('Service_Charge').get('quantity', 1),
                    'price_unit': kw.get('Service_Charge').get('price'),
                })

                lines.append(service_change_line)

            # Weapon Overage Section
            weapon_overage = kw.get('WeaponOverage', False)
            if weapon_overage:
                weapon_overage_line = (0, 0, {
                    'product_id': request.env['product.product'].sudo().search(
                        [('product_type', '=', 'weapon_overage')], limit=1).id,
                    'account_id': account_id.id,
                    'quantity': weapon_overage.get('quantity', 1),
                    'price_unit': weapon_overage.get('price'),
                })
                lines.append(weapon_overage_line)

            total_service_charge = kw.get('Service_Charge').get('quantity') * kw.get('Service_Charge').get('price')
            total_shipping_fees = kw.get('Shipping_Fees').get('quantity') * kw.get('Shipping_Fees').get('price')

            order_val = {
                "partner_id": clientID,
                "team_id": team_id.id if team_id else False,
                "journal_id": journal_id.id,
                "invoice_status": 'wait',
                "move_type": 'out_invoice',
                "order_date": str(kw.get('Order_Datetime')),
                "invoice_ref": kw.get('Invoice_Ref'),
                "service_charge": total_service_charge,
                "shipping_fees": total_shipping_fees,
                "invoice_link": kw.get('Invoice'),
                "is_ecommerce": True,
                "invoice_line_ids": lines,
            }

            order_id = order.create(order_val)
            print("ORDER ->", order_id)
            order_id.action_post()
            if order_id:
                return {
                    "isSubmitted": True,
                    "isSubmittedSuccessfully": True,
                    "errors": [],
                    "model": {
                        'invoice': order_id.invoice_ref,
                        'client': order_id.partner_id.name,
                        'total': round(order_id.amount_total, 2)
                    }}
        except Exception as err:
            print(err)
            return {
                "isSubmitted": True,
                "isSubmittedSuccessfully": False,
                "errors": [str(err.args)],
                "model": None}
