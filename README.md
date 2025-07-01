# 📊 Análise de Horas de Trabalho

Aplicação web para análise de dados de ponto eletrônico e conformidade com regras de trabalho.

## 🚀 Funcionalidades

- **Upload de CSV** - Importa dados do sistema de ponto
- **Limpeza Automática** - Remove duplicatas e processa dados
- **Análise por Setor** - Regras configuráveis por departamento
- **Visualizações** - Gráficos interativos de horas e pontualidade
- **Relatórios** - Export em Excel, CSV e PDF
- **Análise de Conformidade** - Verifica cumprimento de regras

## 📁 Estrutura do Projeto

```
horas/
├── app.py                 # Aplicação principal Streamlit
├── requirements.txt       # Dependências Python
├── utils/                 # Módulos utilitários
│   ├── csv_processor.py   # Processamento de CSV
│   ├── rules_engine.py    # Motor de regras
│   └── report_generator.py # Geração de relatórios
├── rules/                 # Configurações de regras
│   ├── default.json       # Regras padrão
│   └── producao.json      # Regras específicas
└── README.md
```

## 🛠️ Como Executar Localmente

### 1. Instalar Dependências

```powershell
# Criar ambiente virtual (recomendado)
python -m venv venv
.\venv\Scripts\Activate.ps1

# Instalar dependências
pip install -r requirements.txt
```

### 2. Executar a Aplicação

```powershell
streamlit run app.py
```

A aplicação abrirá automaticamente no browser em `http://localhost:8501`

## 📋 Como Usar

1. **Selecionar Setor** - Escolha o departamento na barra lateral
2. **Upload CSV** - Carregue o arquivo de dados do ponto
3. **Visualizar Análises** - Veja métricas, gráficos e conformidade
4. **Gerar Relatórios** - Baixe relatórios em Excel/CSV

## 📊 Formato do CSV

O CSV deve conter as seguintes colunas:
- `Data` - Data no formato DD/MM/YYYY
- `Tipo` - Tipo do dia (Normal, Falta, Folga, etc.)
- `E1, S1, E2, S2, E3, S4, E4, S4` - Horários de entrada e saída
- `Efect` - Horas efetivas trabalhadas

## ⚙️ Configuração de Regras

As regras podem ser personalizadas por setor em arquivos JSON:

```json
{
  "horas_diarias_objetivo": 8.0,
  "tolerancia_atraso_minutos": 15,
  "hora_entrada_padrao": "08:30",
  "hora_saida_padrao": "17:30",
  "max_horas_extras_dia": 2.0
}
```

## 🚀 Deploy no Render

1. Fork este repositório
2. Conecte ao Render
3. Configure como Web Service
4. Build Command: `pip install -r requirements.txt`
5. Start Command: `streamlit run app.py --server.port=$PORT --server.address=0.0.0.0`

## 📈 Métricas Analisadas

- Total de horas trabalhadas
- Conformidade com horário objetivo
- Análise de pontualidade
- Horas extras e déficits
- Padrões mensais de trabalho
- Taxa de ausências

## 🔧 Tecnologias

- **Streamlit** - Interface web
- **Pandas** - Processamento de dados
- **Plotly** - Visualizações interativas
- **OpenPyXL** - Relatórios Excel
- **Python 3.8+**