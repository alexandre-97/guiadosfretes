document.addEventListener('DOMContentLoaded', function() {
    const btnSugerir = document.getElementById('btn-sugerir-preco');
    
    // O Django renderiza o campo 'valor_proposta' com o id 'id_valor_proposta'
    const valorPropostaInput = document.getElementById('id_valor_proposta'); 

    if (btnSugerir && valorPropostaInput) {
        btnSugerir.addEventListener('click', function() {
            const cotacaoId = this.dataset.cotacaoId;
            
            // =================== ALTERAÇÃO AQUI ===================
            // Ajustamos a URL para o novo padrão definido no urls.py
            const url = `/quoteflow/cotacoes/${cotacaoId}/sugerir-preco/`; 
            // ======================================================

            // Feedback visual para o usuário
            this.disabled = true;
            this.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Calculando...';

            fetch(url)
                .then(response => {
                    if (!response.ok) {
                        // Se a resposta do servidor não for OK, tenta pegar a mensagem de erro do JSON
                        return response.json().then(err => { throw new Error(err.erro || 'Ocorreu um erro desconhecido.') });
                    }
                    return response.json();
                })
                .then(data => {
                    if (data.valor_sugerido) {
                        // Formata o valor com vírgula como separador decimal e preenche o campo
                        valorPropostaInput.value = parseFloat(data.valor_sugerido).toFixed(2).replace('.', ',');
                    } else if (data.erro) {
                        // Caso a API retorne um erro conhecido
                        throw new Error(data.erro);
                    }
                })
                .catch(error => {
                    console.error('Erro ao buscar sugestão de preço:', error);
                    alert('Não foi possível obter a sugestão de preço: ' + error.message);
                })
                .finally(() => {
                    // Restaura o botão ao estado original, independentemente do resultado
                    this.disabled = false;
                    this.innerHTML = '<i class="bi bi-magic"></i> IA';
                });
        });
    }
});