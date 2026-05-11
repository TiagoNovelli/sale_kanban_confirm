import logging
from odoo import models, fields, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def write(self, vals):
        if vals.get('state') == 'sale' and not self.env.context.get('_confirming_from_kanban'):
            orders_to_confirm = self.filtered(lambda o: o.state in ('draft', 'sent'))
            others = self - orders_to_confirm

            if orders_to_confirm:
                _logger.info(
                    'Kanban: confirmando %s', orders_to_confirm.mapped('name')
                )
                orders_to_confirm.with_context(
                    _confirming_from_kanban=True
                ).action_confirm()

            if others:
                super(SaleOrder, others).write(vals)

            return True

        if vals.get('state') == 'cancel':
            confirmed = self.filtered(lambda o: o.state == 'sale')
            if confirmed:
                raise UserError(
                    _('Use o botão "Cancelar" dentro do pedido.')
                )

        return super().write(vals)

    @property
    def _rec_names_search(self):
        return ['name', 'partner_id.name']