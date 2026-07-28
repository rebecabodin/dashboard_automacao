import re

with open("app.py", "r") as f:
    content = f.read()

# Create the new function
func_code = """
def render_alert_boasvindas_duplicados(df_boasvindas):
    import pandas as pd
    import streamlit as st
    st.subheader("🔁 Disparos Duplicados de Boas-Vindas")
    try:
        df_dupe = df_boasvindas.copy()
        df_dupe.columns = df_dupe.columns.str.strip().str.lower()
        
        mask_tel = pd.Series(False, index=df_dupe.index)
        
        if 'lead_phone' in df_dupe.columns:
            df_dupe['tel_limpo'] = df_dupe['lead_phone'].astype(str).str.replace(r'\\D', '', regex=True)
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

"""

# Insert function before render_alert_duplicados
content = content.replace("def render_alert_duplicados(df_captacao):", func_code + "\ndef render_alert_duplicados(df_captacao):")

# Insert call to function below the existing render_alert_duplicados in tab_main
search_str = """        render_alert_duplicados(df_captacao)
        
        # --- O DNA DO LEAD ---"""
replace_str = """        render_alert_duplicados(df_captacao)
        st.divider()
        render_alert_boasvindas_duplicados(df_boasvindas)
        
        # --- O DNA DO LEAD ---"""
content = content.replace(search_str, replace_str)

# Insert call to function below the existing render_alert_duplicados in tab_alerts
search_str2 = """            # --- ALERTA 4: LEADS DUPLICADOS ---
            render_alert_duplicados(df_captacao)
            
            st.divider()"""
replace_str2 = """            # --- ALERTA 4: LEADS DUPLICADOS ---
            render_alert_duplicados(df_captacao)
            
            st.divider()
            
            # --- ALERTA 4.1: DISPAROS DUPLICADOS (WHATSAPP) ---
            render_alert_boasvindas_duplicados(df_boasvindas)
            
            st.divider()"""
content = content.replace(search_str2, replace_str2)

with open("app.py", "w") as f:
    f.write(content)
