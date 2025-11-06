// Funções utilitárias globais
function getCSRFToken() {
    const csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');
    if (csrfInput?.value) return csrfInput.value;
    
    const cookieValue = document.cookie
        .split('; ')
        .find(row => row.startsWith('csrftoken='))
        ?.split('=')[1];
    
    return cookieValue || '';
}

// Formatação monetária global
function formatCurrency(value) {
    if (!value) return '0,00';
    
    value = value.toString().replace(/\D/g, '');
    value = value.padStart(3, '0');
    return value.replace(/(\d+)(\d{2})$/, '$1,$2')
               .replace(/(\d)(?=(\d{3})+(?!\d))/g, '$1.');
}

// Inicialização básica quando o DOM estiver pronto
document.addEventListener('DOMContentLoaded', function() {
    // Formata campos monetários
    document.querySelectorAll('.money-input').forEach(input => {
        input.value = formatCurrency(input.value);
        
        input.addEventListener('input', function() {
            const cursorPos = this.selectionStart;
            const digitsBefore = this.value.substring(0, cursorPos).replace(/\D/g, '').length;
            
            this.value = formatCurrency(this.value);
            
            let newCursorPos = 0;
            let countedDigits = 0;
            for (let i = 0; i < this.value.length && countedDigits < digitsBefore; i++) {
                if (this.value[i].match(/\d/)) countedDigits++;
                newCursorPos = i + 1;
            }
            
            this.setSelectionRange(newCursorPos, newCursorPos);
        });
    });
});