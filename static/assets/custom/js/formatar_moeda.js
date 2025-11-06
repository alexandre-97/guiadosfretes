document.addEventListener('DOMContentLoaded', function () {
    const currencyFieldsIds = ['id_valor_mercadoria', 'id_valor_proposta'];
    const form = document.getElementById('cotacaoForm');

    function formatCurrency(input) {
        if (!input || !input.value) return;

        // Remove tudo que não for dígito (inclusive vírgula e ponto)
        let rawValue = input.value.replace(/\D/g, '');

        if (rawValue === '') {
            input.value = '';
            return;
        }

        // Converte para número (centavos)
        const number = parseFloat(rawValue) / 100;

        // Formata para moeda BRL
        input.value = number.toLocaleString('pt-BR', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
    }

    function unformatCurrency(input) {
        if (!input || !input.value) return;
        input.value = input.value.replace(/\./g, '').replace(',', '.');
    }

    currencyFieldsIds.forEach(id => {
        const inputField = document.getElementById(id);

        if (inputField) {
            inputField.type = 'text';
            inputField.setAttribute('inputmode', 'numeric');
            inputField.setAttribute('placeholder', '0,00');

            // Ao digitar, reformatar o valor em tempo real
            inputField.addEventListener('input', () => {
                // Guarda a posição do cursor
                const caret = inputField.selectionStart;

                formatCurrency(inputField);

                // Ajusta o cursor para o final
                inputField.setSelectionRange(inputField.value.length, inputField.value.length);
            });

            // Ao sair do campo, reforça formatação
            inputField.addEventListener('blur', () => {
                formatCurrency(inputField);
            });

            // Ao carregar, formata se houver valor
            formatCurrency(inputField);
        }
    });

    // Antes de enviar, remove a formatação
    if (form) {
        form.addEventListener('submit', function () {
            currencyFieldsIds.forEach(id => {
                const inputField = document.getElementById(id);
                if (inputField) {
                    unformatCurrency(inputField);
                }
            });
        });
    }
});
