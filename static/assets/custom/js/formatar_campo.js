document.addEventListener('DOMContentLoaded', function() {
    // Log para confirmar que o script foi carregado e está executando.
    console.log("✅ formatar_campos.js: Script carregado e pronto.");

    /**
     * CONFIGURAÇÃO DOS CAMPOS PARA FORMATAÇÃO AUTOMÁTICA
     * IDs extraídos do seu arquivo 'editar.html'.
     */
    const camposParaFormatar = [
        { id: 'id_valor_mercadoria', decimais: 2 },
        { id: 'id_valor_proposta', decimais: 2 },
        { id: 'id_peso', decimais: 2 },
        { id: 'id_cubagem', decimais: 3 },
    ];

    const form = document.getElementById('cotacaoForm');

    function formatNumeric(input, casasDecimais) {
        if (!input) return;

        let rawValue = input.value.replace(/\D/g, '');
        if (rawValue === '' || !rawValue) {
            input.value = '';
            return;
        }

        const divisor = Math.pow(10, casasDecimais);
        const numberValue = parseFloat(rawValue) / divisor;

        input.value = numberValue.toLocaleString('pt-BR', {
            minimumFractionDigits: casasDecimais,
            maximumFractionDigits: casasDecimais
        });
    }

    function unformatNumeric(input) {
        if (!input || !input.value) return;
        const unformattedValue = input.value.replace(/\./g, '').replace(',', '.');
        input.value = unformattedValue;
    }

    camposParaFormatar.forEach(config => {
        const inputField = document.getElementById(config.id);

        if (inputField) {
            // Log para cada campo encontrado com sucesso.
            console.log(`🔎 formatar_campos.js: Campo #${config.id} encontrado. Aplicando formatação.`);

            inputField.type = 'text';
            inputField.setAttribute('inputmode', 'numeric');
            const placeholder = '0,' + '0'.repeat(config.decimais);
            inputField.setAttribute('placeholder', placeholder);

            inputField.addEventListener('input', () => formatNumeric(inputField, config.decimais));
            inputField.addEventListener('blur', () => formatNumeric(inputField, config.decimais));
            formatNumeric(inputField, config.decimais);
        } else {
            // Log de erro se um campo configurado não for encontrado no HTML.
            console.error(`❌ formatar_campos.js: Campo com ID #${config.id} não foi encontrado.`);
        }
    });

    if (form) {
        form.addEventListener('submit', function() {
            console.log("🚀 formatar_campos.js: Formulário enviado. Removendo máscaras.");
            camposParaFormatar.forEach(config => {
                const inputField = document.getElementById(config.id);
                if (inputField) {
                    unformatNumeric(inputField);
                }
            });
        });
    }
});
