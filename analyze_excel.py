"""Test script to analyze multiple exported Excel files"""
import pandas as pd
import os

exports_dir = "exports"
files = sorted([f for f in os.listdir(exports_dir) if f.endswith('.xlsx')], 
               key=lambda x: os.path.getctime(os.path.join(exports_dir, x)), reverse=True)

output = []

# Check multiple files (different sizes may be from different portals)
for latest in files[:5]:
    filepath = os.path.join(exports_dir, latest)
    file_size = os.path.getsize(filepath)
    output.append(f"File: {latest} (Size: {file_size} bytes)")
    output.append("=" * 60)
    
    try:
        df = pd.read_excel(filepath, header=None, dtype=str)
        df = df.fillna('')
        
        output.append(f"Total rows: {len(df)}")
        output.append(f"Total columns: {len(df.columns)}")
        
        # Show first 8 rows
        for i in range(min(8, len(df))):
            row = df.iloc[i]
            row_str = " | ".join([str(v)[:40] for v in row.values if str(v).strip()])
            output.append(f"Row {i}: {row_str[:150]}")
        
        output.append("")
    except Exception as e:
        output.append(f"Error: {e}")
    
    output.append("")

# Write to file
with open("excel_analysis.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(output))

print("Analysis written to excel_analysis.txt")
