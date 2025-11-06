# enderecos/views.py
from django.http import JsonResponse
from .models import CEP

def buscar_cep_local(request, cep):
    """
    View que busca um CEP no banco de dados local e retorna um JSON.
    """
    cep_limpo = ''.join(filter(str.isdigit, cep))

    if len(cep_limpo) != 8:
        return JsonResponse({'erro': 'Formato de CEP inválido'}, status=400)

    try:
        cep_obj = CEP.objects.get(pk=cep_limpo)
        data = {
            'cep': cep_obj.cep,
            'logradouro': cep_obj.logradouro,
            'bairro': cep_obj.bairro,
            'localidade': cep_obj.cidade, # Nome 'localidade' para manter compatibilidade com o JS
            'uf': cep_obj.uf,
            'erro': False
        }
        return JsonResponse(data)
    except CEP.DoesNotExist:
        return JsonResponse({'erro': 'CEP não encontrado'}, status=404)