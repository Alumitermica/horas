import pandas as pd
import numpy as np
from datetime import datetime
import streamlit as st
import csv
import io

class CSVProcessor:
    def __init__(self):
        # Mapa para normalizar nomes de colunas que variam entre ficheiros
        self.HEADER_NORMALIZATION_MAP = {
            'Obj.': 'Obj',
            'Aus.': 'Aus',
            'Efect': 'Efect',
            'Efectivo': 'Efect',
            'Período : 01/04/2025 - 30/04/2025': 'Periodo',
            'Período : 01/05/2025 - 31/05/2025': 'Periodo',
            'Período : 01/06/2025 - 30/06/2025': 'Periodo',
            'Objectivo': 'Obj',
            'Ausência': 'Aus'
        }
        
        # Colunas ordenadas para o DataFrame final
        self.ordered_columns = [
            'Numero', 'Nome', 'Departamento', 'Data', 'Tipo',
            'E1', 'S1', 'E2', 'S2', 'E3', 'S3', 'E4', 'S4',
            'Obj', 'Aus', 'Falta', 'Efect', 'Extra', 'Justificação',
            'picagens_validas', 'aviso_picagens'
        ]

    def load_and_process_csv(self, uploaded_file):
        """
        Carrega e processa um ficheiro CSV usando a nova abordagem melhorada
        que lida eficientemente com a estrutura complexa dos ficheiros.
        """
        try:
            # Reset file pointer
            uploaded_file.seek(0)
            
            # Ler o conteúdo como string
            content = uploaded_file.read()
            if isinstance(content, bytes):
                try:
                    content = content.decode('utf-8')
                except UnicodeDecodeError:
                    content = content.decode('latin-1')
            
            # Usar StringIO para simular um ficheiro
            csv_file = io.StringIO(content)
            
            # Lista para guardar os registos processados
            all_records = []
            
            # Usar csv.reader para lidar com campos entre aspas
            csv_reader = csv.reader(csv_file)
            
            for i, row in enumerate(csv_reader):
                if not row:  # Ignorar linhas vazias
                    continue
                
                try:
                    # 1. Extrair dados "fixos" que aparecem no início de cada linha
                    if len(row) < 7:
                        continue
                    
                    record = {
                        'Numero': row[2] if len(row) > 2 else '',
                        'Nome': row[4] if len(row) > 4 else '',
                        'Departamento': row[6] if len(row) > 6 else ''
                    }
                    
                    # 2. Encontrar a posição dos cabeçalhos de dados diários
                    try:
                        header_start_index = row.index('Data')
                        header_end_index = row.index('Justificação')
                    except ValueError:
                        # Se não encontrar 'Data' ou 'Justificação', ignora a linha
                        continue
                    
                    # 3. Extrair a lista de cabeçalhos e a lista de valores
                    headers = row[header_start_index : header_end_index + 1]
                    values = row[header_end_index + 1 :]
                    
                    # Garantir que temos valores suficientes
                    if len(values) < len(headers):
                        values.extend([''] * (len(headers) - len(values)))
                    
                    # 4. Criar um dicionário com os dados diários
                    daily_data = dict(zip(headers, values[:len(headers)]))
                    
                    # 5. Extrair e redistribuir timestamps corretamente
                    # Primeiro, detectar quantas colunas E/S existem no cabeçalho
                    available_e_columns = []
                    available_s_columns = []
                    all_possible_time_columns = ['E1', 'S1', 'E2', 'S2', 'E3', 'S3', 'E4', 'S4']
                    
                    for col in all_possible_time_columns:
                        if col in headers:
                            if col.startswith('E'):
                                available_e_columns.append(col)
                            else:
                                available_s_columns.append(col)
                    
                    # Determinar o número máximo de pares E/S disponíveis
                    max_pairs = min(len(available_e_columns), len(available_s_columns))
                    
                    # Buscar por todos os timestamps válidos na linha
                    all_timestamps = []
                    e_start_idx = None
                    justif_idx = None
                    
                    # Encontrar índices relevantes
                    for idx, header in enumerate(headers):
                        if header == 'E1':
                            e_start_idx = idx
                        elif header == 'Justificação':
                            justif_idx = idx
                    
                    if e_start_idx is not None and justif_idx is not None:
                        # Extrair todos os valores entre E1 e Justificação
                        time_values = values[e_start_idx:justif_idx]
                        
                        # Filtrar apenas timestamps válidos (formato HH:MM)
                        for val in time_values:
                            if val and val.strip() and ':' in str(val):
                                clean_val = str(val).strip()
                                # Verificar se é um timestamp válido
                                if len(clean_val.split(':')) == 2:
                                    try:
                                        parts = clean_val.split(':')
                                        hours = int(parts[0])
                                        minutes = int(parts[1])
                                        if 0 <= hours <= 23 and 0 <= minutes <= 59:
                                            all_timestamps.append(clean_val)
                                    except ValueError:
                                        continue
                        
                        # Limpar as colunas de tempo existentes (todas as possíveis)
                        for col in all_possible_time_columns:
                            if col in daily_data:
                                daily_data[col] = ''
                        
                        # Redistribuir os timestamps encontrados de forma inteligente
                        if all_timestamps and max_pairs > 0:
                            # Caso especial: 4 timestamps = E1-S1-E2-S2 (padrão de trabalho normal)
                            if len(all_timestamps) == 4:
                                daily_data['E1'] = all_timestamps[0]  # Entrada inicial
                                daily_data['S1'] = all_timestamps[1]  # Saída almoço
                                daily_data['E2'] = all_timestamps[2]  # Entrada almoço
                                daily_data['S2'] = all_timestamps[3]  # Saída final
                                # E3, S3, E4, S4 ficam vazios
                                for col in ['E3', 'S3', 'E4', 'S4']:
                                    if col in daily_data:
                                        daily_data[col] = '00:00'
                                
                                # Adicionar flag de validação
                                daily_data['picagens_validas'] = True
                                daily_data['aviso_picagens'] = ''
                                
                            # Caso especial: 6 timestamps = E1-S1-E2-S2-E3-S3
                            elif len(all_timestamps) == 6:
                                daily_data['E1'] = all_timestamps[0]
                                daily_data['S1'] = all_timestamps[1]
                                daily_data['E2'] = all_timestamps[2]
                                daily_data['S2'] = all_timestamps[3]
                                daily_data['E3'] = all_timestamps[4]
                                daily_data['S3'] = all_timestamps[5]
                                # E4, S4 ficam vazios
                                for col in ['E4', 'S4']:
                                    if col in daily_data:
                                        daily_data[col] = '00:00'
                                
                                daily_data['picagens_validas'] = True
                                daily_data['aviso_picagens'] = ''
                                
                            # Caso especial: 8 timestamps = E1-S1-E2-S2-E3-S3-E4-S4
                            elif len(all_timestamps) == 8:
                                for i, timestamp in enumerate(all_timestamps):
                                    col_name = f'E{i//2 + 1}' if i % 2 == 0 else f'S{i//2 + 1}'
                                    if col_name in daily_data:
                                        daily_data[col_name] = timestamp
                                
                                daily_data['picagens_validas'] = True
                                daily_data['aviso_picagens'] = ''
                                
                            # Casos inválidos (número ímpar de picagens ou número inválido)
                            else:
                                # Marcar como inválido
                                daily_data['picagens_validas'] = False
                                daily_data['aviso_picagens'] = f'⚠️ Número inválido de picagens: {len(all_timestamps)} (esperado: 4, 6 ou 8)'
                                
                                # Ainda assim, tentar distribuir os timestamps disponíveis
                                available_pairs = []
                                for i in range(min(max_pairs, len(all_timestamps) // 2)):
                                    e_col = f'E{i+1}'
                                    s_col = f'S{i+1}'
                                    if e_col in available_e_columns and s_col in available_s_columns:
                                        available_pairs.extend([e_col, s_col])
                                
                                for i, timestamp in enumerate(all_timestamps):
                                    if i < len(available_pairs):
                                        daily_data[available_pairs[i]] = timestamp
                    
                    # 6. Adicionar os dados diários ao registo principal
                    record.update(daily_data)
                    
                    # 7. Normalizar as chaves (nomes das colunas)
                    normalized_record = {}
                    for key, value in record.items():
                        # Remove espaços em branco e normaliza usando o mapa
                        clean_key = key.strip()
                        normalized_key = self.HEADER_NORMALIZATION_MAP.get(clean_key, clean_key)
                        normalized_record[normalized_key] = str(value).strip() if value else ''
                    
                    # Só adiciona se tiver data válida
                    if normalized_record.get('Data'):
                        all_records.append(normalized_record)
                
                except (ValueError, IndexError) as e:
                    # Linha mal formada - ignorar
                    continue
            
            # Criar DataFrame
            if not all_records:
                st.warning("Nenhum dado válido foi encontrado no ficheiro.")
                return pd.DataFrame()
            
            df = pd.DataFrame(all_records)
            
            # Limpeza e transformação dos dados
            df = self._clean_and_transform_data(df)
            
            return df
            
        except Exception as e:
            st.error(f"Erro ao processar o ficheiro CSV: {e}")
            return pd.DataFrame()

    def _clean_and_transform_data(self, df):
        """Limpa e transforma os dados do DataFrame."""
        try:
            # 1. Remover duplicados
            df = df.drop_duplicates()
            df = df.reset_index(drop=True)
            
            # 2. Limpar a coluna "Data"
            if 'Data' in df.columns:
                # Remover dia da semana e converter para datetime
                df['Data'] = df['Data'].str.split(' ').str[0]
                df['Data'] = pd.to_datetime(df['Data'], format='%d/%m/%Y', errors='coerce')
                # Remover linhas com datas inválidas
                df = df.dropna(subset=['Data'])
            
            # 3. Converter coluna numérica
            if 'Numero' in df.columns:
                df['Numero'] = pd.to_numeric(df['Numero'], errors='coerce')
            
            # 4. Reordenar colunas
            final_columns = [col for col in self.ordered_columns if col in df.columns]
            df = df[final_columns]
            
            # 5. Limpar colunas de tempo
            time_cols = ['E1', 'S1', 'E2', 'S2', 'E3', 'S3', 'E4', 'S4', 'Efect', 'Extra', 'Falta']
            for col in time_cols:
                if col in df.columns:
                    df[col] = df[col].astype(str).replace('nan', '').str.strip()
                    df[col] = df[col].replace('', '00:00')
            
            # 6. Calcular períodos de trabalho
            df = self._calculate_work_periods(df)
            
            return df
            
        except Exception as e:
            st.error(f"Erro na limpeza dos dados: {e}")
            return df

    def _calculate_work_periods(self, df):
        """Calcula períodos de trabalho e pausas baseado na sequência de marcações."""
        # Adicionar colunas para cálculos
        new_cols = {
            'periodo_manha': pd.Timedelta(0),
            'intervalo_lanche': pd.Timedelta(0),
            'intervalo_almoco': pd.Timedelta(0),
            'periodo_tarde': pd.Timedelta(0),
            'total_trabalho': pd.Timedelta(0),
            'total_pausas': pd.Timedelta(0)
        }
        
        for col, default in new_cols.items():
            df[col] = default
        
        # Detectar dinamicamente quais colunas E/S existem no DataFrame
        available_punch_cols = []
        for col in ['E1', 'S1', 'E2', 'S2', 'E3', 'S3', 'E4', 'S4']:
            if col in df.columns:
                available_punch_cols.append(col)
        
        for index, row in df.iterrows():
            # Recolher marcações válidas das colunas disponíveis
            punches = []
            for col in available_punch_cols:
                if col in row and pd.notna(row[col]) and row[col] and row[col] != '00:00':
                    punches.append(row[col])
            
            # Lógica baseada no número de marcações
            if len(punches) == 4:
                # E1-S1 (trabalho manhã), S1-E2 (almoço), E2-S2 (trabalho tarde)
                df.loc[index, 'periodo_manha'] = self._calculate_duration(punches[0], punches[1])
                df.loc[index, 'intervalo_almoco'] = self._calculate_duration(punches[1], punches[2])
                df.loc[index, 'periodo_tarde'] = self._calculate_duration(punches[2], punches[3])
                
            elif len(punches) == 6:
                # E1-S1 (trabalho), S1-E2 (lanche), E2-S2 (trabalho), S2-E3 (almoço), E3-S3 (trabalho)
                work1 = self._calculate_duration(punches[0], punches[1])
                snack = self._calculate_duration(punches[1], punches[2])
                work2 = self._calculate_duration(punches[2], punches[3])
                lunch = self._calculate_duration(punches[3], punches[4])
                work3 = self._calculate_duration(punches[4], punches[5])
                
                df.loc[index, 'periodo_manha'] = work1 + work2
                df.loc[index, 'intervalo_lanche'] = snack
                df.loc[index, 'intervalo_almoco'] = lunch
                df.loc[index, 'periodo_tarde'] = work3
            
            elif len(punches) == 8:
                # E1-S1, S1-E2, E2-S2, S2-E3, E3-S3, S3-E4, E4-S4
                work1 = self._calculate_duration(punches[0], punches[1])
                break1 = self._calculate_duration(punches[1], punches[2])
                work2 = self._calculate_duration(punches[2], punches[3])
                break2 = self._calculate_duration(punches[3], punches[4])
                work3 = self._calculate_duration(punches[4], punches[5])
                break3 = self._calculate_duration(punches[5], punches[6])
                work4 = self._calculate_duration(punches[6], punches[7])
                
                df.loc[index, 'periodo_manha'] = work1 + work2
                df.loc[index, 'intervalo_lanche'] = break1
                df.loc[index, 'intervalo_almoco'] = break2 + break3
                df.loc[index, 'periodo_tarde'] = work3 + work4
            
            # Calcular totais
            df.loc[index, 'total_trabalho'] = (df.loc[index, 'periodo_manha'] + 
                                               df.loc[index, 'periodo_tarde'])
            df.loc[index, 'total_pausas'] = (df.loc[index, 'intervalo_lanche'] + 
                                             df.loc[index, 'intervalo_almoco'])
        
        return df

    def _time_to_timedelta(self, time_str):
        """Converte uma string de tempo (HH:MM) para um objeto Timedelta."""
        if not time_str or time_str == '00:00':
            return pd.Timedelta(0)
        
        cleaned_time = self._clean_time(time_str)
        if cleaned_time:
            try:
                return pd.to_timedelta(cleaned_time + ':00')
            except (ValueError, TypeError):
                return pd.Timedelta(0)
        return pd.Timedelta(0)

    def _calculate_duration(self, start_str, end_str):
        """Calcula a duração como Timedelta entre duas strings de tempo HH:MM."""
        start_td = self._time_to_timedelta(start_str)
        end_td = self._time_to_timedelta(end_str)
        
        if pd.notna(start_td) and pd.notna(end_td) and end_td > start_td:
            return end_td - start_td
        return pd.Timedelta(0)

    def _clean_time(self, time_str):
        """Limpa e valida strings de tempo."""
        if not time_str or pd.isna(time_str):
            return None
        
        time_str = str(time_str).strip()
        if not time_str or time_str == 'nan' or time_str == '':
            return None
        
        # Verificar se já está no formato HH:MM
        if ':' in time_str and len(time_str.split(':')) == 2:
            try:
                parts = time_str.split(':')
                hours = int(parts[0])
                minutes = int(parts[1])
                if 0 <= hours <= 23 and 0 <= minutes <= 59:
                    return f"{hours:02d}:{minutes:02d}"
            except ValueError:
                pass
        
        return None

    def validate_data(self, df):
        """Valida os dados do DataFrame."""
        if df.empty:
            return False, "DataFrame está vazio"
        
        required_columns = ['Data', 'Tipo']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            return False, f"Colunas obrigatórias em falta: {missing_columns}"
        
        if df['Data'].isna().all():
            return False, "Todas as datas são inválidas"
        
        # Validar picagens se a coluna existir
        if 'picagens_validas' in df.columns:
            invalid_punches = df[df['picagens_validas'] == False]
            if not invalid_punches.empty:
                invalid_dates = invalid_punches['Data'].dt.strftime('%d/%m/%Y').tolist()
                return False, f"Picagens inválidas encontradas nas datas: {', '.join(invalid_dates[:5])}{'...' if len(invalid_dates) > 5 else ''}"
        
        return True, "Dados válidos"

    def get_summary_stats(self, df):
        """Retorna estatísticas resumo dos dados."""
        if df.empty:
            return {}
        
        stats = {
            'total_dias': len(df),
            'periodo_analisado': f"{df['Data'].min().strftime('%d/%m/%Y')} - {df['Data'].max().strftime('%d/%m/%Y')}",
            'tipos_dia': df['Tipo'].value_counts().to_dict(),
            'total_trabalho': df['total_trabalho'].sum(),
            'total_pausas': df['total_pausas'].sum()
        }
        
        return stats

    # Métodos de compatibilidade com a versão anterior
    def load_csv(self, uploaded_file):
        """Método de compatibilidade - usa o novo método melhorado."""
        return self.load_and_process_csv(uploaded_file)
    
    def clean_and_process_data(self, df_raw):
        """Método de compatibilidade - os dados já vêm processados do novo método."""
        return df_raw 