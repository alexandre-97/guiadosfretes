from django import template
from django.utils.formats import number_format

register = template.Library()

@register.filter(name='br_money')
def br_money(value):
    """
    Formata um número para o padrão de moeda brasileira (R$).
    Exemplo: 1234.56 -> R$ 1.234,56
    """
    try:
        # Tenta converter o valor para float, caso seja string ou Decimal
        value = float(value)
    except (ValueError, TypeError, AttributeError):
        # Se falhar, retorna um valor padrão ou o próprio valor sem formatação
        return "R$ 0,00"

    # Usa a função number_format do Django para formatar com separadores.
    # force_grouping=True garante o separador de milhar.
    # use_l10n=True usaria as configurações de localização, mas vamos forçar o padrão BR.
    formatted_value = number_format(value, decimal_pos=2, force_grouping=True)
    
    # O number_format com config EN-US usa ',' para milhar e '.' para decimal.
    # Invertemos para o padrão brasileiro.
    # Ex: 1,234.56 -> 1.234,56
    if ',' in formatted_value and '.' in formatted_value:
         # Inversão segura para evitar conflitos
        formatted_value = formatted_value.replace(',', 'TEMP').replace('.', ',').replace('TEMP', '.')
    
    return f"R$ {formatted_value}"