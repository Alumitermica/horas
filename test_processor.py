import pandas as pd
import sys
sys.path.append('.')
from utils.csv_processor import CSVProcessor

# Testar com o ficheiro Hugo Maio.csv
processor = CSVProcessor()

# Simular file upload
class MockFile:
    def __init__(self, filepath):
        self.filepath = filepath
        
    def read(self):
        with open(self.filepath, 'r', encoding='utf-8') as f:
            return f.read()
    
    def seek(self, pos):
        pass

# Processar o ficheiro
mock_file = MockFile('Hugo Maio.csv')
df = processor.load_and_process_csv(mock_file)

print('=== COLUNAS ENCONTRADAS ===')
print(list(df.columns))
print()

print('=== DADOS PROCESSADOS (primeiras 5 linhas) ===')
time_cols = ['Data', 'Tipo', 'E1', 'S1', 'E2', 'S2', 'E3', 'S3', 'E4', 'S4']
existing_cols = [col for col in time_cols if col in df.columns]
print(df[existing_cols].head())
print()

# Verificar uma linha específica com dados
normal_rows = df[df['Tipo'] == 'Normal']
if not normal_rows.empty:
    print('=== EXEMPLO DE LINHA NORMAL ===')
    print(normal_rows.iloc[0][existing_cols])
    print()
    
    # Verificar se os timestamps estão corretos
    print('=== VERIFICAÇÃO DE TIMESTAMPS ===')
    for col in ['E1', 'S1', 'E2', 'S2', 'E3', 'S3']:
        if col in normal_rows.columns:
            print(f'{col}: {normal_rows.iloc[0][col]}')

print()
print('=== RESUMO ===')
print(f'Total de linhas processadas: {len(df)}')
print(f'Linhas com tipo "Normal": {len(normal_rows)}')
print(f'Colunas de tempo encontradas: {[col for col in existing_cols if col in df.columns]}') 