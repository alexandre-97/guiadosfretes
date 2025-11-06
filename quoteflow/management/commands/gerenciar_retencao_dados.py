from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from quoteflow.models import Cotacao
from perfil.models import Empresa

class Command(BaseCommand):
    help = 'Aplica as políticas de retenção de dados (ocultação e exclusão) para as cotações de cada empresa.'

    def handle(self, *args, **kwargs):
        hoje = timezone.now()
        self.stdout.write(f"[{hoje.strftime('%Y-%m-%d %H:%M:%S')}] Iniciando a verificação de retenção de dados...")

        empresas_com_politicas = Empresa.objects.exclude(
            dias_expiracao_visualizacao__isnull=True,
            dias_expiracao_dados__isnull=True
        )

        for empresa in empresas_com_politicas:
            self.stdout.write(f"\n--- Processando Empresa: {empresa.nome} ---")

            # --- 1. Lógica de Ocultação (Soft Delete) ---
            if empresa.dias_expiracao_visualizacao is not None:
                data_limite_visualizacao = hoje - timedelta(days=empresa.dias_expiracao_visualizacao)
                
                cotacoes_para_inativar = Cotacao.objects.filter(
                    empresa=empresa,
                    visivel=True,  # Pega apenas as que ainda estão visíveis
                    data_recebimento__lt=data_limite_visualizacao
                )
                
                count = cotacoes_para_inativar.count()
                if count > 0:
                    cotacoes_para_inativar.update(visivel=False)
                    self.stdout.write(self.style.SUCCESS(
                        f"  -> {count} cotação(ões) ocultada(s) (mais antigas que {data_limite_visualizacao.strftime('%d/%m/%Y')})."
                    ))
                else:
                    self.stdout.write("  -> Nenhuma cotação para ocultar.")

            # --- 2. Lógica de Exclusão Permanente (Hard Delete) ---
            if empresa.dias_expiracao_dados is not None:
                data_limite_delecao = hoje - timedelta(days=empresa.dias_expiracao_dados)
                
                cotacoes_para_deletar = Cotacao.objects.filter(
                    empresa=empresa,
                    data_recebimento__lt=data_limite_delecao
                )
                
                count, _ = cotacoes_para_deletar.delete()
                if count > 0:
                    self.stdout.write(self.style.WARNING(
                        f"  -> CUIDADO: {count} cotação(ões) permanentemente APAGADA(S) (mais antigas que {data_limite_delecao.strftime('%d/%m/%Y')})."
                    ))
                else:
                    self.stdout.write("  -> Nenhuma cotação para apagar permanentemente.")
        
        self.stdout.write(f"\n[{timezone.now().strftime('%Y-%m-%d %H:%M:%S')}] Verificação de retenção concluída.")
