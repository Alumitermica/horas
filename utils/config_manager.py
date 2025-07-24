import json
import pandas as pd
from datetime import datetime, time
from typing import Dict, List, Optional, Tuple
import streamlit as st

class ConfigManager:
    """
    Classe responsável pela gestão dinâmica de configurações:
    - Horários de trabalho por setor
    - Tolerâncias personalizadas
    - Perfis de funcionários
    - Regras de deteção inteligente
    """
    
    def __init__(self):
        """Inicializa o gestor de configurações."""
        self.default_config = {
            'horarios_setor': {
                'Produção': {
                    'entrada_padrao': '08:00',
                    'saida_padrao': '17:00',
                    'almoco_inicio': '12:00',
                    'almoco_duracao': 60,
                    'intervalo_manha': 15,  # Duração do intervalo da manhã
                    'intervalo_tarde': 15,  # Duração do intervalo da tarde
                    'tolerancia_entrada': 10,
                    'tolerancia_saida': 15,
                    'tolerancia_intervalo': 5,  # Tolerância para intervalos
                    'tolerancia_esquecimento': 30,  # Se atraso > 30min, provavelmente esqueceu
                    'picagens_esperadas': 'auto',  # 'auto', 4, 6, 8
                    'dias_trabalho': ['segunda', 'terça', 'quarta', 'quinta', 'sexta']
                },
                'Administrativo': {
                    'entrada_padrao': '09:00',
                    'saida_padrao': '18:00',
                    'almoco_inicio': '12:30',
                    'almoco_duracao': 60,
                    'intervalo_manha': 20,
                    'intervalo_tarde': 20,
                    'tolerancia_entrada': 15,
                    'tolerancia_saida': 20,
                    'tolerancia_intervalo': 10,
                    'tolerancia_esquecimento': 45,
                    'picagens_esperadas': 'auto',
                    'dias_trabalho': ['segunda', 'terça', 'quarta', 'quinta', 'sexta']
                },
                'Vendas': {
                    'entrada_padrao': '09:00',
                    'saida_padrao': '18:00',
                    'almoco_inicio': '13:00',
                    'almoco_duracao': 45,
                    'intervalo_manha': 10,
                    'intervalo_tarde': 10,
                    'tolerancia_entrada': 30,
                    'tolerancia_saida': 30,
                    'tolerancia_intervalo': 15,
                    'tolerancia_esquecimento': 60,
                    'picagens_esperadas': 4,  # Apenas entrada/almoço/saída
                    'dias_trabalho': ['segunda', 'terça', 'quarta', 'quinta', 'sexta', 'sábado']
                },
                'Logística': {
                    'entrada_padrao': '07:00',
                    'saida_padrao': '16:00',
                    'almoco_inicio': '11:30',
                    'almoco_duracao': 30,
                    'intervalo_manha': 10,
                    'intervalo_tarde': 10,
                    'tolerancia_entrada': 5,
                    'tolerancia_saida': 10,
                    'tolerancia_intervalo': 5,
                    'tolerancia_esquecimento': 20,
                    'picagens_esperadas': 6,  # Entrada/intervalo/almoço/saída
                    'dias_trabalho': ['segunda', 'terça', 'quarta', 'quinta', 'sexta', 'sábado']
                }
            },
            'perfis_funcionario': {},  # Para configurações individuais
            'tipos_dia_sem_picagem': ['folga', 'férias', 'feriado', 'ausência', 'baixa médica'],
            'algoritmos_detecao': {
                'esquecimento_vs_atraso': True,
                'sugerir_correcoes_automaticas': True,
                'confianca_minima_sugestao': 0.7
            }
        }
        
        # Tentar carregar configurações salvas
        self.current_config = self._load_config()
    
    def _load_config(self) -> Dict:
        """Carrega configurações salvas ou usa padrão."""
        try:
            with open('config/horarios.json', 'r', encoding='utf-8') as f:
                saved_config = json.load(f)
                # Mesclar com configurações padrão para garantir completude
                config = self.default_config.copy()
                config.update(saved_config)
                return config
        except (FileNotFoundError, json.JSONDecodeError):
            return self.default_config.copy()
    
    def save_config(self) -> bool:
        """Salva configurações atuais."""
        try:
            import os
            os.makedirs('config', exist_ok=True)
            
            with open('config/horarios.json', 'w', encoding='utf-8') as f:
                json.dump(self.current_config, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Erro ao salvar configurações: {e}")
            return False
    
    def get_sector_config(self, sector: str) -> Dict:
        """Obtém configuração de um setor específico."""
        return self.current_config['horarios_setor'].get(
            sector, 
            self.current_config['horarios_setor']['Produção']  # Default
        )
    
    def get_employee_config(self, employee_number: str, sector: str) -> Dict:
        """Obtém configuração específica de um funcionário ou do setor."""
        # Verificar se há configuração individual
        if employee_number in self.current_config['perfis_funcionario']:
            return self.current_config['perfis_funcionario'][employee_number]
        
        # Usar configuração do setor
        return self.get_sector_config(sector)
    
    def update_sector_config(self, sector: str, config: Dict) -> None:
        """Atualiza configuração de um setor."""
        self.current_config['horarios_setor'][sector] = config
    
    def update_employee_config(self, employee_number: str, config: Dict) -> None:
        """Atualiza configuração individual de um funcionário."""
        self.current_config['perfis_funcionario'][employee_number] = config
    
    def analyze_punch_pattern(self, timestamps: List[Tuple[str, str]], config: Dict) -> Dict:
        """
        Analisa padrão de picagens usando configurações dinâmicas.
        
        Determina se é:
        - Atraso normal (dentro da tolerância de esquecimento)
        - Esquecimento de picagem (atraso > tolerância de esquecimento)
        - Saída antecipada
        - Padrão normal
        """
        if not timestamps:
            return {
                'tipo_analise': 'sem_dados',
                'confianca': 0.0,
                'sugestao': 'Inserir todas as picagens',
                'detalhes': 'Nenhuma picagem encontrada'
            }
        
        entrada_padrao = config['entrada_padrao']
        saida_padrao = config['saida_padrao']
        tolerancia_esquecimento = config['tolerancia_esquecimento']
        tolerancia_entrada = config['tolerancia_entrada']
        
        # Extrair apenas os horários
        times = [t[1] for t in timestamps]
        
        # Analisar primeira picagem (entrada)
        if timestamps:
            primeira_picagem = timestamps[0]
            col_primeira, hora_primeira = primeira_picagem
            
            # Calcular diferença com horário padrão
            diferenca_entrada = self._calculate_time_difference_minutes(
                entrada_padrao, hora_primeira
            )
            
            if col_primeira.startswith('S'):  # Começou com saída
                return {
                    'tipo_analise': 'esqueceu_entrada',
                    'confianca': 0.9,
                    'sugestao': f'Adicionar entrada às {entrada_padrao}',
                    'detalhes': f'Primeira picagem é saída ({hora_primeira}), falta entrada'
                }
            
            elif diferenca_entrada > tolerancia_esquecimento:
                # Atraso muito grande - provavelmente esqueceu de picar
                hora_sugerida = self._calculate_suggested_entry_time(hora_primeira, entrada_padrao)
                return {
                    'tipo_analise': 'possivel_esquecimento_entrada',
                    'confianca': 0.8,
                    'sugestao': f'Verificar se esqueceu entrada às {hora_sugerida}',
                    'detalhes': f'Atraso de {diferenca_entrada}min (>{tolerancia_esquecimento}min) sugere esquecimento'
                }
            
            elif diferenca_entrada > tolerancia_entrada:
                # Atraso normal
                return {
                    'tipo_analise': 'atraso_normal',
                    'confianca': 1.0,
                    'sugestao': '',
                    'detalhes': f'Atraso de {diferenca_entrada}min (tolerável)'
                }
        
        # Analisar padrão geral
        if len(timestamps) % 2 != 0:
            return self._analyze_odd_pattern(timestamps, config)
        
        # Analisar última picagem (saída)
        if len(timestamps) >= 2:
            ultima_picagem = timestamps[-1]
            col_ultima, hora_ultima = ultima_picagem
            
            if col_ultima.startswith('E'):  # Terminou com entrada
                return {
                    'tipo_analise': 'esqueceu_saida',
                    'confianca': 0.8,
                    'sugestao': f'Adicionar saída às {saida_padrao}',
                    'detalhes': f'Última picagem é entrada ({hora_ultima}), falta saída'
                }
        
        return {
            'tipo_analise': 'normal',
            'confianca': 1.0,
            'sugestao': '',
            'detalhes': 'Padrão de picagens normal'
        }
    
    def _analyze_odd_pattern(self, timestamps: List[Tuple[str, str]], config: Dict) -> Dict:
        """Analisa padrões com número ímpar de timestamps."""
        count = len(timestamps)
        
        if count == 1:
            primeira = timestamps[0]
            if primeira[0].startswith('E'):
                return {
                    'tipo_analise': 'esqueceu_saida',
                    'confianca': 0.9,
                    'sugestao': f'Adicionar saída às {config["saida_padrao"]}',
                    'detalhes': 'Apenas entrada registada'
                }
            else:
                return {
                    'tipo_analise': 'esqueceu_entrada',
                    'confianca': 0.9,
                    'sugestao': f'Adicionar entrada às {config["entrada_padrao"]}',
                    'detalhes': 'Apenas saída registada'
                }
        
        elif count == 3:
            # Analisar gaps para determinar o que falta
            times = [t[1] for t in timestamps]
            gaps = []
            for i in range(len(times) - 1):
                gap = self._calculate_time_difference_minutes(times[i], times[i+1])
                gaps.append(gap)
            
            # Se primeiro gap muito grande, provavelmente falta entrada
            if gaps[0] > 120:  # Mais de 2 horas
                return {
                    'tipo_analise': 'esqueceu_entrada',
                    'confianca': 0.7,
                    'sugestao': f'Verificar entrada antes de {times[0]}',
                    'detalhes': f'Grande intervalo ({gaps[0]}min) antes da primeira picagem'
                }
            else:
                return {
                    'tipo_analise': 'esqueceu_saida',
                    'confianca': 0.6,
                    'sugestao': f'Verificar saída após {times[-1]}',
                    'detalhes': 'Número ímpar de picagens sugere saída em falta'
                }
        
        return {
            'tipo_analise': 'padrao_irregular',
            'confianca': 0.3,
            'sugestao': 'Verificação manual necessária',
            'detalhes': f'{count} picagens - padrão não reconhecido'
        }
    
    def _calculate_time_difference_minutes(self, time1: str, time2: str) -> int:
        """Calcula diferença em minutos entre dois horários."""
        try:
            t1 = datetime.strptime(time1, '%H:%M').time()
            t2 = datetime.strptime(time2, '%H:%M').time()
            
            minutes1 = t1.hour * 60 + t1.minute
            minutes2 = t2.hour * 60 + t2.minute
            
            return minutes2 - minutes1
        except ValueError:
            return 0
    
    def _calculate_suggested_entry_time(self, first_punch: str, standard_entry: str) -> str:
        """Calcula horário de entrada sugerido baseado na primeira picagem."""
        try:
            first_time = datetime.strptime(first_punch, '%H:%M').time()
            standard_time = datetime.strptime(standard_entry, '%H:%M').time()
            
            # Se primeira picagem é muito tarde, sugerir algo intermédio
            first_minutes = first_time.hour * 60 + first_time.minute
            standard_minutes = standard_time.hour * 60 + standard_time.minute
            
            # Sugerir horário entre o padrão e a primeira picagem
            suggested_minutes = (standard_minutes + first_minutes) // 2
            
            hours = suggested_minutes // 60
            minutes = suggested_minutes % 60
            
            return f"{hours:02d}:{minutes:02d}"
        except ValueError:
            return standard_entry
    
    def is_work_day(self, date: datetime, sector: str) -> bool:
        """Verifica se uma data é dia de trabalho para um setor."""
        config = self.get_sector_config(sector)
        day_names = {
            0: 'segunda', 1: 'terça', 2: 'quarta', 3: 'quinta',
            4: 'sexta', 5: 'sábado', 6: 'domingo'
        }
        
        day_name = day_names.get(date.weekday(), '')
        return day_name in config.get('dias_trabalho', [])
    
    def should_ignore_missing_punches(self, day_type: str) -> bool:
        """Verifica se um tipo de dia deve ignorar picagens em falta."""
        if not day_type:
            return False
        
        day_type_lower = day_type.lower()
        ignored_types = self.current_config.get('tipos_dia_sem_picagem', [])
        
        return any(ignored_type in day_type_lower for ignored_type in ignored_types)
    
    def create_streamlit_config_interface(self, sector: str) -> Dict:
        """
        Cria interface Streamlit para configuração de horários.
        
        Returns:
            Dict com configurações atualizadas
        """
        st.subheader(f"⚙️ Configuração de Horários - {sector}")
        
        current_config = self.get_sector_config(sector)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Horários Padrão:**")
            entrada = st.time_input(
                "Hora de Entrada",
                value=datetime.strptime(current_config['entrada_padrao'], '%H:%M').time(),
                key=f"entrada_{sector}"
            )
            
            saida = st.time_input(
                "Hora de Saída",
                value=datetime.strptime(current_config['saida_padrao'], '%H:%M').time(),
                key=f"saida_{sector}"
            )
            
            almoco_inicio = st.time_input(
                "Início do Almoço",
                value=datetime.strptime(current_config['almoco_inicio'], '%H:%M').time(),
                key=f"almoco_{sector}"
            )
            
            almoco_duracao = st.number_input(
                "Duração do Almoço (min)",
                min_value=15,
                max_value=180,
                value=current_config['almoco_duracao'],
                key=f"almoco_dur_{sector}"
            )
            
            st.write("**Intervalos:**")
            intervalo_manha = st.number_input(
                "Intervalo Manhã (min)",
                min_value=5,
                max_value=60,
                value=current_config.get('intervalo_manha', 15),
                key=f"int_manha_{sector}"
            )
            
            intervalo_tarde = st.number_input(
                "Intervalo Tarde (min)",
                min_value=5,
                max_value=60,
                value=current_config.get('intervalo_tarde', 15),
                key=f"int_tarde_{sector}"
            )
        
        with col2:
            st.write("**Tolerâncias:**")
            tolerancia_entrada = st.number_input(
                "Tolerância Entrada (min)",
                min_value=0,
                max_value=60,
                value=current_config['tolerancia_entrada'],
                key=f"tol_entrada_{sector}"
            )
            
            tolerancia_saida = st.number_input(
                "Tolerância Saída (min)",
                min_value=0,
                max_value=60,
                value=current_config['tolerancia_saida'],
                key=f"tol_saida_{sector}"
            )
            
            tolerancia_esquecimento = st.number_input(
                "Tolerância Esquecimento (min)",
                min_value=15,
                max_value=120,
                value=current_config['tolerancia_esquecimento'],
                help="Acima deste valor, assume-se esquecimento de picagem",
                key=f"tol_esq_{sector}"
            )
            
            tolerancia_intervalo = st.number_input(
                "Tolerância Intervalos (min)",
                min_value=0,
                max_value=30,
                value=current_config.get('tolerancia_intervalo', 5),
                help="Tolerância para duração de intervalos",
                key=f"tol_int_{sector}"
            )
            
            st.write("**Picagens:**")
            picagens_esperadas = st.selectbox(
                "Picagens Esperadas",
                options=['auto', '4', '6', '8'],
                index=['auto', '4', '6', '8'].index(str(current_config.get('picagens_esperadas', 'auto'))),
                help="Número de picagens esperadas por dia (auto = detectar automaticamente)",
                key=f"picagens_{sector}"
            )
        
        # Dias de trabalho
        st.write("**Dias de Trabalho:**")
        dias_semana = ['segunda', 'terça', 'quarta', 'quinta', 'sexta', 'sábado', 'domingo']
        dias_selecionados = st.multiselect(
            "Selecionar dias de trabalho",
            dias_semana,
            default=current_config.get('dias_trabalho', []),
            key=f"dias_{sector}"
        )
        
        # Botão para salvar
        if st.button(f"💾 Salvar Configurações - {sector}", key=f"save_{sector}"):
            new_config = {
                'entrada_padrao': entrada.strftime('%H:%M'),
                'saida_padrao': saida.strftime('%H:%M'),
                'almoco_inicio': almoco_inicio.strftime('%H:%M'),
                'almoco_duracao': int(almoco_duracao),
                'intervalo_manha': int(intervalo_manha),
                'intervalo_tarde': int(intervalo_tarde),
                'tolerancia_entrada': int(tolerancia_entrada),
                'tolerancia_saida': int(tolerancia_saida),
                'tolerancia_esquecimento': int(tolerancia_esquecimento),
                'tolerancia_intervalo': int(tolerancia_intervalo),
                'picagens_esperadas': picagens_esperadas if picagens_esperadas == 'auto' else int(picagens_esperadas),
                'dias_trabalho': dias_selecionados
            }
            
            self.update_sector_config(sector, new_config)
            if self.save_config():
                st.success(f"✅ Configurações do setor {sector} salvas com sucesso!")
            else:
                st.error("❌ Erro ao salvar configurações")
        
        return self.get_sector_config(sector) 