document.addEventListener('DOMContentLoaded', function() {
    const globalSpinner = document.getElementById('global-spinner');
    
    // Mostra o spinner
    function showGlobalLoading(show = true) {
        if (show) {
            globalSpinner.style.display = 'flex';
            document.body.style.overflow = 'hidden';
        } else {
            globalSpinner.style.display = 'none';
            document.body.style.overflow = '';
        }
    }

    // Intercepta envio do formulário principal
    const cotacaoForm = document.getElementById('cotacaoForm');
    if (cotacaoForm) {
        cotacaoForm.addEventListener('submit', function(e) {
            showGlobalLoading();
        });
    }

    // Intercepta todos os cliques em links/botões de envio
    document.addEventListener('click', function(e) {
        const target = e.target.closest('[href*="enviar"], .btn-envio, [onclick*="window.location"], .aprovar-btn, .rejeitar-btn, .anterior-link, .proxima-link');
        
        if (target) {
            // Se for um link normal
            if (target.tagName === 'A' && (target.href.includes('enviar_') || 
                                          target.href.includes('solicitar_') ||
                                          target.href.includes('cotacao_edit'))) {
                e.preventDefault();
                showGlobalLoading();
                window.location.href = target.href;
            }
            // Se for um botão com onclick
            else if (target.hasAttribute('onclick') && target.getAttribute('onclick').includes('window.location')) {
                e.preventDefault();
                showGlobalLoading();
                const urlMatch = target.getAttribute('onclick').match(/window\.location\.href='([^']+)'/);
                if (urlMatch && urlMatch[1]) {
                    window.location.href = urlMatch[1];
                }
            }
            // Se for um botão de aprovar/rejeitar
            else if (target.classList.contains('aprovar-btn') || target.classList.contains('rejeitar-btn')) {
                e.preventDefault();
                const statusSelect = document.querySelector('select[name="status_cotacao"]');
                if (statusSelect) {
                    statusSelect.value = target.classList.contains('aprovar-btn') ? 'Aprovada' : 'Reprovada';
                    showGlobalLoading();
                    cotacaoForm.submit();
                }
            }
        }
    });

    // Intercepta navegação anterior/próxima
    const anteriorLinks = document.querySelectorAll('.anterior-link');
    const proximaLinks = document.querySelectorAll('.proxima-link');
    
    anteriorLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            showGlobalLoading();
            window.location.href = this.href;
        });
    });
    
    proximaLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            showGlobalLoading();
            window.location.href = this.href;
        });
    });

    // Garante que o spinner seja escondido se a página for recarregada
    window.addEventListener('beforeunload', function() {
        showGlobalLoading();
    });
});