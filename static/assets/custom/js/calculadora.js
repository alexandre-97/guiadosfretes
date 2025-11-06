document.addEventListener('DOMContentLoaded', function() {
    const calcularBtn = document.getElementById('btnCalcularCubagem');
    const transferirBtn = document.getElementById('btnTransferirCubagem');
    const medidasInput = document.getElementById('medidasInput');
    const resultadoDiv = document.getElementById('resultadoCubagem');
    const observacaoTextarea = document.getElementById('id_observacao');
    const volumesInput = document.getElementById('id_volumes');
    const cubagemInput = document.getElementById('id_cubagem');
    const modalTitle = document.getElementById('cubagemModalLabel');
    const valorPropostaInput = document.getElementById('id_valor_proposta');
    const statusEnvioSelect = document.querySelector('select[name="status_envio"]');

    if (valorPropostaInput && statusEnvioSelect) {
        valorPropostaInput.addEventListener('input', function() {
            // Lógica para ler o valor já formatado
            const unformattedValue = this.value.replace(/\./g, '').replace(',', '.');
            const valorProposta = parseFloat(unformattedValue || 0);
            const statusAtual = statusEnvioSelect.value;

            if (valorProposta > 0 && (statusAtual === 'Falta Cubagem' || statusAtual === 'Falta Preço')) {
                statusEnvioSelect.value = 'Não Enviado';
            }
        });
    }

    let ultimoResultadoFormatado = '';
    let ultimoTotalM3 = 0;

    if (calcularBtn) {
        calcularBtn.addEventListener('click', function() {
            const linhas = medidasInput.value.trim().split('\n');
            let resultadoHtml = '';
            let totalM3 = 0;
            let totalItens = 0;
            let unidadeDetectada = 'Mista';
            let unidadesEncontradas = new Set();

            linhas.forEach(linha => {
                if (linha.trim() === '') return;
                const match = linha.match(/^(?:(?:(\d+)\s*[-*x]\s*)|(?:\((\d+)\)\s*))?(\d+(?:[.,]\d+)?)\s*[*x]\s*(\d+(?:[.,]\d+)?)\s*[*x]\s*(\d+(?:[.,]\d+)?)$/i);

                if (match) {
                    const qtd = parseInt(match[1] || match[2] || volumesInput.value || '1', 10);
                    totalItens += qtd;
                    let dims = [match[3], match[4], match[5]].map(d => parseFloat(d.replace(',', '.')));
                    const maxDim = Math.max(...dims);
                    let divisor = 1;
                    let unidade = 'Metros';
                    if (maxDim > 1000) {
                        divisor = 1000;
                        unidade = 'Milímetros';
                    } else if (maxDim > 10) {
                        divisor = 100;
                        unidade = 'Centímetros';
                    }
                    unidadesEncontradas.add(unidade);
                    const dimsEmMetros = dims.map(d => d / divisor);
                    const volumeItem = dimsEmMetros[0] * dimsEmMetros[1] * dimsEmMetros[2];
                    const volumeTotalLinha = qtd * volumeItem;
                    totalM3 += volumeTotalLinha;
                    // ALTERAÇÃO AQUI: de .toFixed(3) para .toFixed(2)
                    resultadoHtml += `${qtd} UN - ${dimsEmMetros[0].toFixed(2)} x ${dimsEmMetros[1].toFixed(2)} x ${dimsEmMetros[2].toFixed(2)} = ${volumeTotalLinha.toFixed(2)} M³\n`;
                } else {
                    resultadoHtml += `Linha inválida: "${linha}"\n`;
                }
            });

            if (unidadesEncontradas.size === 1) {
                unidadeDetectada = [...unidadesEncontradas][0];
            }
            modalTitle.textContent = `Calculadora de Cubagem (Medidas em ${unidadeDetectada})`;
            // ALTERAÇÃO AQUI: de .toFixed(3) para .toFixed(2)
            resultadoHtml += `\n-------------------------\nTOTAL DE ITENS: ${totalItens}\nTOTAL CUBAGEM: ${totalM3.toFixed(2)} M³`;
            resultadoDiv.textContent = resultadoHtml;
            ultimoResultadoFormatado = resultadoHtml.replace(/TOTAL DE ITENS: .*\n/, '');
            ultimoTotalM3 = totalM3;
            transferirBtn.disabled = false;
        });
    }

    if (transferirBtn) {
        transferirBtn.addEventListener('click', function() {
            const textoAtual = observacaoTextarea.value.trim();
            const separador = textoAtual === '' ? '' : '\n\n';
            observacaoTextarea.value = textoAtual + separador + ultimoResultadoFormatado;

            if (ultimoTotalM3 > 0) {
                // Coloca o valor numérico (com ponto) no campo
                // ALTERAÇÃO AQUI: de .toFixed(3) para .toFixed(2)
                cubagemInput.value = ultimoTotalM3.toFixed(2);

                // *** A CORREÇÃO MÁGICA ESTÁ AQUI ***
                // Dispara um evento 'input' para que o script formatar_campos.js
                // possa detectar a mudança e aplicar a formatação de máscara (ex: 1,234).
                const inputEvent = new Event('input', { bubbles: true, cancelable: true });
                cubagemInput.dispatchEvent(inputEvent);
            }

            const modalInstance = bootstrap.Modal.getInstance(document.getElementById('cubagemModal'));
            modalInstance.hide();
        });
    }
});