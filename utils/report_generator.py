import pandas as pd
import numpy as np
from datetime import datetime
import io
import xlsxwriter
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.utils.dataframe import dataframe_to_rows

class ReportGenerator:
    def __init__(self):
        self.company_name = "Análise de Horas de Trabalho"
    
    def generate_excel_report(self, df, sector):
        """Gera relatório completo em Excel"""
        buffer = io.BytesIO()
        
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            # Aba 1: Dados processados
            df.to_excel(writer, sheet_name='Dados', index=False)
            
            # Aba 2: Resumo mensal
            monthly_summary = self._create_monthly_summary(df)
            monthly_summary.to_excel(writer, sheet_name='Resumo Mensal')
            
            # Aba 3: Análise de pontualidade
            punctuality_analysis = self._create_punctuality_analysis(df)
            punctuality_analysis.to_excel(writer, sheet_name='Pontualidade', index=False)
            
            # Aba 4: Métricas gerais
            metrics = self._create_general_metrics(df, sector)
            metrics.to_excel(writer, sheet_name='Métricas', index=False)
            
            # Formatação
            self._format_excel_sheets(writer)
        
        buffer.seek(0)
        return buffer.getvalue()
    
    def _create_monthly_summary(self, df):
        """Cria resumo mensal"""
        monthly = df.groupby(df['Data'].dt.to_period('M')).agg({
            'horas_efetivas_num': ['sum', 'mean', 'count'],
            'cumpriu_horario': 'sum',
            'dia_trabalho': 'sum'
        }).round(2)
        
        monthly.columns = ['Total Horas', 'Média Diária', 'Dias Registrados', 
                          'Dias Cumpriu Meta', 'Dias Trabalho']
        
        # Calcular percentual de conformidade
        monthly['% Conformidade'] = (monthly['Dias Cumpriu Meta'] / 
                                   monthly['Dias Trabalho'] * 100).round(1)
        
        return monthly
    
    def _create_punctuality_analysis(self, df):
        """Análise de pontualidade"""
        work_days = df[df['dia_trabalho'] == True].copy()
        
        punctuality_data = []
        for _, row in work_days.iterrows():
            data_entry = {
                'Data': row['Data'].strftime('%d/%m/%Y'),
                'Tipo': row['Tipo'],
                'Primeiro Entrada': row['primeiro_e1'] if row['primeiro_e1'] else 'N/A',
                'Última Saída': row['ultimo_s'] if row['ultimo_s'] else 'N/A',
                'Horas Efetivas': row['horas_efetivas_num'],
                'Cumpriu Meta': 'Sim' if row['cumpriu_horario'] else 'Não'
            }
            punctuality_data.append(data_entry)
        
        return pd.DataFrame(punctuality_data)
    
    def _create_general_metrics(self, df, sector):
        """Métricas gerais"""
        work_days = df[df['dia_trabalho'] == True]
        
        metrics_data = [
            ['Setor', sector],
            ['Período Analisado', f"{df['Data'].min().strftime('%d/%m/%Y')} - {df['Data'].max().strftime('%d/%m/%Y')}"],
            ['Total de Dias', len(df)],
            ['Dias de Trabalho', len(work_days)],
            ['Total Horas Trabalhadas', f"{work_days['horas_efetivas_num'].sum():.1f}h"],
            ['Média Horas/Dia', f"{work_days['horas_efetivas_num'].mean():.1f}h"],
            ['Dias que Cumpriram Meta', work_days['cumpriu_horario'].sum()],
            ['% Conformidade', f"{(work_days['cumpriu_horario'].sum() / len(work_days) * 100):.1f}%"],
            ['Folgas', len(df[df['Tipo'] == 'Folga'])],
            ['Faltas Totais', len(df[df['Tipo'] == 'Falta'])],
            ['Faltas Parciais', len(df[df['Tipo'] == 'Falta parcial'])],
            ['Feriados', len(df[df['Tipo'] == 'Feriado'])]
        ]
        
        return pd.DataFrame(metrics_data, columns=['Métrica', 'Valor'])
    
    def _format_excel_sheets(self, writer):
        """Formata as abas do Excel"""
        workbook = writer.book
        
        # Formatos
        header_format = workbook.add_format({
            'bold': True,
            'text_wrap': True,
            'valign': 'top',
            'fg_color': '#D7E4BC',
            'border': 1
        })
        
        # Aplicar formatação nos cabeçalhos
        for sheet_name in writer.sheets:
            worksheet = writer.sheets[sheet_name]
            
            # Ajustar largura das colunas
            worksheet.set_column('A:Z', 15)
            
            # Formato do cabeçalho (primeira linha)
            for col_num, value in enumerate(worksheet.table.columns):
                worksheet.write(0, col_num, value, header_format)
    
    def generate_csv_report(self, df):
        """Gera relatório em CSV"""
        return df.to_csv(index=False)
    
    def generate_summary_report(self, df, sector, rules_analysis=None):
        """Gera relatório resumido"""
        work_days = df[df['dia_trabalho'] == True]
        
        summary = {
            'Informações Gerais': {
                'Setor': sector,
                'Período': f"{df['Data'].min().strftime('%d/%m/%Y')} - {df['Data'].max().strftime('%d/%m/%Y')}",
                'Total de Dias': len(df),
                'Dias de Trabalho': len(work_days)
            },
            'Horas de Trabalho': {
                'Total Horas': f"{work_days['horas_efetivas_num'].sum():.1f}h",
                'Média Diária': f"{work_days['horas_efetivas_num'].mean():.1f}h",
                'Dias Conformes': work_days['cumpriu_horario'].sum(),
                'Taxa Conformidade': f"{(work_days['cumpriu_horario'].sum() / len(work_days) * 100):.1f}%"
            },
            'Ausências': {
                'Folgas': len(df[df['Tipo'] == 'Folga']),
                'Faltas Totais': len(df[df['Tipo'] == 'Falta']),
                'Faltas Parciais': len(df[df['Tipo'] == 'Falta parcial']),
                'Feriados': len(df[df['Tipo'] == 'Feriado'])
            }
        }
        
        if rules_analysis:
            summary['Análise de Regras'] = rules_analysis.get('resumo', {})
        
        return summary 