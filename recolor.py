import os
import re
import glob

def recolor():
    src_dir = r"D:\Quote Contest\article-tool\frontend-vue\src"
    
    color_map = {
        r'#6366f1': '#ffffff', # indigo
        r'#4f46e5': '#cccccc', # indigo darker
        r'#a5b4fc': '#e5e7eb', # indigo lighter
        r'#c7d2fe': '#e5e7eb', # indigo very light
        r'rgba\(99,102,241,[\d.]+\)': 'rgba(255,255,255,0.1)',
        
        r'#3b82f6': '#ffffff', # blue
        r'#60a5fa': '#d1d5db',
        r'#93c5fd': '#d1d5db',
        r'rgba\(59,130,246,[\d.]+\)': 'rgba(255,255,255,0.1)',
        
        r'#22c55e': '#ffffff', # green
        r'#16a34a': '#cccccc',
        r'#4ade80': '#d1d5db',
        r'#34d399': '#d1d5db',
        r'rgba\(34,197,94,[\d.]+\)': 'rgba(255,255,255,0.1)',
        r'rgba\(16,185,129,[\d.]+\)': 'rgba(255,255,255,0.1)',
        
        r'#ef4444': '#ffffff', # red
        r'#f87171': '#d1d5db',
        r'#fca5a5': '#9ca3af',
        r'#dc2626': '#cccccc',
        r'rgba\(239,68,68,[\d.]+\)': 'rgba(255,255,255,0.1)',
        r'rgba\(220,38,38,[\d.]+\)': 'rgba(255,255,255,0.1)',
        
        r'#f59e0b': '#ffffff', # amber
        r'#fbbf24': '#d1d5db',
        r'#fcd34d': '#d1d5db',
        r'#facc15': '#d1d5db',
        r'rgba\(245,158,11,[\d.]+\)': 'rgba(255,255,255,0.1)',
        r'rgba\(234,179,8,[\d.]+\)': 'rgba(255,255,255,0.1)',
        
        r'#8b5cf6': '#ffffff', # violet
        r'#c4b5fd': '#d1d5db',
        r'#a78bfa': '#d1d5db',
        r'rgba\(139,92,246,[\d.]+\)': 'rgba(255,255,255,0.1)',
        
        r'#0ea5e9': '#ffffff', # sky
        r'#38bdf8': '#d1d5db',
        r'#7dd3fc': '#d1d5db',
        r'rgba\(14,165,233,[\d.]+\)': 'rgba(255,255,255,0.1)',
        
        r'#ec4899': '#ffffff', # pink
        r'rgba\(236,72,153,[\d.]+\)': 'rgba(255,255,255,0.1)',
        
        r'#14866d': '#ffffff', # green text
        r'#d33': '#ffffff', # red text
        r'#0645ad': '#ffffff', # blue link
    }
    
    files = glob.glob(src_dir + '/**/*.vue', recursive=True) + glob.glob(src_dir + '/**/*.css', recursive=True)
    
    for file_path in files:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        new_content = content
        for pattern, repl in color_map.items():
            new_content = re.sub(pattern, repl, new_content, flags=re.IGNORECASE)
            
        if new_content != content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
                print(f"Updated {file_path}")

if __name__ == '__main__':
    recolor()
