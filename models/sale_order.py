import logging
from odoo import models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def write(self, vals):
        """
        Intercepta a mudança de state para 'sale' (Sales Order).
        Quando isso acontece via drag-and-drop no Kanban, chama action_confirm()
        em vez de setar o campo diretamente, garantindo que toda a lógica
        de confirmação seja executada corretamente.
        """
        if vals.get('state') == 'sale':
            # Separa os pedidos que podem ser confirmados
            orders_to_confirm = self.filtered(
                lambda o: o.state in ('draft', 'sent')
            )
            # Pedidos que já estão confirmados ou em outros estados
            others = self - orders_to_confirm

            if orders_to_confirm:
                _logger.info(
                    'Kanban drag-and-drop: confirmando pedido(s) %s via action_confirm()',
                    orders_to_confirm.mapped('name')
                )
                orders_to_confirm.action_confirm()

            # Para os demais (ex: já confirmados), aplica o write normalmente
            if others:
                super(SaleOrder, others).write(vals)

            return True

        # Intercepta tentativa de mover para 'cancel' via Kanban
        if vals.get('state') == 'cancel':
            confirmed = self.filtered(lambda o: o.state == 'sale')
            if confirmed:
                raise UserError(
                    _('Não é possível cancelar um Pedido de Venda já confirmado '
                      'arrastando o card. Use o botão "Cancelar" dentro do pedido.')
                )

        return super().write(vals)