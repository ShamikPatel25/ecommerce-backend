import os
import re

def process_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    # Replace variations
    content = re.sub(r'store=request\.tenant,\s*', '', content)
    content = re.sub(r'store=self\.request\.tenant,\s*', '', content)
    content = re.sub(r'store=self\.request\.tenant', '', content)
    content = re.sub(r'store=request\.tenant', '', content)
    content = re.sub(r'order__store=request\.tenant,\s*', '', content)
    content = re.sub(r'order__store=tenant,\s*', '', content)
    content = re.sub(r'store=tenant,\s*', '', content)

    # Some remaining stray commas
    content = re.sub(r'\(,\s*', '(', content)

    with open(filepath, 'w') as f:
        f.write(content)

apps_dir = 'apps'
for root, dirs, files in os.walk(apps_dir):
    for file in files:
        if file.endswith('.py'):
            process_file(os.path.join(root, file))

print("Fixed store filtering.")
