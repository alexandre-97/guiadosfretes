document.addEventListener('DOMContentLoaded', function() {
    // --- ELEMENTOS DA PÁGINA ---
    const filtrarCheckbox = document.getElementById('filtrarStatusCheckbox');
    const anteriorLinks = document.querySelectorAll('.anterior-link');
    const proximaLinks = document.querySelectorAll('.proxima-link');
    // Pega o status da cotação que está sendo exibida NESTA página
    const statusDaPaginaAtual = document.getElementById('statusAtual')?.value.trim() || '';

    // --- FUNÇÃO PRINCIPAL PARA ATUALIZAR OS LINKS ---
    function atualizarLinksDeNavegacao() {
        // Lê o estado do filtro e o VALOR do status salvos no navegador
        const filtroEstaAtivo = localStorage.getItem('filtrarStatus') === 'true';
        const statusSalvoParaFiltrar = localStorage.getItem('filtroStatusValor');

        const aplicarFiltro = (link) => {
            if (!link || !link.href) return;

            // new URL(link.href) é mais seguro para obter a URL completa
            const url = new URL(link.href); 
            
            // Sempre remove o parâmetro antigo para garantir que não haja duplicatas
            url.searchParams.delete('filtrar_status');

            // Adiciona o parâmetro de volta SOMENTE se o filtro estiver ativo e um status foi salvo
            if (filtroEstaAtivo && statusSalvoParaFiltrar) {
                url.searchParams.set('filtrar_status', statusSalvoParaFiltrar);
            }

            // Atualiza o link no botão
            link.href = url.pathname + url.search;
        };

        anteriorLinks.forEach(aplicarFiltro);
        proximaLinks.forEach(aplicarFiltro);
    }

    // --- FUNÇÃO PARA LIDAR COM A MUDANÇA NO CHECKBOX ---
    function aoMudarFiltro() {
        if (filtrarCheckbox.checked) {
            // Se MARCOU o checkbox:
            // 1. Salva que o filtro está 'true'
            localStorage.setItem('filtrarStatus', 'true');
            // 2. Salva o status da PÁGINA ATUAL como o valor a ser usado no filtro
            localStorage.setItem('filtroStatusValor', statusDaPaginaAtual);
        } else {
            // Se DESMARCOU o checkbox:
            // 1. Salva que o filtro está 'false'
            localStorage.setItem('filtrarStatus', 'false');
            // 2. Remove o valor do status salvo para limpar o filtro
            localStorage.removeItem('filtroStatusValor');
        }
        
        // Após mudar a configuração, atualiza os links imediatamente
        atualizarLinksDeNavegacao();
    }

    // --- CÓDIGO QUE EXECUTA QUANDO A PÁGINA CARREGA ---

    // 1. Define o estado do checkbox com base no que está salvo no navegador
    if (localStorage.getItem('filtrarStatus') === 'true') {
        filtrarCheckbox.checked = true;
    }
    
    // 2. Atualiza os links da página assim que ela carrega, usando as configurações salvas
    atualizarLinksDeNavegacao();

    // 3. Adiciona o "ouvinte" para reagir a cliques futuros no checkbox
    filtrarCheckbox?.addEventListener('change', aoMudarFiltro);
});
