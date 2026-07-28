import re

with open("app.py", "r") as f:
    content = f.read()

# 1. Create the function at the top
func_code = """
def render_alert_duplicados(df_captacao):
    import pandas as pd
    import streamlit as st
    st.subheader("🚷 Cadastros Duplicados na Captação")
    try:
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
            
        duplicados_geral = df_dupe[mask_email | mask_tel].copy()
        
        if not duplicados_geral.empty:
            st.warning(f"⚠️ Atenção! Encontramos **{len(duplicados_geral)} registros** que indicam repetição de usuário (mesmo E-mail ou Telefone).")
            
            colunas_exibir = []
            for col in ['primeiro_nome', 'email', 'telefone', 'data']:
                if col in duplicados_geral.columns:
                    colunas_exibir.append(col)
                    
            if 'email' in duplicados_geral.columns:
                duplicados_geral = duplicados_geral.sort_values(by='email')
                
            st.dataframe(duplicados_geral[colunas_exibir], use_container_width=True, hide_index=True)
        else:
            st.success("Nenhum lead duplicado! A base de entrada está totalmente higienizada.")
    except Exception as e:
        st.warning(f"Não foi possível verificar leads duplicados: {e}")

"""

# Insert function right before 'st.title'
content = content.replace('st.title("📊 Dashboard de Lançamento e Boas-Vindas")', func_code + '\n' + 'st.title("📊 Dashboard de Lançamento e Boas-Vindas")')

# 2. Insert into tab_main, right after Análise de Erros de Envio (around line 330)
search_str1 = """        else:
            st.success("Nenhum erro de envio registrado!")
        
        # --- O DNA DO LEAD ---"""

replace_str1 = """        else:
            st.success("Nenhum erro de envio registrado!")
        
        st.divider()
        render_alert_duplicados(df_captacao)
        
        # --- O DNA DO LEAD ---"""

content = content.replace(search_str1, replace_str1)


# 3. Replace the huge block in tab_alerts with a simple function call
# We will use regex to find and replace the block
regex = r'# --- ALERTA 4: LEADS DUPLICADOS ---.*?st\.divider\(\)'

replace_str2 = """# --- ALERTA 4: LEADS DUPLICADOS ---
            render_alert_duplicados(df_captacao)
            
            st.divider()"""

content = re.sub(regex, replace_str2, content, flags=re.DOTALL)


with open("app.py", "w") as f:
    f.write(content)
