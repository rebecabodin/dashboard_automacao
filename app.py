import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import datetime
import time
import urllib.parse
from streamlit_autorefresh import st_autorefresh
import requests
import os
from dotenv import load_dotenv

load_dotenv(override=True)

st.set_page_config(page_title="Dashboard Analítico - Lançamento", layout="wide")

@st.cache_data(ttl=30)
def buscar_erros_n8n():
    n8n_url = "https://make2be-editor.ngqhp0.easypanel.host/api/v1/executions?status=error&limit=10"
    api_key = os.getenv("N8N_API_KEY")
    
    if not api_key:
        return "NO_API_KEY"
        
    headers = {
        "X-N8N-API-KEY": api_key,
        "Accept": "application/json"
    }
    
    try:
        response = requests.get(n8n_url, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            # A API nativa do N8N retorna: {"data": [...], "nextCursor": "..."}
            return data.get('data', [])
        return f"HTTP_ERROR_{response.status_code}: {response.text}"
    except Exception as e:
        return f"EXCEPTION: {str(e)}"



def render_alert_boasvindas_duplicados(df_boasvindas):
    import pandas as pd
    import streamlit as st
    st.subheader("🔁 Disparos Duplicados de Boas-Vindas")
    try:
        df_dupe = df_boasvindas.copy()
        df_dupe.columns = df_dupe.columns.str.strip().str.lower()
        
        mask_tel = pd.Series(False, index=df_dupe.index)
        
        if 'lead_phone' in df_dupe.columns:
            df_dupe['tel_limpo'] = df_dupe['lead_phone'].astype(str).str.replace(r'\D', '', regex=True)
            df_valid_tel = df_dupe[df_dupe['tel_limpo'].str.len() > 8]
            dup_tels = df_valid_tel[df_valid_tel.duplicated(subset=['tel_limpo'], keep=False)]['tel_limpo']
            mask_tel = df_dupe['tel_limpo'].isin(dup_tels)
            
        duplicados_geral = df_dupe[mask_tel].copy()
        
        if not duplicados_geral.empty:
            st.error(f"🚨 **ALERTA CRÍTICO:** Encontramos **{len(duplicados_geral)} envios** para telefones repetidos! A automação está mandando a mesma mensagem de Boas-Vindas duas vezes para as mesmas pessoas.")
            
            colunas_exibir = []
            for col in ['created_at', 'lead_name', 'lead_phone', 'status_boas_vindas']:
                if col in duplicados_geral.columns:
                    colunas_exibir.append(col)
                    
            if 'lead_phone' in duplicados_geral.columns:
                duplicados_geral = duplicados_geral.sort_values(by='lead_phone')
                
            st.dataframe(duplicados_geral[colunas_exibir], use_container_width=True, hide_index=True)
            
            st.info("💡 **Ação no N8N:** Adicione um nó de validação 'Google Sheets (Read)' antes do disparo para verificar se a pessoa já recebeu, ou use 'Append or Update' para não acionar webhooks repetidos de sistema externo.")
        else:
            st.success("Tudo limpo! Ninguém recebeu a mensagem de Boas-Vindas duas vezes.")
    except Exception as e:
        st.warning(f"Não foi possível verificar disparos duplicados: {e}")


def get_duplicados(df_captacao):
    import pandas as pd
    df_dupe = df_captacao.copy()
    df_dupe.columns = df_dupe.columns.str.strip().str.lower()
    mask_email = pd.Series(False, index=df_dupe.index)
    mask_tel = pd.Series(False, index=df_dupe.index)
    if 'email' in df_dupe.columns:
        df_dupe['email_limpo'] = df_dupe['email'].astype(str).str.lower().str.strip()
        df_valid_email = df_dupe[df_dupe['email_limpo'].str.len() > 3]
        dup_emails = df_valid_email[df_valid_email.duplicated(subset=['email_limpo'], keep=False)]['email_limpo']
        mask_email = df_dupe['email_limpo'].isin(dup_emails)
    if 'telefone' in df_dupe.columns:
        df_dupe['tel_limpo'] = df_dupe['telefone'].astype(str).str.replace(r'\D', '', regex=True)
        df_valid_tel = df_dupe[df_dupe['tel_limpo'].str.len() > 8]
        dup_tels = df_valid_tel[df_valid_tel.duplicated(subset=['tel_limpo'], keep=False)]['tel_limpo']
        mask_tel = df_dupe['tel_limpo'].isin(dup_tels)
    return df_dupe[mask_email | mask_tel].copy()

def render_alert_duplicados(df_captacao):
    import pandas as pd
    import streamlit as st
    st.subheader("🚷 Cadastros Duplicados na Captação")
    try:
        duplicados_geral = get_duplicados(df_captacao)
        
        if not duplicados_geral.empty:
            st.warning(f"⚠️ Atenção! Encontramos **{len(duplicados_geral)} registros** que indicam repetição de usuário (mesmo E-mail ou Telefone).")
            
            # --- ANÁLISE PROFISSIONAL DE DUPLICATAS ---
            def diagnosticar_duplicata(row, df_full):
                email = row.get('email_limpo', '')
                tel = row.get('tel_limpo', '')
                
                # Checa se o mesmo email tem vários telefones
                if pd.notna(email) and email != '':
                    mesmo_email = df_full[df_full['email_limpo'] == email]
                    if len(mesmo_email['tel_limpo'].unique()) > 1:
                        return "⚠️ E-mail Compartilhado (Múltiplos Usuários ou Teste)"
                        
                # Checa se o mesmo telefone tem vários emails
                if pd.notna(tel) and tel != '':
                    mesmo_tel = df_full[df_full['tel_limpo'] == tel]
                    if len(mesmo_tel['email_limpo'].unique()) > 1:
                        return "⚠️ Mesmo Telefone p/ E-mails Diferentes (Erro Digitação)"
                        
                return "🔄 Cadastro Idêntico (Duplo Clique)"
                
            duplicados_geral['diagnóstico'] = duplicados_geral.apply(lambda r: diagnosticar_duplicata(r, duplicados_geral), axis=1)
            
            colunas_exibir = []
            for col in ['data', 'primeiro_nome', 'email', 'telefone', 'diagnóstico']:
                if col in duplicados_geral.columns:
                    colunas_exibir.append(col)
                    
            if 'email' in duplicados_geral.columns:
                duplicados_geral = duplicados_geral.sort_values(by=['email', 'telefone'])
                
            df_display = duplicados_geral[colunas_exibir].copy()
            # Padronizando os nomes das colunas para combinar com o alerta de erros (padrão cliente)
            df_display = df_display.rename(columns={
                'data': 'Data/Hora',
                'primeiro_nome': 'Nome',
                'email': 'E-mail',
                'telefone': 'Telefone',
                'diagnóstico': 'Diagnóstico'
            })
                
            st.dataframe(df_display, use_container_width=True, hide_index=True)
        else:
            st.success("Nenhum lead duplicado! A base de entrada está totalmente higienizada.")
    except Exception as e:
        st.warning(f"Não foi possível verificar leads duplicados: {e}")


title_placeholder = st.empty()
subtitle_placeholder = st.empty()

# --- CONTROLE DE ATUALIZAÇÃO ---
st.sidebar.title("⚙️ Configurações")
pausar_atualizacao = st.sidebar.checkbox("⏸️ Pausar Atualização Automática", value=False, help="Marque para impedir recarregamentos e ler em paz.")

if not pausar_atualizacao:
    # Atualiza a cada 10 segundos sem pular a tela pro topo!
    count = st_autorefresh(interval=10000, key="f1_refresh")
    hora_br = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-3))).strftime('%H:%M:%S')
    st.caption(f"🔄 Última atualização: **{hora_br}** (Atualiza sozinho a cada 10s sem pular a tela)")
else:
    hora_br = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-3))).strftime('%H:%M:%S')
    st.caption(f"⏸️ **Modo Leitura Ativado.** A tela parou de atualizar. Última checagem: {hora_br}")

@st.cache_data(ttl=1200)
def calcular_leads_perdidos_20m(df_cap, df_bv):
    import pandas as pd
    if 'email_limpo' in df_cap.columns and 'lead_email' in df_bv.columns:
        emails_processados = set(df_bv['lead_email'])
        return df_cap[~df_cap['email_limpo'].isin(emails_processados)]
    return pd.DataFrame()

@st.cache_data(ttl=10) # O cache expira a cada 10 segundos
def carregar_dados():
    try:
        import urllib.parse
        
        sheet_id = "1Sd7-iunFKcgpuexlWMC_IC3JO1pcR2x14utRYPpKggs"
        
        aba_captacao = urllib.parse.quote("📈 Captação")
        aba_boasvindas = urllib.parse.quote("Boas-vindas")
        aba_grupo_tec = urllib.parse.quote("📈 Grupos - Técnico")
        aba_grupo_emp = urllib.parse.quote(" 📈 Grupos - Empreendedores")
        aba_pagina32 = urllib.parse.quote("Página32")
        
        # O "&_t=..." força o Google Sheets a entregar a versão mais nova ignorando o próprio cache
        timestamp = int(time.time())
        url_captacao = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={aba_captacao}&_t={timestamp}"
        url_boasvindas = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={aba_boasvindas}&_t={timestamp}"
        url_grupo_tec = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={aba_grupo_tec}&_t={timestamp}"
        url_grupo_emp = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={aba_grupo_emp}&_t={timestamp}"
        url_pagina32 = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={aba_pagina32}&_t={timestamp}"
        
        df_captacao = pd.read_csv(url_captacao)
        df_boasvindas = pd.read_csv(url_boasvindas)
        df_grupo_tec = pd.read_csv(url_grupo_tec)
        df_grupo_emp = pd.read_csv(url_grupo_emp)
        df_pagina32 = pd.read_csv(url_pagina32, on_bad_lines="skip")
        
        return df_captacao, df_boasvindas, df_grupo_tec, df_grupo_emp, df_pagina32
    except Exception as e:
        st.error(f"Erro ao ler o Google Sheets: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

df_captacao, df_boasvindas, df_grupo_tec, df_grupo_emp, df_pagina32 = carregar_dados()

# --- CONSOLIDAÇÃO DE DISPAROS DE BOAS-VINDAS ---
if not df_boasvindas.empty:
    df_boasvindas['origem_disparo'] = 'Boas-Vindas'
if not df_pagina32.empty:
    df_pagina32_renamed = df_pagina32.rename(columns={
        'data e hora': 'created_at',
        'nome': 'lead_name',
        'telefone': 'lead_phone'
    })
    df_pagina32_renamed['origem_disparo'] = 'Página32'
else:
    df_pagina32_renamed = pd.DataFrame()

if not df_boasvindas.empty and not df_pagina32_renamed.empty:
    df_disparos_consolidados = pd.concat([df_boasvindas, df_pagina32_renamed], ignore_index=True)
elif not df_boasvindas.empty:
    df_disparos_consolidados = df_boasvindas.copy()
else:
    df_disparos_consolidados = pd.DataFrame()


if not df_captacao.empty:
    # --- SISTEMA DE ACESSO ADMIN (URL SECRETA) ---
    is_admin = st.query_params.get("admin") == "mda2026"
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🧭 Navegação")
    
    if is_admin:
        opcoes_menu = [
            '📊 Visão Principal', 
            '🎯 Raio-X Didático CPLs',
            '🕸️ Funil Manychat (WPP)', 
            '🚨 Monitoramento Avançado', 
            '🧠 Plano de Ação', 
            '📊 Pesquisa (WordCloud)', 
            '1️⃣ CPLs (Análise e Funil)',
            '2️⃣ Vendas e Carrinho',
            '5️⃣ E-mails'
        ]
    else:
        opcoes_menu = ['📊 Visão Principal', '🎯 Raio-X Didático CPLs', '🕸️ Funil Manychat (WPP)']
        
    menu_selecionado = st.sidebar.radio("Ir para:", opcoes_menu, label_visibility="collapsed")
    
    # Define o título dinamicamente com base na aba selecionada
    if menu_selecionado == '🎯 Raio-X Didático CPLs':
        title_placeholder.title("🎯 Raio-X Didático das CPLs")
        subtitle_placeholder.markdown("História dos dados explicada passo a passo — 100% auditada direto dos fluxos do Manychat.")
    elif menu_selecionado == '1️⃣ CPLs (Análise e Funil)':
        title_placeholder.title("📊 Dashboard Executivo (Tração, CPLs e Avisos)")
        subtitle_placeholder.markdown("Acompanhamento em tempo real do funil de conversão, engajamento de aulas e perfil dos leads.")
    else:
        title_placeholder.title("📊 Dashboard de Lançamento e Boas-Vindas")
        subtitle_placeholder.markdown("Acompanhamento em tempo real de conversão e perfil dos leads capturados.")

    # --- PROCESSAMENTO DOS KPIs GLOBAIS ---
    total_capturados = len(df_captacao) + len(df_pagina32)
    total_automação = len(df_disparos_consolidados)

    # Métrica de Entregues: leads que possuem a tag específica do evento atual na coluna tag_atual ou status_boas_vindas
    mask_sucesso = pd.Series(False, index=df_disparos_consolidados.index)
    if 'tag_atual' in df_disparos_consolidados.columns:
        mask_sucesso = mask_sucesso | df_disparos_consolidados['tag_atual'].astype(str).str.contains('lc7_mde_ago26_boas_vindas_inicial_enviada', case=False, na=False)
    if 'status_boas_vindas' in df_disparos_consolidados.columns:
        mask_sucesso = mask_sucesso | df_disparos_consolidados['status_boas_vindas'].astype(str).str.contains('lc7_mde_ago26_boas_vindas_inicial_enviada', case=False, na=False)
    
    sucesso_envio = len(df_disparos_consolidados[mask_sucesso])

    # Métrica de Erros: leads que possuem a sinalização exata de 'erro' na coluna status_boas_vindas
    if 'status_boas_vindas' in df_disparos_consolidados.columns:
        erros = len(df_disparos_consolidados[df_disparos_consolidados['status_boas_vindas'].astype(str).str.strip().str.lower() == 'erro'])
    else:
        erros = 0
    taxa_entrega = (sucesso_envio / total_automação) * 100 if total_automação > 0 else 0

    custo_por_mensagem = 0.01
    custo_total = sucesso_envio * custo_por_mensagem

    # --- SCORECARDS (Métricas de Topo) ---
    total_duplicados = len(get_duplicados(df_captacao))
    
    # Limpeza Global para cálculos rigorosos de Quebra
    df_captacao_clean = df_captacao.copy()
    df_boasvindas_clean = df_boasvindas.copy()
    df_captacao_clean.columns = df_captacao_clean.columns.str.strip().str.lower()
    df_boasvindas_clean.columns = df_boasvindas_clean.columns.str.strip().str.lower()
    
    if 'email' in df_captacao_clean.columns:
        df_captacao_clean['email_limpo'] = df_captacao_clean['email'].astype(str).str.lower().str.strip()
    else:
        df_captacao_clean['email_limpo'] = ''
        
    if 'lead_email' in df_boasvindas_clean.columns:
        df_boasvindas_clean['lead_email'] = df_boasvindas_clean['lead_email'].astype(str).str.lower().str.strip()
    else:
        df_boasvindas_clean['lead_email'] = ''
        
    df_falhas_global = calcular_leads_perdidos_20m(df_captacao_clean, df_boasvindas_clean)
    leads_perdidos = len(df_falhas_global)

    if menu_selecionado == '📊 Visão Principal':
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        col1.metric("Leads Capturados", f"{total_capturados}", help="Volume bruto de cadastros registrados na base principal (Landing Page).")
        col2.metric("Duplicados", f"{total_duplicados}", delta_color="inverse", help="Cadastros suspeitos de repetição (mesmo e-mail ou telefone).")
        col3.metric("Enviados p/ Automação", f"{total_automação}", help="Leads inseridos na esteira de WhatsApp.")
        col4.metric("Entregues", f"{sucesso_envio}", f"{taxa_entrega:.1f}%", help="Volume absoluto e percentual de leads que receberam a mensagem com sucesso (Taxa de Entrega).")
        col5.metric("Custo Meta", f"US$ {custo_total:.2f}", delta_color="off", help="Projeção de custo operacional (API Oficial).")
        col6.metric("Erros Envio", f"{erros}", delta_color="inverse", help="Volume de falhas de entrega (Motivos técnicos).")
    

    

        # --- ANÁLISE DE CONVERSÃO WPP ---
        if total_capturados > 0:
            conversao_wpp = (sucesso_envio / total_capturados) * 100
        else:
            conversao_wpp = 0
        
        st.info(f"**💡 Taxa de Conversão Captação ➡️ WhatsApp:** {conversao_wpp:.1f}% dos leads receberam a mensagem com sucesso.")

        st.divider()

        col_charts1, col_charts2 = st.columns(2)
    
        with col_charts1:
            with st.container(border=True):
                st.subheader("Funil de Engajamento")
                fig_funnel = go.Figure(go.Funnel(
                    y=['Capturados (Form)', 'Enviados p/ Automação', 'Mensagem Entregue'],
                    x=[total_capturados, total_automação, sucesso_envio],
                    textinfo="value+percent initial",
                    marker={"color": ["#1f77b4", "#ff7f0e", "#2ca02c"]}
                ))
                fig_funnel.update_layout(margin=dict(l=20, r=20, t=20, b=20), height=380)
                st.plotly_chart(fig_funnel, use_container_width=True)

        with col_charts2:
            with st.container(border=True):
                st.subheader("Distribuição de Perfil", help="Métrica computada em tempo real via webhook a partir das interações ativas dos usuários no fluxo de conversação (Manychat).")
            
                if 'perfil' in df_boasvindas.columns:
                    # Limpar e formatar o texto
                    df_perfil_clean = df_boasvindas[df_boasvindas['perfil'].notna()].copy()
                    df_perfil_clean['perfil'] = df_perfil_clean['perfil'].astype(str).str.strip().str.capitalize()
                    
                    df_perfil = df_perfil_clean['perfil'].value_counts().reset_index()
                    df_perfil.columns = ['Perfil', 'Quantidade']
                    
                    total_perfis = df_perfil['Quantidade'].sum()
                    
                    # Extraindo os valores para as métricas isoladas
                    tec_count = df_perfil[df_perfil['Perfil'].str.contains('Tecnico|Técnico', case=False, na=False)]['Quantidade'].sum()
                    emp_count = df_perfil[df_perfil['Perfil'].str.contains('Empreendedor', case=False, na=False)]['Quantidade'].sum()
                    
                    # Mapeamento estrito de cores
                    cores_map = {
                        'Tecnico': '#FF9800',      # Laranja
                        'Técnico': '#FF9800',      # Laranja (com acento, por segurança)
                        'Empreendedor': '#9b59b6'  # Roxo
                    }
                    cores_lista = [cores_map.get(str(p), '#bdc3c7') for p in df_perfil['Perfil']]
                    
                    fig_pie = go.Figure(go.Pie(
                        labels=df_perfil['Perfil'],
                        values=df_perfil['Quantidade'],
                        hole=0.65,
                        textinfo='percent',
                        textposition='inside',
                        insidetextfont=dict(size=16, color='white'),
                        insidetextorientation='horizontal',
                        marker=dict(colors=cores_lista)
                    ))
                    fig_pie.update_layout(
                        margin=dict(l=10, r=10, t=10, b=30), 
                        height=280, 
                        showlegend=True,
                        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
                        annotations=[dict(text=f'<b>{total_perfis}</b><br>Total', x=0.5, y=0.5, font_size=20, showarrow=False)]
                    )
                    st.plotly_chart(fig_pie, use_container_width=True)

                    # --- UX: Métricas no rodapé do cartão atuando como âncora de peso visual ---
                    st.write("") # Espaçamento
                    cp1, cp2, cp3 = st.columns(3)
                    cp1.metric("Respostas", total_perfis)
                    cp2.metric("Técnicos", tec_count)
                    cp3.metric("Empreendedores", emp_count)
                else:
                    st.warning("Coluna 'perfil' não encontrada na planilha de Boas-vindas.")
            


        # --- GRUPOS DE WHATSAPP ---
        st.divider()
        st.header("👥 Funil de Grupos do WhatsApp")
        st.markdown("Acompanhe o fluxo de pessoas nos seus grupos. O **Total de Registros** mostra todas as movimentações (exatamente as linhas da sua planilha). A partir disso, separamos quem **Entrou**, quem **Saiu**, e qual é o **Total Final** (pessoas ativas agora).")
    
        # Função auxiliar para calcular métricas de grupo com o total de registros
        def calcular_metricas_grupo(df):
            if df.empty or 'Saiu' not in df.columns:
                return 0, 0, 0, 0, 0
            total_linhas = len(df)
            entraram = len(df[df['Saiu'] == 'ENTROU'])
            sairam = len(df[df['Saiu'] == 'SAIU'])
            ficaram = entraram - sairam
            retencao = (ficaram / entraram) * 100 if entraram > 0 else 0
            return total_linhas, entraram, sairam, ficaram, retencao

        # Grupo Técnico
        linhas_t, entraram_t, sairam_t, ficaram_t, ret_t = calcular_metricas_grupo(df_grupo_tec)
        # Grupo Empreendedor
        linhas_e, entraram_e, sairam_e, ficaram_e, ret_e = calcular_metricas_grupo(df_grupo_emp)

        total_entraram_grupos = entraram_t + entraram_e
        conversao_grupos = (total_entraram_grupos / total_capturados * 100) if total_capturados > 0 else 0
        st.info(f"**🎯 Resumo Global:** Dos **{total_capturados}** leads capturados, **{total_entraram_grupos}** decidiram entrar nos grupos (**{conversao_grupos:.1f}% de conversão**).")
    
        st.write("") # Espaçamento


        # Criando colunas para a exibição Premium
        col_g1, col_g2 = st.columns(2)
    
        with col_g1:
            with st.container(border=True):
                st.markdown("### 🟧 LC7 - Técnico")
                st.markdown(f"**Taxa de Retenção:** {ret_t:.1f}%", help="Indicador percentual de permanência ativa nos grupos de WhatsApp. Avalia o nível de retenção e engajamento específico do público Técnico.")
                # Barra de progresso (garantindo que fique entre 0.0 e 1.0)
                st.progress(min(max(ret_t / 100, 0.0), 1.0))
            
                st.write("") # Espaço
            
                cg1, cg2, cg3 = st.columns(3)
                cg1.metric("✅ Entraram", entraram_t)
                cg2.metric("❌ Saíram", sairam_t)
                cg3.metric("🎯 Ativos", ficaram_t, f"{ret_t:.1f}%", delta_color="normal")
            
                st.caption(f"*(Histórico de registros na planilha: {linhas_t})*")
            
        with col_g2:
            with st.container(border=True):
                st.markdown("### 🟪 LC7 - Empreendedor")
                st.markdown(f"**Taxa de Retenção:** {ret_e:.1f}%", help="Indicador percentual de permanência ativa nos grupos de WhatsApp. Avalia o nível de retenção e engajamento específico do público Empreendedor.")
                st.progress(min(max(ret_e / 100, 0.0), 1.0))
            
                st.write("") # Espaço
            
                ce1, ce2, ce3 = st.columns(3)
                ce1.metric("✅ Entraram", entraram_e)
                ce2.metric("❌ Saíram", sairam_e)
                ce3.metric("🎯 Ativos", ficaram_e, f"{ret_e:.1f}%", delta_color="normal")
            
                st.caption(f"*(Histórico de registros na planilha: {linhas_e})*")

        st.write("") # Espaço
    
        # INSIGHT DINÂMICO DE RETENÇÃO
        if ret_t > ret_e:
            vencedor = "Técnico"
            diferenca = ret_t - ret_e
        elif ret_e > ret_t:
            vencedor = "Empreendedor"
            diferenca = ret_e - ret_t
        else:
            vencedor = "Empate"
            diferenca = 0
        
        if vencedor != "Empate":
            st.info(f"💡 **Análise Estratégica:** A segmentação de público nos permite identificar o comportamento exato de cada perfil. Atualmente, o grupo **{vencedor}** apresenta uma taxa de retenção **{diferenca:.1f}% superior**. Esse indicador é valioso, pois mostra claramente qual audiência está mais engajada e propensa a converter nas próximas etapas do funil.")
        else:
            st.info(f"💡 **Análise Estratégica:** A segmentação de público nos permite identificar o comportamento exato de cada perfil. Neste momento, observamos que ambos os grupos apresentam taxas de retenção idênticas, demonstrando um nível de engajamento perfeitamente equilibrado entre as duas audiências.")

        st.divider()
    
        # --- TABELA DE ERROS E DETALHES ---
        st.subheader("⚠️ Análise de Erros de Envio (Boas-Vindas)")
    
        with st.expander("ℹ️ Clique aqui para entender os motivos de erro"):
            st.markdown("""
            * **Incompleto ou DDI Inválido:** Faltam números (ex: o lead só digitou o DDD).
            * **Telefone Fixo ou Falta Nono Dígito:** O número parece ser um telefone fixo ou faltou digitar o `9` na frente.
            * **Provável Número Falso:** O lead digitou uma sequência repetida (ex: 9999-9999).
            * **S/ WhatsApp ou Bloqueio da Meta:** O número é um celular válido e perfeito, mas o chip não possui conta ativa de WhatsApp, ou o lead bloqueou a empresa previamente.
            """)
        
        df_erros = df_disparos_consolidados[df_disparos_consolidados['status_boas_vindas'].astype(str).str.strip().str.lower() == 'erro'].copy()
    
        if not df_erros.empty:
            # Função para diagnosticar o erro baseado no número
            def classificar_erro_telefone(telefone):
                try:
                    # Trata números lidos como float pelo pandas (ex: 5.511999e+12)
                    tel_str = str(telefone).split('.')[0]
                
                    # Regras de negócio
                    if len(tel_str) < 12 or len(tel_str) > 14:
                        return "Incompleto ou DDI Inválido"
                    elif "999999" in tel_str or "123456" in tel_str or "000000" in tel_str:
                        return "Provável Número Falso (Lead Curioso)"
                    elif len(tel_str) == 12:
                        return "Telefone Fixo ou Falta Nono Dígito"
                    else:
                        return "S/ WhatsApp ou Bloqueio da Meta"
                except:
                    return "Erro de Formatação"

            df_erros['diagnostico_do_erro'] = df_erros['lead_phone'].apply(classificar_erro_telefone)
        
            st.warning(f"Encontramos {len(df_erros)} leads com erro no envio. Análise inteligente aplicada.")
            
            
            # Garante que origem_disparo exista
            if 'origem_disparo' not in df_erros.columns:
                df_erros['origem_disparo'] = 'Boas-Vindas'
            if 'utm_source' not in df_erros.columns:
                df_erros['utm_source'] = 'N/A'
                
            df_erros_display = df_erros[['created_at', 'lead_name', 'lead_phone', 'diagnostico_do_erro', 'origem_disparo', 'utm_source']].copy()
            df_erros_display = df_erros_display.rename(columns={
                'created_at': 'Data/Hora',
                'lead_name': 'Nome',
                'lead_phone': 'Telefone',
                'diagnostico_do_erro': 'Diagnóstico do Erro',
                'origem_disparo': 'Aba da Planilha',
                'utm_source': 'Origem (UTM)'
            })
            
            st.dataframe(
                df_erros_display,
                use_container_width=True,
                hide_index=True
            )
        else:
            st.success("Nenhum erro de envio registrado!")
        
        st.divider()
        render_alert_duplicados(df_captacao)
        
        # --- O DNA DO LEAD ---
        st.divider()
        st.header("🧬 O DNA do Lead (Análise Demográfica e Tráfego)")
        st.markdown("Análise estratégica de aquisição e perfil da audiência: mapeamento de procedência do tráfego (UTMs), distribuição geográfica nacional via dados de WhatsApp (DDD) e volumetria de cadastro por faixa horária.")
    
        dna1, dna2, dna3 = st.columns([1, 1, 1])
    
        with dna1:
            with st.container(border=True):
                st.subheader("📍 Mapa de Calor (Top 5 DDDs)")
                # Extrair DDD do telefone
                def extrair_ddd(telefone):
                    try:
                        # O número costuma vir como float (ex: 5.511999e+12) ou string
                        tel_str = str(telefone).split('.')[0].strip().replace('+', '')
                        # Verifica se é do Brasil (55) e tem tamanho de celular com DDD (12 ou 13 dígitos com o 55)
                        if tel_str.startswith('55') and len(tel_str) >= 12:
                            return tel_str[2:4] # Pega o 3º e 4º dígito
                        return "Desconhecido"
                    except:
                        return "Desconhecido"
                    
                df_boasvindas['ddd'] = df_boasvindas['lead_phone'].apply(extrair_ddd)
                df_ddd = df_boasvindas[df_boasvindas['ddd'] != 'Desconhecido']['ddd'].value_counts().reset_index().head(5)
                df_ddd.columns = ['DDD', 'Leads']
            
                # Mapeamento básico de alguns DDDs para Estados (para ficar mais rico)
                mapa_ddd = {
                    '11': 'SP (Capital)', '21': 'RJ (Capital)', '31': 'MG (BH)', '41': 'PR (Curitiba)',
                    '51': 'RS (Poa)', '61': 'DF (Brasília)', '71': 'BA (Salvador)', '81': 'PE (Recife)',
                    '85': 'CE (Fortaleza)', '62': 'GO (Goiânia)', '19': 'SP (Campinas)', '82': 'AL (Maceió)',
                    '83': 'PB (João Pessoa)', '84': 'RN (Natal)', '91': 'PA (Belém)', '92': 'AM (Manaus)',
                    '12': 'SP (S. José)', '13': 'SP (Santos)', '15': 'SP (Sorocaba)', '16': 'SP (Rib. Preto)',
                    '27': 'ES (Vitória)', '48': 'SC (Floripa)', '47': 'SC (Joinville)', '65': 'MT (Cuiabá)'
                }
                df_ddd['Região'] = df_ddd['DDD'].map(mapa_ddd).fillna('Outros')
                df_ddd['Rotulo'] = df_ddd['Região'] + " (DDD " + df_ddd['DDD'] + ")"
            
                if not df_ddd.empty:
                    fig_ddd = px.bar(df_ddd, y='Rotulo', x='Leads', orientation='h', text='Leads',
                                     color_discrete_sequence=['#2980b9'])
                    fig_ddd.update_layout(
                        margin=dict(l=0, r=20, t=20, b=20), height=320, 
                        yaxis_categoryorder='total ascending',
                        xaxis=dict(showgrid=False, showticklabels=False, title=None),
                        yaxis=dict(title=None)
                    )
                    st.plotly_chart(fig_ddd, use_container_width=True)
                else:
                    st.info("Aguardando leads válidos para mapear o DDD.")

        with dna2:
            with st.container(border=True):
                st.subheader("⏰ Relógio de Engajamento")
                try:
                    # Limpar a data e converter created_at para datetime
                    data_limpa = df_boasvindas['created_at'].astype(str).str.replace(',', '')
                    df_boasvindas['hora_cadastro'] = pd.to_datetime(data_limpa, dayfirst=True, errors='coerce').dt.hour
                    df_hora = df_boasvindas['hora_cadastro'].dropna().value_counts().reset_index()
                    df_hora.columns = ['Hora do Dia', 'Leads']
                    df_hora = df_hora.sort_values('Hora do Dia')
                
                    # Formatar para string amigável (ex: "14h")
                    df_hora['Hora do Dia'] = df_hora['Hora do Dia'].apply(lambda x: f"{int(x)}h")
                
                    if not df_hora.empty:
                        fig_hora = px.bar(df_hora, x='Hora do Dia', y='Leads', text='Leads', color_discrete_sequence=['#e74c3c'])
                        fig_hora.update_layout(
                            margin=dict(l=0, r=20, t=20, b=20), height=320, 
                            xaxis=dict(showgrid=False, title=None), 
                            yaxis=dict(showgrid=False, showticklabels=False, title=None)
                        )
                        st.plotly_chart(fig_hora, use_container_width=True)
                    else:
                        st.info("Aguardando dados de horário.")
                except Exception as e:
                    st.warning("Não foi possível processar os horários.")

        with dna3:
            with st.container(border=True):
                st.subheader("🎯 Top Campanhas (UTMs)")
                if 'utm_campaign' in df_boasvindas.columns:
                    # Filtrar vazios
                    df_utm = df_boasvindas[df_boasvindas['utm_campaign'].notna() & (df_boasvindas['utm_campaign'] != '')]
                    if not df_utm.empty:
                        df_utm_counts = df_utm['utm_campaign'].value_counts().reset_index().head(5)
                        df_utm_counts.columns = ['Campanha', 'Leads']
                    
                        # Encurtar nomes de campanha muito grandes
                        df_utm_counts['Campanha'] = df_utm_counts['Campanha'].apply(lambda x: str(x)[:20] + "..." if len(str(x)) > 20 else str(x))
                    
                        fig_utm = px.bar(df_utm_counts, y='Campanha', x='Leads', orientation='h', text='Leads', color_discrete_sequence=['#16a085'])
                        fig_utm.update_layout(
                            margin=dict(l=0, r=20, t=20, b=20), height=320, 
                            yaxis_categoryorder='total ascending',
                            xaxis=dict(showgrid=False, showticklabels=False, title=None),
                            yaxis=dict(title=None)
                        )
                        st.plotly_chart(fig_utm, use_container_width=True)
                    else:
                        st.info("Nenhuma UTM de Campanha capturada ainda.")
                else:
                    st.warning("Coluna 'utm_campaign' não encontrada.")



    elif menu_selecionado == '🚨 Monitoramento Avançado':
        if True:
            st.header("🚨 Monitoramento Avançado (Analista)")
            st.markdown("Bem-vinda ao painel de infraestrutura técnica. Estes dados **não são visíveis** para o cliente.")
            
            # --- ALERTA 1: N8N NODE FAILURES ---
            st.subheader("💥 Monitoramento do Servidor N8N")
            erros_n8n = buscar_erros_n8n()
            if isinstance(erros_n8n, str):
                st.warning(f"Falha na conexão com N8N: {erros_n8n}")
            elif erros_n8n is not None:
                if len(erros_n8n) > 0:
                    st.error(f"⚠️ Atenção! Encontramos **{len(erros_n8n)}** execuções recentes com erro no N8N.")
                    
                    df_n8n = pd.DataFrame(erros_n8n)
                    if 'startedAt' in df_n8n.columns:
                        df_n8n['Data/Hora'] = pd.to_datetime(df_n8n['startedAt']).dt.strftime('%d/%m/%Y %H:%M:%S')
                    if 'workflowId' in df_n8n.columns:
                        df_n8n['Workflow ID'] = df_n8n['workflowId']
                    if 'mode' in df_n8n.columns:
                        df_n8n['Gatilho'] = df_n8n['mode'].str.title()
                        
                    # Criar a URL mágica do N8N
                    if 'id' in df_n8n.columns and 'workflowId' in df_n8n.columns:
                        df_n8n['Ver no N8N'] = "https://make2be-editor.ngqhp0.easypanel.host/workflow/" + df_n8n['workflowId'] + "/executions/" + df_n8n['id']
                        
                    colunas = ['Data/Hora', 'Workflow ID', 'Gatilho', 'status', 'Ver no N8N']
                    colunas_existentes = [c for c in colunas if c in df_n8n.columns]
                    
                    st.dataframe(
                        df_n8n[colunas_existentes], 
                        use_container_width=True, 
                        hide_index=True,
                        column_config={
                            "Ver no N8N": st.column_config.LinkColumn(
                                "Investigar Erro 🔗",
                                display_text="Abrir Canvas",
                                help="Clique para abrir o N8N exatamente no nó que falhou."
                            )
                        }
                    )
                else:
                    st.success("Tudo perfeito! Nenhum fluxo de erro encontrado no N8N.")
            else:
                st.warning("Não foi possível conectar à API do N8N.")

            st.divider()

            # --- ALERTA 2: RISCO DA META ---
            st.subheader("⚠️ Risco de Banimento (Meta)")
            if taxa_entrega < 80 and total_automação > 10:
                st.error(f"🚨 **ALERTA CRÍTICO:** Sua taxa de entrega de WhatsApp está em {taxa_entrega:.1f}%. A Meta pode considerar isso como Spam e bloquear o número.")
            else:
                st.success(f"✅ **Taxa Saudável:** A taxa de entrega está segura em {taxa_entrega:.1f}%.")

            st.divider()

            # --- ALERTA 3: GARGALO DE PROCESSAMENTO ---
            st.subheader("⏳ Gargalo de Automação (Tempo de Resposta)")
            try:
                df_merge = pd.merge(df_captacao_clean, df_boasvindas_clean, left_on='email_limpo', right_on='lead_email', how='inner', suffixes=('_cap', '_bv'))
                
                if not df_merge.empty and 'data' in df_merge.columns and 'created_at' in df_merge.columns:
                    df_merge['tempo_cap'] = pd.to_datetime(df_merge['data'].astype(str).str.replace(',', ''), dayfirst=True, errors='coerce')
                    df_merge['tempo_bv'] = pd.to_datetime(df_merge['created_at'].astype(str).str.replace(',', ''), dayfirst=True, errors='coerce')
                    
                    df_merge['demora_segundos'] = (df_merge['tempo_bv'] - df_merge['tempo_cap']).dt.total_seconds()
                    media_demora = df_merge['demora_segundos'].mean()
                    
                    if pd.notna(media_demora):
                        if media_demora > 180: # mais de 3 minutos
                            st.warning(f"🐢 **Gargalo Detectado:** O fluxo N8N/Manychat está demorando em média {media_demora/60:.1f} minutos para entregar a mensagem após o cadastro.")
                        else:
                            st.success(f"⚡ **Processamento Rápido:** Tempo médio de resposta da automação: {media_demora:.1f} segundos.")
                    else:
                        st.info("Aguardando mais dados precisos de horário para calcular o tempo.")
                else:
                    st.info("Dados insuficientes para cruzar o tempo de processamento.")
            except Exception as e:
                st.warning(f"Não foi possível calcular o tempo de processamento: {e}")

            st.divider()

            # --- ALERTA DE INFRAESTRUTURA: QUALIDADE DE RASTREAMENTO (UTMs) ---
            st.subheader("🔗 Qualidade de Rastreamento (UTMs Vazias)")
            try:
                total_leads_cap = len(df_captacao_clean)
                if total_leads_cap > 0 and 'utm_source' in df_captacao_clean.columns:
                    # Verifica leads onde utm_source está vazio ou nulo
                    leads_sem_utm = df_captacao_clean['utm_source'].isna().sum() + (df_captacao_clean['utm_source'] == '').sum()
                    taxa_sem_utm = (leads_sem_utm / total_leads_cap) * 100
                    
                    if taxa_sem_utm > 15:
                        st.warning(f"🕵️‍♀️ **Atenção ao Rastreio:** {taxa_sem_utm:.1f}% dos leads ({leads_sem_utm} registros) estão chegando sem UTM Source. Verifique se os links das campanhas no Meta Ads estão parametrizados corretamente ou se há quebra de cookies na Landing Page.")
                    else:
                        st.success(f"✅ **Rastreamento Saudável:** Apenas {taxa_sem_utm:.1f}% dos leads estão sem UTM. Captação bem parametrizada.")
                else:
                    st.info("Coluna utm_source não encontrada ou sem dados na captação.")
            except Exception as e:
                st.warning(f"Não foi possível calcular a qualidade das UTMs: {e}")
            
            st.divider()
            
            # --- ALERTA 4: LEADS DUPLICADOS ---
            render_alert_duplicados(df_captacao)
            
            st.divider()
            
            # --- ALERTA 4.1: DISPAROS DUPLICADOS (WHATSAPP) ---
            render_alert_boasvindas_duplicados(df_boasvindas)
            
            st.divider()

            # --- ALERTA 5: LEADS NÃO PROCESSADOS (O ANTIGO) ---
            st.metric("Quebra (Falhas de Integração)", f"{leads_perdidos}", delta_color="inverse", help="Leads que caíram por falha de API ou erro na automação WPP antes de iniciar. (Não inclui os duplicados).")
            
            st.subheader("❌ Leads Perdidos (Falha de Processamento)")
            try:
                df_falhas = df_falhas_global
                
                if not df_falhas.empty:
                    st.error(f"⚠️ Encontramos **{len(df_falhas)} leads** na captação que não chegaram no WhatsApp.")
                    st.info("💡 **O que precisa ser feito:**\n1. Verifique se o webhook do formulário ou o node inicial do n8n/Make falhou.\n2. Se os telefones listados acima forem válidos, baixe esta lista em CSV.\n3. Suba essa base no N8N e dispare a automação de repescagem apenas para eles.")
                    
                    colunas_exibir = []
                    for col in ['data', 'primeiro_nome', 'email', 'telefone', 'utm_source', 'utm_campaign']:
                        if col in df_falhas.columns:
                            colunas_exibir.append(col)
                            
                    st.dataframe(df_falhas[colunas_exibir], use_container_width=True, hide_index=True)
                else:
                    st.success("100% dos leads capturados foram processados com sucesso.")
            except Exception as e:
                st.error(f"Erro ao cruzar dados de perda: {e}") 

    elif menu_selecionado == '🧠 Plano de Ação':
        if True:
            st.header("🧠 Central de Insights e Plano de Ação")
            st.markdown("Bem-vinda ao cérebro do projeto. Aqui eu mapeio os principais gargalos e te dou o passo a passo para resolver. Marque as caixinhas conforme for concluindo!")
            
            st.subheader("🛠️ Engenharia de Dados (N8N e Integrações)")
            
            with st.expander("📉 Risco de Queda no Funil de Engajamento", expanded=True):
                st.warning("**Diagnóstico:** Cerca de 17% dos leads não recebem a mensagem no WhatsApp. Isso é normal, mas é dinheiro deixado na mesa.")
                
                st.markdown("""
                **Como solucionar com segurança:**
                No fluxo do N8N de Boas-vindas, adicione um nó de envio de e-mail (ou SMS) como resgate (Fallback).
                **Fique tranquila:** Adicionar isso **não quebra a automação principal**. Funciona como o "airbag" do carro: não interfere no motor e só dispara se acontecer uma falha no envio do WhatsApp.
                """)
                
                check2 = st.checkbox("✅ Implementei o e-mail/SMS de Resgate (Fallback)", key="chk_funil_fallback")
                if check2:
                    st.success("Excelente! Estamos blindando a conversão do lançamento.")

            st.subheader("🎯 Negócios, Tráfego e BI")
            
            with st.expander("💸 Auditoria de Qualidade de Tráfego (Leads Falsos/Incompletos)", expanded=True):
                st.warning("**Diagnóstico:** Leads que deixam números incompletos ou falsos (ex: 9999-9999) indicam tráfego 'sujo' ou cliques acidentais no Ads, desperdiçando o seu orçamento de campanha.")
                
                st.markdown("""
                **Ação Recomendada:** 
                1. Avise o Gestor de Tráfego para negativar públicos de baixa qualidade ou pausar criativos que atraem curiosos.
                2. Na Landing Page, ative a máscara obrigatória no campo de telefone (formato exato: `(11) 99999-9999`).
                """)
                
                check_trafego = st.checkbox("✅ Alinhei com o Gestor de Tráfego e revisei a Landing Page", key="chk_trafego_qualidade")
                if check_trafego:
                    st.success("Perfeito! Estamos protegendo a verba do lançamento.")
                    
            with st.expander("🚪 Alerta de Evasão (Churn) nos Grupos de WhatsApp", expanded=True):
                st.warning("**Diagnóstico:** O lead custa caro para entrar no grupo. Se a taxa de saída (Churn) começar a subir, significa que o grupo está 'frio' ou os leads estão incomodados.")
                
                st.markdown("""
                **Ação Recomendada:** 
                1. Mantenha os grupos sempre **Silenciados** (Somente Admins enviam mensagens).
                2. Peça ao Expert para enviar 1 áudio curto ou vídeo de antecipação (hype) a cada 2 dias. O lead precisa sentir que estar ali dentro tem valor.
                """)
                
                check_evasao = st.checkbox("✅ Estratégia de engajamento dos grupos definida com o Expert", key="chk_evasao_grupos")
                if check_evasao:
                    st.success("Excelente! Reter o lead no grupo é a chave para o pico de vendas.")

            with st.expander("🤖 Prevenção contra Tráfego Bot (Cadastros de Madrugada)", expanded=True):
                st.warning("**Diagnóstico Preditivo:** Se houver um pico de cadastros entre as 2h e 5h da manhã com números inválidos, é provável que a campanha Meta Ads esteja rodando em Audience Network ou sendo vítima de click farms.")
                
                st.markdown("""
                **Ação Recomendada (Insight Proativo):** 
                1. Verifique agora mesmo o gráfico **Relógio de Engajamento** (na Aba do Cliente). 
                2. Se houver barras muito altas de madrugada, bloqueie imediatamente o posicionamento 'Audience Network' nas campanhas ativas.
                """)
                
                check_bot = st.checkbox("✅ Gráfico analisado e tráfego blindado contra bots", key="chk_trafego_bot")
                if check_bot:
                    st.success("Operação limpa! Cada centavo agora está indo para leads reais.")

            with st.expander("👥 Monopólio de Perfil (82% Técnicos)", expanded=False):
                st.warning("**Diagnóstico:** O seu público é esmagadoramente 'Técnico' (mais de 80%). O tráfego não está atraindo Empreendedores em grande volume.")
                st.info("**Ação Recomendada:** Se o ticket do produto for focado em Negócios/Escala, peça ao Gestor de Tráfego para pausar os criativos focados em 'ferramenta' e subir testes focados em 'gestão e faturamento'.")
                
                check3 = st.checkbox("✅ Alinhei os criativos com o Gestor de Tráfego", key="chk_trafego_perfil")
                if check3:
                    st.success("Alinhamento feito! Vamos acompanhar se a distribuição melhora na próxima semana.")
            
            
    elif menu_selecionado == '🕸️ Funil Manychat (WPP)':
        st.header("🕸️ Funil de Boas-Vindas Manychat (BI A/B)")
        st.write("Identifique vazamentos na automação e entenda qual versão converte mais leads.")
        st.write("---")
        
        st.info("💡 **Aguardando dados oficiais:** Este é um protótipo visual. Para que os dados sejam reais, assegure-se de que a automação N8N/Manychat grave a tag específica na planilha ou conectaremos direto a API.")
        
        # --- FILTROS DE BI ---
        visao_funil = st.radio("Selecione a Visão de Análise (BI):", ["Visão Macro (Consolidado)", "Comparativo de Copys", "Comparativo de Perfis"], horizontal=True)
        
        st.markdown("### ⚡ Engajamento Inicial (Fase 1)")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total de Envios", "4670", help="Total de pessoas que entraram no fluxo (V1+V2+V3)")
        with col2:
            st.metric("Taxa de Entrega", "99.9%", delta="Excelente", help="Leads que efetivamente receberam a mensagem")
        with col3:
            st.metric("Taxa de Clique (CTR)", "54.9%", help="Média de cliques de interesse")
        with col4:
            st.metric("Opt-out (Rejeição)", "1.5%", delta="Menor é melhor", delta_color="inverse", help="O Manychat cravou 68 descadastros (1.5%).")
            
        st.markdown("---")
        import plotly.graph_objects as go
        
        if visao_funil == "Visão Macro (Consolidado)":
            col_a, col_b = st.columns([2, 1])
            with col_a:
                st.subheader(
                    "🌪️ Funil de Conversão (Global)",
                    help="**Glossário do Funil:**\n\n**1. Total Disparado:** Todos os leads acionados pela automação (V1+V2+V3).\n\n**2. Entregue no Celular:** Leads que de fato receberam a mensagem (excluindo números inválidos ou sem internet no momento).\n\n**3. Interesse:** Soma de todos os cliques na 1ª Mensagem.\n\n**4. Escolheu Perfil:** Total de leads que optaram por 'Técnico' ou 'Empreendedor'.\n\n**5. Assistiu ao Vídeo:** Total que chegou na página do Grupo VIP.\n\n**6. Recebeu Pesquisa:** Leads que permaneceram e receberam a pesquisa.\n\n**7. Concluiu (Fim):** Aqueles que preencheram a pesquisa e concluíram a jornada."
                )
                fig_sankey = go.Figure(go.Funnel(
                    y=["1. Disparado", "2. Entregue", "3. Interesse (Cliques)", "4. Escolheu Perfil", "5. Assistiu Vídeo", "6. Recebeu Pesquisa", "7. Concluiu (Fim)", "8. Leads 'Super Quentes'"],
                    x=[4670, 4670, 2564, 1318, 1318, 1041, 561, 478],
                    textinfo="value+percent previous",
                    hoverinfo="text",
                    textfont=dict(size=15, family="Arial, sans-serif", color="black"),
                    hovertext=[
                        "Total de disparos pela automação",
                        "Mensagens confirmadas como entregues pelo WhatsApp",
                        "Soma de todos os cliques na 1ª Mensagem: V1 (Botões Perfil) + V2 (Receber Info) + V3 (Acessar Info).",
                        "Total de cliques nos botões 'Técnico' e 'Empreendedor'.",
                        "Total de leads que chegaram na página/vídeo do Grupo VIP.",
                        "Leads que seguiram no fluxo e receberam a primeira mensagem da Pesquisa.",
                        "Leads que preencheram a pesquisa (Nó: Respondeu Pesquisa).",
                        "O Pote de Ouro: Leads que pediram para receber o link 1x1."
                    ],
                    marker={"color": ["#B0C4DE", "#87CEFA", "#4B8BBE", "#4B8BBE", "#4B8BBE", "#FFD43B", "#FFD43B", "#FFA500"]}
                ))
                fig_sankey.update_layout(
                    height=500,
                    margin=dict(l=180, r=20, t=20, b=20),
                    yaxis=dict(tickfont=dict(size=14, color="#333333", family="Arial, sans-serif"))
                )
                st.plotly_chart(fig_sankey, use_container_width=True)
            
            with col_b:
                st.markdown("### 🥧 Público Atraído")
                import plotly.express as px
                df_pie = pd.DataFrame({'Perfil': ['Técnicos', 'Empreendedores'], 'Qtd': [1064, 254]})
                fig_pie = px.pie(df_pie, values='Qtd', names='Perfil', hole=0.4, color_discrete_sequence=['#F97316', '#8B5CF6'])
                fig_pie.update_layout(height=400, margin=dict(l=0, r=0, t=20, b=0))
                st.plotly_chart(fig_pie, use_container_width=True)

            st.markdown("### 🚨 Diagnóstico de Gargalos")
            st.info("**Insight DBA:** Os dados de disparo inicial foram atualizados. Vemos que 54.9% dos leads demonstram interesse na 1ª mensagem (v1, v2, v3). O público atraído consolida-se em ~80.7% Técnicos (1064) e ~19.3% Empreendedores (254).\n\n**♻️ Retenção no Opt-out:** O botão de descadastramento (Parar Mensagens/Bloquear) foi acionado por 68 pessoas (apenas 1.5% do tráfego total de abertura). Destas, **14 delas (20.6%)** clicaram no genial botão de repescagem **'Mudei de Ideia'**, retornando ativamente para o funil! Essa estratégia de segurança recuperou leads valiosos e protegeu o CPL antes que eles saíssem em definitivo.\n\n**🏆 O Pote de Ouro (Dados Oficiais):** Exatamente **561 leads** preencheram a pesquisa e receberam a última mensagem do funil. Desses, **478 leads (85%)** clicaram em 'Sim, pode mandar' e apenas **73 leads (13%)** avisaram que já estavam no grupo (totalizando 551 interações; apenas 10 leads ignoraram os botões). A sua automação filtrou e entregou **478 leads 'Super Quentes'**! **Ação Recomendada:** A equipe comercial já tem a volumetria exata e precisa focar 100% da energia no atendimento 1x1 para fechar vendas com esses 478 diamantes.")

        elif visao_funil == "Comparativo de Copys":
            st.markdown("### 🏆 Vencedor do Teste A/B")
            st.success("A **Copy V1 (Direta)** é a grande vencedora absoluta! Ela teve o maior volume de Engajamento Inicial (555 cliques únicos) e, por não ter nó extra de permissão, converte direto para a escolha do perfil, com 0% de atrito (drop-off).")
            
            fig = go.Figure()
            fig.add_trace(go.Funnel(name='V1 (Direta)', y=["Interesse na Copy", "Escolheu Perfil (Téc/Emp)"], x=[555, 555], textinfo="value+percent initial"))
            fig.add_trace(go.Funnel(name='V2 (1 Nó Extra)', y=["Interesse na Copy", "Escolheu Perfil (Téc/Emp)"], x=[546, 464], textinfo="value+percent initial"))
            fig.add_trace(go.Funnel(name='V3 (1 Nó Extra)', y=["Interesse na Copy", "Escolheu Perfil (Téc/Emp)"], x=[342, 297], textinfo="value+percent initial"))
            st.plotly_chart(fig, use_container_width=True)
            
            st.markdown("### 🚨 Diagnóstico de Copys")
            st.warning("**Insight DBA:** A estratégia de 'pedir permissão' na V2 e V3 antes de exibir os botões de perfil gerou uma fuga avassaladora de tráfego. A V2 perdeu 45% do seu volume no nó intermediário, enquanto a V3 perdeu quase 69%. A V1, que atira direto para a escolha do Perfil (Técnico ou Empreendedor), provou ser a via expressa perfeita para injetar volume na automação. Recomendo rotear 100% do tráfego para a V1 nas próximas campanhas.")

        elif visao_funil == "Comparativo de Perfis":
            col_t, col_e = st.columns(2)
            with col_t:
                st.markdown("#### 🔧 Jornada do Técnico")
                fig_tec = go.Figure(go.Funnel(y=["Escolheu Técnico", "Assistiu Vídeo Téc", "Entrou Grupo Téc"], x=[1064, 1064, 787], textinfo="value+percent previous", marker={"color": "#F97316"}))
                st.plotly_chart(fig_tec, use_container_width=True)
            with col_e:
                st.markdown("#### 💼 Jornada do Empreendedor")
                fig_emp = go.Figure(go.Funnel(y=["Escolheu Empreendedor", "Assistiu Vídeo Emp", "Entrou Grupo Emp"], x=[254, 254, 184], textinfo="value+percent previous", marker={"color": "#8B5CF6"}))
                st.plotly_chart(fig_emp, use_container_width=True)

            st.markdown("### 🚨 Diagnóstico de Perfis")
            st.warning("**Insight DBA:** O seu funil apresenta uma taxa alta de ação na pós-visualização do vídeo.\n\n**🎯 Destaque para a Repescagem:** A sua estratégia de perguntar 'Conseguiu entrar no grupo?' é fantástica! O lembrete secundário foi acionado para 213 Técnicos e 60 Empreendedores que clicaram em 'Não consegui'. Desse volume, o link bruto da repescagem conseguiu salvar e converter **181 Técnicos** (85.0%) e **55 Empreendedores** (91.7%). Sem esse nó inteligente, você teria perdido 236 leads extremamente qualificados e o seu CPL (Custo por Lead) teria disparado!")
        
    elif menu_selecionado == '📊 Pesquisa (WordCloud)':
        st.markdown("<h1 style='text-align: left; color: #4B8BBE; font-size: 3rem;'>🧠 Raio-X da Audiência</h1>", unsafe_allow_html=True)
        st.markdown("<h3 style='text-align: left; color: #AAAAAA; font-weight: 300;'>Decodificando os desejos, dores e o poder de compra do seu cliente.</h3>", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        st.info("Mais do que números, a pesquisa de check-in revela a **alma** do lançamento. Aqui, saímos do 'achismo' e ouvimos a voz da audiência para escrever copys cirúrgicas que quebram objeções antes mesmo de o carrinho abrir.")
        
        try:
            df_pesq = pd.read_csv("pesquisa.csv")
            # Renomeando as colunas difíceis
            df_pesq = df_pesq.rename(columns={
                "Qual a sua idade?": "Idade",
                "Qual dessas opções mais representa você hoje?\\n": "Perfil_Inicial",
                "Qual o seu objetivo para aprender a manutenção de Scooter Elétrica?\\n\\nSOU/SER UM TÉCNICO\\nQuero fazer ou faço a manutenção de Scooters Elétricas.\\n\\nSOU/SER UM EMPREENDEDOR\\nQuero ou tenho uma oficina/loja no ramo de Scooters Elétricas.\\n": "Objetivo_Geral",
                "Como Técnico, qual o seu objetivo principal?\\n": "Objetivo_Tecnico",
                "Como Empreendedor, qual a sua situação hoje?\\n": "Situacao_Empreendedor",
                "Qual o seu nível de Conhecimento Técnico das Scooters/Motos Elétricas?": "Nivel_Tecnico",
                "Hoje em dia, qual é a sua renda mensal aproximada?": "Renda",
                "Você tem cartão de crédito?": "Cartao",
                "O que você espera aprender na Jornada Mundo dos Elétricos?": "Expectativa"
            })
            
            import numpy as np
            # Filtra erros da planilha (como #ERROR!) usando np.nan para evitar erro de JSON do Plotly
            df_pesq = df_pesq.replace('#ERROR!', np.nan)
            
            # Conta totais reais
            total_respostas = len(df_pesq)
            
            st.markdown("<h2 style='color: #4B8BBE;'>1. Demografia e Perfil Técnico</h2>", unsafe_allow_html=True)
            st.metric(label="Total de Respostas Analisadas", value=total_respostas, help="Volume total de leads que completaram o formulário de Check-in.")
            st.markdown("<br>", unsafe_allow_html=True)
            
            col1, col2 = st.columns(2)
            
            with col1:
                with st.container(border=True):
                    df_idade = df_pesq['Idade'].value_counts().reset_index()
                    df_idade.columns = ['Idade', 'Quantidade']
                    df_idade = df_idade.sort_values(by='Idade')
                    fig_idade = px.bar(df_idade, x='Idade', y='Quantidade', title='Faixa Etária', text_auto=True, color='Idade', color_discrete_sequence=px.colors.qualitative.Pastel)
                    fig_idade.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", showlegend=False, xaxis_title=None, yaxis_title=None)
                    st.plotly_chart(fig_idade, use_container_width=True)
                    
            with col2:
                with st.container(border=True):
                    df_tec = df_pesq['Nivel_Tecnico'].value_counts().reset_index()
                    df_tec.columns = ['Nivel_Tecnico', 'Quantidade']
                    df_tec['Nivel_Curto'] = df_tec['Nivel_Tecnico'].apply(lambda x: str(x).split('.')[0] if pd.notnull(x) else 'Não Informado')
                    fig_tec = px.bar(df_tec, x='Nivel_Curto', y='Quantidade', title='Nível de Conhecimento Técnico', text_auto=True, color='Nivel_Curto', color_discrete_sequence=px.colors.qualitative.Set1)
                    fig_tec.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", showlegend=False, xaxis_title=None, yaxis_title=None)
                    st.plotly_chart(fig_tec, use_container_width=True)
                
            try:
                idade_comum = df_pesq['Idade'].mode()[0] if not df_pesq['Idade'].empty else "Não informada"
                tecnico_counts = df_pesq['Nivel_Tecnico'].value_counts(normalize=True) * 100
                perc_leigo = tecnico_counts[tecnico_counts.index.str.contains('Nenhum|Básico', case=False, na=False)].sum()
                
                st.info(f"**🎯 Insight Demográfico (Aprofundado):** A grande maioria do público ({perc_leigo:.1f}%) é de iniciantes ('Nenhum' ou 'Básico'), com a faixa etária principal concentrada em **{idade_comum}**. \n\n**O que isso significa na prática?** Essa audiência madura busca transição de carreira ou uma nova fonte de renda segura, mas sente profunda insegurança técnica (medo de não conseguir aprender ou de estragar um equipamento). \n\n**Estratégia de Copy e Conteúdo:** Remova completamente jargões complexos das aulas gratuitas (CPLs). Foque nos termos 'passo a passo', 'do zero', 'qualquer um consegue' e 'método à prova de falhas'. A promessa principal deve girar em torno da *segurança financeira* e *facilidade de implementação*, reduzindo a fricção e o medo da complexidade elétrica.")
            except:
                st.info("**🎯 Insight Demográfico:** O público é predominantemente leigo ('Nenhum' ou 'Básico') e concentrado em faixas etárias maduras (35-54 anos). Isso exige uma copy didática, sem jargões complexos, focada em segurança e passo-a-passo estruturado.")
            st.markdown("<hr style='border: 1px solid #d3d3d3; margin: 50px 0;'>", unsafe_allow_html=True)
            st.markdown("<h2 style='color: #4B8BBE;'>2. Poder de Compra (Renda vs Cartão)</h2>", unsafe_allow_html=True)
            
            col3, col4 = st.columns(2)
            
            with col3:
                with st.container(border=True):
                    df_renda = df_pesq['Renda'].dropna().value_counts().reset_index()
                    df_renda.columns = ['Renda', 'Quantidade']
                    
                    # Limpar rótulos longos e ordenar do menor para o maior
                    df_renda['Renda'] = df_renda['Renda'].apply(lambda x: str(x).split('(')[0].strip())
                    ordem_renda = ["Nenhuma renda", "Até 1 salário mínimo", "De 1 a 3 salários mínimos", "De 3 a 5 salários mínimos", "Mais de 5 salários mínimos"]
                    df_renda['Renda'] = pd.Categorical(df_renda['Renda'], categories=ordem_renda, ordered=True)
                    df_renda = df_renda.sort_values('Renda', ascending=False)
                    
                    fig_renda = px.bar(df_renda, y='Renda', x='Quantidade', orientation='h', title='Distribuição de Renda', color='Renda', color_discrete_sequence=px.colors.qualitative.Pastel, text_auto=True)
                    fig_renda.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", xaxis_title="Quantidade", yaxis_title=None, showlegend=False)
                    st.plotly_chart(fig_renda, use_container_width=True)
                    
            with col4:
                with st.container(border=True):
                    fig_cartao = px.pie(df_pesq.dropna(subset=['Cartao']), names='Cartao', title='Possui Cartão de Crédito?', color_discrete_sequence=px.colors.qualitative.Set3)
                    fig_cartao.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
                    st.plotly_chart(fig_cartao, use_container_width=True)
                
            try:
                perc_cartao = (df_pesq['Cartao'].value_counts(normalize=True).get('Sim', 0) * 100)
                renda_comum = df_pesq['Renda'].mode()[0] if not df_pesq['Renda'].empty else "Não informada"
                
                st.info(f"**💰 Insight Financeiro (Aprofundado):** Uma enorme parcela da sua base ({perc_cartao:.1f}%) afirma possuir Cartão de Crédito. No entanto, a renda predominante detectada nos gráficos se concentra na faixa de **{renda_comum}**. \n\n**O que isso significa na prática?** O lead *tem o limite no cartão*, mas o orçamento mensal dele é extremamente restrito. \n\n**Estratégia de Vendas (Copy):** A ancoragem do preço cheio (ex: R$ 997) pode gerar susto e abandono de carrinho. O foco absoluto do seu pitch e da página de vendas deve ser o valor da parcela ('Por menos de X reais por dia' ou '12x de Y'). Além disso, oferecer modalidades híbridas (Pix + Cartão) ou Boleto Parcelado será o grande diferencial para contornar o bloqueio de limite único.")
            except:
                st.info("**💰 Insight Financeiro:** A base apresenta alta adesão a cartão de crédito, mas a renda predominante sugere cautela na ancoragem do ticket. Ofertas com parcelamento estendido terão altíssima conversão.")
            st.markdown("<hr style='border: 1px solid #d3d3d3; margin: 50px 0;'>", unsafe_allow_html=True)
            st.markdown("<h2 style='color: #F97316;'>3. Nuvem de Palavras (Desejos Latentes)</h2>", unsafe_allow_html=True)
            st.markdown("O que a audiência respondeu quando perguntada sobre suas expectativas.")
            
            with st.container(border=True):
                # Wordcloud
                try:
                    import matplotlib.pyplot as plt
                    from wordcloud import WordCloud, STOPWORDS
                    from collections import Counter
                    import re
                    
                    textos = " ".join(df_pesq['Expectativa'].dropna().astype(str).tolist())
                    
                    # Limpeza para contagem correta
                    texto_limpo = re.sub(r'[^\w\s]', '', textos.lower())
                    palavras = texto_limpo.split()
                    
                    stop_words = set(STOPWORDS)
                    pt_stops = ["o", "a", "os", "as", "um", "uma", "uns", "umas", "de", "do", "da", "dos", "das", "em", "no", "na", "nos", "nas", "para", "pra", "com", "que", "se", "por", "como", "mais", "mas", "eu", "ele", "ela", "eles", "elas", "me", "te", "se", "nos", "vos", "e", "ou", "tudo", "muito", "sobre", "ser", "ter", "aprender", "fazer", "saber", "isso", "aquilo", "estou", "quero", "vou", "nao", "não", "sim", "sou", "q", "ja", "já", "meu", "minha", "vem", "tem", "até", "dos", "das"]
                    stop_words.update(pt_stops)
                    
                    # Top 5 Métricas
                    palavras_filtradas = [p for p in palavras if p not in stop_words and len(p) > 2]
                    contagem = Counter(palavras_filtradas)
                    top_5 = contagem.most_common(5)
                    
                    st.markdown("##### 🏆 Top 5 Temas Mais Citados")
                    cols_top = st.columns(5)
                    for i, (palavra, freq) in enumerate(top_5):
                        with cols_top[i]:
                            st.metric(label=f"#{i+1} Tema", value=palavra.title(), delta=f"{freq} citações", delta_color="off")
                    
                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    # Renderização Wordcloud
                    wordcloud = WordCloud(width=800, height=400, background_color='#1E1E1E', stopwords=stop_words, colormap='Wistia').generate(textos)
                    
                    fig_wc, ax = plt.subplots(figsize=(10, 5), facecolor='#1E1E1E')
                    ax.imshow(wordcloud, interpolation='bilinear')
                    ax.axis("off")
                    st.pyplot(fig_wc)
                    
                    # Insight Comportamental
                    termos_top = [p.title() for p, c in top_5]
                    st.info(f"**🧠 Insight Comportamental (Dores e Desejos):** As 5 palavras que mais ecoam na mente do seu lead são: **{', '.join(termos_top)}**. \n\n**O que isso revela?** Estes termos representam as maiores 'dores latentes' ou ambições do cliente. A copy de abertura do CPL e dos anúncios de remarketing deve utilizar exatamente este vocabulário para gerar ancoragem e conexão instantânea (ex: 'Eu sei que o que você mais quer agora é [Tema #1] e [Tema #2]').")
                    
                except ImportError:
                    st.error("As bibliotecas 'wordcloud' ou 'matplotlib' não estão instaladas neste ambiente da nuvem.")
            
        except Exception as e:
            st.error(f"Erro ao processar a pesquisa: {e}")
            
    elif menu_selecionado == '🎯 Raio-X Didático CPLs':
        st.header("🎯 Raio-X Didático das CPLs (Auditoria 100% Real)")
        st.markdown("A história dos dados contada passo a passo — sem achismos, com dados extraídos direto das telas do Manychat.")
        
        # --- PAINEL DE STATUS DA AUDITORIA ---
        st.markdown("### 📋 Status da Auditoria por CPL")
        s1, s2, s3, s4 = st.columns(4)
        s1.success("🟢 **CPL 01**: 100% Auditado\n\n(3 Disparos | 9 Nós)")
        s2.warning("⏳ **CPL 02**: Pendente\n\n(Aguardando prints)")
        s3.warning("⏳ **CPL 03**: Pendente\n\n(Aguardando prints)")
        s4.success("🟢 **CPL 04**: 100% Auditado\n\n(5 Nós Mapeados)")

        st.markdown("---")

        # =========================================================
        # SEÇÃO 1: CPL 01 - DIDÁTICA E NARRATIVA
        # =========================================================
        st.subheader("1️⃣ CPL 01 — A Jornada Completa (10/08 a 12/08)")
        st.markdown("A CPL 01 utilizou uma estratégia de **3 disparos encadeados** para alcançar, engajar e recuperar os leads.")

        # KPIs Topo CPL 01
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("📤 Base Impactada", "4.604 leads", "Disparo Principal")
        c2.metric("✅ Entregues (Nó 1)", "4.294 leads", "93.3% Entrega", delta_color="normal")
        c3.metric("📖 Aberturas (Nó 1)", "3.167 leads", "68.8% Open Rate", delta_color="normal")
        c4.metric("👆 Cliques no Broadcast", "1.023 leads", "23.8% CTR Exclusivo", delta_color="normal")

        st.markdown("<br>", unsafe_allow_html=True)

        # CAPÍTULOS CPL 01
        with st.container(border=True):
            st.markdown("#### 🎬 Capítulo 1: O Disparo Principal (10/08 - 20h28)")
            st.markdown("O broadcast inicial enviou o convite da Aula 1 para **4.604 pessoas**. **3.167 abriram (69%)** e a mensagem bifurcou os leads em dois caminhos:")

            col_path_nao, col_path_sim = st.columns(2)

            with col_path_nao:
                st.markdown("""
                <div style="background-color:#1a2b1a; border-left:4px solid #2ca02c; padding:15px; border-radius:8px;">
                    <h5 style="color:#2ca02c; margin-0;">🟣 Caminho 'NÃO' (Ainda não assistiram)</h5>
                    <p style="font-size:0.9rem; color:#ddd; margin-top:8px;">
                        <b>540 leads</b> informaram que não tinham visto a aula.<br>
                        • <b>Msg #5 (Link Direto):</b> 533 abriram e <b>477 clicaram (88% CTR)</b> para receber o link!<br>
                        • <b>Msg #6 (Entrega da Aula):</b> 461 abriram e <b>376 clicaram p/ ASSISTIR (79% CTR)</b>.<br>
                        • <b>SDR Virtual (Check-in 2h):</b> 370 receberam o lembrete e <b>145 confirmaram que assistiram (39% CTR)</b>.<br><br>
                        <b style="color:#2ca02c;">⭐ Insight de Ouro:</b> Quando o link foi entregue de forma direta (sem pedágio de consentimento), <b>88% da base clicou na hora</b>.
                    </p>
                </div>
                """, unsafe_allow_html=True)

            with col_path_sim:
                st.markdown("""
                <div style="background-color:#3b2b1a; border-left:4px solid #f39c12; padding:15px; border-radius:8px;">
                    <h5 style="color:#f39c12; margin-0;">🟡 Caminho 'SIM' (Já assistiram)</h5>
                    <p style="font-size:0.9rem; color:#ddd; margin-top:8px;">
                        <b>414 leads</b> disseram que já tinham assistido à Aula 1.<br>
                        • <b>Msg #3 (Convite p/ Comentário):</b> 219 toparam ir ao Instagram (53%).<br>
                        • <b>Msg #4 (Link do Post IG):</b> 170 clicaram no link e saíram do WhatsApp (78%).<br>
                        • <b>Comentaram no IG (DM Automática):</b> <b>Apenas 21 pessoas comentaram de fato (12%)</b>.<br><br>
                        <b style="color:#e74c3c;">🚨 Fuga de Canal:</b> Tirar o lead do WhatsApp para comentar no Instagram gerou uma <b>fuga de 99.5% da base total</b>. Apenas 21 de 4.604 pessoas completaram a ação.
                    </p>
                </div>
                """, unsafe_allow_html=True)

        with st.container(border=True):
            st.markdown("#### 🎬 Capítulo 2: O Lembrete Direto para o Instagram (10/08)")
            st.markdown(
                "Um segundo disparo paralelo foi feito diretamente para **164 leads** com o link direto da postagem do Instagram.\n\n"
                "• **164 Entregues (100%)** | **144 Abertos (87.8%)** | **36 Cliques no Link (22.0% CTR)**\n\n"
                "**Conclusão:** O post do Instagram acumulou **129 comentários**, provando que o engajamento orgânico do próprio Instagram teve um papel relevante em conjunto com o tráfego do WhatsApp."
            )

        with st.container(border=True):
            st.markdown("#### 🎬 Capítulo 3: Reprise + Aviso Ao Vivo Aula 2 (11/08 a 12/08)")
            st.markdown("No dia seguinte (11/08 às 18h30), um fluxo retido em **Atraso Inteligente** preparou a base para a Aula 2:")

            r1, r2, r3 = st.columns(3)
            r1.metric("1️⃣ Reprise (11/08 18h30)", "878 Entregues", "137 Cliques (15.6% CTR)")
            r2.metric("2️⃣ Pernoite (Atraso)", "893 Aprovados", "Aguardaram até 12/08 08h")
            r3.metric("3️⃣ Ao Vivo Aula 2 (08h00)", "229 Entregues", "59 Cliques (25.8% CTR)")

            st.warning(
                "⚠️ **Gargalo Técnico Detectado:** Das 893 pessoas aprovadas no Atraso Inteligente para receber o aviso da Aula 2 às 08h00, apenas **230 receberam**.\n\n"
                "**Motivo:** A mensagem foi enviada usando a regra de *'Janela de 24 horas'*. Como 663 pessoas não tinham interagido nas últimas 24h, a Meta barrou a entrega.\n\n"
                "**Solução p/ LC8:** Utilizar um *Template Aprovado da Meta* nos avisos pontuais de aula para garantir 100% de entrega a todos os 893 leads."
            )

        st.markdown("---")

        # =========================================================
        # SEÇÃO 2: CPL 04 - DIDÁTICA E APRENDIZADO
        # =========================================================
        st.subheader("4️⃣ CPL 04 — O Impacto do 'Botão de Consentimento' (17/08)")
        
        col_cpl4_funil, col_cpl4_text = st.columns([1, 1])

        with col_cpl4_funil:
            with st.container(border=True):
                st.markdown("#### 📉 Funil Auditado CPL 04")
                fig_cpl4 = go.Figure(go.Funnel(
                    y=["1. Disparados", "2. Entregues (90.9%)", "3. Abertos (56.9%)", "4. Cliques (5.0%)"],
                    x=[4543, 4129, 2348, 208],
                    textinfo="value+percent initial",
                    marker={"color": ["#4B8BBE", "#28a745", "#ff7f0e", "#dc3545"]}
                ))
                fig_cpl4.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=260, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig_cpl4, use_container_width=True)

        with col_cpl4_text:
            st.markdown("""
            <div style="background-color:#2b1a1a; border-left:4px solid #dc3545; padding:15px; border-radius:8px;">
                <h5 style="color:#dc3545; margin-0;">🚨 O Erro do Pedágio em Números</h5>
                <p style="font-size:0.9rem; color:#ddd; margin-top:8px;">
                    • <b>2.348 pessoas abriram</b> a mensagem (57% Open Rate — excelente!).<br>
                    • Porém, a mensagem exigia clicar em <i>'Receber Informações'</i> antes de liberar o link.<br>
                    • Apenas <b>208 pessoas clicaram em algum botão</b> (8.9% dos que abriram).<br>
                    • <b>Fuga de 95%:</b> 2.140 pessoas leram a mensagem e fecharam o WhatsApp sem interagir.<br><br>
                    <b>Conclusão:</b> O público técnico quer o conteúdo direto. Intermediários matam a conversão.
                </p>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("---")

        # =========================================================
        # SEÇÃO 3: RECOMENDAÇÕES EXECUTIVAS PARA O LC8
        # =========================================================
        st.subheader("💡 Plano de Ação Estratégico para o Lançamento LC8")

        p1, p2, p3 = st.columns(3)

        with p1:
            st.success(
                "#### 🟢 1. Link Direto sem Pedágio\n\n"
                "**Ação:** A primeira mensagem de cada CPL deve conter o link da aula diretamente no botão ('Assistir Aula 1 Agora').\n\n"
                "**Impacto Esperado:** Subir o CTR de 5% para 25%+ (baseado na prova da CPL 01 Msg #5)."
            )

        with p2:
            st.warning(
                "#### 🟡 2. Retenção Total no WhatsApp\n\n"
                "**Ação:** Não direcionar o lead para comentar no Instagram durante a maratona de aulas.\n\n"
                "**Impacto Esperado:** Manter 100% da audiência engajada no canal oficial de vendas (WhatsApp)."
            )

        with p3:
            st.info(
                "#### 🔵 3. Templates Pagos nas Aulas\n\n"
                "**Ação:** Usar Templates Aprovados da Meta nos disparos das 08h00 do dia da aula.\n\n"
                "**Impacto Esperado:** Destravar os 74% de leads barrados pela regra da Janela de 24h."
            )

    elif menu_selecionado == '1️⃣ CPLs (Análise e Funil)':
        st.header("1️⃣ Dashboard de Tração e CPLs")
        st.markdown("Análise de conversão do funil de avisos: Disparos ➔ Entrega ➔ Clique.")
        
        # Dados de CPLs — Auditados nó a nó via fluxos Manychat (24/08/2026)
        # CPL 01: Auditado fluxo por fluxo
        #   Disparo 1 (Inscritos): 4.604 env | 4.294 ent (93,3%) | 3.167 abertos (68,8%) | 1.023 cliques unicos (22,2%)
        #   Disparo 2 (Aviso IG): 164 env | 164 ent (100%) | 144 abertos (87,8%) | 36 cliques (22,0%)
        #   Disparo 3 (Reprise/Ao Vivo): 887 env | 878 ent (98,9%) | 712 abertos (80,2%) | 137 cliques reprise (15,6%) + 59 cliques ao vivo (25,8%)
        # CPL 04: Auditado nó a nó
        #   Nó 01: 4.543 env | 4.129 ent | 2.348 abertos | 208 cliques (162 Receber Info + 48 Bloquear)
        df_cpl = pd.DataFrame({
            "CPL": ["CPL 01", "CPL 02", "CPL 03", "CPL 04"],
            "Data_Disparo": ["10/08/2026", "13/08/2026", "15/08/2026", "17/08/2026"],
            "Disparados": [4604,  896, 1334, 4543],
            "Entregues":  [4294,  890, 1310, 4129],
            "Cliques":    [1023,   63,   89,  208],
            "Custo_US":   [33.22, 36.98, 49.27, 45.00]
        })
        
        cpl_selecionado = st.selectbox("Selecione o CPL para análise detalhada:", ["Visão Geral"] + df_cpl['CPL'].tolist())
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        if cpl_selecionado == "Visão Geral":

            # --- KPIs GLOBAIS ---
            total_disp = df_cpl['Disparados'].sum()
            total_ent  = df_cpl['Entregues'].sum()
            total_cli  = df_cpl['Cliques'].sum()
            taxa_ent   = (total_ent / total_disp) * 100 if total_disp > 0 else 0
            taxa_cli   = (total_cli / total_ent)  * 100 if total_ent  > 0 else 0

            k1, k2, k3, k4 = st.columns(4)
            k1.metric("📤 Total Disparado",  f"{total_disp:,}".replace(',','.'))
            k2.metric("✅ Total Entregue",   f"{total_ent:,}".replace(',','.'),  f"{taxa_ent:.1f}% de entrega",  delta_color="normal")
            k3.metric("👆 Total de Cliques", f"{total_cli:,}".replace(',','.'),  f"{taxa_cli:.1f}% CTR global",  delta_color="normal")
            k4.metric("📅 CPLs Realizadas",  "4",  "11/08 a 17/08/2026", delta_color="off")

            st.markdown("<br>", unsafe_allow_html=True)

            # --- FUNIL (esq) + CARDS CPL (dir) ---
            col_funil, col_cards = st.columns([1, 1], gap="large")

            with col_funil:
                with st.container(border=True):
                    st.markdown("#### 📊 Funil Consolidado")
                    fig_funnel = go.Figure(go.Funnel(
                        y=["Disparados", "Entregues", "Cliques"],
                        x=[total_disp, total_ent, total_cli],
                        textinfo="value+percent initial",
                        textfont=dict(size=14),
                        marker={"color": ["#4B8BBE", "#28a745", "#FFD43B"]}
                    ))
                    fig_funnel.update_layout(
                        margin=dict(t=10, b=10, l=10, r=10),
                        height=320,
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)"
                    )
                    st.plotly_chart(fig_funnel, use_container_width=True)
                    st.caption(f"De **{total_disp:,}** disparados, **{total_cli:,}** interagiram ({taxa_cli:.1f}% CTR)".replace(',','.'))

            with col_cards:
                st.markdown("#### 🗂️ Resumo por CPL")

                anotacoes = {
                    "CPL 01": ("🟢", "#1a3a1a", "#2ca02c", "Auditado: 4.604 disp. | 4.294 ent. (93,3%) | 1.023 cliques (23.8% CTR)<br>Pico de 88% CTR quando o link foi enviado sem fricção."),
                    "CPL 02": ("🔴", "#3a1a1a", "#e74c3c", "Template 'Utility' reclassificado para 'Marketing'<br>Verba esgotada — 80% da base não recebeu."),
                    "CPL 03": ("🟡", "#2a2a10", "#c9a800", "Teste A/B/C realizado<br>Imagem + Pergunta teve melhor CTR (10%)."),
                    "CPL 04": ("🔴", "#3a1a1a", "#e74c3c", "Botão de consentimento causou fuga de 95%<br>Apenas 208 de 4.543 interagiram."),
                }

                for _, row in df_cpl.iterrows():
                    cpl = row['CPL']
                    emoji, bg, cor, nota = anotacoes[cpl]
                    ctr_card = (row['Cliques'] / row['Entregues'] * 100) if row['Entregues'] > 0 else 0
                    tx_ent_card = (row['Entregues'] / row['Disparados'] * 100) if row['Disparados'] > 0 else 0
                    st.markdown(f"""
                    <div style="background:{bg}; border-left:4px solid {cor}; border-radius:8px;
                                padding:12px 16px; margin-bottom:10px;">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <span style="font-weight:700; font-size:1rem;">{emoji} {cpl}
                                <span style="font-size:0.78rem; color:#aaa; font-weight:400; margin-left:8px;">{row['Data_Disparo']}</span>
                            </span>
                            <span style="font-size:0.9rem; color:{cor}; font-weight:700;">{ctr_card:.1f}% CTR</span>
                        </div>
                        <div style="display:flex; gap:16px; margin:6px 0 4px 0; font-size:0.82rem; color:#ccc;">
                            <span>📤 {row['Disparados']:,} disp.</span>
                            <span>✅ {row['Entregues']:,} ent. ({tx_ent_card:.0f}%)</span>
                            <span>👆 {row['Cliques']:,} cliques</span>
                        </div>
                        <div style="font-size:0.8rem; color:#bbb; border-top:1px solid #333;
                                    padding-top:6px; margin-top:4px;">{nota}</div>
                    </div>
                    """.replace(',', '.'), unsafe_allow_html=True)

            # --- AUTÓPSIA EM EXPANDER (COLAPSADO) ---
            st.markdown("<br>", unsafe_allow_html=True)
            with st.expander("📚 Ver Autópsia Completa e Regras de Ouro (Próximo Lançamento)"):
                st.markdown("### ⚠️ O Perigo do 'Botão de Consentimento' (CPL 1 e CPL 4)")
                st.error("**O Erro:** Exigir que o lead clique em 'Receber Informação' na primeira mensagem antes de entregar o link. Isso causou uma **fuga de 68% na CPL 01 e de assustadores 95% na CPL 04**.")
                st.warning("**A Punição da Meta:** Quando você dispara para milhares de pessoas e a grande maioria não interage, a Meta enxerga **Baixo Engajamento**. O algoritmo de Qualidade da Conta (Quality Rating) cai para Amarelo ou Vermelho. Trabalhar com a base inteira sem engajamento faz a Meta limitar os envios diários (Tier Limits) e derrubar a sua taxa de entrega de forma generalizada, interpretando a automação como SPAM.")
                st.success("**A Solução:** Comunicação direta. A primeira mensagem já deve entregar o valor real (o link da aula) com um botão claro ('Assistir Agora'). A fricção deve ser zero para consumir o evento.")
                st.markdown("---")
                st.markdown("### 💸 A Armadilha da 'Copy Promocional' (CPL 2 e 3)")
                st.error("**O Erro:** Usar textos que soam muito comerciais. A Meta reclassificou templates 'Utility' para 'Marketing' de surpresa. Isso esgotou a verba da carteira em segundos e bloqueou os disparos, **barrando 80% da base** de receber os avisos das CPLs 02 e 03.")
                st.success("**A Solução:** Blindar a Copy. Reduza gatilhos de escassez agressivos (ex: 'Liberado', 'Última Chance', Emojis de 🚨) nos avisos de aula gratuitos. Torne o texto puramente transacional e educacional para o crivo da IA do WhatsApp.")
                st.markdown("---")
                st.markdown("### 🧭 O Labirinto de Canais")
                st.error("**O Erro:** Pegar o lead altamente engajado e forçá-lo a sair do WhatsApp para comentar em um post do Instagram. Isso causou **66% a 75% de fuga** nas interações.")
                st.success("**A Solução:** Retenção absoluta. O WhatsApp é o ambiente de conversão. Se o lead engaja, ofereça um PDF nativo ou convide-o para o 'Grupo VIP' (como feito com sucesso na Reprise da CPL 3, convertendo 28%).")
                st.markdown("---")
                st.markdown("### 🧪 A Força do Visual (UX no WhatsApp)")
                st.success("**O Acerto:** O Teste A/B/C da CPL 03 provou que o template com **Imagem + Pergunta** (Copy B) teve o maior CTR (10%). **Regra Máxima:** Use imagens para fisgar a atenção e SEMPRE utilize 'Botões' de ação claros no lugar de links no meio do texto.")

        else:
            # Visão Individual por CPL
            with st.container(border=True):
                if cpl_selecionado == "CPL 01":
                    st.markdown("### 📈 Performance da CPL 01 (Visão Detalhada)")
                    
                    disparo_selecionado = st.radio(
                        "Filtre por Disparo (CPL 01):", 
                        ["📦 Visão Consolidada", "1️⃣ Disparo Principal", "2️⃣ Engajamento", "3️⃣ Reprise e Ao Vivo"],
                        horizontal=True
                    )
                    
                    if disparo_selecionado == "📦 Visão Consolidada":
                        st.subheader("📦 Visão Consolidada: A Estratégia de 3 Passos")
                        st.markdown("Para garantir que a base assistisse à CPL 01, não enviamos apenas uma mensagem solta. O fluxo foi dividido em 3 etapas estratégicas para 'cercar' o lead:")
                        
                        st.info(
                            "**1. Disparo Principal (Em Massa):** O convite oficial enviado para toda a base ativa.\n\n"
                            "**2. Aviso Direto:** Uma mensagem curta enviada logo depois, apenas para 'cutucar' quem precisava de um empurrãozinho extra.\n\n"
                            "**3. Repescagem (Dia Seguinte):** Um lembrete com a gravação da aula, aproveitando para já fisgar a pessoa para o 'Ao Vivo' da aula seguinte."
                        )
                        
                        df_cpl1_disparos = pd.DataFrame({
                            "Etapa da Estratégia": ["1. Disparo Principal (Massa)", "2. Aviso Direto (Engajamento)", "3. Repescagem (Reprise/Ao Vivo)"],
                            "Data/Hora": ["10 Ago, 20:25", "10 Ago, 20:33", "11 Ago, 18:30"],
                            "Volume de Pessoas": ["4.604 leads", "164 leads", "887 leads"],
                            "Taxa de Abertura": ["68,0%", "87,8%", "80,9%"]
                        })
                        st.dataframe(df_cpl1_disparos, use_container_width=True, hide_index=True)

                    elif disparo_selecionado == "1️⃣ Disparo Principal":
                        st.markdown("### 🔀 O Mapa da Distribuição (Comportamento do Lead)")
                        st.markdown("O que aconteceu com os leads após abrirem a primeira mensagem:")
                        
                        # Fase 1
                        st.markdown("#### 🚧 Fase 1: O Pedágio Inicial")
                        col0, arr0, col1, arr1, col2, arr2, col3 = st.columns([3, 1, 3, 1, 3, 1, 3])
                        
                        with col0:
                            with st.container(border=True):
                                st.metric("1. Disparo Total", "4.604", "Base Enviada", delta_color="off")
                        with arr0:
                            st.markdown("<h2 style='text-align: center; margin-top: 15px;'>➔</h2>", unsafe_allow_html=True)
                            
                        with col1:
                            with st.container(border=True):
                                st.metric("2. Entregues", "4.294", "93.3% Entrega", delta_color="normal")
                        with arr1:
                            st.markdown("<h2 style='text-align: center; margin-top: 15px;'>➔</h2>", unsafe_allow_html=True)
                            
                        with col2:
                            with st.container(border=True):
                                st.metric("3. Abertos", "3.167", "68.8% Abertura", delta_color="normal")
                        with arr2:
                            st.markdown("<h2 style='text-align: center; margin-top: 15px;'>➔</h2>", unsafe_allow_html=True)
                            
                        with col3:
                            with st.container(border=True):
                                st.metric("4. Clicaram Botão", "1.023", "22.2% p/ Info", delta_color="off")
                            
                        st.markdown("<br>", unsafe_allow_html=True)
                        
                        # Fase 2
                        st.markdown("#### 🔀 Fase 2: O Foco na Conversão (Aula 1)")
                        
                        col_sim, col_nao = st.columns(2)
                        
                        with col_sim:
                            with st.container(border=True):
                                st.markdown("<h4 style='text-align: center; color: #f59e0b;'>🟡 Caminho 'SIM'</h4>", unsafe_allow_html=True)
                                st.metric("➡️ Escolheram 'Sim'", "414 leads", "Disseram que já assistiram", delta_color="off")
                                st.markdown("<h3 style='text-align: center;'>⬇️</h3>", unsafe_allow_html=True)
                                st.metric("📸 Foram pro Instagram", "170 cliques", "🚨 Desvio (Saíram do WhatsApp)", delta_color="off")
                                
                        with col_nao:
                            with st.container(border=True):
                                st.markdown("<h4 style='text-align: center; color: #8b5cf6;'>🟣 Caminho 'NÃO'</h4>", unsafe_allow_html=True)
                                st.metric("➡️ Escolheram 'Não'", "540 leads", "Receberam o link da aula", delta_color="off")
                                st.markdown("<h3 style='text-align: center;'>⬇️</h3>", unsafe_allow_html=True)
                                st.metric("▶️ Foram pra Aula", "477 cliques", "88% de Conversão", delta_color="normal")

                        st.markdown("### 🧠 Resumo das Análises (O que aprendemos?)")
                        st.info(
                            "**1. O Pedágio do Template:** Perdemos 2.000 pessoas logo na primeira mensagem porque exigimos que elas clicassem em 'Receber Informação' antes de entregar o link da aula.\n\n"
                            "**2. A Bifurcação (Sim/Não):** O robô separou muito bem quem já tinha assistido de quem estava atrasado. Para os atrasados (Caminho 'Não'), o envio do link resultou em incríveis 88% de cliques para a aula na hora.\n\n"
                            "**3. O 'SDR' Virtual:** Cobrar o lead 2 horas depois funcionou perfeitamente. 376 pessoas receberam a cobrança automática e isso resgatou quem tinha esquecido de assistir.\n\n"
                            "**4. Baixa Rejeição:** Mesmo com várias mensagens, apenas 42 pessoas (1,3%) bloquearam o contato. A base é excelente e quer receber o conteúdo."
                        )
                        
                        st.markdown("### 🎯 Regra de Ouro para o Próximo Lançamento")
                        st.error(
                            "**Comunicação Direta (Foco na Conversão):** O perfil desse lead não gosta de ficar clicando em interações longas. "
                            "O nosso objetivo final é **fazer ele assistir a aula sem sair do WhatsApp**. "
                            "Para os próximos disparos, devemos entregar o link da aula **direto na primeira mensagem**, sem botões de 'Receber Informação'. "
                            "Também devemos evitar mandar o lead para outras redes (como o Instagram) no meio do fluxo, pois isso tira o foco do objetivo principal."
                        )
                    elif disparo_selecionado == "2️⃣ Engajamento":
                        st.markdown("### ✅ O Contraste Perfeito (Aviso Direto)")
                        st.markdown("Neste pequeno disparo, testamos enviar apenas uma mensagem super curta: *'Vou deixar o link aqui...'* (Sem enrolação, sem pedir cliques extras).")
                        
                        col1, arr1, col2, arr2, col3 = st.columns([3, 1, 3, 1, 3])
                        with col1:
                            with st.container(border=True):
                                st.metric("1. Enviados", "164", "Pessoas", delta_color="off")
                        with arr1:
                            st.markdown("<h2 style='text-align: center; margin-top: 15px;'>➔</h2>", unsafe_allow_html=True)
                        with col2:
                            with st.container(border=True):
                                st.metric("2. Entregues", "164", "100% de Entrega", delta_color="normal")
                        with arr2:
                            st.markdown("<h2 style='text-align: center; margin-top: 15px;'>➔</h2>", unsafe_allow_html=True)
                        with col3:
                            with st.container(border=True):
                                st.metric("3. Clicaram no Link", "36", "22% de Conversão", delta_color="normal")
                                
                        st.markdown("<br>", unsafe_allow_html=True)
                        
                        st.success('**🎯 Lição Aprendida (A Regra do Menos é Mais):** Compare esse fluxo minúsculo com o labirinto do Disparo Principal (onde 2.000 pessoas desistiram). Aqui, nós entregamos o link diretamente na mão de 164 pessoas. O resultado? **Todos receberam a mensagem e 22% clicaram na mesma hora!** Isso prova matematicamente que a nossa base é altamente reativa quando o caminho é fácil.')

                    elif disparo_selecionado == "3️⃣ Reprise e Ao Vivo":
                        st.markdown("### 🕵️‍♀️ A Repescagem (Reprise e Lembrete da Aula 2)")
                        st.markdown("No dia seguinte, o robô foi atrás de quem perdeu a aula para entregar a Gravação (Reprise) e já avisar do Ao Vivo que ia acontecer.")
                        
                        st.info('**⏳ A Regra das 24 Horas do WhatsApp:** O WhatsApp não deixa o robô mandar mensagens automáticas gratuitas para sempre. Ele só permite falar de graça com quem respondeu algo nas últimas 24h. Das 887 pessoas da repescagem, **apenas 230 (25%) ainda estavam dentro desse limite**. Esses 230 são o que chamamos de leads "Super-Engajados".')
                        
                        st.warning('**🔥 O Poder da palavra "Ao Vivo":** Quando a mensagem oferecia a gravação (Reprise), 15% das pessoas clicavam. Mas, para os Super-Engajados que receberam o alerta "Estamos Ao Vivo agora!", o clique pulou para incríveis **26%**! A urgência gera muito mais cliques.')
                                        
                        cpl1_funnel = dict(
                            number=[887, 878, 712, 137],
                            stage=["Base Selecionada (Reprise)", "Entregues (99%)", "Abriram a Mensagem (80%)", "Clicaram na Reprise (15%)"]
                        )
                        fig_f1 = go.Figure(go.Funnel(
                            y=cpl1_funnel["stage"],
                            x=cpl1_funnel["number"],
                            textinfo="value+percent initial",
                            marker={"color": ["#4B8BBE", "#28a745", "#555555", "#FF4B4B"]}
                        ))
                        fig_f1.update_layout(title="Aviso da Reprise (Aula 1)", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_color="#FFF" if st.get_option("theme.base") == "dark" else "#000", height=350, margin=dict(t=50, b=0))
                        
                        cpl1_live = dict(
                            number=[230, 229, 189, 59],
                            stage=["Super-Engajados (Restaram na Janela 24h)", "Entregues (100%)", "Abriram o 'Ao Vivo' (82%)", "Clicaram na Aula 2 (26%)"]
                        )
                        fig_f2 = go.Figure(go.Funnel(
                            y=cpl1_live["stage"],
                            x=cpl1_live["number"],
                            textinfo="value+percent initial",
                            marker={"color": ["#4B8BBE", "#28a745", "#555555", "#FFD43B"]}
                        ))
                        fig_f2.update_layout(title="Lembrete 'Ao Vivo' (Aula 2)", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_color="#FFF" if st.get_option("theme.base") == "dark" else "#000", height=350, margin=dict(t=50, b=0))
                        
                        col_c1, col_c2 = st.columns(2)
                        with col_c1:
                            st.plotly_chart(fig_f1, use_container_width=True)
                        with col_c2:
                            st.plotly_chart(fig_f2, use_container_width=True)
                    
                        st.success('**💡 Dinheiro na Mesa (Oportunidade de Ouro):** O WhatsApp bloqueou quase 650 pessoas (que já tinham saído da Janela de 24h gratuitas) de receberem o aviso de que a Live estava começando. \n\n**A Solução para o Próximo Lançamento:** Basta pagar alguns centavos por lead e mandar uma "Mensagem Oficial" da Meta passando por cima dessa regra das 24h. Se pagássemos para avisar essas 650 pessoas atrasadas, e elas clicassem na mesma taxa de 26%, teríamos jogado **mais de 160 pessoas extras na sua Live** instantaneamente. O custo das mensagens é moedas perto do lucro das vendas que elas fariam!')

                elif cpl_selecionado == "CPL 02":
                    st.markdown("### 📈 Performance da CPL 02 (Aula 2 - Inscritos)")
                    
                    st.markdown("#### 🚧 Fase 1: O Filtro Inicial (Gargalo de Público)")
                    col0, arr0, col1 = st.columns([3, 1, 3])
                    
                    with col0:
                        with st.container(border=True):
                            st.metric("1. Público Total Selecionado", "4.568", "Pessoas com a tag", delta_color="off")
                    with arr0:
                        st.markdown("<h2 style='text-align: center; margin-top: 15px;'>➔</h2>", unsafe_allow_html=True)
                    with col1:
                        with st.container(border=True):
                            st.metric("2. Passaram no Filtro Inicial", "896", "19,6% da base total", delta_color="normal")
                            
                    st.error('**🚨 Bloqueio por Falta de Verba (Filtro Involuntário):** Logo na largada, o disparo parou de enviar para **80% da base**. O motivo não foi uma condição lógica do fluxo, mas sim **Falta de Verba**. A reclassificação inesperada do template para a tarifa de Marketing sugou o saldo da carteira instantaneamente, e a plataforma bloqueou os disparos. Tentar recarregar e forçar como Utility depois não reverteu a perda do *timing* do envio.')
                    
                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    st.markdown("#### 🔀 Fase 2: O Desempenho dos 896 Leads (O que eles escolheram?)")
                    
                    col_a, col_b, col_c = st.columns(3)
                    
                    with col_a:
                        with st.container(border=True):
                            st.markdown("<h4 style='text-align: center; color: #22c55e;'>🟢 'Assistir Agora'</h4>", unsafe_allow_html=True)
                            st.metric("Chegaram na Etapa", "63 leads", "7% da Base", delta_color="off")
                            st.markdown("<h3 style='text-align: center;'>⬇️</h3>", unsafe_allow_html=True)
                            st.metric("Foram pra Aula (Conversão)", "55 cliques", "87,3% de Conversão", delta_color="normal")
                            
                    with col_b:
                        with st.container(border=True):
                            st.markdown("<h4 style='text-align: center; color: #f59e0b;'>🟡 'Já Assisti'</h4>", unsafe_allow_html=True)
                            st.metric("Chegaram na Etapa", "79 leads", "8,8% da Base", delta_color="off")
                            st.markdown("<h3 style='text-align: center;'>⬇️</h3>", unsafe_allow_html=True)
                            st.metric("Foram pro Instagram", "25 cliques", "🚨 Desvio (Fuga de 68%)", delta_color="off")
                            
                    with col_c:
                        with st.container(border=True):
                            st.markdown("<h4 style='text-align: center; color: #ef4444;'>🔴 'Parar Mensagem'</h4>", unsafe_allow_html=True)
                            st.metric("Chegaram na Etapa", "7 leads", "0,7% da Base", delta_color="off")
                            st.markdown("<h3 style='text-align: center;'>⬇️</h3>", unsafe_allow_html=True)
                            st.metric("Descadastrados", "Fim do Fluxo", "", delta_color="off")
                            
                    st.markdown("---")
                    st.markdown("### 🧠 Diagnóstico Executivo e Regra de Ouro (CPL 02)")
                    st.info(
                        "**1. A Alta Intenção da Base:** Dos 63 leads que escolheram 'Assistir Agora', 55 de fato foram para a aula (uma taxa brutal de 87,3%). Isso mostra que quando oferecemos o caminho direto para o objetivo, a conversão é quase garantida.\n\n"
                        "**2. A Regra de Ouro Violada:** Lembra que o perfil desse lead **não quer ser distraído**? No caminho 'Já Assisti', criamos um labirinto de 3 passos para levá-los a comentar no Instagram. Resultado: de 79 pessoas super engajadas que chegaram, apenas 25 concluíram no Instagram. "
                        "Desperdiçamos a energia de 54 pessoas hiper-engajadas em um fluxo de interação longa, que poderiam estar sendo redirecionadas para um Resumo em PDF ou oferta VIP.\n\n"
                        "**3. O Efeito Dominó do Custo (Falta de Verba):** O template foi aprovado originalmente como 'Utility' (gratuito/barato), mas durante o disparo a Meta reclassificou as mensagens para 'Marketing' (Marketing Lite). Essa mudança gerou um custo inesperado de **US$ 36,98** que esgotou o saldo da carteira instantaneamente. Esse foi o verdadeiro motivo de 80% da base não ter recebido a Aula 2: o fluxo simplesmente foi interrompido por falta de fundos."
                    )
                
                elif cpl_selecionado == "CPL 03":
                    st.markdown("### 📈 Performance da CPL 03 (Aula 3: Teste A/B/C e Resgate)")
                    
                    st.markdown("---")
                    st.markdown("### 🧪 Disparo 1: O Teste A/B/C (A Base Toda)")
                    st.markdown("Um randomizador dividiu a base para testar qual copy convertia mais cliques para a Aula 3. Infelizmente, este disparo também foi vítima da taxação da Meta.")
                    
                    col0, arr0, col1 = st.columns([3, 1, 3])
                    with col0:
                        with st.container(border=True):
                            st.metric("Público Alvo (Aviso Aula 3)", "4.501", "Pessoas", delta_color="off")
                    with arr0:
                        st.markdown("<h2 style='text-align: center; margin-top: 15px;'>➔</h2>", unsafe_allow_html=True)
                    with col1:
                        with st.container(border=True):
                            st.metric("Enviados Reais", "1.269", "Interrompido por Falta de Verba", delta_color="normal")
                            
                    st.markdown("<br>", unsafe_allow_html=True)
                    st.markdown("#### 📊 Resultado do Teste de Copys")
                    
                    col_a, col_b, col_c = st.columns(3)
                    with col_a:
                        with st.container(border=True):
                            st.markdown("<h4 style='text-align: center; color: #94a3b8;'>Copy A (Direta s/ Img)</h4>", unsafe_allow_html=True)
                            st.metric("Enviados", "433 leads", "", delta_color="off")
                            st.metric("Cliques Totais", "39 cliques", "CTR 9%", delta_color="off")
                            
                    with col_b:
                        with st.container(border=True):
                            st.markdown("<h4 style='text-align: center; color: #facc15;'>🏆 Copy B (Pergunta c/ Img)</h4>", unsafe_allow_html=True)
                            st.metric("Enviados", "409 leads", "", delta_color="off")
                            st.metric("Cliques Totais", "41 cliques", "CTR 10%", delta_color="off")
                            
                    with col_c:
                        with st.container(border=True):
                            st.markdown("<h4 style='text-align: center; color: #94a3b8;'>Copy C (Pergunta s/ Img)</h4>", unsafe_allow_html=True)
                            st.metric("Enviados", "427 leads", "", delta_color="off")
                            st.metric("Cliques Totais", "34 cliques", "CTR 8%", delta_color="off")
                            
                    st.markdown("<br>", unsafe_allow_html=True)
                    st.markdown("#### 🔀 O Desempenho dos 3 Caminhos (União das 3 Copys)")
                    
                    col_path_a, col_path_b, col_path_c = st.columns(3)
                    
                    with col_path_a:
                        with st.container(border=True):
                            st.markdown("<h4 style='text-align: center; color: #22c55e;'>🟢 'Assistir Agora'</h4>", unsafe_allow_html=True)
                            st.metric("Receberam o Link", "74 leads", "A união dos cliques", delta_color="off")
                            st.markdown("<h3 style='text-align: center;'>⬇️</h3>", unsafe_allow_html=True)
                            st.metric("Follow-up (1h depois)", "19 respostas", "Sim / Ainda Não", delta_color="normal")
                            
                    with col_path_b:
                        with st.container(border=True):
                            st.markdown("<h4 style='text-align: center; color: #f59e0b;'>🟡 'Já Assisti'</h4>", unsafe_allow_html=True)
                            st.metric("Chegaram na Etapa", "36 leads", "A união dos cliques", delta_color="off")
                            st.markdown("<h3 style='text-align: center;'>⬇️</h3>", unsafe_allow_html=True)
                            st.metric("Foram pro Instagram", "12 cliques", "🚨 Fuga de 66%", delta_color="off")
                            
                    with col_path_c:
                        with st.container(border=True):
                            st.markdown("<h4 style='text-align: center; color: #ef4444;'>🔴 'Parar Mensagem'</h4>", unsafe_allow_html=True)
                            st.metric("Chegaram na Etapa", "17 leads", "A união dos cliques", delta_color="off")
                            st.markdown("<h3 style='text-align: center;'>⬇️</h3>", unsafe_allow_html=True)
                            st.metric("Descadastrados", "17 pessoas", "Fim do Fluxo", delta_color="off")

                    st.markdown("<br>", unsafe_allow_html=True)
                    st.markdown("#### 🔄 Análise do Caminho Verde (O Follow-up Inteligente)")
                    st.info("Para os 74 leads que clicaram para receber o link da aula, a automação inovou: aguardou 1 hora e fez uma verificação ativa ('Deu tempo de assistir à Aula 3?'). Isso é excelente para segmentar quem realmente consumiu o conteúdo na boca do funil.")

                    st.markdown("---")
                    st.markdown("### 🛟 Disparo 2: O Resgate Super Segmentado (Reprise)")
                    st.markdown("Este disparo foi direcionado a um grupo hiper restrito, focado na transição para a oferta.")
                    
                    col_path_1, col_path_2 = st.columns(2)
                    
                    with col_path_1:
                        with st.container(border=True):
                            st.markdown("<h4 style='text-align: center; color: #94a3b8;'>📣 Aviso de Reprise</h4>", unsafe_allow_html=True)
                            st.metric("Enviados", "65 leads", "Filtro altamente restrito", delta_color="off")
                            st.markdown("<h3 style='text-align: center;'>⬇️</h3>", unsafe_allow_html=True)
                            st.metric("Cliques no Link", "15 cliques", "CTR 23,4%", delta_color="normal")
                            st.error("**⚠️ Erro de Conversão:** O link da aula foi enviado **embutido no texto** em vez de um botão clicável abaixo da mensagem. É fundamental **'colocar o botão'** sempre. Mensagens com botões reduzem a fricção visual e convertem drasticamente mais do que links perdidos no meio de um parágrafo longo.")
                            
                    with col_path_2:
                        with st.container(border=True):
                            st.markdown("<h4 style='text-align: center; color: #22c55e;'>🔥 O Convite VIP</h4>", unsafe_allow_html=True)
                            st.metric("Follow-up (2 Dias Depois)", "60 leads", "Convite Grupo VIP", delta_color="off")
                            st.markdown("<h3 style='text-align: center;'>⬇️</h3>", unsafe_allow_html=True)
                            st.metric("Entraram no Grupo", "17 cliques", "CTR 28,3%", delta_color="normal")
                            st.success("O engajamento subiu! O envio do convite para o 'Grupo de Super Interessados' funcionou muito bem, atraindo 28% daqueles que receberam a mensagem de transição de vendas.")
                            
                    st.markdown("---")
                    st.markdown("### 🧠 Diagnóstico Executivo (CPL 03)")
                    st.info(
                        "**1. A Força da Imagem (Teste A/B/C):** O Disparo 1 provou que mandar o aviso da aula fazendo uma pergunta atrelada a uma imagem (Copy B) tem o melhor CTR (10%). O uso de mídias aumenta a atenção na caixa de entrada do WhatsApp em relação ao texto puro.\n\n"
                        "**2. A Transição para Vendas (Convite VIP):** O Disparo 2 focou em uma base micro (65 leads) e, apesar do erro tático de enviar o link dentro do texto e não em um botão (aumentando a fricção), ele engrenou muito bem para o 'Grupo de Super Interessados', alcançando um excelente CTR de 28,3%. Isso mostra que leads na fase final de CPL têm apetite por exclusividade.\n\n"
                        "**3. Punição Financeira Repetida:** O histórico mostra o mesmo padrão da CPL 02. O WhatsApp cobrou as mensagens em massa como 'Marketing', gerando um custo alto que esgotou a verba e travou os disparos. É urgente adaptar a copy (texto) para soar menos promocional ao algoritmo da Meta."
                    )
                elif cpl_selecionado == "CPL 04":
                    st.markdown("### 📉 Performance da CPL 04 (Aula 4 Ao Vivo)")
                    
                    st.markdown("#### 🚨 O Retorno do 'Erro Fatal' (Botão de Consentimento)")
                    st.markdown("Na reta final do lançamento, o disparo da CPL 04 repetiu **exatamente o mesmo gargalo da CPL 01**. Em vez de enviar o link direto para a aula, a automação obrigou a base fria a clicar em um botão de 'Receber Informação'. O resultado foi catastrófico para a tração.")
                    
                    col1, arr1, col2, arr2, col3, arr3, col4 = st.columns([2, 1, 2, 1, 2, 1, 2])
                    with col1:
                        with st.container(border=True):
                            st.metric("1. Enviados", "4.543", "Base", delta_color="off")
                    with arr1:
                        st.markdown("<h2 style='text-align: center; margin-top: 15px;'>➔</h2>", unsafe_allow_html=True)
                    with col2:
                        with st.container(border=True):
                            st.metric("2. Entregues", "4.124", "91% de Entrega", delta_color="normal")
                    with arr2:
                        st.markdown("<h2 style='text-align: center; margin-top: 15px;'>➔</h2>", unsafe_allow_html=True)
                    with col3:
                        with st.container(border=True):
                            st.metric("3. 'Receber Info'", "159", "4% CTR", delta_color="inverse")
                    with arr3:
                        st.markdown("<h2 style='text-align: center; margin-top: 15px;'>➔</h2>", unsafe_allow_html=True)
                    with col4:
                        with st.container(border=True):
                            st.metric("4. Assistiram", "89", "2,1% Real", delta_color="inverse")
                    
                    st.error('**⚠️ Fuga de 3.919 Leads (95% da base entregue):** Ao usar o botão de "Receber Informação", a imensa maioria dos leads ignorou a mensagem. Apenas 159 pediram o link. Desses 159, apenas 89 de fato clicaram na Aula 04. Em um universo de 4,5 mil envios, levar apenas 89 pessoas para a aula final é um desperdício enorme de potencial e de verba.')
                    
                    st.markdown("<br>", unsafe_allow_html=True)
                    st.markdown("#### 💎 A Luz no Fim do Túnel (Retenção no Grupo VIP)")
                    st.markdown("Para os parcos 89 leads que passaram pelo funil e clicaram na aula, a automação fez um disparo de repescagem 2 horas depois, convidando-os para o **Grupo VIP de Super Interessados**.")
                    
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.metric("Convites VIP Enviados", "81")
                    with c2:
                        st.metric("Visualizações da Mensagem", "59", "73% Open Rate")
                    with c3:
                        st.metric("Entraram no VIP", "13", "16% de Conversão (Altíssimo)")
                    
                    st.success("**🧠 Insight de Fechamento:** Aqueles que sobrevivem ao funil são extremamente engajados. Uma conversão de 16% direto para um Grupo VIP é fantástica. Se não houvesse o gargalo inicial do botão, teríamos centenas de pessoas a mais nesse grupo de fechamento.")
                    
                    st.markdown("<br>", unsafe_allow_html=True)
                    st.markdown("### 🧠 Diagnóstico Executivo (CPL 04)")
                    st.warning(
                        "**1. A Síndrome do Refil (Não Aprender com o Erro):** O funil da CPL 04 foi desenhado ignorando a principal métrica da CPL 01. O botão 'Receber Informação' atua como uma muralha, matando a escala do tráfego orgânico/pago e penalizando o engajamento da conta na Meta.\\n\\n"
                        "**2. Taxa de Mortalidade Absurda:** De 4.124 mensagens entregues no WhatsApp da pessoa, extrair apenas 89 cliques reais na aula revela uma taxa de conversão real de 2,1%. Uma Copy de entrega direta de link traria entre 10% a 22% (provado nos disparos da CPL 02 e CPL 03).\\n\\n"
                        "**3. Estratégia VIP Validada:** O atraso inteligente de 2 horas após o clique na aula para oferecer o Grupo VIP se provou excelente (16% de retenção). Esse fluxo secundário de 'Super Interessados' está totalmente validado e deve ser usado com força no pós-carrinho."
                    )
                
                else:
                    dados_cpl = df_cpl[df_cpl['CPL'] == cpl_selecionado].iloc[0]
                    data_disp = dados_cpl.get('Data_Disparo', 'N/D')
                    st.markdown(f"### 📈 Performance do {cpl_selecionado} (Disparado em {data_disp})")
                    
                    disp = dados_cpl['Disparados']
                    ent = dados_cpl['Entregues']
                    cli = dados_cpl['Cliques']
                    custo = dados_cpl['Custo_US']
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Enviado", f"{disp:,}".replace(',','.'))
                    with col2:
                        tx_ent = (ent/disp)*100 if disp > 0 else 0
                        st.metric("Entregue", f"{ent:,}".replace(',','.'), f"{tx_ent:.1f}% de Entrega", delta_color="normal")
                    with col3:
                        tx_cli = (cli/ent)*100 if ent > 0 else 0
                        st.metric("Cliques", f"{cli:,}".replace(',','.'), f"{tx_cli:.1f}% CTR", delta_color="normal")
                    
                    fig_funnel = go.Figure(go.Funnel(
                        y=["Enviados", "Entregues (Inbox)", "Cliques (Acessos)"],
                        x=[disp, ent, cli],
                        textinfo="value+percent previous",
                        marker={"color": ["#4B8BBE", "#28a745", "#FFD43B"]}
                    ))
                    fig_funnel.update_layout(margin=dict(t=20, b=20), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                    st.plotly_chart(fig_funnel, use_container_width=True)
                    
                    if tx_cli < 10:
                        st.error(f"**🚨 Alerta Crítico:** A taxa de clique do {cpl_selecionado} despencou para {tx_cli:.1f}%. Enviar link para uma base fria (ou com copy fraca) destrói o CTR. Reveja a chamada de ação para os próximos envios.")
                    else:
                        st.success(f"**✅ Insight Estratégico Multi-Copy:** O {cpl_selecionado} alcançou um CTR de {tx_cli:.1f}% ao combinar duas abordagens de copywriting no mesmo fluxo. **1. Recuperação (Reprise):** A primeira copy age com utilidade ('se ainda não assistiu... vou deixar o link'), repescando leads sem pressão. **2. Escassez e Urgência (Ao Vivo):** A segunda copy ataca com um micro-compromisso imediato ('Bora? Estamos ao vivo agora!'). **Plano de Ação:** A conversão foi fortíssima porque a copy atendeu a dois perfis (o atrasado e o pontual). Mantenha essa dobra de comunicação para os próximos CPLs.")
                    
                    cpc = custo / cli if cli > 0 else 0
                    st.info(f"💰 **Inteligência Financeira (ROI da Automação):** O {cpl_selecionado} teve um volume total de **{disp} disparos** processados pelo Manychat, gerando um custo operacional de **US$ {custo:.2f}**. Considerando os **{cli} cliques absolutos** recebidos, o seu Custo Por Clique (CPC) direto no WhatsApp foi de apenas **US$ {cpc:.2f}**. Um tráfego extremamente barato, hiper qualificado e que não depende do algoritmo do Instagram para entregar!")

    elif menu_selecionado == '2️⃣ Vendas e Carrinho':
        st.header("2️⃣ Captação de Vendas e Abandono de Carrinho")
        st.markdown("Monitoramento de eventos (Vendas Aprovadas vs Abandono de Checkout).")
        
        try:
            # Lendo direto da Planilha no Google Sheets (preparado para Streamlit Cloud)
            url_vendas = "https://docs.google.com/spreadsheets/d/1Sd7-iunFKcgpuexlWMC_IC3JO1pcR2x14utRYPpKggs/gviz/tq?tqx=out:csv&sheet=%5Bpop-up%5D%20Vendas"
            url_recuperacao = "https://docs.google.com/spreadsheets/d/1Sd7-iunFKcgpuexlWMC_IC3JO1pcR2x14utRYPpKggs/gviz/tq?tqx=out:csv&sheet=%F0%9F%93%88%20Recupera%C3%A7%C3%A3o%20de%20Vendas"
            
            df_vendas = pd.read_csv(url_vendas)
            df_recuperacao = pd.read_csv(url_recuperacao)
            
            # Filtro Data: a partir de 17/08/2026 07:00:27
            df_vendas['DATA'] = pd.to_datetime(df_vendas['DATA'], format='%d/%m/%Y %H:%M:%S', errors='coerce')
            df_vendas = df_vendas[df_vendas['DATA'] >= '2026-08-17 07:00:27']
            
            df_recuperacao['DATA'] = pd.to_datetime(df_recuperacao['DATA'], format='%d/%m/%Y %H:%M:%S', errors='coerce')
            df_recuperacao = df_recuperacao[df_recuperacao['DATA'] >= '2026-08-17 07:00:27']
            
            # Métricas Vendas
            total_leads = len(df_vendas)
            compras = len(df_vendas[df_vendas['Comprou?'] == 'Sim'])
            abandonos = len(df_vendas[df_vendas['Comprou?'] == 'Não'])
            taxa_conversao = (compras / total_leads * 100) if total_leads > 0 else 0
            
            receita_gerada = compras * 1497
            receita_perdida = abandonos * 1497
            
            # Métricas Recuperação
            recup_total = len(df_recuperacao)
            recup_msg_enviada = len(df_recuperacao[df_recuperacao['STATUS PÓS AUTOMAÇÃO'] == 'Mensagem Enviada'])
            recup_compraram_msg = len(df_recuperacao[(df_recuperacao['STATUS PÓS AUTOMAÇÃO'] == 'Mensagem Enviada') & (df_recuperacao['Comprou?'] == 'Sim')])
            
            cobertura = (recup_msg_enviada / recup_total * 100) if recup_total > 0 else 0

            # --- TOPO: Resumo Executivo ---
            st.markdown("### 💰 Financeiro & Conversão")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Leads (Checkout)", total_leads)
            c2.metric("Conversão", f"{taxa_conversao:.1f}%", f"{compras} Vendas")
            c3.metric("Receita Gerada", f"R$ {receita_gerada:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            c4.metric("Valor 'Na Mesa'", f"R$ {receita_perdida:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), delta="- Abandonos", delta_color="inverse")
            
            # --- MEIO: Cobertura da Automação (Storytelling) ---
            st.markdown("---")
            st.markdown("### 🤖 Motor de Recuperação Ativa")
            
            col_chart, col_insight = st.columns([1, 1])
            
            with col_chart:
                fig_gauge = go.Figure(go.Indicator(
                    mode = "gauge+number",
                    value = cobertura,
                    number = {'suffix': "%"},
                    title = {'text': "Cobertura da Automação (Envios)"},
                    gauge = {
                        'axis': {'range': [None, 100]},
                        'bar': {'color': "#4CAF50"},
                        'steps': [
                            {'range': [0, 50], 'color': "#2b1a1a"},
                            {'range': [50, 80], 'color': "#3e3e1c"},
                            {'range': [80, 100], 'color': "#1a2b1a"}
                        ]
                    }
                ))
                fig_gauge.update_layout(height=250, margin=dict(l=10, r=10, t=40, b=10), paper_bgcolor="rgba(0,0,0,0)", font={'color': "white"})
                st.plotly_chart(fig_gauge, use_container_width=True)
                
            with col_insight:
                st.markdown(f"""
                <div style="background-color: #1e1e1e; padding: 20px; border-radius: 10px; border-left: 5px solid #00E676;">
                    <h4>🔥 Insight de ROI da Automação</h4>
                    <p>A automação enviou mensagens para <b>{recup_msg_enviada} dos {recup_total}</b> abandonos rastreados.</p>
                    <p>O mais impressionante: <b>{recup_compraram_msg} clientes compraram APÓS receber a mensagem</b>, provando que o fluxo está recuperando faturamento diretamente!</p>
                </div>
                """, unsafe_allow_html=True)
            
            # --- BASE: Matriz de Qualidade / Acionável ---
            st.markdown("---")
            st.markdown("### 🎯 Fila de Recuperação Prioritária (Leads Quentes)")
            
            # Tratamento da tabela para UX
            df_fila = df_vendas[df_vendas['Comprou?'] == 'Não'].copy()
            df_fila['Mensagem Enviada'] = df_fila['Mensagem Enviada'].fillna('')
            df_fila['Status Fila'] = df_fila.apply(
                lambda x: "🔴 ALERTA: Valido s/ Mensagem" if x['TELEFONE_STATUS'] == 'VALIDO' and x['Mensagem Enviada'] == '' 
                else ("🟡 Aguardando Resposta" if x['Mensagem Enviada'] != '' else "⚪ Frio (Erro Cliente)"), axis=1
            )
            
            def color_status(val):
                color = 'red' if 'ALERTA' in val else ('orange' if 'Aguardando' in val else 'gray')
                return f'color: {color}; font-weight: bold;'
                
            colunas_exibicao = ['DATA', 'NOME', 'TELEFONE_STATUS', 'TELEFONE_DIAGNOSTICO', 'Status Fila']
            df_display = df_fila[colunas_exibicao].sort_values(by='Status Fila')
            
            try:
                st.dataframe(df_display.style.map(color_status, subset=['Status Fila']), use_container_width=True, hide_index=True)
            except AttributeError:
                st.dataframe(df_display.style.applymap(color_status, subset=['Status Fila']), use_container_width=True, hide_index=True)
            
            st.markdown('<div class="alert-box" style="border-left: 5px solid #FF4B4B; background-color: #2b1a1a; padding: 15px; border-radius: 8px;"><b>🚨 Atenção Comercial:</b> Os leads marcados em <b>Vermelho</b> não receberam a mensagem automática, MAS possuem telefones válidos! Ligar imediatamente. (Ex: Lorenzo, Joao Arthur).</div>', unsafe_allow_html=True)
            
            st.markdown("<br><br>", unsafe_allow_html=True)

        except Exception as e:
            st.error(f"Erro ao processar dados de vendas: {e}")

    elif menu_selecionado == '5️⃣ E-mails':
        st.header("5️⃣ Performance de E-mail Marketing")
        
        df_email = pd.DataFrame({
            "Métrica": ["Enviados", "Aberturas (Open Rate)", "Cliques (CTR)"],
            "Valor": [10000, 200, 15]
        })
        
        fig_email = go.Figure(go.Funnel(
            y=df_email['Métrica'],
            x=df_email['Valor'],
            textinfo="value+percent initial",
            marker={"color": ["#2C3E50", "#E74C3C", "#27AE60"]}
        ))
        st.plotly_chart(fig_email, use_container_width=True)
        
        st.markdown('<div class="alert-box" style="padding: 15px; border-radius: 8px; background-color: #2b1a1a; border-left: 5px solid #FF4B4B;"><b>❌ Insight de Canal:</b> A dependência de E-mail Marketing para a Venda (Carrinho Aberto) foi letal. O Open Rate de 2% significa que de 10.000 pessoas, apenas 200 viram que o carrinho abriu.</div>', unsafe_allow_html=True)
        
else:
    st.warning("Não foi possível carregar os dados. Verifique a planilha.")
