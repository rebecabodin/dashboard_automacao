import re

with open("app.py", "r") as f:
    content = f.read()

# 1. Create get_duplicados function
func_get = """def get_duplicados(df_captacao):
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
        df_dupe['tel_limpo'] = df_dupe['telefone'].astype(str).str.replace(r'\\D', '', regex=True)
        df_valid_tel = df_dupe[df_dupe['tel_limpo'].str.len() > 8]
        dup_tels = df_valid_tel[df_valid_tel.duplicated(subset=['tel_limpo'], keep=False)]['tel_limpo']
        mask_tel = df_dupe['tel_limpo'].isin(dup_tels)
    return df_dupe[mask_email | mask_tel].copy()

def render_alert_duplicados(df_captacao):"""

content = content.replace("def render_alert_duplicados(df_captacao):", func_get)

# 2. Refactor render_alert_duplicados to use get_duplicados
regex_render = r'        df_dupe = df_captacao.*?duplicados_geral = df_dupe\[mask_email \| mask_tel\]\.copy\(\)'
content = re.sub(regex_render, "        duplicados_geral = get_duplicados(df_captacao)", content, flags=re.DOTALL)

# 3. Update top metrics
search_metrics = """        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Leads Capturados", f"{total_capturados}", help="Volume bruto de cadastros registrados na base principal (Landing Page).")
        col2.metric("Processados no WPP", f"{total_automação}", help="Volume de leads submetidos à esteira de automação e processamento via WhatsApp.")
        col3.metric("Mensagens Entregues", f"{sucesso_envio}", f"{taxa_entrega:.1f}%", help="Volume absoluto e percentual de leads que receberam a mensagem com sucesso (Taxa de Entrega).")
        col4.metric("Custo Estimado", f"US$ {custo_total:.2f}", f"US$ {custo_por_mensagem:.2f} / msg", delta_color="off", help="Projeção de custo operacional de disparo via API Oficial do WhatsApp Meta.")
        col5.metric("Erros de Envio", f"{erros}", delta_color="inverse", help="Volume de falhas de entrega (Motivos: números inválidos, fixos, sem conta no app ou restrições da Meta).")"""

replace_metrics = """        total_duplicados = len(get_duplicados(df_captacao))
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        col1.metric("Leads Capturados", f"{total_capturados}", help="Volume bruto de cadastros registrados na base principal (Landing Page).")
        col2.metric("Duplicados", f"{total_duplicados}", delta_color="inverse", help="Cadastros suspeitos de repetição (mesmo e-mail ou telefone).")
        col3.metric("Processados no WPP", f"{total_automação}", help="Volume de leads submetidos à esteira de automação e processamento via WhatsApp.")
        col4.metric("Entregues", f"{sucesso_envio}", f"{taxa_entrega:.1f}%", help="Volume absoluto e percentual de leads que receberam a mensagem com sucesso (Taxa de Entrega).")
        col5.metric("Custo Meta", f"US$ {custo_total:.2f}", delta_color="off", help="Projeção de custo operacional (API Oficial).")
        col6.metric("Erros Envio", f"{erros}", delta_color="inverse", help="Volume de falhas de entrega (Motivos técnicos).")"""

content = content.replace(search_metrics, replace_metrics)

with open("app.py", "w") as f:
    f.write(content)
