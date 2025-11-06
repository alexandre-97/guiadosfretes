# enderecos/models.py
from django.db import models

class CEP(models.Model):
    cep = models.CharField(max_length=8, primary_key=True, help_text="CEP sem traços ou pontos")
    logradouro = models.CharField(max_length=255)
    bairro = models.CharField(max_length=100)
    cidade = models.CharField(max_length=100)
    uf = models.CharField(max_length=2)

    class Meta:
        verbose_name = "CEP"
        verbose_name_plural = "CEPs"

    def __str__(self):
        return f"{self.cep} - {self.logradouro}, {self.cidade}/{self.uf}"