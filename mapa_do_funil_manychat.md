# Mapa Mental e Arquitetura do Funil Manychat (Jornada)

Este documento guarda as regras de negócio da automação do Manychat para que a Engenharia de Dados (Dashboard Streamlit) consiga interpretar corretamente os prints de tela sempre que o painel for atualizado.

## 📍 Fase 1: Captação e Escolha de Perfil (Copys V1, V2, V3)
A automação possui 3 portas de entrada (Copys) que terminam sempre na escolha de dois perfis (Técnico ou Empreendedor).
- **V1 (Fluxo Direto):** A mensagem inicial já possui os botões `Técnico` e `Empreendedor`.
  - *Métrica:* Cliques diretos nos perfis.
- **V2 (Fluxo com Nó Extra):** A mensagem inicial pergunta se o usuário quer receber informações.
  - *Botões:* `Receber Informação` e `Bloquear`.
  - *Nó Intermediário (v2):* Só após clicar em "Receber Informação" o lead vê os botões de `Técnico` e `Empreendedor`.
- **V3 (Fluxo com Nó Extra):** Similar à V2.
  - *Botões:* `Acessar Informação` e `Parar Mensagens`.
  - *Nó Intermediário (v3):* Após acessar, o lead escolhe `Técnico` ou `Empreendedor`.

## 📍 Fase 2: Consumo do Vídeo e Direcionamento
Após o lead escolher seu segmento (independente se veio da V1, V2 ou V3), ele cai em duas grandes vias:
- **Via do Técnico:** Recebe o `VÍDEO PARA TÉCNICO (1).mp4`. O botão de ação é `ENTRAR NO GRUPO` (que o manda para o Grupo VIP de Técnicos).
- **Via do Empreendedor:** Recebe o `VÍDEO PARA EMPREENDEDOR (1).mp4`. O botão de ação é `ENTRAR NO GRUPO` (que o manda para o Grupo VIP de Empreendedores).
> **Nota de Dados:** Para o BI, aqui nós somamos todos os envios de vídeo (ex: V1+V2 + V3) para ter o Volume Total de Técnicos e Volume Total de Empreendedores.

## 📍 Fase 3: Repescagem do Grupo VIP
Após o lead receber o botão do Grupo VIP, existe uma verificação de segurança (Follow-up):
- Mensagem: *"Conseguiu entrar no grupo?"*
- Botões: `Consegui` e `Não consegui`.
- **Ação de Salvação:** Se ele clicar em `Não consegui`, o Manychat dispara uma **Mensagem Secundária (Lembrete #10)** contendo apenas o Link bruto do grupo.
> **Nota de Dados:** O Painel de BI rastreia isso como "Gargalo Recuperado" (salva em média 30% dos leads).

## 📍 Fase 4: O Envio da Pesquisa (Engajamento Quente)
Apenas leads que avançaram (estão engajados) recebem a Pesquisa após um delay.
- Disparo do Botão: `Responder Pesquisa`.
- **Atraso Inteligente (5 Minutos):** O sistema checa se ele clicou.
- **Lembrete da Pesquisa:** Se ele não respondeu ou não confirmou, recebe a cobrança.
  - Botões: `Já preenchi!` e `Ainda não`.
- **Repescagem Final da Pesquisa:** Quem clica em `Ainda não` recebe a mensagem de *Não respondeu pesquisa* novamente, com o link para tentar mais uma vez.

## 📍 Fase 5: Conclusão do Funil (Lead Scoring)
Os leads que sobrevivem ao funil da pesquisa (Nó *Respondeu pesquisa*) chegam na escolha final de qualificação:
- Mensagem final: *"posso mandar o link de cada aula direto aqui?"*
- Botões:
  1. `Sim, pode mandar`: Dispara a Ação #5 (Tag: `clicou_botao_receber_link_aulas`). **Esse é o Lead Super Quente.**
  2. `Já estou no grupo`: Dispara a Ação #6 (Tag: `apenas_grupo_...`).
> **Nota de Dados:** O total de cliques no Botão 1 representa a métrica de "O Pote de Ouro" (Retenção Máxima da base) dentro do BI.
