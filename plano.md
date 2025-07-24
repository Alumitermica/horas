# 📋 Plano de Implementação - Sistema de Análise de Horas de Trabalho

## 🎯 Análise das Necessidades

### Necessidades Identificadas:

1. **Visualização de Picagens** 
   - ✅ Ver picagens individuais (E1, S1, E2, S2, E3, S3, E4, S4)
   - ✅ Detectar picagens em falta ou inválidas
   - ✅ Avisos sobre problemas nas picagens

2. **Análise de Pontualidade**
   - ⚠️ Saber se entrou a horas (com tolerância customizável)
   - ⚠️ Detectar se esteve mais que X tempo no intervalo
   - ⚠️ Verificar se teve mais que X tempo para almoço
   - ⚠️ Saber se saiu a horas
   - ⚠️ Identificar horas extra

3. **Configurações Customizáveis**
   - ✅ Tolerância de atraso customizável (já implementado)
   - ✅ Hora de entrada configurável por setor
   - ✅ Hora de saída configurável por setor
   - ⚠️ Tempo de almoço configurável (parcialmente implementado)

4. **Gestão de Tipos de Dia**
   - ✅ Marcar dias como falta total
   - ✅ Marcar dias como férias
   - ✅ Marcar dias como falta parcial
   - ✅ Editor interativo para alterar tipos

5. **Métricas e Relatórios**
   - ✅ Total de horas trabalhadas
   - ✅ Total de dias de trabalho
   - ✅ Total de tempo extra
   - ✅ Total de tempo perdido (faltas)
   - ⚠️ Média de atraso (parcialmente implementado)

---

## 🔍 Estado Atual do Sistema

### ✅ O que está a funcionar bem:

1. **Processamento de CSV:**
   - Leitura correta da estrutura complexa dos ficheiros
   - Detecção automática de picagens (4, 6 ou 8 timestamps)
   - Redistribuição inteligente das picagens nas colunas E1-S1-E2-S2
   - Validação de picagens e avisos de problemas

2. **Interface Streamlit:**
   - Editor interativo de dados
   - Visualizações com gráficos
   - Sistema de abas para diferentes vistas
   - Download de relatórios (Excel, CSV)

3. **Sistema de Regras:**
   - Regras por setor (Produção, Administrativo, etc.)
   - Configurações de horários e tolerâncias
   - Sistema de validação de conformidade

4. **Cálculos Básicos:**
   - Total de horas trabalhadas
   - Detecção de faltas e extras
   - Distribuição por tipos de dia

### ⚠️ O que precisa ser melhorado:

1. **Análise de Intervalos:**
   - Não calcula corretamente a duração dos intervalos
   - Não detecta se o tempo de almoço excedeu o limite
   - Não analisa pausas individuais (lanche vs almoço)

2. **Análise de Pontualidade Detalhada:**
   - Não calcula atrasos específicos por dia
   - Não verifica saídas antecipadas
   - Não gera relatórios de pontualidade detalhados

3. **Validação de Dados:**
   - Algumas picagens mal formadas não são detectadas
   - Duplicados ainda podem passar despercebidos
   - Validação de horários sequenciais incompleta

4. **Interface de Configuração:**
   - Não permite ajustar regras pela interface
   - Configurações fixas nos ficheiros JSON
   - Falta feedback visual sobre violações de regras

---

## 🛠️ Plano de Implementação

### Fase 1: Correção do Processamento de CSV ⭐ PRIORITÁRIO

**Problemas identificados:**
- Linhas duplicadas no CSV (visível no Hugo Julho 1.csv)
- Picagens mal distribuídas em alguns casos
- Validação incompleta de timestamps sequenciais

**Tarefas:**
1. **Melhorar detecção de duplicados**
   - Implementar hash de linha completa
   - Detectar duplicados baseado em Data + picagens
   
2. **Validar sequência temporal das picagens**
   - E1 < S1 < E2 < S2 < E3 < S3 < E4 < S4
   - Alertar sobre picagens fora de ordem
   
3. **Melhorar parsing de timestamps**
   - Detectar formatos alternativos (8:30 vs 08:30)
   - Lidar com timestamps inválidos (ex: 25:00)

### Fase 2: Análise Detalhada de Intervalos

**Implementar:**
1. **Cálculo preciso de intervalos**
   ```python
   # Para 4 picagens: E1-S1-E2-S2
   tempo_almoco = S1 to E2
   # Para 6 picagens: E1-S1-E2-S2-E3-S3  
   intervalo_lanche = S1 to E2
   tempo_almoco = S2 to E3
   ```

2. **Validação de limites**
   - Tempo mínimo de almoço (ex: 30 min)
   - Tempo máximo de almoço (ex: 90 min)
   - Tempo máximo de pausas (ex: 15 min)

3. **Alertas específicos**
   - "Almoço muito curto (<30 min)"
   - "Almoço muito longo (>90 min)"
   - "Pausa excessiva"

### Fase 3: Análise de Pontualidade Avançada

**Implementar:**
1. **Cálculos de atraso detalhados**
   ```python
   atraso_entrada = max(0, E1 - hora_entrada_padrao)
   saida_antecipada = max(0, hora_saida_padrao - ultimo_S)
   ```

2. **Métricas de pontualidade**
   - Atraso médio por mês
   - Dias consecutivos sem atraso
   - Padrões de atraso (ex: sempre às segundas)

3. **Dashboard de pontualidade**
   - Gráfico de atrasos ao longo do tempo
   - Heatmap de pontualidade por dia da semana
   - Ranking de pontualidade

### Fase 4: Interface de Configuração Dinâmica

**Implementar:**
1. **Painel de configurações na sidebar**
   - Sliders para tolerâncias
   - Time pickers para horários
   - Toggle para regras específicas

2. **Aplicação em tempo real**
   - Recalcular métricas ao alterar configurações
   - Preview de impacto das alterações
   - Salvar configurações personalizadas

3. **Perfis de configuração**
   - Múltiplos perfis por utilizador
   - Configurações por departamento
   - Histórico de alterações

### Fase 5: Melhorias na Interface e Relatórios

**Implementar:**
1. **Dashboard melhorado**
   - KPIs em cards visuais
   - Alertas coloridos para violações
   - Progresso em relação a metas

2. **Relatórios avançados**
   - Relatório de pontualidade detalhado
   - Análise de tendências
   - Comparação entre períodos

3. **Exportação melhorada**
   - PDF com gráficos
   - Relatórios automáticos por email
   - Templates customizáveis

---

## 🔧 Estrutura Técnica Proposta

### Novos Módulos:

1. **`utils/time_analyzer.py`**
   ```python
   class TimeAnalyzer:
       def calculate_work_periods(self, row)
       def validate_time_sequence(self, times)
       def calculate_breaks(self, times)
       def detect_overtime(self, work_time, standard_hours)
   ```

2. **`utils/punctuality_analyzer.py`**
   ```python
   class PunctualityAnalyzer:
       def calculate_delays(self, df, rules)
       def analyze_patterns(self, delays)
       def generate_punctuality_report(self, df)
   ```

3. **`utils/config_manager.py`**
   ```python
   class ConfigManager:
       def load_dynamic_rules(self, sector)
       def save_user_preferences(self, user_id, config)
       def validate_configuration(self, config)
   ```

### Melhorias nos Módulos Existentes:

1. **`csv_processor.py`**
   - Adicionar `_validate_time_sequence()`
   - Melhorar `_detect_duplicates()`
   - Implementar `_handle_malformed_data()`

2. **`rules_engine.py`**
   - Adicionar validação de intervalos
   - Implementar análise de padrões
   - Melhorar sistema de recomendações

---

## 📊 Exemplos de Melhorias Visuais

### Dashboard Proposto:

```
┌─────────────────────────────────────────────────────────────┐
│  📊 RESUMO GERAL                                           │
├─────────────┬─────────────┬─────────────┬─────────────────┤
│ 160h        │ 95.2%       │ 3.2min      │ 2.5h            │
│ Trabalhadas │ Pontualidad │ Atraso Méd  │ Horas Extra     │
└─────────────┴─────────────┴─────────────┴─────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  ⚠️ ALERTAS ATIVOS                                         │
├─────────────────────────────────────────────────────────────┤
│ • 15/07: Almoço muito longo (125 min)                      │
│ • 22/07: Atraso excessivo (25 min)                         │
│ • 23/07: Falta não justificada                             │
└─────────────────────────────────────────────────────────────┘
```

### Relatório de Pontualidade:

```
Data       | Entrada | Atraso | Almoço  | Saída   | Status
-----------|---------|--------|---------|---------|--------
26/06/2025 | 08:30   | 0 min  | 65 min  | 17:57   | ✅ OK
27/06/2025 | 08:29   | 0 min  | 68 min  | 17:48   | ⚠️ Almoço longo
15/07/2025 | 10:44   | 134min | 73 min  | 17:53   | ❌ Atraso grave
```

---

## ⏱️ Cronograma de Implementação

| Fase | Duração | Prioridade | Entregáveis |
|------|---------|------------|-------------|
| **Fase 1** | 2-3 dias | 🔴 Alta | CSV parser melhorado, validação robusta |
| **Fase 2** | 3-4 dias | 🟡 Média | Análise de intervalos completa |
| **Fase 3** | 2-3 dias | 🟡 Média | Dashboard de pontualidade |
| **Fase 4** | 4-5 dias | 🟢 Baixa | Interface de configuração |
| **Fase 5** | 3-4 dias | 🟢 Baixa | Relatórios avançados |

**Total estimado: 14-19 dias de desenvolvimento**

---

## 🎯 Critérios de Sucesso

### Funcionais:
- [ ] Processar 100% dos CSVs sem erros
- [ ] Detectar todas as picagens inválidas
- [ ] Calcular intervalos com precisão
- [ ] Gerar alertas de pontualidade relevantes
- [ ] Permitir configuração dinâmica de regras

### Técnicos:
- [ ] Processar ficheiros em <5 segundos
- [ ] Interface responsiva e intuitiva
- [ ] Cobertura de testes >80%
- [ ] Documentação completa

### Utilizador:
- [ ] Reduzir tempo de análise manual em 90%
- [ ] Fornecer insights acionáveis
- [ ] Interface intuitiva para utilizadores não técnicos

---

## 🚀 Próximos Passos

1. **Validar este plano** com os requisitos finais
2. **Começar pela Fase 1** - correção do processamento CSV
3. **Testar com os ficheiros existentes** (Hugo Julho, Junho, Maio)
4. **Implementar incrementalmente** uma fase de cada vez
5. **Validar cada fase** antes de avançar para a próxima

---

**Nota:** Este plano foi baseado na análise do sistema atual e nos ficheiros CSV de exemplo. Pode ser ajustado conforme necessário durante a implementação. 