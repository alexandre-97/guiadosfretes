# quoteflow/management/commands/populate_sequenciais.py

from django.core.management.base import BaseCommand
from django.db import transaction
from quoteflow.models import Cotacao
from perfil.models import Empresa

class Command(BaseCommand):
    help = 'Encontra cotações sem número sequencial e as popula na ordem correta por empresa.'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS("--- INICIANDO SCRIPT DE CORREÇÃO DE SEQUENCIAIS ---"))

        # Primeiro, avisa sobre cotações sem empresa, que são a causa raiz do problema.
        cotacoes_sem_empresa = Cotacao.objects.filter(empresa__isnull=True)
        if cotacoes_sem_empresa.exists():
            self.stdout.write(self.style.WARNING(f"\n[AVISO] Encontradas {cotacoes_sem_empresa.count()} cotações sem empresa associada."))
            ids_orf_as = list(cotacoes_sem_empresa.values_list('id', flat=True))
            self.stdout.write(self.style.WARNING(f"IDs das cotações órfãs: {ids_orf_as}"))
            self.stdout.write(self.style.WARNING("Estas cotações não receberão um número sequencial até que uma empresa seja associada a elas no painel de administração.\n"))

        # Agora, corrige as que têm empresa mas não têm sequencial.
        total_corrigido = 0
        empresas = Empresa.objects.all()

        for empresa in empresas:
            self.stdout.write(f"Verificando empresa: '{empresa.nome}' (ID: {empresa.id})")
            
            with transaction.atomic():
                # Pega a última cotação COM sequencial para saber de onde continuar
                ultima_cotacao_com_sequencial = Cotacao.objects.filter(
                    empresa=empresa, 
                    numero_sequencial_empresa__isnull=False
                ).select_for_update().order_by('-numero_sequencial_empresa').first()

                proximo_numero = 1
                if ultima_cotacao_com_sequencial and ultima_cotacao_com_sequencial.numero_sequencial_empresa:
                    proximo_numero = ultima_cotacao_com_sequencial.numero_sequencial_empresa + 1
                
                self.stdout.write(f"  Último sequencial encontrado: {proximo_numero - 1}. Próximo número a ser usado: {proximo_numero}")

                # Pega todas as cotações da empresa que estão sem sequencial, em ordem de criação (ID)
                cotacoes_para_corrigir = Cotacao.objects.filter(
                    empresa=empresa,
                    numero_sequencial_empresa__isnull=True
                ).select_for_update().order_by('id')

                if not cotacoes_para_corrigir.exists():
                    self.stdout.write(self.style.NOTICE("  Nenhuma cotação para corrigir nesta empresa."))
                    continue

                self.stdout.write(f"  Encontradas {cotacoes_para_corrigir.count()} cotações para popular...")
                
                # Itera e atribui o novo número sequencial
                for cotacao in cotacoes_para_corrigir:
                    cotacao.numero_sequencial_empresa = proximo_numero
                    cotacao.save()
                    self.stdout.write(f"    -> Cotação ID {cotacao.id} agora tem o sequencial {proximo_numero}")
                    proximo_numero += 1
                    total_corrigido += 1

        self.stdout.write(self.style.SUCCESS("\n--- SCRIPT FINALIZADO ---"))
        self.stdout.write(self.style.SUCCESS(f"Total de {total_corrigido} cotações foram corrigidas com um novo número sequencial."))

