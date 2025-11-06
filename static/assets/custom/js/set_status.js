// Atribui a função diretamente ao objeto 'window' para garantir que ela seja global
// e acessível pelo atributo 'onclick' dos botões.
window.salvarCotacaoInstantanea = async function(event, status) {
  // Passo 1: Impedir o recarregamento da página. ESSENCIAL.
  event.preventDefault();

  // Passo 2: Selecionar os elementos necessários
  const statusSelect = document.querySelector('select[name="status_cotacao"]');
  const form = document.getElementById('cotacaoForm');
  const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;

  if (!statusSelect || !form || !csrfToken) {
    alert('Erro: Elementos essenciais do formulário não foram encontrados.');
    return;
  }

  // Passo 3: Atualizar o status visualmente
  statusSelect.value = status;
  if (status === 'Aprovada') {
    statusSelect.classList.remove('bg-danger', 'bg-opacity-10');
    statusSelect.classList.add('bg-success', 'bg-opacity-10');
  } else if (status === 'Reprovada') {
    statusSelect.classList.remove('bg-success', 'bg-opacity-10');
    statusSelect.classList.add('bg-danger', 'bg-opacity-10');
  }
  
  // Passo 3.1: Atualizar o "Status Envio" de acordo com a ação
  const statusEnvioSelect = document.querySelector('select[name="status_envio"]');
  if (statusEnvioSelect) {
    if (status === 'Aprovada') {
        statusEnvioSelect.value = 'Enviado Whats + Email';
    } else if (status === 'Reprovada') {
        statusEnvioSelect.value = 'Rejeitada';
    }
  }

  // Passo 4: Preparar os dados do formulário, limpando os valores numéricos
  const formData = new FormData(form);
  const valorMercadoriaInput = form.querySelector('[name="valor_mercadoria"]');
  const valorPropostaInput = form.querySelector('[name="valor_proposta"]');

  if (valorMercadoriaInput && valorMercadoriaInput.value) {
      const valorLimpo = valorMercadoriaInput.value.replace(/\./g, '').replace(',', '.');
      formData.set('valor_mercadoria', valorLimpo);
  }

  if (valorPropostaInput && valorPropostaInput.value) {
      const valorLimpo = valorPropostaInput.value.replace(/\./g, '').replace(',', '.');
      formData.set('valor_proposta', valorLimpo);
  }
  
  // Passo 5: Enviar os dados para o servidor
  try {
    const response = await fetch(form.action, {
      method: 'POST',
      body: formData,
      headers: { 'X-CSRFToken': csrfToken }
    });
    
    if (response.ok) {
      // Exibir notificação de sucesso
      const feedback = document.createElement('div');
      feedback.className = 'position-fixed bottom-0 end-0 p-3';
      feedback.style.zIndex = '11';
      const toast = document.createElement('div');
      toast.className = `toast show align-items-center text-white bg-${status === 'Aprovada' ? 'success' : 'danger'} border-0`;
      toast.innerHTML = `<div class="d-flex"><div class="toast-body">Cotação ${status.toLowerCase()} com sucesso!</div><button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button></div>`;
      feedback.appendChild(toast);
      document.body.appendChild(feedback);
      setTimeout(() => { feedback.remove(); }, 3000);
    } else {
        // Exibir alerta com erros de validação
        const errorHtml = await response.text();
        const parser = new DOMParser();
        const doc = parser.parseFromString(errorHtml, "text/html");
        const errorList = doc.querySelector('.alert-danger ul');
        let errorMessage = 'Erro ao salvar. Verifique os dados.';
        if (errorList) {
            errorMessage = Array.from(errorList.querySelectorAll('li')).map(li => li.textContent).join('\n');
        }
        alert(errorMessage);
    }
  } catch (error) {
    alert('Ocorreu um erro de conexão ao salvar a cotação.');
  }
}
