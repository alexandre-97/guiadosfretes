document.addEventListener('DOMContentLoaded', function() {
    const modalElement = document.getElementById('envioMassaModal');
    const cotacoesSelecionadas = document.getElementById('cotacoesSelecionadas');
    const resultadoEnvioModal = new bootstrap.Modal(document.getElementById('resultadoEnvioModal'));
    const resultadoEnvioBody = document.getElementById('resultadoEnvioBody');
    
    let eligibleQuotesList = [];

    if (!modalElement || !cotacoesSelecionadas || !resultadoEnvioModal || !resultadoEnvioBody) {
        console.error('Um ou mais elementos do modal não foram encontrados no DOM.');
        return;
    }

    function showLoading(message = 'Carregando...', element = cotacoesSelecionadas) {
        element.innerHTML = `<div class="text-center py-4"><div class="spinner-border text-primary" role="status"><span class="visually-hidden">Carregando...</span></div><p class="mt-2">${message}</p></div>`;
    }

    function showError(message, details = '', element = cotacoesSelecionadas) {
        element.innerHTML = `<div class="alert alert-danger"><strong>Erro:</strong> ${message}</div>`;
    }

    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    function loadEligibleQuotes() {
        showLoading('Buscando cotações elegíveis...');
        eligibleQuotesList = [];
        fetch('/quoteflow/cotacoes/carregar-cotacoes-envio-massa/', { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
            .then(response => response.ok ? response.json() : response.json().then(err => Promise.reject(err)))
            .then(data => {
                if (data.error || !data.cotacoes || data.cotacoes.length === 0) {
                    cotacoesSelecionadas.innerHTML = `<div class="alert alert-info"><strong>Nenhuma cotação elegível encontrada.</strong></div>`;
                    return;
                }
                eligibleQuotesList = data.cotacoes;
                renderQuotesList(data);
            })
            .catch(error => showError('Falha ao carregar cotações', error.error || error.message));
    }

    function renderQuotesList(data) {
        const quotesHtml = data.cotacoes.map(quote => `
            <div class="card mb-2" id="card-cotacao-${quote.proposta_id_url}">
                <div class="card-body p-2">
                    <div class="d-flex justify-content-between align-items-center">
                        <p class="fw-bold mb-0">#${quote.proposta_id_url} - ${quote.contato}</p>
                        <div class="spinner-border spinner-border-sm text-muted d-none" role="status"></div>
                    </div>
                    <p class="mb-0"><small>${quote.origem} → ${quote.destino}</small></p>
                </div>
            </div>`).join('');
        cotacoesSelecionadas.innerHTML = `
            <div class="alert alert-light border"><strong>${data.total}</strong> cotações prontas para envio.</div>
            <div id="lista-cards-envio" class="mb-3" style="max-height: 300px; overflow-y: auto;">${quotesHtml}</div>
            <div class="d-grid gap-2"><button id="confirmarEnvioMassa" class="btn btn-primary btn-lg"><i class="bi bi-send"></i> Iniciar Envios</button></div>`;
    }

    async function enviarCotacoesMassa() {
        const btn = document.getElementById('confirmarEnvioMassa');
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = `
                <span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
                Enviando, por favor aguarde...
            `;
        }

        const resultados = { sucesso: [], erros: [] };

        for (const quote of eligibleQuotesList) {
            const cardElement = document.getElementById(`card-cotacao-${quote.proposta_id_url}`);
            
            if (!cardElement) {
                console.error(`Elemento do card para a cotação ${quote.proposta_id_url} não foi encontrado.`);
                continue;
            }

            const spinner = cardElement.querySelector('.spinner-border');
            spinner.classList.remove('d-none');

            try {
                const response = await fetch('/quoteflow/cotacoes/enviar-individual-api/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken'),
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    // ==========================================================
                    // CORREÇÃO 1: Enviar o ID numérico que o back-end espera.
                    // ==========================================================
                    body: JSON.stringify({ id: quote.id })
                });

                const result = await response.json();

                if (response.ok && result.success) {
                    resultados.sucesso.push(result);
                    cardElement.classList.add('border-success');
                } else {
                    result.id = quote.proposta_id_url; 
                    result.erro = result.error || (result.erros ? result.erros.join(', ') : 'Erro desconhecido');
                    resultados.erros.push(result);
                    cardElement.classList.add('border-danger');
                }
            } catch (error) {
                const errorResult = { id: quote.proposta_id_url, contato: quote.contato, erro: 'Erro de rede ou comunicação.' };
                resultados.erros.push(errorResult);
                cardElement.classList.add('border-danger');
            } finally {
                spinner.classList.add('d-none');
            }
        }

        const envioMassaModalInstance = bootstrap.Modal.getInstance(modalElement);
        if (envioMassaModalInstance) envioMassaModalInstance.hide();
        showResults(resultados);
    }
    
    // ==========================================================
    // CORREÇÃO 2: Função de resultados ajustada para mostrar os detalhes.
    // ==========================================================
    function showResults(data) {
        let html = '';
        
        if (data.sucesso && data.sucesso.length > 0) {
            html += `<div class="alert alert-success"><h5><i class="bi bi-check-circle"></i> ${data.sucesso.length} cotações processadas com sucesso</h5></div>
                <table class="table table-sm table-hover">
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Contato</th>
                            <th>Canais Enviados</th>
                            <th>Status Final</th>
                        </tr>
                    </thead>
                    <tbody>
                    ${data.sucesso.map(item => `
                        <tr>
                            <td>#${item.id}</td>
                            <td>${item.contato || ''}</td>
                            <td>
                                ${item.enviado_whatsapp ? '<span class="badge bg-success me-1" title="Enviado por WhatsApp"><i class="bi bi-whatsapp"></i> WhatsApp</span>' : ''}
                                ${item.enviado_email ? '<span class="badge bg-primary" title="Enviado por E-mail"><i class="bi bi-envelope"></i> E-mail</span>' : ''}
                            </td>
                            <td><span class="badge bg-success">${item.status_final || 'Enviado'}</span></td>
                        </tr>`).join('')}
                    </tbody>
                </table>`;
        }

        if (data.erros && data.erros.length > 0) {
            html += `<div class="alert alert-danger mt-3"><h5><i class="bi bi-exclamation-triangle"></i> ${data.erros.length} falhas ocorreram</h5></div>
                <table class="table table-sm table-hover">
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Contato</th>
                            <th>Erro</th>
                        </tr>
                    </thead>
                    <tbody>
                    ${data.erros.map(erro => `
                        <tr>
                            <td>#${erro.id}</td>
                            <td>${erro.contato || ''}</td>
                            <td class="text-danger"><small>${erro.erro || 'Erro desconhecido'}</small></td>
                        </tr>`).join('')}
                    </tbody>
                </table>`;
        }

        if (html === '') {
            html = `<div class="alert alert-warning">Nenhuma cotação foi processada.</div>`;
        }
        
        resultadoEnvioBody.innerHTML = html;
        resultadoEnvioModal.show();
    }

    modalElement.addEventListener('show.bs.modal', loadEligibleQuotes);

    document.addEventListener('click', function(e) {
        if (e.target && e.target.id === 'confirmarEnvioMassa' && !e.target.disabled) {
            enviarCotacoesMassa();
        }
    });
});