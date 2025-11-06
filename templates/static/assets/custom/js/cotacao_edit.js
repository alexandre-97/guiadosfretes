// Variáveis globais específicas para edição
let statusEnvio = null;
let cotacaoId = null;
const BASE_URL = 'https://mudancasja.com.br/quoteflow';

// Inicialização quando o DOM estiver pronto
document.addEventListener('DOMContentLoaded', function() {
    // Obtém o ID da cotação
    cotacaoId = document.querySelector('form input[name="id"]')?.value || 
               document.querySelector('h4.fw-bold')?.textContent.match(/#(\d+)/)?.[1];
    
    // Configura eventos
    setupEventListeners();
    
    // Configura o modal de envio em massa
    setupMassSendModal();
});

function setupEventListeners() {
    // Botão de abrir mapa
    document.getElementById('btnAbrirMapa')?.addEventListener('click', openMapRoute);
    
    // Botão de solicitar pagamento
    document.getElementById('btnSolicitarPagamento')?.addEventListener('click', function(e) {
        e.preventDefault();
        window.location.href = `${BASE_URL}/cotacoes/${cotacaoId}/solicitar-pagamento/`;
    });

    // Modais de pagamento (se existirem na página)
    setupPaymentModals();
}

function setupMassSendModal() {
    const modalElement = document.getElementById('envioMassaModal');
    const cotacoesSelecionadas = document.getElementById('cotacoesSelecionadas');
    
    if (!modalElement || !cotacoesSelecionadas) return;

    modalElement.addEventListener('show.bs.modal', function() {
        loadEligibleQuotes();
    });

    document.addEventListener('click', function(e) {
        if (e.target && e.target.id === 'confirmarEnvioMassa') {
            enviarCotacoesMassa();
        }
    });
}

function openMapRoute() {
    const origem = document.getElementById('inputOrigem')?.value.trim();
    const destino = document.getElementById('inputDestino')?.value.trim();

    if (!origem || !destino) {
        alert('Por favor, preencha os campos Origem e Destino para abrir o mapa.');
        return;
    }

    const url = `https://www.google.com/maps/dir/?api=1&origin=${encodeURIComponent(origem)}&destination=${encodeURIComponent(destino)}`;
    window.open(url, '_blank');
}

function setupPaymentModals() {
    // Configuração do botão principal
    const btnStatusFrete = document.getElementById('btnStatusFrete');
    if (btnStatusFrete) {
        btnStatusFrete.addEventListener('click', function(e) {
            e.preventDefault();
            new bootstrap.Modal(document.getElementById('modalChegada')).show();
        });
    }

    // Modal de Status de Chegada
    document.getElementById('btnChegou')?.addEventListener('click', function(e) {
        e.preventDefault();
        statusEnvio = 'chegou';
        bootstrap.Modal.getInstance(document.getElementById('modalChegada')).hide();
        new bootstrap.Modal(document.getElementById('modalCobranca')).show();
    });

    document.getElementById('btnVaiDireto')?.addEventListener('click', function(e) {
        e.preventDefault();
        statusEnvio = 'vai_direto';
        bootstrap.Modal.getInstance(document.getElementById('modalChegada')).hide();
        new bootstrap.Modal(document.getElementById('modalCobranca')).show();
    });

    // Modal de Cobrança
    document.getElementById('btn100')?.addEventListener('click', function(e) {
        e.preventDefault();
        handlePayment(100);
    });

    document.getElementById('btn50')?.addEventListener('click', function(e) {
        e.preventDefault();
        handlePayment(50);
    });
}

function handlePayment(percentual) {
    const button = document.getElementById(percentual === 50 ? 'btn50' : 'btn100');
    
    // Validações
    if (!statusEnvio) {
        alert('Selecione o status de chegada primeiro');
        return;
    }
    
    if (![50, 100].includes(percentual)) {
        alert('Percentual inválido');
        return;
    }

    // Mostra estado de loading
    if (button) {
        button.disabled = true;
        button.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Processando...';
    }

    // Cria formulário dinâmico
    const form = document.createElement('form');
    form.method = 'POST';
    form.action = `${BASE_URL}/cotacoes/${cotacaoId}/solicitar-pagamento/`;
    form.style.display = 'none';

    // Adiciona campos
    const csrfInput = document.createElement('input');
    csrfInput.type = 'hidden';
    csrfInput.name = 'csrfmiddlewaretoken';
    csrfInput.value = getCSRFToken();
    form.appendChild(csrfInput);

    const statusInput = document.createElement('input');
    statusInput.type = 'hidden';
    statusInput.name = 'status_envio';
    statusInput.value = statusEnvio;
    form.appendChild(statusInput);

    const percentualInput = document.createElement('input');
    percentualInput.type = 'hidden';
    percentualInput.name = 'percentual';
    percentualInput.value = percentual;
    form.appendChild(percentualInput);

    // Adiciona ao DOM e submete
    document.body.appendChild(form);
    form.submit();
}

// Funções para envio em massa
function loadEligibleQuotes() {
    const cotacoesSelecionadas = document.getElementById('cotacoesSelecionadas');
    if (!cotacoesSelecionadas) return;

    showLoading('Buscando cotações elegíveis...', cotacoesSelecionadas);
    
    fetch(`${BASE_URL}/cotacoes/carregar-cotacoes-envio-massa/`, {
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'Accept': 'application/json'
        },
        credentials: 'include'
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(err => {
                throw new Error(err.error || 'Erro na requisição');
            });
        }
        return response.json();
    })
    .then(data => {
        if (data.error) {
            showError(data.error, data.detalhes, cotacoesSelecionadas);
            return;
        }
        renderQuotesList(data, cotacoesSelecionadas);
    })
    .catch(error => {
        showError('Falha ao carregar cotações', error.message, cotacoesSelecionadas);
    });
}

function enviarCotacoesMassa() {
    const cotacoesSelecionadas = document.getElementById('cotacoesSelecionadas');
    const btn = document.getElementById('confirmarEnvioMassa');
    
    if (!cotacoesSelecionadas) return;

    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Enviando...';
    }

    showLoading('Enviando propostas, por favor aguarde...', cotacoesSelecionadas);

    fetch(`${BASE_URL}/cotacoes/enviar-cotacoes-massa/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken(),
            'X-Requested-With': 'XMLHttpRequest'
        },
        credentials: 'include',
        body: JSON.stringify({})
    })
    .then(response => {
        if (!response.ok) {
            return response.text().then(text => {
                throw new Error(text || 'Erro ao processar envio');
            });
        }
        return response.json();
    })
    .then(data => {
        showResults(data, cotacoesSelecionadas);
    })
    .catch(error => {
        showError('Erro ao enviar cotações', error.message, cotacoesSelecionadas);
    })
    .finally(() => {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-send"></i> Tentar novamente';
        }
    });
}

// Funções auxiliares
function showLoading(message, container) {
    if (!container) return;
    
    container.innerHTML = `
        <div class="text-center py-4">
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Carregando...</span>
            </div>
            <p class="mt-2">${message}</p>
        </div>
    `;
}

function showError(message, details, container) {
    if (!container) return;
    
    let html = `
        <div class="alert alert-danger">
            <strong>Erro:</strong> ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        </div>
    `;
    
    if (details) {
        html += `
            <details class="mt-2">
                <summary>Detalhes</summary>
                <pre class="bg-light p-2">${details}</pre>
            </details>
        `;
    }
    
    container.innerHTML = html;
}

function renderQuotesList(data, container) {
    if (!container || !data.cotacoes) return;

    const quotesHtml = data.cotacoes.map(quote => `
        <div class="card mb-2">
            <div class="card-body">
                <h5 class="card-title">#${quote.id} - ${quote.origem} → ${quote.destino}</h5>
                <p class="card-text">
                    <small class="text-muted">
                        <i class="bi bi-person"></i> ${quote.contato || 'Sem contato'} | 
                        ${quote.email ? `<i class="bi bi-envelope"></i> ${quote.email}` : 'Sem e-mail'} | 
                        ${quote.telefone ? `<i class="bi bi-telephone"></i> ${quote.telefone}` : 'Sem telefone'}
                    </small>
                </p>
            </div>
        </div>
    `).join('');

    container.innerHTML = `
        <div class="alert alert-success">
            <strong>${data.total}</strong> cotações elegíveis encontradas
            <span class="float-end">Empresa: ${data.empresa || ''}</span>
        </div>
        <div class="mb-3" style="max-height: 300px; overflow-y: auto;">
            ${quotesHtml}
        </div>
        <div class="d-grid gap-2">
            <button id="confirmarEnvioMassa" class="btn btn-primary btn-lg">
                <i class="bi bi-send"></i> Enviar ${data.total} Propostas
            </button>
        </div>
    `;
}

function showResults(data, container) {
    if (!container) return;
    
    let html = '';
    
    if (data.sucesso && data.sucesso.length > 0) {
        html += `
            <div class="alert alert-success">
                <strong>${data.sucesso.length}</strong> propostas enviadas com sucesso!
            </div>
        `;
    }
    
    if (data.erros && data.erros.length > 0) {
        html += `
            <div class="alert alert-danger">
                <strong>${data.erros.length}</strong> falhas ocorreram:
                <ul class="mt-2">
                    ${data.erros.map(erro => `<li>#${erro.id}: ${erro.mensagem}</li>`).join('')}
                </ul>
            </div>
        `;
    }
    
    container.innerHTML = html;
}

function getCSRFToken() {
    const cookieValue = document.cookie
        .split('; ')
        .find(row => row.startsWith('csrftoken='))
        ?.split('=')[1];
    return cookieValue || '';
}

// Tratamento global de erros
window.handleApiError = function(error) {
    console.error('Erro na API:', error);
    
    const errorContainer = document.getElementById('error-messages') || 
                         document.getElementById('cotacoesSelecionadas');
    
    if (errorContainer) {
        errorContainer.innerHTML = `
            <div class="alert alert-danger">
                Ocorreu um erro ao comunicar com o servidor.
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;
    }
    
    throw error;
};