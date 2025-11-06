# enderecos/management/commands/importar_ceps.py
import csv
from django.core.management.base import BaseCommand
from enderecos.models import CEP
from tqdm import tqdm

class Command(BaseCommand):
    help = 'Importa CEPs de um arquivo CSV para o banco de dados. Use: python manage.py importar_ceps <caminho_do_arquivo.csv>'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='O caminho para o arquivo CSV de CEPs')

    def handle(self, *args, **options):
        csv_file_path = options['csv_file']
        
        if CEP.objects.exists():
            confirm = input("A base de dados de CEPs já contém dados. Deseja limpá-la e importar novamente? (s/n): ")
            if confirm.lower() != 's':
                self.stdout.write(self.style.WARNING('Importação cancelada.'))
                return
            self.stdout.write(self.style.WARNING('Limpando a base de dados de CEPs existente...'))
            CEP.objects.all().delete()

        self.stdout.write(f"Iniciando importação do arquivo: {csv_file_path}")

        ceps_para_criar = []
        try:
            with open(csv_file_path, 'r', encoding='utf-8') as file:
                # Adapte o delimiter se o seu CSV usar ';' ou outro separador
                reader = csv.reader(file, delimiter=',') 
                # Pule o cabeçalho, se houver
                next(reader, None)  
                
                # Use tqdm para uma barra de progresso visual
                for row in tqdm(reader, desc="Processando CEPs"):
                    # Ajuste os índices [0], [1], etc., conforme a ordem das colunas no seu CSV
                    # Ex: cep,logradouro,bairro,cidade,uf
                    cep_limpo = ''.join(filter(str.isdigit, row[0]))
                    if len(cep_limpo) == 8:
                        ceps_para_criar.append(
                            CEP(cep=cep_limpo, logradouro=row[1], bairro=row[2], cidade=row[3], uf=row[4])
                        )
                    
                    # Insere em lotes (bulk) para melhor performance
                    if len(ceps_para_criar) >= 5000:
                        CEP.objects.bulk_create(ceps_para_criar)
                        ceps_para_criar = []

            if ceps_para_criar:
                CEP.objects.bulk_create(ceps_para_criar)
            
            self.stdout.write(self.style.SUCCESS('Importação de CEPs concluída com sucesso!'))

        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f"Arquivo não encontrado: {csv_file_path}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Ocorreu um erro inesperado: {e}"))
