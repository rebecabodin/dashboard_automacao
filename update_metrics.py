import re

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update Fase 1 Metrics
content = re.sub(r'st\.metric\("Total de Envios", "1478"', 'st.metric("Total de Envios", "2126"', content)
content = re.sub(r'help="Total de pessoas que entraram no fluxo \(V1\+V2\+V3\)"\)', 'help="Total de pessoas que entraram no fluxo (V1+V2+V3)")', content)

content = re.sub(r'st\.metric\("Taxa de Entrega", "95\.1\%"', 'st.metric("Taxa de Entrega", "95.5%"', content)
content = re.sub(r'help="Leads que efetivamente receberam a mensagem \(1405/1478\)"', 'help="Leads que efetivamente receberam a mensagem (2030/2126)"', content)

content = re.sub(r'st\.metric\("Taxa de Clique \(CTR\)", "58\.6\%"', 'st.metric("Taxa de Clique (CTR)", "56.5%"', content)
content = re.sub(r'help="824 cliques de interesse em 1405 entregas"', 'help="1147 cliques de interesse em 2030 entregas"', content)

content = re.sub(r'st\.metric\("Opt-out \(Rejeição\)", "2\.4\%"', 'st.metric("Opt-out (Rejeição)", "1.6%"', content)
content = re.sub(r'help="O Manychat cravou 35 descadastros \(2\.4\%\)\."', 'help="O Manychat cravou 34 descadastros (1.6%)."', content)

# 2. Update Visão Macro (Sankey/Funnel)
content = re.sub(
    r'x=\[1478, 1405, 824, 746, 729, 370, 202\]',
    'x=[2126, 2030, 1147, 1067, 1042, 528, 288]',
    content
)

# 3. Update Público Atraído (Pie chart)
content = re.sub(
    r"df_pie = pd\.DataFrame\(\{'Perfil': \['Técnicos', 'Empreendedores'\], 'Qtd': \[598, 148\]\}\)",
    "df_pie = pd.DataFrame({'Perfil': ['Técnicos', 'Empreendedores'], 'Qtd': [865, 202]})",
    content
)

# 4. Update Comparativo de Copys
content = re.sub(
    r'maior volume de Engajamento \(321 cliques\)',
    'maior volume de Engajamento (447 cliques)',
    content
)
content = re.sub(
    r'fig\.add_trace\(go\.Funnel\(name=\'V1 \(Direta\)\', y=\["Interesse na Copy", "Escolheu Perfil \(Téc/Emp\)"\], x=\[321, 321\]',
    'fig.add_trace(go.Funnel(name=\'V1 (Direta)\', y=["Interesse na Copy", "Escolheu Perfil (Téc/Emp)"], x=[447, 447]',
    content
)
content = re.sub(
    r'fig\.add_trace\(go\.Funnel\(name=\'V2 \(1 Nó Extra\)\', y=\["Interesse na Copy", "Escolheu Perfil \(Téc/Emp\)"\], x=\[299, 253\]',
    'fig.add_trace(go.Funnel(name=\'V2 (1 Nó Extra)\', y=["Interesse na Copy", "Escolheu Perfil (Téc/Emp)"], x=[421, 375]',
    content
)
content = re.sub(
    r'fig\.add_trace\(go\.Funnel\(name=\'V3 \(1 Nó Extra\)\', y=\["Interesse na Copy", "Escolheu Perfil \(Téc/Emp\)"\], x=\[204, 172\]',
    'fig.add_trace(go.Funnel(name=\'V3 (1 Nó Extra)\', y=["Interesse na Copy", "Escolheu Perfil (Téc/Emp)"], x=[275, 245]',
    content
)

# 5. Update Comparativo de Perfis (Técnico / Empreendedor Funnels)
content = re.sub(
    r'fig_tec = go\.Figure\(go\.Funnel\(y=\["Escolheu Técnico", "Assistiu Vídeo Téc", "Entrou Grupo Téc"\], x=\[598, 584, 397\]',
    'fig_tec = go.Figure(go.Funnel(y=["Escolheu Técnico", "Assistiu Vídeo Téc", "Entrou Grupo Téc"], x=[865, 845, 591]',
    content
)
content = re.sub(
    r'fig_emp = go\.Figure\(go\.Funnel\(y=\["Escolheu Empreendedor", "Assistiu Vídeo Emp", "Entrou Grupo Emp"\], x=\[148, 145, 91\]',
    'fig_emp = go.Figure(go.Funnel(y=["Escolheu Empreendedor", "Assistiu Vídeo Emp", "Entrou Grupo Emp"], x=[202, 198, 125]',
    content
)

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Update successfully applied.")
