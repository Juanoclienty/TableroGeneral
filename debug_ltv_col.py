import re

with open(r'C:\Users\rjuan\dashboard\pages\6_LTV.py', 'r', encoding='utf-8') as f:
    content = f.read()

for i, line in enumerate(content.splitlines()):
    if '_es_impl' in line and 'Prod' in line:
        print(f'Line {i+1}: {repr(line)}')
        m = re.search(r'"(Prod[^"]+)"', line)
        if m:
            s = m.group(1)
            print(f'  String: {repr(s)}')
            print(f'  Bytes:  {s.encode("utf-8").hex()}')
            print(f'  Len:    {len(s)}')
