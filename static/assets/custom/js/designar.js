document.addEventListener('DOMContentLoaded', function() {
    if (typeof getCookie !== 'function') {
        console.error('Função getCookie não encontrada.');
        return;
    }
    const csrftoken = getCookie('csrftoken');

    // --- LÓGICA PARA DESIGNAÇÃO INDIVIDUAL ---
    document.querySelectorAll('.responsavel-select').forEach(select => {
        select.addEventListener('change', function() {
            const cotacaoId = this.dataset.cotacaoId;
            const responsavelId = this.value;

            // USA A VARIÁVEL DE URL
            fetch(DESIGNAR_URL, { 
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrftoken },
                body: JSON.stringify({ cotacao_id: cotacaoId, responsavel_id: responsavelId })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    this.style.borderColor = '#198754';
                    setTimeout(() => { this.style.borderColor = ''; }, 1500);
                } else {
                    alert('Erro: ' + data.error);
                }
            })
            .catch(error => console.error('Erro:', error));
        });
    });

    // --- LÓGICA PARA DESIGNAÇÃO EM MASSA ---
    const selecionarTodos = document.getElementById('selecionar-todos');
    const checkboxes = document.querySelectorAll('.check-cotacao');
    const btnAcoesMassa = document.getElementById('btn-acoes-massa');
    // ... (função toggleAcoesMassaButton e listeners de checkbox continuam iguais)

    const btnConfirmarMassa = document.getElementById('btn-confirmar-designacao-massa');
    if(btnConfirmarMassa){
        btnConfirmarMassa.addEventListener('click', function() {
            const responsavelId = document.getElementById('select-responsavel-massa').value;
            if (!responsavelId) {
                alert('Por favor, selecione um responsável.');
                return;
            }

            const cotacaoIds = Array.from(checkboxes).filter(cb => cb.checked).map(cb => cb.value);
            this.disabled = true;
            this.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Designando...';

            // USA A VARIÁVEL DE URL
            fetch(DESIGNAR_MASSA_URL, { 
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrftoken },
                body: JSON.stringify({ cotacao_ids: cotacaoIds, responsavel_id: responsavelId })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert(data.message);
                    window.location.reload();
                } else {
                    alert('Erro: ' + data.error);
                    this.disabled = false;
                    this.innerHTML = 'Confirmar Designação';
                }
            })
            .catch(error => {
                console.error('Erro na requisição em massa:', error);
                this.disabled = false;
                this.innerHTML = 'Confirmar Designação';
            });
        });
    }
});