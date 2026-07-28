import sys

with open('app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
in_main_block = False
main_block_start = -1

for i, line in enumerate(lines):
    if line.strip() == "# --- PROCESSAMENTO DOS KPIs ---":
        main_block_start = i
        new_lines.append("    tab_main, tab_alerts = st.tabs(['📊 Visão Principal', '🚨 Alertas de Integração'])\n\n")
        new_lines.append("    with tab_main:\n")
        new_lines.append("    " + line)
        in_main_block = True
        continue
    
    if in_main_block:
        if line.strip() == "else:" and lines[i-1].strip() == "" and "warning" in lines[i+1]:
            # End of the block
            in_main_block = False
            
            # Insert the Alerts tab code before the else
            alerts_code = """
    with tab_alerts:
        st.header("🚨 Monitoramento de Alertas")
        st.markdown("Acompanhe aqui os leads que se cadastraram na Landing Page, mas **não chegaram à planilha de Boas-vindas** (falha no processamento do N8N/Webhook).")
        
        try:
            # Normalizar emails
            df_captacao_alerta = df_captacao.copy()
            df_boasvindas_alerta = df_boasvindas.copy()
            
            # Garantir colunas em minusculo para acessar
            df_captacao_alerta.columns = df_captacao_alerta.columns.str.strip().str.lower()
            df_boasvindas_alerta.columns = df_boasvindas_alerta.columns.str.strip().str.lower()
            
            if 'email' in df_captacao_alerta.columns and 'lead_email' in df_boasvindas_alerta.columns:
                emails_processados = set(df_boasvindas_alerta['lead_email'].astype(str).str.lower().str.strip())
                
                # Filtrar leads captados que não estão nos processados
                df_captacao_alerta['email_limpo'] = df_captacao_alerta['email'].astype(str).str.lower().str.strip()
                df_falhas = df_captacao_alerta[~df_captacao_alerta['email_limpo'].isin(emails_processados)]
                
                if not df_falhas.empty:
                    st.error(f"⚠️ Atenção! Encontramos **{len(df_falhas)} leads** que não foram processados.")
                    
                    # Selecionar colunas úteis
                    colunas_exibir = []
                    for col in ['data', 'primeiro_nome', 'email', 'telefone', 'utm_source', 'utm_campaign']:
                        if col in df_falhas.columns:
                            colunas_exibir.append(col)
                            
                    st.dataframe(df_falhas[colunas_exibir], use_container_width=True, hide_index=True)
                else:
                    st.success("Tudo perfeito! 100% dos leads capturados foram processados com sucesso no WhatsApp.")
            else:
                st.warning("Não foi possível encontrar a coluna de e-mail para fazer o cruzamento de dados.")
        except Exception as e:
            st.error(f"Erro ao processar alertas: {e}")
            
"""
            new_lines.extend([line_c + "\n" for line_c in alerts_code.split("\n")[:-1]])
            new_lines.append(line)
        else:
            if line.strip() == "":
                new_lines.append(line)
            else:
                new_lines.append("    " + line)
    else:
        new_lines.append(line)

with open('app.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
