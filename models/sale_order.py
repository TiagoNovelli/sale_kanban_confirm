import logging
from odoo import models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def write(self, vals):
        # Evita recursão: action_confirm() também chama write({'state': 'sale'})
        if vals.get('state') == 'sale' and not self.env.context.get('_confirming_from_kanban'):
            orders_to_confirm = self.filtered(
                lambda o: o.state in ('draft', 'sent')
            )
            others = self - orders_to_confirm

            if orders_to_confirm:
                _logger.info(
                    'Kanban drag-and-drop: confirmando pedido(s) %s via action_confirm()',
                    orders_to_confirm.mapped('name')
                )
                # Flag de contexto para evitar loop infinito
                orders_to_confirm.with_context(_confirming_from_kanban=True).action_confirm()

            if others:
                super(SaleOrder, others).write(vals)

            return True

        if vals.get('state') == 'cancel':
            confirmed = self.filtered(lambda o: o.state == 'sale')
            if confirmed:
                raise UserError(
                    _('Não é possível cancelar um Pedido de Venda já confirmado '
                      'arrastando o card. Use o botão "Cancelar" dentro do pedido.')
                )

        return super().write(vals)