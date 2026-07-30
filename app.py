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


st.title("📊 Dashboard de Lançamento e Boas-Vindas")
st.markdown("Acompanhamento em tempo real de conversão e perfil dos leads capturados.")

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
        aba_grupo_emp = urllib.parse.quote(" 📈 Grupos - Empreendedores") # O espaço extra no início existe na planilha
        
        # O "&_t=..." força o Google Sheets a entregar a versão mais nova ignorando o próprio cache
        timestamp = int(time.time())
        url_captacao = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={aba_captacao}&_t={timestamp}"
        url_boasvindas = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={aba_boasvindas}&_t={timestamp}"
        url_grupo_tec = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={aba_grupo_tec}&_t={timestamp}"
        url_grupo_emp = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={aba_grupo_emp}&_t={timestamp}"
        
        df_captacao = pd.read_csv(url_captacao)
        df_boasvindas = pd.read_csv(url_boasvindas)
        df_grupo_tec = pd.read_csv(url_grupo_tec)
        df_grupo_emp = pd.read_csv(url_grupo_emp)
        
        return df_captacao, df_boasvindas, df_grupo_tec, df_grupo_emp
    except Exception as e:
        st.error(f"Erro ao ler o Google Sheets: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

df_captacao, df_boasvindas, df_grupo_tec, df_grupo_emp = carregar_dados()

if not df_captacao.empty:
    # --- SISTEMA DE ACESSO ADMIN (URL SECRETA) ---
    is_admin = st.query_params.get("admin") == "mda2026"
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🧭 Navegação")
    
    if is_admin:
        opcoes_menu = ['📊 Visão Principal', '🕸️ Funil Manychat (WPP)', '🚨 Monitoramento Avançado', '🧠 Plano de Ação']
    else:
        opcoes_menu = ['📊 Visão Principal', '🕸️ Funil Manychat (WPP)']
        
    menu_selecionado = st.sidebar.radio("Ir para:", opcoes_menu, label_visibility="collapsed")

    # --- PROCESSAMENTO DOS KPIs GLOBAIS ---
    total_capturados = len(df_captacao)
    total_automação = len(df_boasvindas)

    # Métrica de Entregues: leads que possuem a tag específica do evento atual
    if 'tag_atual' in df_boasvindas.columns:
        sucesso_envio = len(df_boasvindas[df_boasvindas['tag_atual'].astype(str).str.contains('lc7_mde_ago26_boas_vindas_inicial_enviada', case=False, na=False)])
    else:
        sucesso_envio = 0

    # Métrica de Erros: leads que possuem a sinalização exata de 'erro' na coluna status_boas_vindas
    if 'status_boas_vindas' in df_boasvindas.columns:
        erros = len(df_boasvindas[df_boasvindas['status_boas_vindas'].astype(str).str.strip().str.lower() == 'erro'])
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
        
        df_erros = df_boasvindas[df_boasvindas['status_boas_vindas'] == 'erro'].copy()
    
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
            
            df_erros_display = df_erros[['created_at', 'lead_name', 'lead_phone', 'diagnostico_do_erro', 'utm_source']].copy()
            df_erros_display = df_erros_display.rename(columns={
                'created_at': 'Data/Hora',
                'lead_name': 'Nome',
                'lead_phone': 'Telefone',
                'diagnostico_do_erro': 'Diagnóstico do Erro',
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
            st.metric("Total de Envios", "1478", help="Total de pessoas que entraram no fluxo (V1+V2+V3)")
        with col2:
            st.metric("Taxa de Entrega", "95.1%", delta="Excelente", help="Leads que efetivamente receberam a mensagem (1405/1478)")
        with col3:
            st.metric("Taxa de Clique (CTR)", "58.6%", help="824 cliques de interesse em 1405 entregas")
        with col4:
            st.metric("Opt-out (Rejeição)", "2.4%", delta="Menor é melhor", delta_color="inverse", help="O Manychat cravou 35 descadastros (2.4%).")
            
        st.markdown("---")
        import plotly.graph_objects as go
        
        if visao_funil == "Visão Macro (Consolidado)":
            col_a, col_b = st.columns([2, 1])
            with col_a:
                st.subheader(
                    "🌪️ Funil de Conversão (Global)",
                    help="**Glossário do Funil:**\\n\\n**1. Total Disparado:** Todos os leads acionados pela automação (V1+V2+V3).\\n\\n**2. Entregue no Celular:** Leads que de fato receberam a mensagem (excluindo números inválidos ou sem internet no momento).\\n\\n**3. Interesse:** Soma de todos os cliques na 1ª Mensagem.\\n\\n**4. Escolheu Perfil:** Total de leads que optaram por 'Técnico' ou 'Empreendedor'.\\n\\n**5. Assistiu ao Vídeo:** Total que chegou na página do Grupo VIP.\\n\\n**6. Recebeu Pesquisa:** Leads que permaneceram e receberam a pesquisa.\\n\\n**7. Concluiu (Fim):** Aqueles que preencheram a pesquisa e concluíram a jornada."
                )
                fig_sankey = go.Figure(go.Funnel(
                    y=["1. Disparado", "2. Entregue", "3. Interesse (Cliques)", "4. Escolheu Perfil", "5. Assistiu Vídeo", "6. Recebeu Pesquisa", "7. Concluiu (Fim)"],
                    x=[1478, 1405, 824, 746, 729, 370, 202],
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
                        "Leads finais super quentes que preencheram a pesquisa e chegaram ao fim do funil."
                    ],
                    marker={"color": ["#B0C4DE", "#87CEFA", "#4B8BBE", "#4B8BBE", "#4B8BBE", "#FFD43B", "#FFD43B"]}
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
                df_pie = pd.DataFrame({'Perfil': ['Técnicos', 'Empreendedores'], 'Qtd': [598, 148]})
                fig_pie = px.pie(df_pie, values='Qtd', names='Perfil', hole=0.4, color_discrete_sequence=['#F97316', '#8B5CF6'])
                fig_pie.update_layout(height=400, margin=dict(l=0, r=0, t=20, b=0))
                st.plotly_chart(fig_pie, use_container_width=True)

            st.markdown("### 🚨 Diagnóstico de Gargalos")
            st.info("**Insight DBA:** Os dados de disparo inicial foram atualizados. Vemos que 58.6% dos leads demonstram interesse na 1ª mensagem (v1, v2, v3). O público atraído consolida-se em ~80% Técnicos (598) e ~20% Empreendedores (148).\\n\\n**♻️ Retenção no Opt-out:** O botão 'Parar Mensagens' foi acionado por 35 pessoas, porém, 30 chegaram ao nó de descadastro e **5 delas (17%)** clicaram em 'Mudei de ideia', voltando para o funil. Essa estratégia salvou leads que seriam perdidos!\\n\\n**🏆 O Pote de Ouro:** Dos 202 leads que terminam a jornada e concluem a pesquisa, inacreditáveis **178 leads (88%)** pedem ativamente para receber os links das aulas no privado clicando em 'Sim, pode mandar'! Sua automação gerou 178 leads 'Super Quentes'. **Ação Recomendada:** A equipe deve dar prioridade máxima no atendimento 1x1 para esses 178 leads, pois estão com a temperatura no máximo.")

        elif visao_funil == "Comparativo de Copys":
            st.markdown("### 🏆 Vencedor do Teste A/B")
            st.success("A **Copy V1 (Direta)** é a grande vencedora absoluta! Ela teve o maior volume de Engajamento (321 cliques) e, por não ter nó extra, obteve 0% de atrito (drop-off).")
            
            fig = go.Figure()
            fig.add_trace(go.Funnel(name='V1 (Direta)', y=["Interesse na Copy", "Escolheu Perfil (Téc/Emp)"], x=[321, 321], textinfo="value+percent initial"))
            fig.add_trace(go.Funnel(name='V2 (1 Nó Extra)', y=["Interesse na Copy", "Escolheu Perfil (Téc/Emp)"], x=[299, 253], textinfo="value+percent initial"))
            fig.add_trace(go.Funnel(name='V3 (1 Nó Extra)', y=["Interesse na Copy", "Escolheu Perfil (Téc/Emp)"], x=[204, 172], textinfo="value+percent initial"))
            st.plotly_chart(fig, use_container_width=True)
            
            st.markdown("### 🚨 Diagnóstico de Copys")
            st.warning("**Insight DBA:** A estratégia de 'pedir permissão' na V2 e V3 antes de exibir os botões de perfil gerou uma fuga de aproximadamente **15% do tráfego (Drop-off)** no nó intermediário. A V1, que atira direto para a escolha do Perfil (Técnico ou Empreendedor), provou ser a mais eficaz tanto para despertar o clique inicial quanto para reter o lead na escolha. Recomendo focar todo o tráfego nela nas próximas captações.")

        elif visao_funil == "Comparativo de Perfis":
            col_t, col_e = st.columns(2)
            with col_t:
                st.markdown("#### 🔧 Jornada do Técnico")
                fig_tec = go.Figure(go.Funnel(y=["Escolheu Técnico", "Assistiu Vídeo Téc", "Entrou Grupo Téc"], x=[598, 584, 397], textinfo="value+percent previous", marker={"color": "#F97316"}))
                st.plotly_chart(fig_tec, use_container_width=True)
            with col_e:
                st.markdown("#### 💼 Jornada do Empreendedor")
                fig_emp = go.Figure(go.Funnel(y=["Escolheu Empreendedor", "Assistiu Vídeo Emp", "Entrou Grupo Emp"], x=[148, 145, 91], textinfo="value+percent previous", marker={"color": "#8B5CF6"}))
                st.plotly_chart(fig_emp, use_container_width=True)

            st.markdown("### 🚨 Diagnóstico de Perfis")
            st.warning("**Insight DBA:** O seu funil apresenta uma taxa alta de ação na pós-visualização do vídeo.\\n\\n**🎯 Destaque para a Repescagem:** A sua estratégia de perguntar 'Conseguiu entrar no grupo?' é fantástica! O lembrete secundário foi acionado para 113 Técnicos e 26 Empreendedores que clicaram em 'Não consegui'. Desse volume, o link bruto da repescagem conseguiu salvar e converter **93 Técnicos** (82.3%) e **24 Empreendedores** (92.3%). Sem esse nó inteligente, você teria perdido 117 leads extremamente qualificados e o CPL (Custo por Lead) seria muito maior!")
        
else:
    st.warning("Não foi possível carregar os dados. Verifique a planilha.")
