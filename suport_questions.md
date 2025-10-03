Cenário A: usuário client789 (KYC verificado, transferências ativas, plano Pro, 2FA ativado)

Qual é meu saldo disponível?
O que o agente faz: consulta overview e calcula saldo disponível = balance − holds.
Resposta esperada: Seu saldo é R$ 5.234,50, com R$ 50,00 em retenções. Saldo disponível para uso: R$ 5.184,50.
Ferramentas: get_support_overview(user_id=client789)
2. Tenho algum valor em retenção?

Resposta esperada: Sim, há R$ 50,00 em retenções no momento.
Ferramentas: get_support_overview
3. Minhas transferências estão ativas?

Resposta esperada: Sim, suas transferências estão ativadas e seu KYC está verificado.
Ferramentas: get_support_overview
4. Qual é meu plano?

Resposta esperada: Seu plano atual é Pro.
Ferramentas: get_support_overview
5. Tenho tickets abertos?

Resposta esperada: Não há tickets abertos ou pendentes no momento.
Ferramentas: get_support_overview
6. O 2FA está habilitado?

Resposta esperada: Sim, a autenticação em duas etapas (2FA) está habilitada.
Ferramentas: get_support_overview
7. Qual foi meu último status de login?

Resposta esperada: Seu acesso está habilitado e não há bloqueios; apenas 1 tentativa recente de login falha foi registrada.
Ferramentas: get_support_overview
Cenário B: usuário client123 (KYC pendente, transfer desativada, login desabilitado, 2FA desativado)

Por que não consigo fazer transferências?
Resposta esperada: Suas transferências estão desativadas porque seu KYC está pendente. Motivo: KYC documents pending review. Posso abrir um ticket para priorizar a análise?
Ferramentas: get_support_overview; opcionalmente create_ticket
2. Não consigo entrar na minha conta. Podem ajudar?

Resposta esperada: Seu login está desabilitado no momento, com 5 tentativas falhas recentes e 2FA desativado. Recomendo resetar a senha e habilitar 2FA. Deseja que eu abra um ticket para reativação do acesso?
Ferramentas: get_support_overview; opcionalmente create_ticket
3. Quais tickets abertos eu tenho?

Resposta esperada: Você possui 1 ticket aberto: TCK-1234ABCD — “Transfer blocked”, status: open.
Ferramentas: get_support_overview
4. Qual é meu saldo e retenções?

Resposta esperada: Seu saldo é R$ 123,40 e não há valores em retenção.
Ferramentas: get_support_overview
5. Qual é meu status de verificação (KYC)?

Resposta esperada: Seu KYC está pendente; risco atual 48. Transferências permanecem desativadas até a conclusão do KYC.
Ferramentas: get_support_overview
6. Podem habilitar minhas transferências agora?

Resposta esperada: Não posso habilitar diretamente. É necessário concluir o KYC. Posso abrir um ticket para agilizar a análise?
Ferramentas: get_support_overview; opcionalmente create_ticket
7. Qual é meu plano e posso mudar para Pro?

Resposta esperada: Seu plano atual é Basic. Posso abrir um ticket para solicitar a migração para Pro e instruí-lo sobre os próximos passos.
Ferramentas: get_support_overview; opcionalmente create_ticket
Abertura de tickets (interações que o agente executa muito bem)

Abra um ticket para revisar meu bloqueio de transferências.
Ação: o agente confirma contexto (KYC pendente) e cria ticket.
Resposta esperada: Ticket criado com sucesso: TCK-XXXXXXXX — “Review transfer block”. Nosso time fará contato em breve.
Ferramentas: create_ticket(user_id, subject, description)
2. Quero reativar meu acesso; crie um ticket para desbloqueio de login.

Resposta esperada: Ticket criado: TCK-XXXXXXXX — “Login unlock request”. Instruções de segurança serão enviadas ao seu email.
Ferramentas: create_ticket
3. Preciso atualizar meu email de cadastro.

Resposta esperada: Ticket criado: TCK-XXXXXXXX — “Email update request”. Verificaremos sua identidade e concluiremos a alteração.
Ferramentas: create_ticket
Outras perguntas úteis que o agente consegue responder (PT/EN)

PT: Tenho 2FA ativado? Como posso ativar/desativar?

Resposta: Confirma status atual e envia instruções resumidas. Oferece abrir ticket se precisar de intervenção.
Ferramentas: get_support_overview
EN: What is my current plan and balance?

Resposta: Returns plan and balance in BRL, with holds if any.
Ferramentas: get_support_overview
PT: Existe algum bloqueio na minha conta?

Resposta: Checa login_disabled, transfer_enabled e KYC; explica claramente.
Ferramentas: get_support_overview
EN: Do I have any pending support cases?

Resposta: Lists open/pending tickets with id and subject.
Ferramentas: get_support_overview
PT: Quero abrir um chamado para migrar para o plano Pro.

Resposta: Cria ticket e informa o id.
Ferramentas: create_ticket
