/**
 * Função que encontra e configura todos os widgets de prazo na página.
 * É mais robusta pois não assume que os elementos existem globalmente.
 */
const setupAllPrazoWidgets = () => {
    console.log("[Prazo.js] Procurando por widgets de prazo...");

    // Seleciona todos os grupos de input que contêm um botão de prazo
    const widgetGroups = document.querySelectorAll('.input-group');

    let widgetsFound = 0;
    widgetGroups.forEach(group => {
        const incrementBtn = group.querySelector('[class*="increment-prazo-"]');
        const decrementBtn = group.querySelector('[class*="decrement-prazo-"]');
        const inputElement = group.querySelector('input[name*="prazo_"]');

        // Se o grupo não contiver os 3 elementos de um widget, pula para o próximo
        if (!incrementBtn || !decrementBtn || !inputElement) {
            return;
        }
        
        // Verifica se este widget específico já foi inicializado
        if (group.dataset.prazoInitialized) {
            return;
        }
        group.dataset.prazoInitialized = 'true';
        widgetsFound++;

        console.log(`[Prazo.js] Widget encontrado para: ${inputElement.name}. Configurando...`);

        // Lógica específica baseada no nome do campo (coleta ou entrega)
        const config = {
            type: inputElement.name.includes('entrega') ? 'entrega' : 'coleta',
            unit: inputElement.name.includes('entrega') ? 'dias úteis' : 'horas',
        };
        
        setupWidget(inputElement, incrementBtn, decrementBtn, config);
    });

    if (widgetsFound === 0) {
        console.warn("[Prazo.js] Nenhum widget de prazo foi encontrado na página.");
    }
};

/**
 * Configura um único widget de prazo (coleta ou entrega).
 */
const setupWidget = (inputElement, incrementBtn, decrementBtn, config) => {
    
    // Define o valor inicial apenas se estiver vazio
    if (!inputElement.value.trim()) {
        inputElement.value = config.type === 'entrega' ? '1 a 3 dias úteis' : 'Até 24 horas';
    }

    const parseFunctions = {
        entrega: prazo => {
            if (prazo.includes('Até 24 horas')) return -1;
            if (prazo.includes('24 a 48 horas')) return 0;
            const match = prazo.match(/(\d+)/);
            return match ? parseInt(match[0], 10) : 1;
        },
        coleta: prazo => {
            if (prazo.includes('Até 24 horas')) return 1;
            const match = prazo.match(/(\d+)\s*a\s*(\d+)/);
            return match ? (parseInt(match[2], 10) / 24) : 1;
        }
    };

    const formatFunctions = {
        entrega: state => {
            state = Math.max(-1, state);
            if (state === -1) return 'Até 24 horas';
            if (state === 0) return '24 a 48 horas';
            return `${state} a ${state + 2} ${config.unit}`;
        },
        coleta: state => {
            state = Math.max(1, state);
            if (state === 1) return 'Até 24 horas';
            const fim = state * 24;
            return `${fim - 24} a ${fim} ${config.unit}`;
        }
    };

    const handleIncrement = (event) => {
        event.preventDefault();
        let currentState = parseFunctions[config.type](inputElement.value);
        inputElement.value = formatFunctions[config.type](++currentState);
    };

    const handleDecrement = (event) => {
        event.preventDefault();
        let currentState = parseFunctions[config.type](inputElement.value);
        inputElement.value = formatFunctions[config.type](--currentState);
    };

    // Garante que não haja eventos duplicados
    incrementBtn.removeEventListener('click', handleIncrement);
    incrementBtn.addEventListener('click', handleIncrement);
    decrementBtn.removeEventListener('click', handleDecrement);
    decrementBtn.addEventListener('click', handleDecrement);

    console.log(`[Prazo.js] Eventos para ${inputElement.name} anexados com sucesso.`);
};

/**
 * Função que inicia todo o processo.
 * Atrasamos a execução em 150ms para dar tempo ao DOM de ser totalmente renderizado por outros scripts.
 */
const initialize = () => {
    setTimeout(setupAllPrazoWidgets, 150);
};

// --- CONTROLE DE EXECUÇÃO ---
document.addEventListener('DOMContentLoaded', initialize);
document.addEventListener('turbo:load', initialize);
